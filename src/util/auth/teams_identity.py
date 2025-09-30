"""Microsoft Teams 身份验证封装。"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import msal

from ..constants import Paths

ProgressCallback = Callable[[str], None]


class TeamsAuthError(RuntimeError):
    """Teams 身份验证过程中出现的异常。"""


class TeamsIdentityClient:
    """封装 MSAL 公共客户端，提供交互式/静默登录能力。"""

    def __init__(
        self,
        *,
        client_id: str,
        tenant_id: str | None = None,
        authority: str | None = None,
        redirect_uri: str | None = None,
        default_scopes: Sequence[str] | None = None,
        cache_path: Path | None = None,
    ) -> None:
        if not client_id:
            raise ValueError("client_id 不能为空")
        self._client_id = client_id
        self._authority = authority or f"https://login.microsoftonline.com/{tenant_id or 'common'}"
        self._redirect_uri = redirect_uri
        self._default_scopes = list(default_scopes or ["User.Read"])
        self._cache_path = cache_path or Path(Paths.CONFIG_DIR) / "teams_auth.json"
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache = msal.SerializableTokenCache()
        self._load_cache()
        self._app = msal.PublicClientApplication(
            client_id=self._client_id,
            authority=self._authority,
            token_cache=self._cache,
        )

    # ------------------------------------------------------------------
    @classmethod
    def from_config_file(cls, config_path: str | Path) -> "TeamsIdentityClient":
        """从配置文件加载 Teams 应用信息。"""

        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"未找到 Teams 身份配置文件：{path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        client_id = data.get("client_id")
        tenant_id = data.get("tenant_id")
        authority = data.get("authority")
        redirect_uri = data.get("redirect_uri")
        scopes = data.get("scopes")
        cache_name = data.get("cache_file", "teams_auth.json")
        cache_path = Path(Paths.CONFIG_DIR) / cache_name
        return cls(
            client_id=client_id,
            tenant_id=tenant_id,
            authority=authority,
            redirect_uri=redirect_uri,
            default_scopes=scopes,
            cache_path=cache_path,
        )

    # ------------------------------------------------------------------
    def acquire_token_interactive(
        self,
        *,
        scopes: Iterable[str] | None = None,
        login_hint: str | None = None,
        prompt: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """通过授权码 + PKCE 交互登录获取令牌。"""

        scope_list = list(scopes or self._default_scopes)
        if progress_callback:
            progress_callback("正在打开浏览器完成微软账户登录…")
        try:
            result = self._app.acquire_token_interactive(
                scopes=scope_list,
                login_hint=login_hint,
                prompt=prompt,
                redirect_uri=self._redirect_uri,
                use_pkce=True,
            )
        except Exception as exc:  # pragma: no cover - 网络环境导致的异常
            raise TeamsAuthError(f"交互式登录失败：{exc}") from exc
        self._persist_cache()
        return self._process_result(result, login_hint)

    def refresh_token(
        self,
        *,
        username: str | None = None,
        scopes: Iterable[str] | None = None,
        force_refresh: bool = False,
        allow_interactive: bool = True,
        use_device_code: bool = False,
        progress_callback: ProgressCallback | None = None,
        timeout: int = 600,
    ) -> dict[str, Any]:
        """尝试静默刷新令牌，必要时回退到交互流程。"""

        scope_list = list(scopes or self._default_scopes)
        with self._lock:
            accounts = self._app.get_accounts(username=username)
            if not accounts:
                accounts = self._app.get_accounts()
        for account in accounts:
            try:
                result = self._app.acquire_token_silent(
                    scope_list,
                    account=account,
                    force_refresh=force_refresh,
                )
            except Exception:
                result = None
            if result:
                self._persist_cache()
                result["account"] = account
                return self._process_result(result, account.get("username"))
        if not allow_interactive:
            raise TeamsAuthError("令牌已过期且禁止交互式登录，请重新登录。")
        if use_device_code:
            return self._acquire_token_by_device_code(
                scope_list,
                progress_callback=progress_callback,
                timeout=timeout,
            )
        return self.acquire_token_interactive(
            scopes=scope_list,
            login_hint=username,
            progress_callback=progress_callback,
        )

    def acquire_token_silent(
        self,
        *,
        username: str | None = None,
        scopes: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """仅尝试静默获取令牌，不触发交互。"""

        scope_list = list(scopes or self._default_scopes)
        with self._lock:
            accounts = self._app.get_accounts(username=username)
        for account in accounts:
            result = self._app.acquire_token_silent(scope_list, account=account)
            if result:
                self._persist_cache()
                result["account"] = account
                return self._process_result(result, account.get("username"))
        raise TeamsAuthError("未找到有效的缓存令牌，请发起交互式登录。")

    def sign_out(self, username: str | None = None) -> None:
        """移除账户并删除缓存文件。"""

        with self._lock:
            accounts = self._app.get_accounts(username=username)
            for account in accounts:
                self._app.remove_account(account)
        self.clear_cache()

    def clear_cache(self) -> None:
        """删除本地缓存文件。"""

        with self._lock:
            self._cache.clear()
            if self._cache_path.exists():
                try:
                    self._cache_path.unlink()
                except FileNotFoundError:
                    pass

    # ------------------------------------------------------------------
    def _acquire_token_by_device_code(
        self,
        scope_list: Sequence[str],
        *,
        progress_callback: ProgressCallback | None = None,
        timeout: int = 600,
    ) -> dict[str, Any]:
        with self._lock:
            flow = self._app.initiate_device_flow(scopes=list(scope_list))
        if "user_code" not in flow:
            raise TeamsAuthError(flow.get("error_description") or "启动设备码流程失败。")
        if progress_callback:
            message = flow.get("message") or (
                f"请访问 {flow.get('verification_uri')} 并输入代码 {flow.get('user_code')} 完成登录。"
            )
            progress_callback(message)
        try:
            result = self._app.acquire_token_by_device_flow(flow, timeout=timeout)
        except Exception as exc:  # pragma: no cover - 网络环境导致的异常
            raise TeamsAuthError(f"设备码登录失败：{exc}") from exc
        self._persist_cache()
        return self._process_result(result, None)

    def _process_result(self, result: dict[str, Any] | None, login_hint: str | None) -> dict[str, Any]:
        if not result:
            raise TeamsAuthError("身份验证失败，Azure AD 未返回结果。")
        if "error" in result:
            raise TeamsAuthError(self._format_error(result))
        if "access_token" not in result:
            raise TeamsAuthError("返回结果缺少访问令牌。")
        if "account" not in result:
            with self._lock:
                accounts = self._app.get_accounts(username=login_hint)
                if not accounts:
                    accounts = self._app.get_accounts()
            if accounts:
                result["account"] = accounts[0]
        return result

    def _format_error(self, payload: dict[str, Any]) -> str:
        message = payload.get("error_description") or payload.get("error_codes") or payload.get("error")
        return f"身份验证失败：{message}"

    def _load_cache(self) -> None:
        if not self._cache_path.exists():
            return
        try:
            cache_data = self._cache_path.read_text(encoding="utf-8")
        except Exception:
            return
        if cache_data:
            self._cache.deserialize(cache_data)

    def _persist_cache(self) -> None:
        if not self._cache.has_state_changed:
            return
        data = self._cache.serialize()
        temp_path = self._cache_path.with_suffix(".tmp")
        temp_path.write_text(data, encoding="utf-8")
        os.replace(temp_path, self._cache_path)
        try:
            if os.name != "nt":
                os.chmod(self._cache_path, 0o600)
        except OSError:
            pass
        self._cache.has_state_changed = False

    @property
    def default_scopes(self) -> list[str]:
        return list(self._default_scopes)


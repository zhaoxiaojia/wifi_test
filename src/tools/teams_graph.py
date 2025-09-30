"""Microsoft Teams Graph API 客户端封装。"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Mapping, MutableMapping, Sequence, TypeVar

import requests

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GraphError(RuntimeError):
    """调用 Microsoft Graph API 失败时抛出的异常。"""


class GraphAuthError(GraphError):
    """Graph API 认证失败或令牌失效时抛出的异常。"""


class GraphClient:
    """轻量级 Graph API 封装，负责统一的请求与令牌管理。"""

    BASE_URL = "https://graph.microsoft.com"

    def __init__(
        self,
        access_token: str | Mapping[str, Any] | None = None,
        *,
        token_provider: Callable[..., str | Mapping[str, Any] | None] | None = None,
        on_auth_failure: Callable[[str], None] | None = None,
        graph_version: str = "v1.0",
        timeout: float = 10.0,
        max_workers: int = 2,
    ) -> None:
        if not access_token and not token_provider:
            raise ValueError("GraphClient 初始化时必须提供 access_token 或 token_provider。")
        self._token_lock = threading.RLock()
        self._access_token = self._extract_token(access_token)
        self._token_provider = token_provider
        self._on_auth_failure = on_auth_failure
        self._graph_version = graph_version.strip("/") or "v1.0"
        self._timeout = timeout
        self._session = requests.Session()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="teams-graph",
        )

    # ------------------------------------------------------------------
    def close(self) -> None:
        """释放底层资源。"""

        self._executor.shutdown(wait=False)
        self._session.close()

    def submit(self, func: Callable[..., T], *args, **kwargs) -> Future[T]:
        """在内部线程池中异步执行函数。"""

        return self._executor.submit(func, *args, **kwargs)

    def update_token(self, token: str | Mapping[str, Any]) -> None:
        """更新缓存的访问令牌。"""

        with self._token_lock:
            self._access_token = self._extract_token(token)

    # ------------------------------------------------------------------
    def get_me(self, *, background: bool = False) -> Future[dict[str, Any]] | dict[str, Any]:
        """获取当前用户信息。"""

        if background:
            return self.submit(self._get_me)
        return self._get_me()

    def list_joined_teams(
        self, *, background: bool = False
    ) -> Future[Sequence[Mapping[str, Any]]] | Sequence[Mapping[str, Any]]:
        """列出用户加入的 Teams 团队。"""

        if background:
            return self.submit(self._list_joined_teams)
        return self._list_joined_teams()

    def send_chat_message(
        self,
        chat_id: str,
        content: str,
        *,
        subject: str | None = None,
        content_type: str = "html",
        background: bool = False,
    ) -> Future[dict[str, Any]] | dict[str, Any]:
        """向指定聊天发送消息。"""

        if background:
            return self.submit(self._send_chat_message, chat_id, content, subject, content_type)
        return self._send_chat_message(chat_id, content, subject, content_type)

    # ------------------------------------------------------------------
    def _get_me(self) -> dict[str, Any]:
        return self._request("GET", "/me")

    def _list_joined_teams(self) -> Sequence[Mapping[str, Any]]:
        data = self._request("GET", "/me/joinedTeams")
        if isinstance(data, Mapping):
            value = data.get("value")
            if isinstance(value, Sequence):
                return value
        return []

    def _send_chat_message(
        self,
        chat_id: str,
        content: str,
        subject: str | None,
        content_type: str,
    ) -> dict[str, Any]:
        if not chat_id:
            raise ValueError("chat_id 不能为空。")
        body = {
            "body": {
                "contentType": content_type,
                "content": content,
            }
        }
        if subject:
            body["subject"] = subject
        return self._request("POST", f"/chats/{chat_id}/messages", json=body)

    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        headers: MutableMapping[str, str] | None = None,
        retry_on_unauthorized: bool = True,
    ) -> Any:
        url = self._build_url(path)
        request_headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if json is not None:
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        try:
            token = self._get_token()
        except GraphAuthError as exc:
            message = str(exc) or "缺少访问令牌，请重新登录。"
            self._notify_auth_failure(message)
            raise
        if not token:
            message = "缺少访问令牌，请重新登录。"
            self._notify_auth_failure(message)
            raise GraphAuthError(message)
        request_headers["Authorization"] = f"Bearer {token}"

        try:
            response = self._session.request(
                method.upper(),
                url,
                params=params,
                json=json,
                data=data,
                headers=request_headers,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.error("请求 Microsoft Graph 失败：%s %s -> %s", method.upper(), url, exc)
            raise GraphError(f"请求 Microsoft Graph 失败：{exc}") from exc

        if response.status_code in (401, 403) and retry_on_unauthorized:
            try:
                refreshed = self._refresh_access_token()
            except GraphAuthError as exc:
                message = str(exc) or "访问令牌刷新失败，请重新登录。"
                self._notify_auth_failure(message)
                raise
            if refreshed:
                request_headers["Authorization"] = f"Bearer {refreshed}"
                try:
                    response = self._session.request(
                        method.upper(),
                        url,
                        params=params,
                        json=json,
                        data=data,
                        headers=request_headers,
                        timeout=self._timeout,
                    )
                except requests.RequestException as exc:
                    logger.error("请求 Microsoft Graph 失败：%s %s -> %s", method.upper(), url, exc)
                    raise GraphError(f"请求 Microsoft Graph 失败：{exc}") from exc

        if response.status_code in (401, 403):
            message = self._format_error(response) or "访问 Microsoft Graph 被拒绝，请重新登录。"
            self._notify_auth_failure(message)
            raise GraphAuthError(message)

        if not response.ok:
            message = self._format_error(response)
            logger.error(
                "Graph API 响应错误：%s %s -> %s %s",
                method.upper(),
                url,
                response.status_code,
                message,
            )
            raise GraphError(message or f"Graph API 返回错误状态：{response.status_code}")

        if response.status_code == 204 or not response.content:
            return None
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type.lower():
            try:
                return response.json()
            except ValueError:
                logger.warning("解析 Graph API JSON 响应失败，返回原始文本。")
        return response.text

    # ------------------------------------------------------------------
    def _refresh_access_token(self) -> str | None:
        if not self._token_provider:
            return None
        try:
            token_obj = self._call_token_provider(force_refresh=True)
        except GraphAuthError:
            raise
        except GraphError:
            return None
        token = self._extract_token(token_obj)
        if not token:
            return None
        with self._token_lock:
            self._access_token = token
        return token

    def _get_token(self, force_refresh: bool = False) -> str | None:
        with self._token_lock:
            token = self._access_token
        if token and not force_refresh:
            return token
        if not self._token_provider:
            return token
        try:
            token_obj = self._call_token_provider(force_refresh=force_refresh)
        except GraphAuthError:
            raise
        except GraphError:
            return None
        token = self._extract_token(token_obj)
        if token:
            with self._token_lock:
                self._access_token = token
        return token

    def _call_token_provider(self, force_refresh: bool) -> Any:
        provider = self._token_provider
        if not provider:
            return None
        try:
            return self._invoke_provider(provider, force_refresh)
        except GraphAuthError:
            raise
        except Exception as exc:
            logger.exception("调用 token_provider 刷新 Graph 令牌失败")
            raise GraphError(f"刷新访问令牌失败：{exc}") from exc

    @staticmethod
    def _invoke_provider(
        provider: Callable[..., str | Mapping[str, Any] | None],
        force_refresh: bool,
    ) -> str | Mapping[str, Any] | None:
        try:
            return provider(force_refresh=force_refresh)
        except TypeError:
            if force_refresh:
                try:
                    return provider(True)
                except TypeError:
                    return provider()
            return provider()

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        normalized = path if path.startswith("/") else f"/{path}"
        if normalized.startswith("/v1.0/") or normalized.startswith("/beta/"):
            return f"{self.BASE_URL}{normalized}"
        return f"{self.BASE_URL}/{self._graph_version}{normalized}"

    @staticmethod
    def _extract_token(token: str | Mapping[str, Any] | None) -> str | None:
        if not token:
            return None
        if isinstance(token, str):
            return token
        if isinstance(token, Mapping):
            for key in ("access_token", "token", "accessToken"):
                value = token.get(key)
                if isinstance(value, str) and value:
                    return value
        return None

    def _format_error(self, response: requests.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text.strip()
        if not isinstance(data, Mapping):
            return str(data)
        error = data.get("error")
        if isinstance(error, Mapping):
            code = error.get("code")
            message = error.get("message")
            if code and message:
                return f"{code}: {message}"
            if message:
                return str(message)
        message = data.get("message")
        if isinstance(message, Mapping):
            message = message.get("value")
        if message:
            return str(message)
        return str(data)

    def _notify_auth_failure(self, message: str) -> None:
        if self._on_auth_failure:
            try:
                self._on_auth_failure(message)
            except Exception:  # pragma: no cover - 回调异常不应终止流程
                logger.exception("Graph 客户端通知回调执行失败")


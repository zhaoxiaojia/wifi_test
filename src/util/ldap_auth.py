"""Amlogic LDAP 登录工具。"""

from __future__ import annotations

import contextlib
import logging
import os
from dataclasses import dataclass

from ldap3 import Connection, NTLM, Server
from ldap3.core.exceptions import LDAPException

# 允许通过环境变量覆盖 LDAP 服务器地址，默认指向公司目录服务。
LDAP_SERVER = os.getenv("AMLOGIC_LDAP_SERVER", "ldaps://ad.amlogic.com")
LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "amlogic.com")


@dataclass(slots=True)
class LDAPLoginResult:
    """LDAP 登录结果载体。"""

    username: str
    domain_user: str
    server: str


class LDAPAuthenticationError(RuntimeError):
    """LDAP 登录失败时抛出的异常。"""


def _build_domain_user(username: str) -> str:
    """根据输入用户名生成带域前缀的账号。"""

    if not username:
        return ""
    if "\\" in username or "@" in username:
        logging.debug("检测到用户已经包含域信息: %s", username)
        return username
    domain_user = f"{LDAP_DOMAIN}\\{username}"
    logging.debug("拼接域账号: %s -> %s", username, domain_user)
    return domain_user


def ldap_authenticate(username: str, password: str) -> LDAPLoginResult:
    """使用 NTLM 方式登录 Amlogic LDAP 目录。"""

    clean_username = (username or "").strip()
    if not clean_username or not password:
        logging.warning("ldap_authenticate: 账号或密码为空 (username=%s)", clean_username)
        raise LDAPAuthenticationError("账号或密码不能为空。")

    domain_user = _build_domain_user(clean_username)
    logging.info("ldap_authenticate: 使用 LDAP 服务器 %s", LDAP_SERVER)
    logging.info("ldap_authenticate: 尝试为账号 %s 发起绑定", domain_user)

    server = Server(LDAP_SERVER, get_info="ALL")
    connection: Connection | None = None
    try:
        connection = Connection(
            server,
            user=domain_user,
            password=password,
            authentication=NTLM,
            raise_exceptions=False,
        )
        logging.debug("ldap_authenticate: Connection 对象创建完成 (server=%s)", server)
        if not connection.bind():
            logging.error("ldap_authenticate: LDAP 绑定失败 -> %s", connection.result)
            raise LDAPAuthenticationError("LDAP 认证失败，请检查账号或密码。")
        logging.info("ldap_authenticate: LDAP 绑定成功 (user=%s)", domain_user)
        return LDAPLoginResult(
            username=clean_username,
            domain_user=domain_user,
            server=LDAP_SERVER,
        )
    except LDAPAuthenticationError:
        raise
    except LDAPException as exc:  # pragma: no cover - 运行时异常记录
        logging.exception("ldap_authenticate: LDAP 异常 -> %s", exc)
        raise LDAPAuthenticationError(f"LDAP 服务异常：{exc}") from exc
    except Exception as exc:  # pragma: no cover - 运行期防御
        logging.exception("ldap_authenticate: 未知异常 -> %s", exc)
        raise LDAPAuthenticationError(f"LDAP 认证过程中出现异常：{exc}") from exc
    finally:
        if connection is not None:
            with contextlib.suppress(Exception):
                logging.debug("ldap_authenticate: 断开 LDAP 连接")
                connection.unbind()

import logging
import os

from ldap3 import ALL, Connection, NTLM, Server
from ldap3.core.exceptions import LDAPException

LDAP_SERVER = os.getenv("AMLOGIC_LDAP_SERVER", "ldaps://ad.amlogic.com")
LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "amlogic.com")


def get_configured_ldap_server() -> str:
    """返回当前使用的 LDAP 服务器地址。"""

    return LDAP_SERVER


def create_ldap_server(host: str | None = None) -> Server:
    """构造 LDAP Server 实例，封装示例代码中的初始化。"""

    server_host = (host or LDAP_SERVER).strip()
    return Server(server_host, get_info=ALL)


def create_ldap_connection(server: Server, username: str, password: str) -> Connection:
    """按照公司要求封装 Connection 创建逻辑。"""

    domain_user = _normalize_username(username)
    return Connection(
        server,
        user=domain_user,
        password=password,
        authentication=NTLM,
    )


def ldap_authenticate(username: str, password: str) -> str | None:
    """按照示例流程重新实现的 LDAP 登录验证。"""

    clean_username = (username or "").strip()
    if not clean_username or not password:
        logging.info("ldap_authenticate: 账号或密码为空 (username=%s)", clean_username)
        return None

    server = create_ldap_server()
    connection: Connection | None = None
    try:
        connection = create_ldap_connection(server, clean_username, password)
        if not connection.bind():
            logging.info("ldap_authenticate: LDAP bind failed -> %s", connection.result)
            return None
        logging.info("ldap_authenticate: LDAP bind success")
        return clean_username
    except LDAPException as exc:
        logging.error("ldap_authenticate: LDAP 异常 -> %s", exc)
        return None
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:  # pragma: no cover - 清理阶段无需抛出
                logging.debug("ldap_authenticate: 忽略 unbind 异常", exc_info=True)


def _normalize_username(username: str) -> str:
    """根据是否包含域信息拼接完整账号。"""

    clean_username = username.strip()
    if "\\" in clean_username or "@" in clean_username:
        return clean_username
    return f"{LDAP_DOMAIN}\\{clean_username}"

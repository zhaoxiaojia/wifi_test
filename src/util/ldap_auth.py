import logging
import os

from ldap3 import Connection, NTLM, Server
from ldap3.core.exceptions import LDAPException

LDAP_SERVER = os.getenv("AMLOGIC_LDAP_SERVER", "ldaps://ad.amlogic.com")
LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "amlogic.com")


def get_configured_ldap_server() -> str:
    """返回当前使用的 LDAP 服务器地址。"""

    return LDAP_SERVER

def ldap_authenticate(username: str, password: str) -> str | None:
    """按照示例代码实现的最小化 LDAP 登录流程。"""

    clean_username = (username or "").strip()
    if not clean_username or not password:
        logging.info("ldap_authenticate: 账号或密码为空 (username=%s)", clean_username)
        return None

    if "\\" in clean_username or "@" in clean_username:
        domain_user = clean_username
    else:
        domain_user = f"{LDAP_DOMAIN}\\{clean_username}"

    logging.info("ldap_authenticate: ldap server=%s", LDAP_SERVER)
    logging.info("ldap_authenticate: domain user=%s", domain_user)
    print(
        f"[ldap_authenticate] LDAP server={LDAP_SERVER}, user={domain_user}",
        flush=True,
    )

    server = Server(LDAP_SERVER, get_info="ALL")
    connection: Connection | None = None
    try:
        connection = Connection(
            server,
            user=domain_user,
            password=password,
            authentication=NTLM,
        )
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
            except Exception:
                pass

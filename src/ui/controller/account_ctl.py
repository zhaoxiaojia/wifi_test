"""Controller and backend helpers for the Account (login) page.

This module hosts the non-UI logic that was previously implemented in
``src.ui.company_login``: LDAP connection helpers, username
normalisation and the background worker used to authenticate in a
separate thread.

The actual Qt widget/page that composes the login form now lives in
``src.ui.view.account``.  Callers should import the page class from
there and use the helpers exposed in this module when they need to
perform synchronous credential checks or query the configured LDAP
server.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from ldap3 import ALL, Connection, NTLM, Server
from ldap3.core.exceptions import LDAPException
from PyQt5.QtCore import QObject, pyqtSignal

from src.util.constants import Paths


# -----------------------------------------------------------------------------
# Global constants
# -----------------------------------------------------------------------------

LDAP_HOST = os.getenv("AMLOGIC_LDAP_HOST", "ldap.amlogic.com")
"""Default LDAP host used by the company authentication system."""

LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "AMLOGIC")
"""Default NTLM domain used for username normalization."""


# -----------------------------------------------------------------------------
# Background worker
# -----------------------------------------------------------------------------


class _LDAPAuthWorker(QObject):
    """
    Background worker that performs LDAP authentication in a separate thread.

    Signals
    -------
    finished : pyqtSignal(bool, str, dict)
        Emitted when authentication completes; carries (success, message, payload).
    progress : pyqtSignal(str)
        Emitted with progress or status messages to display in the UI.

    Parameters
    ----------
    username : str
        Username provided by the user (can be bare name or domain-qualified).
    password : str
        Plaintext password.
    """

    finished = pyqtSignal(bool, str, dict)
    progress = pyqtSignal(str)

    def __init__(self, username: str, password: str) -> None:
        super().__init__()
        self._username = (username or "").strip()
        self._password = password or ""

    def run(self) -> None:  # pragma: no cover
        """
        Perform LDAP authentication on the background thread.

        Emits
        -----
        finished(bool, str, dict)
            Always emitted with the final result, even on error.
        """
        if not self._username or not self._password:
            message = "Account or password cannot be empty."
            logging.warning("LDAP login failed: missing username or password")
            self.finished.emit(False, message, {})
            return

        server_host = LDAP_HOST.strip()
        self.progress.emit(f"Connecting to LDAP server: {server_host}")
        success, message, payload = _ldap_authenticate(self._username, self._password)
        self.finished.emit(success, message, payload)


# -----------------------------------------------------------------------------
# LDAP helpers
# -----------------------------------------------------------------------------


def _ldap_authenticate(username: str, password: str) -> tuple[bool, str, dict]:
    """
    Perform LDAP authentication using the `ldap3` library.

    Parameters
    ----------
    username : str
        The username provided by the user.
    password : str
        The associated password.

    Returns
    -------
    tuple[bool, str, dict]
        - success (bool): True if authentication succeeded.
        - message (str): Human-readable status.
        - payload (dict): Additional info (e.g., username, server).
    """
    clean_username = username.strip()
    domain_user = _normalize_username(clean_username)
    server_host = LDAP_HOST.strip()
    connection: Connection | None = None

    try:
        server = Server(server_host, get_info=ALL)
        connection = Connection(
            server,
            user=domain_user,
            password=password,
            authentication=NTLM,
        )
        if connection.bind():
            logging.info(
                "LDAP authentication succeeded (username=%s, server=%s)",
                domain_user,
                server_host,
            )
            payload = {"username": clean_username, "server": server_host}
            return True, f"Sign-in successful. Welcome, {clean_username}", payload

        logging.warning(
            "LDAP bind failed (username=%s, server=%s, result=%s)",
            domain_user,
            server_host,
            connection.result,
        )
        return False, "LDAP sign-in failed. Please check your account or password.", {}

    except LDAPException as exc:
        logging.error(
            "LDAP connection/authentication exception (username=%s, server=%s): %s",
            clean_username,
            server_host,
            exc,
        )
        return False, f"Sign-in failed: {exc}", {}

    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:
                logging.debug("LDAP unbind raised an exception and was ignored.", exc_info=True)


def _normalize_username(username: str) -> str:
    """
    Normalize username by ensuring the proper domain prefix.

    If the username already contains ``\\`` or ``@``, it is returned as-is.
    Otherwise, the company’s default domain prefix is added.

    Parameters
    ----------
    username : str
        Raw username string.

    Returns
    -------
    str
        Fully qualified username with domain.
    """
    clean_username = username.strip()
    if "\\" in clean_username or "@" in clean_username:
        return clean_username
    return f"{LDAP_DOMAIN}\\{clean_username}"


def get_configured_ldap_server() -> str:
    """
    Return the currently configured LDAP host name.

    Returns
    -------
    str
        Host name of the LDAP server.
    """
    return LDAP_HOST


def ldap_authenticate(username: str, password: str) -> str | None:
    """
    Lightweight synchronous LDAP authentication helper.

    Performs a bind test against the configured server. Intended for quick
    credential checks that do not require thread-based async logic.

    Parameters
    ----------
    username : str
        User name to authenticate.
    password : str
        Corresponding password.

    Returns
    -------
    str | None
        The validated username if successful, otherwise None.
    """
    clean_username = (username or "").strip()
    if not clean_username or not password:
        logging.info(
            "ldap_authenticate: username or password empty (username=%s)",
            clean_username,
        )
        return None

    server_host = LDAP_HOST.strip()
    connection: Connection | None = None
    try:
        server = Server(server_host, get_info=ALL)
        domain_user = _normalize_username(clean_username)
        connection = Connection(
            server,
            user=domain_user,
            password=password,
            authentication=NTLM,
        )
        if not connection.bind():
            logging.warning(
                "ldap_authenticate: LDAP bind failed (username=%s, server=%s, result=%s)",
                domain_user,
                server_host,
                connection.result,
            )
            return None
        logging.info(
            "ldap_authenticate: LDAP bind success (username=%s, server=%s)",
            domain_user,
            server_host,
        )
        return clean_username
    except LDAPException as exc:
        logging.error(
            "ldap_authenticate: LDAP exception (username=%s, server=%s): %s",
            clean_username,
            server_host,
            exc,
        )
        return None
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:
                logging.debug("ldap_authenticate: ignored unbind exception", exc_info=True)


# -----------------------------------------------------------------------------
# Authentication state persistence
# -----------------------------------------------------------------------------

AUTH_STATE_FILENAME = "auth_state.json"


def _auth_state_path() -> Path:
    """Return the path for the persisted authentication state file."""
    return Path(Paths.CONFIG_DIR) / AUTH_STATE_FILENAME


def load_auth_state() -> dict | None:
    """
    Load the last authentication state from disk.

    Returns
    -------
    dict | None
        A dict containing at least ``username`` and ``authenticated``
        when a previous login was recorded successfully, otherwise None.
    """
    path = _auth_state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("Failed to read auth state file %s: %s", path, exc)
        return None

    username = str(data.get("username", "") or "").strip()
    authenticated = bool(data.get("authenticated", False))
    if not username or not authenticated:
        return None
    updated_at = str(data.get("updated_at") or "")
    return {"username": username, "authenticated": authenticated, "updated_at": updated_at}


def save_auth_state(username: str, authenticated: bool) -> None:
    """
    Persist the current authentication state to disk.

    Only the username and a boolean flag are stored. Passwords are
    never written to disk.
    """
    username = (username or "").strip()
    if not username:
        clear_auth_state()
        return

    data = {
        "username": username,
        "authenticated": bool(authenticated),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    path = _auth_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logging.warning("Failed to write auth state file %s: %s", path, exc)


def clear_auth_state() -> None:
    """Remove any persisted authentication state."""
    path = _auth_state_path()
    try:
        if path.exists():
            path.unlink()
    except Exception as exc:
        logging.warning("Failed to clear auth state file %s: %s", path, exc)


__all__ = [
    "_LDAPAuthWorker",
    "get_configured_ldap_server",
    "ldap_authenticate",
    "LDAP_HOST",
    "LDAP_DOMAIN",
]

"""Backward compatible shim for legacy imports.

All functionality has moved to the structured modules within this package.
"""

from __future__ import annotations

if __package__:
    from . import (
        MySqlClient,
        PerformanceTableManager,
        bootstrap_mysql_environment,
        sync_configuration,
        sync_file_to_db,
        sync_test_result_to_db,
    )
else:
    from pathlib import Path as _Path
    import sys as _sys

    _package_root = _Path(__file__).resolve().parents[3]
    if str(_package_root) not in _sys.path:
        _sys.path.insert(0, str(_package_root))
    from src.tools.mysql_tool import (
        MySqlClient,
        PerformanceTableManager,
        bootstrap_mysql_environment,
        sync_configuration,
        sync_file_to_db,
        sync_test_result_to_db,
    )

__all__ = [
    "MySqlClient",
    "PerformanceTableManager",
    "bootstrap_mysql_environment",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
]


if __name__ == "__main__":
    from pathlib import Path
    import sys

    package_root = Path(__file__).resolve().parents[3]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from src.tools.mysql_tool.cli import main as _cli_main

    sys.exit(_cli_main())

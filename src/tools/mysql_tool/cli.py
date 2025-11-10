from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .bootstrap import bootstrap_mysql_environment
from .operations import sync_test_result_to_db


def _build_parser() -> argparse.ArgumentParser:
    """
    Build parser.

    Defines and configures command-line arguments for the CLI.
    Reads data from a CSV file and processes each row.

    Parameters
    ----------
    None
        This function does not accept any parameters.

    Returns
    -------
    argparse.ArgumentParser
        A value of type ``argparse.ArgumentParser``.
    """
    parser = argparse.ArgumentParser(
        description="Bootstrap MySQL environment and optionally sync a CSV log file.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="CSV log file to ingest into the database.",
    )
    parser.add_argument(
        "--data-type",
        help="Logical data type label stored alongside the results (required with --log-file).",
    )
    parser.add_argument(
        "--case-path",
        help="Optional case path used to derive the target table name.",
    )
    parser.add_argument(
        "--refresh-config",
        action="store_true",
        help="Force reload of config sections before syncing.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (default: INFO).",
    )
    parser.add_argument(
        "--run-source",
        default="local",
        help="Label stored in run_source column (default: local).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main.

    Logs informational messages and errors for debugging purposes.

    Parameters
    ----------
    argv : Any
        The ``argv`` parameter.

    Returns
    -------
    int
        A value of type ``int``.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    log_level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

    config, result = bootstrap_mysql_environment(refresh_config=args.refresh_config or bool(args.log_file))
    if result:
        logging.info(
            "Configuration synced (dut_id=%s, execution_id=%s)",
            result.dut_id,
            result.execution_id,
        )
    else:
        logging.warning("Configuration sync skipped or failed; continuing with best effort.")

    if not args.log_file:
        logging.info("No log file provided; finished bootstrap only.")
        return 0

    if not args.log_file.exists():
        logging.error("Log file %s does not exist", args.log_file)
        return 2
    if not args.data_type:
        logging.error("--data-type is required when providing --log-file")
        return 3

    affected = sync_test_result_to_db(
        config,
        log_file=str(args.log_file),
        data_type=args.data_type,
        case_path=args.case_path,
        run_source=args.run_source,
    )
    logging.info("Synced %s rows from %s", affected, args.log_file)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

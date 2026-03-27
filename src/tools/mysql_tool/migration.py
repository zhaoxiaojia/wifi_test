import argparse
import logging
import sys

from src.tools.mysql_tool.client import MySqlClient
from src.tools.mysql_tool.schema import ensure_report_tables


def _column_exists(client: MySqlClient, *, table: str, column: str) -> bool:
    row = client.query_one(
        "SELECT COUNT(*) AS cnt "
        "FROM information_schema.COLUMNS "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return int(row["cnt"]) > 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drop performance.data_type column if present.")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO).")
    args = parser.parse_args(argv)

    log_level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

    client = MySqlClient(autocommit=True)

    table = "performance"
    column = "data_type"
    if not _column_exists(client, table=table, column=column):
        logging.info("%s.%s does not exist; nothing to do.", table, column)
        ensure_report_tables(client)
        return 0

    logging.info("Dropping %s.%s ...", table, column)
    client.execute(f"ALTER TABLE `{table}` DROP COLUMN `{column}`")
    ensure_report_tables(client)
    logging.info("Done.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))

from __future__ import annotations

import logging
import re
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

from app_config import settings

log = logging.getLogger("bill_agent.setup")


ROOT = Path(__file__).resolve().parent / "db"


def _read_sql(filename: str) -> str:
    return (ROOT / filename).read_text(encoding="utf-8")


def _strip_client_commands(sql: str) -> str:
    # MySQL client commands (DELIMITER, USE) must not be passed to PyMySQL.
    sql = re.sub(r"(?im)^\s*DELIMITER\s+\S+\s*$", "", sql)
    sql = re.sub(r"(?im)^\s*USE\s+`?[A-Za-z0-9_]+`?\s*;?\s*$", "", sql)
    return sql.strip()


def _split_standard_sql(sql: str) -> list[str]:
    """Split ordinary SQL statements while preserving strings/comments."""
    statements: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    escape = False

    i = 0
    while i < len(sql):
        ch = sql[i]
        buf.append(ch)

        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
        else:
            if ch in ("'", '"', "`"):
                quote = ch
            elif ch == ";":
                statement = "".join(buf[:-1]).strip()
                if statement:
                    statements.append(statement)
                buf = []
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _split_procedure_file(sql: str) -> list[str]:
    """Parse a mysql-client procedure script into executable PyMySQL statements.

    A CREATE PROCEDURE contains internal semicolons inside BEGIN/END. The client
    normally uses DELIMITER to hide those semicolons. PyMySQL does not process
    DELIMITER, so we explicitly extract DROP statements and each full CREATE
    PROCEDURE block.
    """
    sql = sql.replace("\r\n", "\n")
    sql = re.sub(r"(?im)^\s*DELIMITER\s+\S+\s*$", "", sql)
    sql = re.sub(r"(?im)^\s*USE\s+`?[A-Za-z0-9_]+`?\s*;?\s*$", "", sql)

    statements: list[str] = []

    for match in re.finditer(r"(?is)\bDROP\s+PROCEDURE\s+IF\s+EXISTS\s+`?[A-Za-z0-9_]+`?\s*;", sql):
        statements.append(match.group(0).rstrip("; "))

    for match in re.finditer(
        r"(?is)\bCREATE\s+PROCEDURE\s+`?[A-Za-z0-9_]+`?.*?\bBEGIN\b.*?\bEND\s*;",
        sql,
    ):
        statements.append(match.group(0).rstrip("; "))

    if len([s for s in statements if s.upper().startswith("CREATE PROCEDURE")]) < 2:
        raise RuntimeError("procedures.sql must contain both stored procedure definitions")

    return statements


def _execute_script(cursor, filename: str) -> None:
    raw = _read_sql(filename)
    if filename == "procedures.sql":
        statements = _split_procedure_file(raw)
    else:
        statements = _split_standard_sql(_strip_client_commands(raw))

    for statement in statements:
        # Schema/database selection is handled by bootstrap below.
        if re.match(r"(?is)^CREATE\s+DATABASE\s+", statement):
            # schema.sql is allowed to contain the canonical CREATE DATABASE.
            cursor.execute(statement.replace("IF NOT EXISTS bill_analyzer", f"IF NOT EXISTS `{settings.DB_NAME}`", 1))
            continue
        cursor.execute(statement)

    log.info("Database script applied: %s (%d statements)", filename, len(statements))


def bootstrap() -> None:
    connection = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
        client_flag=CLIENT.MULTI_STATEMENTS,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(f"USE `{settings.DB_NAME}`")

            # Tables first, then seed data, views, and procedures.
            for filename in ("schema.sql", "seed_categories.sql", "views.sql", "procedures.sql"):
                _execute_script(cursor, filename)
    finally:
        connection.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(settings, "LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    bootstrap()
    print("MySQL database schema, views, procedures and categories are ready.")

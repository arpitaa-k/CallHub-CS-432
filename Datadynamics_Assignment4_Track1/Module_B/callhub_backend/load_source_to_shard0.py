import argparse
from pathlib import Path

import mysql.connector

from config import SHARD_HOST, SHARD_PORTS, TEAM_DB_NAME, TEAM_DB_PASSWORD, TEAM_DB_USER


def split_sql_statements(sql_text):
    statements = []
    buff = []
    in_single = False
    in_double = False

    for ch in sql_text:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double

        if ch == ";" and not in_single and not in_double:
            stmt = "".join(buff).strip()
            if stmt:
                statements.append(stmt)
            buff = []
        else:
            buff.append(ch)

    tail = "".join(buff).strip()
    if tail:
        statements.append(tail)
    return statements


def main():
    parser = argparse.ArgumentParser(description="Load base CallHub schema+data to IITGN shard 0 source database")
    parser.add_argument("--host", default=SHARD_HOST)
    parser.add_argument("--port", type=int, default=SHARD_PORTS[0])
    parser.add_argument("--user", default=TEAM_DB_USER)
    parser.add_argument("--password", default=TEAM_DB_PASSWORD)
    parser.add_argument("--database", default=TEAM_DB_NAME)
    parser.add_argument(
        "--sql-file",
        default="../sql/tables_CallHub.sql",
        help="Path to source SQL file with base schema and seed data",
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing base tables before loading",
    )
    args = parser.parse_args()

    sql_path = Path(__file__).resolve().parent / args.sql_file
    sql_text = sql_path.read_text(encoding="utf-8")

    statements = split_sql_statements(sql_text)

    conn = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        autocommit=False,
    )
    cur = conn.cursor()

    base_tables = [
        "User_Credentials",
        "Audit_Trail",
        "Search_Logs",
        "Emergency_Contacts",
        "Locations",
        "Contact_Details",
        "Member_Role_Assignments",
        "Members",
        "Role_Permissions",
        "Roles",
        "Data_Categories",
        "Departments",
    ]

    try:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        if args.drop_existing:
            for table in base_tables:
                cur.execute(f"DROP TABLE IF EXISTS `{table}`")
        cur.execute("SET FOREIGN_KEY_CHECKS=1")

        skipped = 0
        executed = 0
        for stmt in statements:
            upper = stmt.upper()
            if upper.startswith("CREATE DATABASE") or upper.startswith("USE "):
                skipped += 1
                continue
            cur.execute(stmt)
            executed += 1

        conn.commit()
        print(f"Loaded source schema/data into {args.database} at {args.host}:{args.port}")
        print(f"Statements executed: {executed}, skipped: {skipped}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

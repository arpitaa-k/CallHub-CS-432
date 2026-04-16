import argparse
import json
import re
from pathlib import Path

import mysql.connector

from config import (
    MYSQL_DB,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_USER,
    NUM_SHARDS,
    SHARD_HOST,
    SHARD_PORTS,
    TEAM_DB_NAME,
    TEAM_DB_PASSWORD,
    TEAM_DB_USER,
)


REFERENCE_TABLES = [
    "Departments",
    "Data_Categories",
    "Roles",
    "Role_Permissions",
]

PARTITIONED_TABLES = [
    "Members",
    "Member_Role_Assignments",
    "Contact_Details",
    "Locations",
    "Emergency_Contacts",
    "User_Credentials",
    "Search_Logs",
    "Audit_Trail",
]

SHARD_FILTERS = {
    "Members": "MOD(member_id, {num_shards}) = {shard_id}",
    "Member_Role_Assignments": "MOD(member_id, {num_shards}) = {shard_id}",
    "Contact_Details": "MOD(member_id, {num_shards}) = {shard_id}",
    "Locations": "MOD(member_id, {num_shards}) = {shard_id}",
    "Emergency_Contacts": "MOD(member_id, {num_shards}) = {shard_id}",
    "User_Credentials": "MOD(member_id, {num_shards}) = {shard_id}",
    "Search_Logs": "(searched_by_member_id IS NULL AND {shard_id}=0) OR (searched_by_member_id IS NOT NULL AND MOD(searched_by_member_id, {num_shards}) = {shard_id})",
    "Audit_Trail": "MOD(actor_id, {num_shards}) = {shard_id}",
}

PK_COLUMNS = {
    "Members": "member_id",
    "Member_Role_Assignments": "assignment_id",
    "Contact_Details": "contact_id",
    "Locations": "location_id",
    "Emergency_Contacts": "record_id",
    "User_Credentials": "user_id",
    "Search_Logs": "log_id",
    "Audit_Trail": "audit_id",
}


def connect_mysql(host, port, user, password, database):
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        autocommit=False,
    )


def table_to_prefixed(table_name, shard_id):
    return f"shard_{shard_id}_{table_name.lower()}"


def build_table_name_map(all_tables, shard_id):
    return {table: table_to_prefixed(table, shard_id) for table in all_tables}


def rewrite_create_table_sql(create_sql, table_name_map, shard_id):
    # Replace table names and FK references from original names to prefixed names.
    rewritten = create_sql
    for src_name, dst_name in table_name_map.items():
        rewritten = rewritten.replace(f"`{src_name}`", f"`{dst_name}`")

    # Constraint names must be unique inside a schema.
    rewritten = re.sub(
        r"CONSTRAINT `([^`]+)`",
        lambda m: f"CONSTRAINT `{m.group(1)}_s{shard_id}`",
        rewritten,
    )
    return rewritten


def fetch_table_schema(source_cur, table_name):
    source_cur.execute(f"SHOW CREATE TABLE `{table_name}`")
    row = source_cur.fetchone()
    return row[1]


def recreate_shard_tables(source_cur, shard_cur, all_tables, shard_id, reset_tables):
    table_name_map = build_table_name_map(all_tables, shard_id)

    shard_cur.execute("SET FOREIGN_KEY_CHECKS=0")
    if reset_tables:
        # Cleanup stale shard tables from prior runs so each node only keeps
        # the tables intended for its own shard_id in the current migration.
        for cleanup_shard_id in range(NUM_SHARDS):
            cleanup_map = build_table_name_map(all_tables, cleanup_shard_id)
            for table_name in all_tables:
                shard_cur.execute(f"DROP TABLE IF EXISTS `{cleanup_map[table_name]}`")

    for table_name in all_tables:
        dst_table = table_name_map[table_name]
        if reset_tables:
            create_sql = fetch_table_schema(source_cur, table_name)
            rewritten = rewrite_create_table_sql(create_sql, table_name_map, shard_id)
            shard_cur.execute(rewritten)
        else:
            shard_cur.execute(f"TRUNCATE TABLE `{dst_table}`")
    shard_cur.execute("SET FOREIGN_KEY_CHECKS=1")

    return table_name_map


def fetch_rows(source_cur, table_name, where_clause=None):
    if where_clause:
        query = f"SELECT * FROM `{table_name}` WHERE {where_clause}"
    else:
        query = f"SELECT * FROM `{table_name}`"
    source_cur.execute(query)
    return source_cur.fetchall()


def insert_rows(shard_cur, dst_table, rows):
    if not rows:
        return 0
    placeholders = ", ".join(["%s"] * len(rows[0]))
    shard_cur.executemany(f"INSERT INTO `{dst_table}` VALUES ({placeholders})", rows)
    return len(rows)


def migrate_to_shard(source_cur, shard_cur, shard_id, num_shards, reset_tables):
    all_tables = REFERENCE_TABLES + PARTITIONED_TABLES
    table_name_map = recreate_shard_tables(source_cur, shard_cur, all_tables, shard_id, reset_tables)

    copied = {}

    # Replicate reference tables fully on every shard.
    for table_name in REFERENCE_TABLES:
        rows = fetch_rows(source_cur, table_name)
        copied[table_name] = insert_rows(shard_cur, table_name_map[table_name], rows)

    # Partition large tables by shard key.
    for table_name in PARTITIONED_TABLES:
        where_clause = SHARD_FILTERS[table_name].format(num_shards=num_shards, shard_id=shard_id)
        rows = fetch_rows(source_cur, table_name, where_clause=where_clause)
        copied[table_name] = insert_rows(shard_cur, table_name_map[table_name], rows)

    return copied


def count_rows(cur, table_name, where_clause=None):
    query = f"SELECT COUNT(*) FROM `{table_name}`"
    if where_clause:
        query += f" WHERE {where_clause}"
    cur.execute(query)
    return cur.fetchone()[0]


def verify_counts(source_cur, shard_cursors, num_shards):
    result = {}

    # Reference tables should be identical on each shard.
    for table_name in REFERENCE_TABLES:
        source_count = count_rows(source_cur, table_name)
        shard_counts = []
        for shard_id, shard_cur in enumerate(shard_cursors):
            dst = table_to_prefixed(table_name, shard_id)
            shard_counts.append(count_rows(shard_cur, dst))
        result[table_name] = {
            "source_count": source_count,
            "shard_counts": shard_counts,
            "status": "OK" if all(c == source_count for c in shard_counts) else "MISMATCH",
        }

    # Partitioned tables should sum to source count.
    for table_name in PARTITIONED_TABLES:
        source_count = count_rows(source_cur, table_name)
        shard_counts = []
        for shard_id, shard_cur in enumerate(shard_cursors):
            dst = table_to_prefixed(table_name, shard_id)
            shard_counts.append(count_rows(shard_cur, dst))
        shard_sum = sum(shard_counts)
        result[table_name] = {
            "source_count": source_count,
            "shard_counts": shard_counts,
            "shard_sum": shard_sum,
            "status": "OK" if shard_sum == source_count else "MISMATCH",
        }

    return result


def verify_no_duplicates(shard_cursors):
    duplicate_report = {}
    for table_name, pk_col in PK_COLUMNS.items():
        key_locations = {}
        for shard_id, shard_cur in enumerate(shard_cursors):
            dst = table_to_prefixed(table_name, shard_id)
            shard_cur.execute(f"SELECT `{pk_col}` FROM `{dst}`")
            for (pk_value,) in shard_cur.fetchall():
                key_locations.setdefault(pk_value, set()).add(shard_id)

        duplicates = [key for key, locations in key_locations.items() if len(locations) > 1]
        duplicate_report[table_name] = {
            "duplicate_keys": len(duplicates),
            "status": "OK" if not duplicates else "MISMATCH",
        }

    return duplicate_report


def parse_ports(csv_text):
    values = [int(x.strip()) for x in csv_text.split(",") if x.strip()]
    if len(values) < 3:
        raise ValueError("At least 3 shard ports are required")
    return values


def main():
    parser = argparse.ArgumentParser(description="Migrate CallHub data to IITGN shard nodes")
    parser.add_argument("--source-host", default=MYSQL_HOST)
    parser.add_argument("--source-port", type=int, default=3306)
    parser.add_argument("--source-user", default=MYSQL_USER)
    parser.add_argument("--source-password", default=MYSQL_PASSWORD)
    parser.add_argument("--source-db", default=MYSQL_DB)

    parser.add_argument("--shard-host", default=SHARD_HOST)
    parser.add_argument("--num-shards", type=int, default=NUM_SHARDS)
    parser.add_argument("--shard-ports", default=",".join(str(p) for p in SHARD_PORTS))
    parser.add_argument("--team-user", default=TEAM_DB_USER)
    parser.add_argument("--team-password", default=TEAM_DB_PASSWORD)
    parser.add_argument("--team-db", default=TEAM_DB_NAME)
    parser.add_argument(
        "--reset-tables",
        action="store_true",
        help="Drop and recreate shard_* tables before loading data",
    )

    parser.add_argument(
        "--report-path",
        default="../benchmarks/iitgn_shard_migration_report.json",
        help="Where to save migration report JSON",
    )

    args = parser.parse_args()

    if args.num_shards < 3:
        raise ValueError("This setup requires at least 3 shards")

    ports = parse_ports(args.shard_ports)
    if len(ports) != args.num_shards:
        raise ValueError("num-shards must match number of ports in --shard-ports")

    if not args.source_user or not args.source_password or not args.source_db:
        raise ValueError("Source DB credentials are required for migration")

    source_conn = connect_mysql(
        host=args.source_host,
        port=args.source_port,
        user=args.source_user,
        password=args.source_password,
        database=args.source_db,
    )
    source_cur = source_conn.cursor()

    shard_conns = []
    shard_cursors = []

    try:
        for shard_id in range(args.num_shards):
            shard_conn = connect_mysql(
                host=args.shard_host,
                port=ports[shard_id],
                user=args.team_user,
                password=args.team_password,
                database=args.team_db,
            )
            shard_conns.append(shard_conn)
            shard_cursors.append(shard_conn.cursor())

        copied_per_shard = {}
        for shard_id, shard_cur in enumerate(shard_cursors):
            copied = migrate_to_shard(
                source_cur,
                shard_cur,
                shard_id,
                args.num_shards,
                args.reset_tables,
            )
            copied_per_shard[f"shard_{shard_id}"] = copied

        for shard_conn in shard_conns:
            shard_conn.commit()

        count_report = verify_counts(source_cur, shard_cursors, args.num_shards)
        duplicate_report = verify_no_duplicates(shard_cursors)

        report = {
            "copied_per_shard": copied_per_shard,
            "count_verification": count_report,
            "duplicate_verification": duplicate_report,
        }

        report_path = Path(__file__).resolve().parent / args.report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        print("IITGN shard migration completed.")
        print(f"Report written to: {report_path}")

        failed_count_checks = [k for k, v in count_report.items() if v["status"] != "OK"]
        failed_dupe_checks = [k for k, v in duplicate_report.items() if v["status"] != "OK"]

        if failed_count_checks or failed_dupe_checks:
            print("Verification status: MISMATCH")
            if failed_count_checks:
                print("Count mismatches:", ", ".join(failed_count_checks))
            if failed_dupe_checks:
                print("Duplicate mismatches:", ", ".join(failed_dupe_checks))
        else:
            print("Verification status: OK")

    finally:
        source_cur.close()
        source_conn.close()
        for cur in shard_cursors:
            cur.close()
        for conn in shard_conns:
            conn.close()


if __name__ == "__main__":
    main()

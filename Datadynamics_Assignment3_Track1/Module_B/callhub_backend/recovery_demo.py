import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

from config import MYSQL_DB, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_USER


def now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


def get_connection() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        autocommit=False,
    )


def count_member_by_name(name: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM Members WHERE full_name=%s", (name,))
    count = int(cur.fetchone()[0])
    cur.close()
    conn.close()
    return count


def probe_failed_multistep_rollback() -> dict:
    tag = now_tag()
    full_name = f"RecoveryFail_{tag}"
    conn = get_connection()
    cur = conn.cursor()
    inserted_member_id = None

    try:
        # Step 1: valid insert into Members.
        cur.execute(
            """
            INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date)
            VALUES (%s, %s, %s, %s, %s, CURDATE())
            """,
            (full_name, "Recovery Probe", 30, "M", 1),
        )
        inserted_member_id = int(cur.lastrowid)

        # Step 2: force transaction failure with an invalid foreign key.
        cur.execute(
            """
            INSERT INTO Contact_Details (member_id, contact_type, contact_value, category_id)
            VALUES (%s, %s, %s, %s)
            """,
            (inserted_member_id, "Official Email", f"{full_name.lower()}@example.com", -999),
        )

        conn.commit()
        return {
            "probe": "failed_multistep_rollback",
            "unexpected": True,
            "message": "Failure was expected but transaction committed",
        }
    except Exception as exc:
        conn.rollback()
        remaining = count_member_by_name(full_name)
        return {
            "probe": "failed_multistep_rollback",
            "forced_failure": str(exc),
            "rollback_verified": remaining == 0,
            "remaining_rows_with_tag": remaining,
        }
    finally:
        cur.close()
        conn.close()


def probe_connection_drop_recovery() -> dict:
    tag = now_tag()
    full_name = f"RecoveryDrop_{tag}"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date)
            VALUES (%s, %s, %s, %s, %s, CURDATE())
            """,
            (full_name, "Recovery Probe", 30, "F", 1),
        )
        # Simulate app/process crash: close connection before commit.
        cur.close()
        conn.close()

        remaining = count_member_by_name(full_name)
        return {
            "probe": "connection_drop_before_commit",
            "rollback_verified": remaining == 0,
            "remaining_rows_with_tag": remaining,
        }
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {
            "probe": "connection_drop_before_commit",
            "error": str(exc),
        }


def probe_commit_durability() -> dict:
    tag = now_tag()
    full_name = f"RecoveryCommit_{tag}"

    conn = get_connection()
    cur = conn.cursor()
    member_id = None

    try:
        cur.execute(
            """
            INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date)
            VALUES (%s, %s, %s, %s, %s, CURDATE())
            """,
            (full_name, "Recovery Probe", 31, "M", 1),
        )
        member_id = int(cur.lastrowid)
        conn.commit()

        persisted = count_member_by_name(full_name) == 1

        # Cleanup probe row so repeated runs stay clean.
        cleanup_conn = get_connection()
        cleanup_cur = cleanup_conn.cursor()
        cleanup_cur.execute("DELETE FROM Members WHERE member_id=%s", (member_id,))
        cleanup_conn.commit()
        cleanup_cur.close()
        cleanup_conn.close()

        return {
            "probe": "commit_durability",
            "persisted_after_commit": persisted,
            "cleanup_member_id": member_id,
        }
    except Exception as exc:
        conn.rollback()
        return {
            "probe": "commit_durability",
            "error": str(exc),
        }
    finally:
        cur.close()
        conn.close()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Crash recovery demo for SQL transaction behavior")
    parser.add_argument("--out-file", default="../benchmarks/recovery_demo_report.json")
    args = parser.parse_args()

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "db": {
            "host": MYSQL_HOST,
            "database": MYSQL_DB,
        },
        "probes": [
            probe_failed_multistep_rollback(),
            probe_connection_drop_recovery(),
            probe_commit_durability(),
        ],
    }

    checks = {
        "failed_multistep_rollback": bool(report["probes"][0].get("rollback_verified")),
        "connection_drop_recovery": bool(report["probes"][1].get("rollback_verified")),
        "commit_durability": bool(report["probes"][2].get("persisted_after_commit")),
    }
    report["verdict"] = {
        "overall": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }

    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Recovery demo complete")
    print(f"Saved: {out_path.resolve()}")
    print(f"[verdict] {report['verdict']}")


if __name__ == "__main__":
    main()

from db import mysql
import os
from datetime import datetime


def _ensure_logs_dir():
    logs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    logs_dir = os.path.abspath(logs_dir)
    if not os.path.isdir(logs_dir):
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except Exception:
            pass
    return logs_dir


def log_action(actor_id, table, record_id, action, source='API'):
    """Log action into Audit_Trail table and append a human-readable copy to logs/audit.log.

    The optional `source` field can be used to indicate whether the change originated from
    the application (`'API'`) or was produced by a DB trigger/other source (`'DB'`).
    """

    cur = mysql.connection.cursor()

    # no-op if already present.
    try:
        cur.execute("SELECT source FROM Audit_Trail LIMIT 1")
    except Exception:
        try:
            cur.execute("ALTER TABLE Audit_Trail ADD COLUMN source VARCHAR(16) DEFAULT 'API'")
            mysql.connection.commit()
        except Exception:
            # If alter fails, ignore;
            pass

    try:
        cur.execute("""
            INSERT INTO Audit_Trail
            (actor_id, target_table, target_record_id, action_type, source)
            VALUES (%s,%s,%s,%s,%s)
        """, (actor_id, table, record_id, action, source))
        mysql.connection.commit()
    except Exception:
        # fallback:
        try:
            cur.execute("""
                INSERT INTO Audit_Trail
                (actor_id, target_table, target_record_id, action_type)
                VALUES (%s,%s,%s,%s)
            """, (actor_id, table, record_id, action))
            mysql.connection.commit()
        except Exception:
            # give up silently to avoid breaking API flow;
            print("Failed to write Audit_Trail entry")

    # Append human-readable log to file
    try:
        logs_dir = _ensure_logs_dir()
        logfile = os.path.join(logs_dir, 'audit.log')
        timestamp = datetime.utcnow().isoformat() + 'Z'
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp}\tactor={actor_id}\ttable={table}\trecord={record_id}\taction={action}\tsource={source}\n")
    except Exception:
        # don't let file logging break application
        pass
import os
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime

load_dotenv()
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DB')
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_audit_column_and_triggers():
    """Ensure Audit_Trail has a `source` column and create DB triggers to capture direct DB changes.

    This script is intended to be run once (or re-run safely). It will:
    - add `source VARCHAR(16)` to `Audit_Trail` if missing
    - drop FK on `actor_id` and make it nullable if needed
    - create AFTER INSERT/UPDATE/DELETE triggers for critical tables

    Run with: `python setup_audit_triggers.py` from the `callhub_backend` folder.
    Note: CREATE TRIGGER and ALTER TABLE require appropriate DB privileges.
    """
    conn = get_connection()
    cur = conn.cursor()
    # Add source column if missing
    cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='Audit_Trail' AND COLUMN_NAME='source'", (DB_CONFIG['database'],))
    if not cur.fetchone():
        try:
            cur.execute("ALTER TABLE Audit_Trail ADD COLUMN source VARCHAR(16) DEFAULT 'API'")
            conn.commit()
            print('Added source column to Audit_Trail')
        except Exception as e:
            print('Could not add source column:', e)

    # Ensure actor_id allows NULL (triggers will insert NULL for DB-origin events)
    try:
        cur.execute("SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='Audit_Trail' AND COLUMN_NAME='actor_id'", (DB_CONFIG['database'],))
        row = cur.fetchone()
        if row and row[0] == 'NO':
            # Drop foreign key constraint on actor_id if present, then alter to allow NULL
            cur.execute("SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND TABLE_NAME='Audit_Trail' AND COLUMN_NAME='actor_id' AND REFERENCED_TABLE_NAME='Members'", (DB_CONFIG['database'],))
            fk = cur.fetchone()
            if fk:
                try:
                    cur.execute(f"ALTER TABLE Audit_Trail DROP FOREIGN KEY {fk[0]}")
                    conn.commit()
                    print(f"Dropped foreign key constraint {fk[0]} on Audit_Trail.actor_id")
                except Exception as e:
                    print('Could not drop foreign key on actor_id:', e)
            try:
                cur.execute("ALTER TABLE Audit_Trail MODIFY actor_id INT NULL")
                conn.commit()
                print('Modified Audit_Trail.actor_id to allow NULL')
            except Exception as e:
                print('Could not modify Audit_Trail.actor_id to NULL:', e)
    except Exception as e:
        print('Could not check/modify actor_id nullability:', e)

    # Create triggers for Members table if not present
    cur.execute("SELECT TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME='trg_audit_members_insert'", (DB_CONFIG['database'],))
    if not cur.fetchone():
        try:
            cur.execute("CREATE TRIGGER trg_audit_members_insert AFTER INSERT ON Members FOR EACH ROW INSERT INTO Audit_Trail (actor_id, target_table, target_record_id, action_type, source) VALUES (NULL, 'Members', NEW.member_id, 'INSERT', 'DB')")
            conn.commit()
            print('Created trigger: trg_audit_members_insert')
        except Exception as e:
            print('Could not create insert trigger for Members:', e)

    cur.execute("SELECT TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME='trg_audit_members_update'", (DB_CONFIG['database'],))
    if not cur.fetchone():
        try:
            cur.execute("CREATE TRIGGER trg_audit_members_update AFTER UPDATE ON Members FOR EACH ROW INSERT INTO Audit_Trail (actor_id, target_table, target_record_id, action_type, source) VALUES (NULL, 'Members', NEW.member_id, 'UPDATE', 'DB')")
            conn.commit()
            print('Created trigger: trg_audit_members_update')
        except Exception as e:
            print('Could not create update trigger for Members:', e)

    cur.execute("SELECT TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME='trg_audit_members_delete'", (DB_CONFIG['database'],))
    if not cur.fetchone():
        try:
            cur.execute("CREATE TRIGGER trg_audit_members_delete AFTER DELETE ON Members FOR EACH ROW INSERT INTO Audit_Trail (actor_id, target_table, target_record_id, action_type, source) VALUES (NULL, 'Members', OLD.member_id, 'DELETE', 'DB')")
            conn.commit()
            print('Created trigger: trg_audit_members_delete')
        except Exception as e:
            print('Could not create delete trigger for Members:', e)

    other_tables = [
        ('Contact_Details', 'contact_id'),
        ('Locations', 'location_id'),
        ('Emergency_Contacts', 'record_id'),
        ('Member_Role_Assignments', 'assignment_id'),
        ('User_Credentials', 'user_id')
    ]

    for tbl, pk in other_tables:
        trg_ins = f'trg_audit_{tbl.lower()}_insert'
        cur.execute("SELECT TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME=%s", (DB_CONFIG['database'], trg_ins))
        if not cur.fetchone():
            try:
                cur.execute(f"CREATE TRIGGER {trg_ins} AFTER INSERT ON {tbl} FOR EACH ROW INSERT INTO Audit_Trail (actor_id, target_table, target_record_id, action_type, source) VALUES (NULL, '{tbl}', NEW.{pk}, 'INSERT', 'DB')")
                conn.commit()
                print('Created trigger:', trg_ins)
            except Exception as e:
                print(f'Could not create insert trigger for {tbl}:', e)

        trg_upd = f'trg_audit_{tbl.lower()}_update'
        cur.execute("SELECT TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME=%s", (DB_CONFIG['database'], trg_upd))
        if not cur.fetchone():
            try:
                cur.execute(f"CREATE TRIGGER {trg_upd} AFTER UPDATE ON {tbl} FOR EACH ROW INSERT INTO Audit_Trail (actor_id, target_table, target_record_id, action_type, source) VALUES (NULL, '{tbl}', NEW.{pk}, 'UPDATE', 'DB')")
                conn.commit()
                print('Created trigger:', trg_upd)
            except Exception as e:
                print(f'Could not create update trigger for {tbl}:', e)

        trg_del = f'trg_audit_{tbl.lower()}_delete'
        cur.execute("SELECT TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME=%s", (DB_CONFIG['database'], trg_del))
        if not cur.fetchone():
            try:
                cur.execute(f"CREATE TRIGGER {trg_del} AFTER DELETE ON {tbl} FOR EACH ROW INSERT INTO Audit_Trail (actor_id, target_table, target_record_id, action_type, source) VALUES (NULL, '{tbl}', OLD.{pk}, 'DELETE', 'DB')")
                conn.commit()
                print('Created trigger:', trg_del)
            except Exception as e:
                print(f'Could not create delete trigger for {tbl}:', e)

    cur.close()
    conn.close()


if __name__ == '__main__':
    print('Running audit/trigger setup. This will ALTER Audit_Trail and CREATE TRIGGERS if permitted.')
    ensure_audit_column_and_triggers()

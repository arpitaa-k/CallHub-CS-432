from db import mysql

def log_action(actor_id, table, record_id, action):

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO Audit_Trail
        (actor_id, target_table, target_record_id, action_type)
        VALUES (%s,%s,%s,%s)
    """,(actor_id,table,record_id,action))

    mysql.connection.commit()
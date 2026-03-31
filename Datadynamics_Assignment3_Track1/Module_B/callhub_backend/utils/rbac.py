from db import mysql

def has_permission(member_id, category_id):

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT rp.can_view
        FROM Member_Role_Assignments mra
        JOIN Role_Permissions rp
        ON mra.role_id = rp.role_id
        WHERE mra.member_id=%s
        AND rp.category_id=%s
    """, (member_id, category_id))

    result = cur.fetchone()

    return result is not None and result[0] == 1


def is_admin(member_id):
    cur = mysql.connection.cursor()

    # Check whether any of the member's assigned roles has can_edit_others flag set
    cur.execute("""
        SELECT r.can_edit_others
        FROM Member_Role_Assignments mra
        JOIN Roles r ON mra.role_id = r.role_id
        WHERE mra.member_id = %s
    """, (member_id,))

    rows = cur.fetchall()

    for row in rows:
        if row and row[0] == 1:
            return True

    return False


def can_edit_others(role):

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT can_edit_others
        FROM Roles
        WHERE role_title = %s
    """, (role,))

    result = cur.fetchone()

    return result and result[0] == 1

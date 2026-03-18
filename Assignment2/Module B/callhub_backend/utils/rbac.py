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
    """,(member_id,category_id))

    result = cur.fetchone()

    return result is not None


def is_admin(member_id):

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT r.role_title
        FROM Member_Role_Assignments mra
        JOIN Roles r ON mra.role_id = r.role_id
        WHERE mra.member_id = %s
    """,(member_id,))

    roles = cur.fetchall()

    admin_roles = ["admin", "director", "dean academics", "registrar"]
    print("ROLES FROM DB:", roles)
    for role in roles:
        if role[0].lower() in admin_roles:
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

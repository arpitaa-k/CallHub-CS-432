from utils.shard_manager import shard_manager

def has_permission(member_id, category_id):

    shard_id = shard_manager.get_shard_id(member_id)

    result = shard_manager.execute_on_shard(shard_id, """
        SELECT rp.can_view
        FROM shard_{}_member_role_assignments mra
        JOIN Role_Permissions rp
        ON mra.role_id = rp.role_id
        WHERE mra.member_id=%s
        AND rp.category_id=%s
    """.format(shard_id), (member_id, category_id), fetch=True)

    return len(result) > 0 and result[0][0] == 1


def is_admin(member_id):
    shard_id = shard_manager.get_shard_id(member_id)

    # Check whether any of the member's assigned roles has can_edit_others flag set
    result = shard_manager.execute_on_shard(shard_id, """
        SELECT r.can_edit_others
        FROM shard_{}_member_role_assignments mra
        JOIN Roles r ON mra.role_id = r.role_id
        WHERE mra.member_id = %s
    """.format(shard_id), (member_id,), fetch=True)

    for row in result:
        if row and row[0] == 1:
            return True

    return False


def can_edit_others(role):
    if not role:
        return False

    result = shard_manager.execute_on_shard(0, """
        SELECT can_edit_others
        FROM Roles
        WHERE role_title = %s
    """, (role,), fetch=True)

    row = result[0] if result else None
    return bool(row and row[0] == 1)

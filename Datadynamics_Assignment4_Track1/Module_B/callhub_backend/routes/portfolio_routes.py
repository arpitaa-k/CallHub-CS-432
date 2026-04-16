from flask import Blueprint, jsonify, session
from utils.auth import login_required
from utils.shard_manager import shard_manager

portfolio = Blueprint("portfolio", __name__)


@portfolio.route("/member/<int:member_id>/portfolio", methods=["GET"])
@login_required
def get_portfolio(member_id):
    actor_id = session["member_id"]
    actor_shard = shard_manager.get_shard_id(actor_id)
    target_shard = shard_manager.get_shard_id(member_id)

    # DEBUG: Verify single-key lookup routing
    print(f"[DEBUG] portfolio lookup: member_id={member_id}, target_shard={target_shard}, actor_id={actor_id}, actor_shard={actor_shard}")

    is_owner = actor_id == member_id

    allowed_categories = []
    if not is_owner:
        rows = shard_manager.execute_on_shard(actor_shard, """
            SELECT DISTINCT rp.category_id
            FROM shard_{}_member_role_assignments mra
            JOIN shard_{}_role_permissions rp ON mra.role_id = rp.role_id
            WHERE mra.member_id=%s AND rp.can_view=1
        """.format(actor_shard, actor_shard), (actor_id,), fetch=True)
        allowed_categories = [row[0] for row in rows]

    rows = shard_manager.execute_on_shard(target_shard, """
        SELECT member_id, full_name, designation, age, gender, dept_id, join_date, is_active
        FROM shard_{}_members
        WHERE member_id=%s AND is_deleted=0
    """.format(target_shard), (member_id,), fetch=True)
    member_row = rows[0] if rows else None

    if not member_row:
        return {"error": "Member not found"}, 404

    member = {
        "member_id": member_row[0],
        "full_name": member_row[1],
        "designation": member_row[2],
        "age": member_row[3],
        "gender": member_row[4],
        "dept_id": member_row[5],
        "join_date": member_row[6].isoformat() if member_row[6] else None,
        "is_active": member_row[7],
    }

    contacts_raw = shard_manager.execute_on_shard(target_shard, """
        SELECT cd.contact_type, cd.contact_value, cd.category_id, dc.category_name
        FROM shard_{}_contact_details cd
        JOIN shard_{}_data_categories dc ON cd.category_id = dc.category_id
        WHERE cd.member_id=%s
    """.format(target_shard, target_shard), (member_id,), fetch=True)

    contacts = []
    for contact_type, contact_value, category_id, category_name in contacts_raw:
        if is_owner or category_id in allowed_categories:
            contacts.append({
                "contact_type": contact_type,
                "contact_value": contact_value,
                "category_id": category_id,
                "category_name": category_name,
            })

    locations_raw = shard_manager.execute_on_shard(target_shard, """
        SELECT l.location_type, l.building_name, l.room_number, l.category_id, dc.category_name
        FROM shard_{}_locations l
        JOIN shard_{}_data_categories dc ON l.category_id = dc.category_id
        WHERE l.member_id=%s
    """.format(target_shard, target_shard), (member_id,), fetch=True)

    locations = []
    for location_type, building_name, room_number, category_id, category_name in locations_raw:
        if is_owner or category_id in allowed_categories:
            locations.append({
                "location_type": location_type,
                "building_name": building_name,
                "room_number": room_number,
                "category_id": category_id,
                "category_name": category_name,
            })

    emergency_raw = shard_manager.execute_on_shard(target_shard, """
        SELECT ec.contact_person_name, ec.relation, ec.emergency_phone, ec.category_id, dc.category_name
        FROM shard_{}_emergency_contacts ec
        JOIN shard_{}_data_categories dc ON ec.category_id = dc.category_id
        WHERE ec.member_id=%s
    """.format(target_shard, target_shard), (member_id,), fetch=True)

    emergency_contacts = []
    for contact_person_name, relation, emergency_phone, category_id, category_name in emergency_raw:
        if is_owner or category_id in allowed_categories:
            emergency_contacts.append({
                "contact_person_name": contact_person_name,
                "relation": relation,
                "emergency_phone": emergency_phone,
                "category_id": category_id,
                "category_name": category_name,
            })

    dept_rows = shard_manager.execute_on_shard(target_shard, """
        SELECT dept_code, dept_name, building_location, is_academic
        FROM shard_{}_departments
        WHERE dept_id=%s
    """.format(target_shard), (member["dept_id"],), fetch=True)
    department = dept_rows[0] if dept_rows else None

    member["department"] = {
        "dept_code": department[0] if department else None,
        "dept_name": department[1] if department else None,
        "building_location": department[2] if department else None,
        "is_academic": department[3] if department else None,
    }

    return jsonify({
        "member": member,
        "contacts": contacts,
        "locations": locations,
        "emergency_contacts": emergency_contacts,
    })

from flask import Blueprint, jsonify, request, session
from db import mysql
from utils.auth import login_required
from utils.rbac import can_edit_others
from utils.logger import log_action
from utils.shard_manager import shard_manager
import bcrypt

members = Blueprint("members", __name__)


def _normalize_detail_entries(data):
    """Normalize legacy single-entry payload into multi-entry lists.

    New payload shape supports:
    - contacts: [{contact_type, contact_value, category_name}]
    - locations: [{location_type, building_name, room_number, category_name}]
    - emergency_contacts: [{contact_person_name, relation, emergency_phone, category_name}]
    """
    default_category = data.get("category_name")

    contacts = data.get("contacts")
    if not isinstance(contacts, list):
        contacts = []
        if data.get("contact_type") and data.get("contact_value"):
            contacts.append({
                "contact_type": data.get("contact_type"),
                "contact_value": data.get("contact_value"),
                "category_name": data.get("contact_category_name") or default_category,
            })

    locations = data.get("locations")
    if not isinstance(locations, list):
        locations = []
        if data.get("location_type") and data.get("building_name") and data.get("room_number"):
            locations.append({
                "location_type": data.get("location_type"),
                "building_name": data.get("building_name"),
                "room_number": data.get("room_number"),
                "category_name": data.get("location_category_name") or default_category,
            })

    emergency_contacts = data.get("emergency_contacts")
    if not isinstance(emergency_contacts, list):
        emergency_contacts = []
        if data.get("emergency_name") and data.get("relation") and data.get("emergency_contact"):
            emergency_contacts.append({
                "contact_person_name": data.get("emergency_name"),
                "relation": data.get("relation"),
                "emergency_phone": data.get("emergency_contact"),
                "category_name": data.get("emergency_category_name") or default_category,
            })

    return contacts, locations, emergency_contacts


def _category_id(category_name, shard_id=0):
    """Get category_id. Reference tables are replicated, so query shard 0."""
    if not category_name:
        return None
    result = shard_manager.execute_on_shard(shard_id, "SELECT category_id FROM Data_Categories WHERE category_name = %s", (category_name,), fetch=True)
    row = result[0] if result else None
    return row[0] if row else None

# Get editable roles for current user

@members.route("/editable-roles", methods=["GET"])
@login_required
def get_editable_roles():

    role = session.get("role")
    
    # Check if current user's role has can_edit_others = 1 (reference table on shard 0)
    result = shard_manager.execute_on_shard(0, """
        SELECT can_edit_others
        FROM Roles
        WHERE role_title = %s
    """, (role,), fetch=True)

    user_role = result[0] if result else None

    # If user doesn't have edit permission, return empty
    if not user_role or user_role[0] == 0:
        return jsonify([])

    # If user has permission, return ALL roles (from replicated reference table on shard 0)
    rows = shard_manager.execute_on_shard(0, """
        SELECT role_id, role_title
        FROM Roles
        ORDER BY role_title
    """, fetch=True)

    result = []
    for row in rows:
        result.append({
            "role_id": row[0],
            "role_title": row[1]
        })

    return jsonify(result)


# Get all members and filter by role:

@members.route("/members", methods=["GET"])
@login_required
def get_members():

    actor_id = session["member_id"]
    user_role = session.get("role")

    role_filter = request.args.get("role", "")

    cur = mysql.connection.cursor()

    if can_edit_others(user_role):
        # Admin: can see all
        if role_filter:
            # Query all shards
            query = """
                SELECT m.member_id, m.full_name, m.designation
                FROM shard_{}_members m
                JOIN shard_{}_member_role_assignments mra ON m.member_id = mra.member_id
                JOIN shard_{}_roles r ON mra.role_id = r.role_id
                WHERE r.role_title = %s AND m.is_deleted = 0
            """
            data = []
            for shard_id in range(3):  # NUM_SHARDS
                print(f"[DEBUG] GET /members role_filter={role_filter} shard={shard_id}")
                result = shard_manager.execute_on_shard(shard_id, query.format(shard_id, shard_id, shard_id), (role_filter,), fetch=True)
                data.extend(result)
        else:
            query = """
                SELECT member_id, full_name, designation
                FROM shard_{}_members
                WHERE is_deleted = 0
            """
            data = []
            for shard_id in range(3):
                print(f"[DEBUG] GET /members all shards shard={shard_id}")
                result = shard_manager.execute_on_shard(shard_id, query.format(shard_id), fetch=True)
                data.extend(result)
    else:
        # Regular user: only own
        shard_id = shard_manager.get_shard_id(actor_id)
        data = shard_manager.execute_on_shard(shard_id, """
            SELECT member_id, full_name, designation
            FROM shard_{}_members
            WHERE member_id = %s AND is_deleted = 0
        """.format(shard_id), (actor_id,), fetch=True)

    result = []
    for row in data:
        result.append({
            "member_id": row[0],
            "full_name": row[1],
            "designation": row[2]
        })

    return jsonify(result)


# Create member (Admin only)
@members.route("/members", methods=["POST"])
@login_required
def create_member():

    actor_id = session["member_id"]
    role = session.get("role")

    if not can_edit_others(role):
        return {"error": "Edit privileges required"},403

    data = request.json

    # Department (for new member only) - removed from UI; default to 1 if not provided
    dept_id = data.get("dept_id") or 1

    # Role
    role_title = data.get("role_title")

    # Member
    full_name = data.get("full_name")
    designation = data.get("designation")
    age = data.get("age")
    gender = data.get("gender")
    join_date = data.get("join_date")
    assign_date = data.get("assign_date")

    contacts, locations, emergency_contacts = _normalize_detail_entries(data)

    # Credentials
    username = data.get("username")
    password = data.get("password")

    cur = mysql.connection.cursor()

    try:
        # Get role_id
        result = shard_manager.execute_on_shard(0, "SELECT role_id FROM Roles WHERE role_title = %s", (role_title,), fetch=True)
        role_row = result[0] if result else None
        if not role_row:
            return {"error": "Invalid role"}, 400
        role_id = role_row[0]

        if not contacts:
            return {"error": "At least one contact detail is required"}, 400
        if not locations:
            return {"error": "At least one location detail is required"}, 400
        if not emergency_contacts:
            return {"error": "At least one emergency contact is required"}, 400

        # Get next member_id
        new_member_id = shard_manager.get_next_member_id()
        shard_id = shard_manager.get_shard_id(new_member_id)

        # Insert Member
        shard_manager.execute_on_shard(shard_id, """
            INSERT INTO shard_{}_members (member_id, full_name, designation, age, gender, dept_id, join_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """.format(shard_id), (new_member_id, full_name, designation, age, gender, dept_id, join_date))

        # Insert Contact_Details (multi-entry)
        for c in contacts:
            cat_id = _category_id(c.get("category_name"))
            if not cat_id:
                return {"error": f"Invalid contact category: {c.get('category_name')}"}, 400
            shard_manager.execute_on_shard(shard_id, """
                INSERT INTO shard_{}_contact_details (member_id, contact_type, contact_value, category_id)
                VALUES (%s, %s, %s, %s)
            """.format(shard_id), (new_member_id, c.get("contact_type"), c.get("contact_value"), cat_id))

        # Insert Locations (multi-entry)
        for l in locations:
            cat_id = _category_id(l.get("category_name"))
            if not cat_id:
                return {"error": f"Invalid location category: {l.get('category_name')}"}, 400
            shard_manager.execute_on_shard(shard_id, """
                INSERT INTO shard_{}_locations (member_id, location_type, building_name, room_number, category_id)
                VALUES (%s, %s, %s, %s, %s)
            """.format(shard_id), (new_member_id, l.get("location_type"), l.get("building_name"), l.get("room_number"), cat_id))

        # Insert Emergency_Contacts (multi-entry)
        for e in emergency_contacts:
            cat_id = _category_id(e.get("category_name"))
            if not cat_id:
                return {"error": f"Invalid emergency category: {e.get('category_name')}"}, 400
            shard_manager.execute_on_shard(shard_id, """
                INSERT INTO shard_{}_emergency_contacts (member_id, contact_person_name, relation, emergency_phone, category_id)
                VALUES (%s, %s, %s, %s, %s)
            """.format(shard_id), (new_member_id, e.get("contact_person_name"), e.get("relation"), e.get("emergency_phone"), cat_id))

        # Insert User_Credentials
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        shard_manager.execute_on_shard(shard_id, """
            INSERT INTO shard_{}_user_credentials (member_id, username, password_hash)
            VALUES (%s, %s, %s)
        """.format(shard_id), (new_member_id, username, hashed.decode()))

        # Insert Member_Role_Assignments (optional)
        if assign_date:
            shard_manager.execute_on_shard(shard_id, """
                INSERT INTO shard_{}_member_role_assignments (member_id, role_id, assigned_date)
                VALUES (%s, %s, %s)
            """.format(shard_id), (new_member_id, role_id, assign_date))
        else:
            shard_manager.execute_on_shard(shard_id, """
                INSERT INTO shard_{}_member_role_assignments (member_id, role_id)
                VALUES (%s, %s)
            """.format(shard_id), (new_member_id, role_id))

        # Audit_Trail is partitioned by actor_id, so log on actor's shard.
        log_action(actor_id, "Members", new_member_id, "INSERT")

        return {"message":"Member created", "member_id": new_member_id, "shard_id": shard_id}

    except Exception as e:
        return {"error": str(e)}, 500


# Get member by id
@members.route("/members/<int:id>", methods=["GET"])
@login_required
def get_member(id):
    actor_id = session["member_id"]
    user_role = session.get("role")

    if not can_edit_others(user_role) and actor_id != id:
        return {"error": "Access denied"}, 403

    try:
        shard_id = shard_manager.get_shard_id(id)

        # Initialize data structure
        data = {
            "member_id": None,
            "full_name": "",
            "designation": "",
            "age": None,
            "gender": "",
            "dept_id": None,
            "join_date": None,
            "dept_code": "",
            "dept_name": "",
            "building_location": "",
            "category_name": "",
            "role_title": "",
            "assign_date": None,
            "contact_type": "",
            "contact_value": "",
            "location_type": "",
            "building_name": "",
            "room_number": "",
            "emergency_name": "",
            "relation": "",
            "emergency_contact": "",
            "username": ""
        }

        # Get member basic info
        result = shard_manager.execute_on_shard(shard_id, """
            SELECT member_id, full_name, designation, age, gender, dept_id, join_date 
            FROM shard_{}_members 
            WHERE member_id = %s AND is_deleted = 0
        """.format(shard_id), (id,), fetch=True)
        member = result[0] if result else None

        if not member:
            return jsonify({"error": "Member not found"}), 404

        data["member_id"] = member[0]
        data["full_name"] = member[1] if member[1] else ""
        data["designation"] = member[2] if member[2] else ""
        data["age"] = member[3] if member[3] else None
        data["gender"] = member[4] if member[4] else ""
        data["dept_id"] = member[5] if member[5] else None
        data["join_date"] = str(member[6]) if member[6] else None

        # Get department info
        if data["dept_id"]:
            result = shard_manager.execute_on_shard(0, """
                SELECT dept_code, dept_name, building_location 
                FROM Departments 
                WHERE dept_id = %s
            """, (data["dept_id"],), fetch=True)
            dept = result[0] if result else None
            if dept:
                data["dept_code"] = dept[0] if dept[0] else ""
                data["dept_name"] = dept[1] if dept[1] else ""
                data["building_location"] = dept[2] if dept[2] else ""

        # Get first contact detail (if exists)
        result = shard_manager.execute_on_shard(shard_id, """
            SELECT contact_type, contact_value, category_id 
            FROM shard_{}_contact_details 
            WHERE member_id = %s 
            LIMIT 1
        """.format(shard_id), (id,), fetch=True)
        contact = result[0] if result else None
        if contact:
            data["contact_type"] = contact[0] if contact[0] else ""
            data["contact_value"] = contact[1] if contact[1] else ""
            
            # Get category name
            if contact[2]:
                result = shard_manager.execute_on_shard(0, "SELECT category_name FROM Data_Categories WHERE category_id = %s", (contact[2],), fetch=True)
                category = result[0] if result else None
                data["category_name"] = category[0] if category and category[0] else ""

        # Also return full multi-entry details for advanced create/update forms.
        result = shard_manager.execute_on_shard(shard_id, """
            SELECT cd.contact_type, cd.contact_value, dc.category_name
            FROM shard_{}_contact_details cd
            JOIN shard_{}_data_categories dc ON cd.category_id = dc.category_id
            WHERE cd.member_id = %s
            ORDER BY cd.contact_id
        """.format(shard_id, shard_id), (id,), fetch=True)
        data["contacts"] = [
            {
                "contact_type": row[0],
                "contact_value": row[1],
                "category_name": row[2],
            }
            for row in result
        ]

        # Get first location (if exists)
        result = shard_manager.execute_on_shard(shard_id, """
            SELECT location_type, building_name, room_number 
            FROM shard_{}_locations 
            WHERE member_id = %s 
            LIMIT 1
        """.format(shard_id), (id,), fetch=True)
        location = result[0] if result else None
        if location:
            data["location_type"] = location[0] if location[0] else ""
            data["building_name"] = location[1] if location[1] else ""
            data["room_number"] = location[2] if location[2] else ""

        result = shard_manager.execute_on_shard(shard_id, """
            SELECT l.location_type, l.building_name, l.room_number, dc.category_name
            FROM shard_{}_locations l
            JOIN shard_{}_data_categories dc ON l.category_id = dc.category_id
            WHERE l.member_id = %s
            ORDER BY l.location_id
        """.format(shard_id, shard_id), (id,), fetch=True)
        data["locations"] = [
            {
                "location_type": row[0],
                "building_name": row[1],
                "room_number": row[2],
                "category_name": row[3],
            }
            for row in result
        ]

        # Get first emergency contact (if exists)
        result = shard_manager.execute_on_shard(shard_id, """
            SELECT contact_person_name, relation, emergency_phone 
            FROM shard_{}_emergency_contacts 
            WHERE member_id = %s 
            LIMIT 1
        """.format(shard_id), (id,), fetch=True)
        emergency = result[0] if result else None
        if emergency:
            data["emergency_name"] = emergency[0] if emergency[0] else ""
            data["relation"] = emergency[1] if emergency[1] else ""
            data["emergency_contact"] = emergency[2] if emergency[2] else ""

        result = shard_manager.execute_on_shard(shard_id, """
            SELECT ec.contact_person_name, ec.relation, ec.emergency_phone, dc.category_name
            FROM shard_{}_emergency_contacts ec
            JOIN shard_{}_data_categories dc ON ec.category_id = dc.category_id
            WHERE ec.member_id = %s
            ORDER BY ec.record_id
        """.format(shard_id, shard_id), (id,), fetch=True)
        data["emergency_contacts"] = [
            {
                "contact_person_name": row[0],
                "relation": row[1],
                "emergency_phone": row[2],
                "category_name": row[3],
            }
            for row in result
        ]

        # Get username (if exists)
        result = shard_manager.execute_on_shard(shard_id, """
            SELECT username 
            FROM shard_{}_user_credentials 
            WHERE member_id = %s 
            LIMIT 1
        """.format(shard_id), (id,), fetch=True)
        user = result[0] if result else None
        if user:
            data["username"] = user[0] if user[0] else ""

        # Get role and assigned date
        result = shard_manager.execute_on_shard(shard_id, """
            SELECT r.role_title, mra.assigned_date 
            FROM shard_{}_member_role_assignments mra
            JOIN shard_{}_roles r ON mra.role_id = r.role_id
            WHERE mra.member_id = %s 
            LIMIT 1
        """.format(shard_id, shard_id), (id,), fetch=True)
        role_assignment = result[0] if result else None
        if role_assignment:
            data["role_title"] = role_assignment[0] if role_assignment[0] else ""
            
            # Format assigned_date properly for date input (in YYYY-MM-DD form)
            if role_assignment[1]:
                assign_dt = role_assignment[1]
                if hasattr(assign_dt, 'date'):
                    # If it's a datetime object
                    data["assign_date"] = str(assign_dt.date())
                else:
                    # If it's already a string
                    data["assign_date"] = str(assign_dt)[:10]
            else:
                data["assign_date"] = None

        return jsonify(data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in get_member: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# Update member (Admin only)
@members.route("/members/<int:id>", methods=["PUT"])
@login_required
def update_member(id):

    actor_id = session["member_id"]
    role = session.get("role")

    if not can_edit_others(role):
        return {"error": "Edit privileges required"},403

    data = request.json
    shard_id = shard_manager.get_shard_id(id)

    dept_id = data.get("dept_id")
    role_title = data.get("role_title")
    full_name = data.get("full_name")
    designation = data.get("designation")
    age = data.get("age")
    gender = data.get("gender")
    join_date = data.get("join_date")
    assign_date = data.get("assign_date")
    username = data.get("username")
    password = data.get("password")

    try:
        # Get member from correct shard
        result = shard_manager.execute_on_shard(shard_id, """
            SELECT member_id, full_name, designation, age, gender, join_date
            FROM shard_{}_members
            WHERE member_id=%s AND is_deleted=0
        """.format(shard_id), (id,), fetch=True)
        existing = result[0] if result else None
        if not existing:
            return {"error": "Member not found or already deleted"}, 404

        existing_member = {
            "full_name": existing[1],
            "designation": existing[2],
            "age": existing[3],
            "gender": existing[4],
            "join_date": existing[5],
        }

        role_id = None

        # Get role_id from reference table on shard 0
        if role_title:
            result = shard_manager.execute_on_shard(0, "SELECT role_id FROM Roles WHERE role_title = %s", (role_title,), fetch=True)
            role_row = result[0] if result else None
            if not role_row:
                return {"error": "Invalid role"}, 400
            role_id = role_row[0]

        # Partial update support: keep existing values for omitted fields.
        next_full_name = full_name if full_name is not None else existing_member["full_name"]
        next_designation = designation if designation is not None else existing_member["designation"]
        next_age = age if age is not None else existing_member["age"]
        next_gender = gender if gender is not None else existing_member["gender"]
        next_join_date = join_date if join_date is not None else existing_member["join_date"]

        # Update Member in correct shard
        shard_manager.execute_on_shard(shard_id, """
            UPDATE shard_{}_members
            SET full_name=%s, designation=%s, age=%s, gender=%s, join_date=%s
            WHERE member_id=%s AND is_deleted=0
        """.format(shard_id), (next_full_name, next_designation, next_age, next_gender, next_join_date, id))

        # Replace detail rows only when the respective section is provided.
        contacts_provided = isinstance(data.get("contacts"), list) or (
            data.get("contact_type") is not None or data.get("contact_value") is not None
        )
        locations_provided = isinstance(data.get("locations"), list) or (
            data.get("location_type") is not None
            or data.get("building_name") is not None
            or data.get("room_number") is not None
        )
        emergency_provided = isinstance(data.get("emergency_contacts"), list) or (
            data.get("emergency_name") is not None
            or data.get("relation") is not None
            or data.get("emergency_contact") is not None
        )

        contacts, locations, emergency_contacts = _normalize_detail_entries(data)

        if contacts_provided:
            if not contacts:
                return {"error": "At least one contact detail is required"}, 400
            shard_manager.execute_on_shard(shard_id, "DELETE FROM shard_{}_contact_details WHERE member_id=%s".format(shard_id), (id,))
            for c in contacts:
                cat_id = _category_id(c.get("category_name"), 0)
                if not cat_id:
                    return {"error": f"Invalid contact category: {c.get('category_name')}"}, 400
                shard_manager.execute_on_shard(shard_id, """
                    INSERT INTO shard_{}_contact_details (member_id, contact_type, contact_value, category_id)
                    VALUES (%s, %s, %s, %s)
                """.format(shard_id), (id, c.get("contact_type"), c.get("contact_value"), cat_id))

        if locations_provided:
            if not locations:
                return {"error": "At least one location detail is required"}, 400
            shard_manager.execute_on_shard(shard_id, "DELETE FROM shard_{}_locations WHERE member_id=%s".format(shard_id), (id,))
            for l in locations:
                cat_id = _category_id(l.get("category_name"), 0)
                if not cat_id:
                    return {"error": f"Invalid location category: {l.get('category_name')}"}, 400
                shard_manager.execute_on_shard(shard_id, """
                    INSERT INTO shard_{}_locations (member_id, location_type, building_name, room_number, category_id)
                    VALUES (%s, %s, %s, %s, %s)
                """.format(shard_id), (id, l.get("location_type"), l.get("building_name"), l.get("room_number"), cat_id))

        if emergency_provided:
            if not emergency_contacts:
                return {"error": "At least one emergency contact is required"}, 400
            shard_manager.execute_on_shard(shard_id, "DELETE FROM shard_{}_emergency_contacts WHERE member_id=%s".format(shard_id), (id,))
            for e in emergency_contacts:
                cat_id = _category_id(e.get("category_name"), 0)
                if not cat_id:
                    return {"error": f"Invalid emergency category: {e.get('category_name')}"}, 400
                shard_manager.execute_on_shard(shard_id, """
                    INSERT INTO shard_{}_emergency_contacts (member_id, contact_person_name, relation, emergency_phone, category_id)
                    VALUES (%s, %s, %s, %s, %s)
                """.format(shard_id), (id, e.get("contact_person_name"), e.get("relation"), e.get("emergency_phone"), cat_id))

        # Update User_Credentials in correct shard
        if username and password:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            shard_manager.execute_on_shard(shard_id, """
                UPDATE shard_{}_user_credentials SET username=%s, password_hash=%s WHERE member_id=%s
            """.format(shard_id), (username, hashed.decode(), id))
        elif password:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            shard_manager.execute_on_shard(shard_id, """
                UPDATE shard_{}_user_credentials SET password_hash=%s WHERE member_id=%s
            """.format(shard_id), (hashed.decode(), id))
        elif username:
            shard_manager.execute_on_shard(shard_id, """
                UPDATE shard_{}_user_credentials SET username=%s WHERE member_id=%s
            """.format(shard_id), (username, id))

        # Update Member_Role_Assignments in correct shard
        if role_id:
            if assign_date:
                shard_manager.execute_on_shard(shard_id, """
                    UPDATE shard_{}_member_role_assignments SET role_id=%s, assigned_date=%s WHERE member_id=%s
                """.format(shard_id), (role_id, assign_date, id))
            else:
                shard_manager.execute_on_shard(shard_id, """
                    UPDATE shard_{}_member_role_assignments SET role_id=%s WHERE member_id=%s
                """.format(shard_id), (role_id, id))

        # log audit trail
        log_action(actor_id, "Members", id, "UPDATE")

        return {"message":"Member updated"}

    except Exception as e:
        return {"error": str(e)}, 500


# Soft delete member (Admin only)
@members.route("/members/<int:id>", methods=["DELETE"])
@login_required
def delete_member(id):

    actor_id = session["member_id"]
    role = session.get("role")

    if not can_edit_others(role):
        return {"error": "Delete privileges required"},403

    shard_id = shard_manager.get_shard_id(id)

    try:
        # Check if member exists on correct shard
        result = shard_manager.execute_on_shard(shard_id, "SELECT member_id FROM shard_{}_members WHERE member_id=%s AND is_deleted=0".format(shard_id), (id,), fetch=True)
        existing = result[0] if result else None
        if not existing:
            return {"error": "Member not found or already deleted"}, 404

        shard_manager.execute_on_shard(shard_id, """
            UPDATE shard_{}_members
            SET is_deleted=1,
                deleted_at=NOW()
            WHERE member_id=%s AND is_deleted=0
        """.format(shard_id), (id,))

        log_action(actor_id, "Members", id, "SOFT_DELETE")
        return {"message": "Member deleted"}
    except Exception as e:
        return {"error": str(e)}, 500


@members.route("/search", methods=["GET"])  # Search all members by name, optionally filter by selected role.
@login_required  
def search_member():

    name = request.args.get("name", "")
    role = request.args.get("role", "").strip()
    log = request.args.get("log", "true").lower() == "true"

    if role:
        query = """
        SELECT 
            m.member_id, 
            m.full_name, 
            m.designation

        FROM shard_{}_members m

        WHERE m.full_name LIKE %s
        AND m.is_deleted = 0
        AND EXISTS (
            SELECT 1 FROM shard_{}_member_role_assignments mra
            JOIN shard_{}_roles r ON mra.role_id = r.role_id
            WHERE mra.member_id = m.member_id
            AND r.role_title = %s
        )
        """

        params = [f"{name}%", role]
        rows = []
        for shard_id in range(3):
            print(f"[DEBUG] GET /search role={role} name={name} shard={shard_id}")
            result = shard_manager.execute_on_shard(shard_id, query.format(shard_id, shard_id, shard_id), params, fetch=True)
            rows.extend(result)
    else:
        query = """
        SELECT 
            m.member_id, 
            m.full_name, 
            m.designation

        FROM shard_{}_members m

        WHERE m.full_name LIKE %s
        AND m.is_deleted = 0
        """

        params = [f"{name}%"]
        rows = []
        for shard_id in range(3):
            print(f"[DEBUG] GET /search name={name} shard={shard_id}")
            result = shard_manager.execute_on_shard(shard_id, query.format(shard_id), params, fetch=True)
            rows.extend(result)

    # Format response
    result = []

    for row in rows:
        result.append({
            "member_id": row[0],
            "full_name": row[1],
            "designation": row[2],
            "frequency": 0  # Simplified
        })

    # Store search log (only when logging is enabled)
    if log:
        shard_id = shard_manager.get_shard_id(session["member_id"])
        shard_manager.execute_on_shard(shard_id, """
            INSERT INTO shard_{}_search_logs (searched_term, searched_by_member_id, results_found_count)
            VALUES (%s, %s, %s)
        """.format(shard_id), (name, session["member_id"], len(result)))

    return jsonify(result)
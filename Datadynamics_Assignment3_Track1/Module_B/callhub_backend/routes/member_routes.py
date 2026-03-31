from flask import Blueprint, jsonify, request, session
from db import mysql
from utils.auth import login_required
from utils.rbac import can_edit_others
from utils.logger import log_action
import bcrypt

members = Blueprint("members", __name__)

# Get editable roles for current user

@members.route("/editable-roles", methods=["GET"])
@login_required
def get_editable_roles():

    role = session.get("role")
    
    cur = mysql.connection.cursor()

    # Check if current user's role has can_edit_others = 1
    cur.execute("""
        SELECT can_edit_others
        FROM Roles
        WHERE role_title = %s
    """, (role,))

    user_role = cur.fetchone()

    # If user doesn't have edit permission, return empty
    if not user_role or user_role[0] == 0:
        return jsonify([])

    # If user has permission, return ALL roles
    cur.execute("""
        SELECT role_id, role_title
        FROM Roles
        ORDER BY role_title
    """)

    rows = cur.fetchall()

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
            cur.execute("""
                SELECT m.member_id, m.full_name, m.designation
                FROM Members m
                JOIN Member_Role_Assignments mra ON m.member_id = mra.member_id
                JOIN Roles r ON mra.role_id = r.role_id
                WHERE r.role_title = %s AND m.is_deleted = 0
            """, (role_filter,))
        else:
            cur.execute("""
                SELECT member_id, full_name, designation
                FROM Members
                WHERE is_deleted = 0
            """)
    else:
        # Regular user: only own
        cur.execute("""
            SELECT member_id, full_name, designation
            FROM Members
            WHERE member_id = %s AND is_deleted = 0
        """, (actor_id,))

    data = cur.fetchall()

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

    # Category
    category_name = data.get("category_name")

    # Role
    role_title = data.get("role_title")

    # Member
    full_name = data.get("full_name")
    designation = data.get("designation")
    age = data.get("age")
    gender = data.get("gender")
    join_date = data.get("join_date")
    assign_date = data.get("assign_date")

    # Contact
    contact_type = data.get("contact_type")
    contact_value = data["contact_value"]

    # Location
    location_type = data.get("location_type")
    building_name = data.get("building_name")
    room_number = data.get("room_number")

    # Emergency
    emergency_name = data.get("emergency_name")
    relation = data.get("relation")
    emergency_contact = data.get("emergency_contact")

    # Credentials
    username = data.get("username")
    password = data.get("password")

    cur = mysql.connection.cursor()

    try:
        # Get category_id
        cur.execute("SELECT category_id FROM Data_Categories WHERE category_name = %s", (category_name,))
        category = cur.fetchone()
        if not category:
            return {"error": "Invalid category"}, 400
        category_id = category[0]

        # Get role_id
        cur.execute("SELECT role_id FROM Roles WHERE role_title = %s", (role_title,))
        role_row = cur.fetchone()
        if not role_row:
            return {"error": "Invalid role"}, 400
        role_id = role_row[0]

        # Insert Member
        cur.execute("""
            INSERT INTO Members (full_name, designation, age, gender, dept_id, join_date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (full_name, designation, age, gender, dept_id, join_date))

        new_member_id = cur.lastrowid

        # Insert Contact_Details
        cur.execute("""
            INSERT INTO Contact_Details (member_id, contact_type, contact_value, category_id)
            VALUES (%s, %s, %s, %s)
        """, (new_member_id, contact_type, contact_value, category_id))

        # Insert Locations
        cur.execute("""
            INSERT INTO Locations (member_id, location_type, building_name, room_number, category_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (new_member_id, location_type, building_name, room_number, category_id))

        # Insert Emergency_Contacts
        cur.execute("""
            INSERT INTO Emergency_Contacts (member_id, contact_person_name, relation, emergency_phone, category_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (new_member_id, emergency_name, relation, emergency_contact, category_id))

        # Insert User_Credentials
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        cur.execute("""
            INSERT INTO User_Credentials (member_id, username, password_hash)
            VALUES (%s, %s, %s)
        """, (new_member_id, username, hashed.decode()))

        # Insert Member_Role_Assignments (optional)
        if assign_date:
            cur.execute("""
                INSERT INTO Member_Role_Assignments (member_id, role_id, assigned_date)
                VALUES (%s, %s, %s)
            """, (new_member_id, role_id, assign_date))
        else:
            cur.execute("""
                INSERT INTO Member_Role_Assignments (member_id, role_id)
                VALUES (%s, %s)
            """, (new_member_id, role_id))

        mysql.connection.commit()

        # log audit trail
        log_action(actor_id, "Members", new_member_id, "INSERT")

        return {"message":"Member created", "member_id": new_member_id}

    except Exception as e:
        mysql.connection.rollback()
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
        cur = mysql.connection.cursor()

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
        cur.execute("""
            SELECT member_id, full_name, designation, age, gender, dept_id, join_date 
            FROM Members 
            WHERE member_id = %s AND is_deleted = 0
        """, (id,))
        member = cur.fetchone()

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
            cur.execute("""
                SELECT dept_code, dept_name, building_location 
                FROM Departments 
                WHERE dept_id = %s
            """, (data["dept_id"],))
            dept = cur.fetchone()
            if dept:
                data["dept_code"] = dept[0] if dept[0] else ""
                data["dept_name"] = dept[1] if dept[1] else ""
                data["building_location"] = dept[2] if dept[2] else ""

        # Get first contact detail (if exists)
        cur.execute("""
            SELECT contact_type, contact_value, category_id 
            FROM Contact_Details 
            WHERE member_id = %s 
            LIMIT 1
        """, (id,))
        contact = cur.fetchone()
        if contact:
            data["contact_type"] = contact[0] if contact[0] else ""
            data["contact_value"] = contact[1] if contact[1] else ""
            
            # Get category name
            if contact[2]:
                cur.execute("SELECT category_name FROM Data_Categories WHERE category_id = %s", (contact[2],))
                category = cur.fetchone()
                data["category_name"] = category[0] if category and category[0] else ""

        # Get first location (if exists)
        cur.execute("""
            SELECT location_type, building_name, room_number 
            FROM Locations 
            WHERE member_id = %s 
            LIMIT 1
        """, (id,))
        location = cur.fetchone()
        if location:
            data["location_type"] = location[0] if location[0] else ""
            data["building_name"] = location[1] if location[1] else ""
            data["room_number"] = location[2] if location[2] else ""

        # Get first emergency contact (if exists)
        cur.execute("""
            SELECT contact_person_name, relation, emergency_phone 
            FROM Emergency_Contacts 
            WHERE member_id = %s 
            LIMIT 1
        """, (id,))
        emergency = cur.fetchone()
        if emergency:
            data["emergency_name"] = emergency[0] if emergency[0] else ""
            data["relation"] = emergency[1] if emergency[1] else ""
            data["emergency_contact"] = emergency[2] if emergency[2] else ""

        # Get username (if exists)
        cur.execute("""
            SELECT username 
            FROM User_Credentials 
            WHERE member_id = %s 
            LIMIT 1
        """, (id,))
        user = cur.fetchone()
        if user:
            data["username"] = user[0] if user[0] else ""

        # Get role and assigned date
        cur.execute("""
            SELECT r.role_title, mra.assigned_date 
            FROM Member_Role_Assignments mra
            JOIN Roles r ON mra.role_id = r.role_id
            WHERE mra.member_id = %s 
            LIMIT 1
        """, (id,))
        role_assignment = cur.fetchone()
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

        cur.close()
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

    # Similar to create, but update
    # For simplicity, update all fields

    dept_id = data.get("dept_id")
    dept_code = data.get("dept_code")
    dept_name = data.get("dept_name")
    building_location = data.get("building_location")
    category_name = data.get("category_name")
    role_title = data.get("role_title")
    full_name = data.get("full_name")
    designation = data.get("designation")
    age = data.get("age")
    gender = data.get("gender")
    join_date = data.get("join_date")
    assign_date = data.get("assign_date")
    contact_type = data.get("contact_type")
    contact_value = data.get("contact_value")
    location_type = data.get("location_type")
    building_name = data.get("building_name")
    room_number = data.get("room_number")
    emergency_name = data.get("emergency_name")
    relation = data.get("relation")
    emergency_contact = data.get("emergency_contact")
    username = data.get("username")
    password = data.get("password")

    cur = mysql.connection.cursor()

    try:
        # Get category_id
        if category_name:
            cur.execute("SELECT category_id FROM Data_Categories WHERE category_name = %s", (category_name,))
            category = cur.fetchone()
            category_id = category[0] if category else None

        # Get role_id
        if role_title:
            cur.execute("SELECT role_id FROM Roles WHERE role_title = %s", (role_title,))
            role_row = cur.fetchone()
            role_id = role_row[0] if role_row else None

        # Update Member
        cur.execute("""
            UPDATE Members SET full_name=%s, designation=%s, age=%s, gender=%s, join_date=%s WHERE member_id=%s
        """, (full_name, designation, age, gender, join_date, id))

        # Update Contact_Details
        if category_id:
            cur.execute("""
                UPDATE Contact_Details SET contact_type=%s, contact_value=%s, category_id=%s WHERE member_id=%s
            """, (contact_type, contact_value, category_id, id))

        # Update Locations
        if category_id:
            cur.execute("""
                UPDATE Locations SET location_type=%s, building_name=%s, room_number=%s, category_id=%s WHERE member_id=%s
            """, (location_type, building_name, room_number, category_id, id))

        # Update Emergency_Contacts
        if category_id:
            cur.execute("""
                UPDATE Emergency_Contacts SET contact_person_name=%s, relation=%s, emergency_phone=%s, category_id=%s WHERE member_id=%s
            """, (emergency_name, relation, emergency_contact, category_id, id))

        # Update User_Credentials
        if password:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            cur.execute("""
                UPDATE User_Credentials SET username=%s, password_hash=%s WHERE member_id=%s
            """, (username, hashed.decode(), id))

        # Update Member_Role_Assignments (also update assigned_date when provided)
        if role_id:
            if assign_date:
                cur.execute("""
                    UPDATE Member_Role_Assignments SET role_id=%s, assigned_date=%s WHERE member_id=%s
                """, (role_id, assign_date, id))
            else:
                cur.execute("""
                    UPDATE Member_Role_Assignments SET role_id=%s WHERE member_id=%s
                """, (role_id, id))

        mysql.connection.commit()

        # log audit trail
        log_action(actor_id, "Members", id, "UPDATE")

        return {"message":"Member updated"}

    except Exception as e:
        mysql.connection.rollback()
        return {"error": str(e)}, 500


# Soft delete member (Admin only)
@members.route("/members/<int:id>", methods=["DELETE"])
@login_required
def delete_member(id):

    actor_id = session["member_id"]
    role = session.get("role")

    if not can_edit_others(role):
        return {"error": "Delete privileges required"},403

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE Members
        SET is_deleted=1,
            deleted_at=NOW()
        WHERE member_id=%s
    """,(id,))

    mysql.connection.commit()

    log_action(actor_id, "Members", id, "SOFT_DELETE")

    return {"message":"Member deleted"}
    #Log search
    if log:
        cur.execute("""
            INSERT INTO Search_Logs (searched_term, searched_by_member_id, results_found_count)
            VALUES (%s, %s, %s)
        """, (name, session["member_id"], len(rows)))

        mysql.connection.commit()  #return jsonify(result)
     

@members.route("/search", methods=["GET"])  # Search all members by name, optionally filter by selected role.
@login_required  
def search_member():

    name = request.args.get("name", "")
    role = request.args.get("role", "").strip()
    log = request.args.get("log", "true").lower() == "true"

    cur = mysql.connection.cursor()

    if role:  # Category permissions are checked in get_member endpoint
        query = f"""
        SELECT 
            m.member_id, 
            m.full_name, 
            m.designation,
            COALESCE(SUM(s.results_found_count), 0) AS frequency   

        FROM Members m

        LEFT JOIN Search_Logs s 
            ON m.full_name LIKE CONCAT(s.searched_term, '%%')

        WHERE m.full_name LIKE %s
        AND m.is_deleted = 0
        AND EXISTS (
            SELECT 1 FROM Member_Role_Assignments mra
            JOIN Roles r ON mra.role_id = r.role_id
            WHERE mra.member_id = m.member_id
            AND r.role_title = %s
        )

        GROUP BY m.member_id
        ORDER BY frequency DESC
        """

        params = [f"{name}%", role]   # Use EXISTS to avoid result duplication when member has multiple roles.
    else:
        query = f"""
        SELECT 
            m.member_id, 
            m.full_name, 
            m.designation,
            COALESCE(COUNT(s.searched_term), 0) AS frequency

        FROM Members m

        LEFT JOIN Search_Logs s 
            ON m.full_name LIKE CONCAT(s.searched_term, '%%')

        WHERE m.full_name LIKE %s
        AND m.is_deleted = 0

        GROUP BY m.member_id
        ORDER BY frequency DESC
        """

        params = [f"{name}%"]

    cur.execute(query, params)

    rows = cur.fetchall()

    # Format response
    result = []

    for row in rows:
        result.append({
            "member_id": row[0],
            "full_name": row[1],
            "designation": row[2],
            "frequency": row[3]
        })

    # Store search log (only when logging is enabled)
    if log:
        cur.execute("""
            INSERT INTO Search_Logs (searched_term, searched_by_member_id, results_found_count)
            VALUES (%s, %s, %s)
        """, (name, session["member_id"], 1))

        mysql.connection.commit()

    cur.close()
    return jsonify(result)
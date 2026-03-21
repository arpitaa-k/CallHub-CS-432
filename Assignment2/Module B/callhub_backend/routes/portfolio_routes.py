from flask import Blueprint, jsonify, session
from db import mysql
from utils.auth import login_required

portfolio = Blueprint("portfolio", __name__)


@portfolio.route("/member/<int:member_id>/portfolio", methods=["GET"])
@login_required
def get_portfolio(member_id):

    actor_id = session["member_id"]

    # Data visibility should be based on caller role permissions only (no owner bypass)
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT DISTINCT rp.category_id
        FROM Member_Role_Assignments mra
        JOIN Role_Permissions rp ON mra.role_id = rp.role_id
        WHERE mra.member_id=%s AND rp.can_view=1
    """, (actor_id,))
    allowed_categories = [row[0] for row in cur.fetchall()]

    is_owner = False

    # member info
    cur.execute("""
        SELECT member_id, full_name, designation, age, gender, dept_id, join_date, is_active
        FROM Members
        WHERE member_id=%s AND is_deleted=0
    """, (member_id,))
    member_row = cur.fetchone()

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
        "is_active": member_row[7]
    }

    # contacts
    cur.execute("""
        SELECT cd.contact_type, cd.contact_value, cd.category_id, dc.category_name
        FROM Contact_Details cd
        JOIN Data_Categories dc ON cd.category_id = dc.category_id
        WHERE cd.member_id=%s
    """, (member_id,))
    contacts_raw = cur.fetchall()

    contacts = []
    for contact_type, contact_value, category_id, category_name in contacts_raw:
        if is_owner or category_id in allowed_categories:
            contacts.append({
                "contact_type": contact_type,
                "contact_value": contact_value,
                "category_id": category_id,
                "category_name": category_name
            })

    # locations
    cur.execute("""
        SELECT l.location_type, l.building_name, l.room_number, l.category_id, dc.category_name
        FROM Locations l
        JOIN Data_Categories dc ON l.category_id = dc.category_id
        WHERE l.member_id=%s
    """, (member_id,))
    locations_raw = cur.fetchall()

    locations = []
    for location_type, building_name, room_number, category_id, category_name in locations_raw:
        if is_owner or category_id in allowed_categories:
            locations.append({
                "location_type": location_type,
                "building_name": building_name,
                "room_number": room_number,
                "category_id": category_id,
                "category_name": category_name
            })

    # emergency contacts
    cur.execute("""
        SELECT ec.contact_person_name, ec.relation, ec.emergency_phone, ec.category_id, dc.category_name
        FROM Emergency_Contacts ec
        JOIN Data_Categories dc ON ec.category_id = dc.category_id
        WHERE ec.member_id=%s
    """, (member_id,))
    emergency_raw = cur.fetchall()

    emergency_contacts = []
    for contact_person_name, relation, emergency_phone, category_id, category_name in emergency_raw:
        if is_owner or category_id in allowed_categories:
            emergency_contacts.append({
                "contact_person_name": contact_person_name,
                "relation": relation,
                "emergency_phone": emergency_phone,
                "category_id": category_id,
                "category_name": category_name
            })

    # department details (optional)
    cur.execute("""
        SELECT dept_code, dept_name, building_location, is_academic
        FROM Departments
        WHERE dept_id=%s
    """, (member["dept_id"],))
    department = cur.fetchone()

    member["department"] = {
        "dept_code": department[0] if department else None,
        "dept_name": department[1] if department else None,
        "building_location": department[2] if department else None,
        "is_academic": department[3] if department else None
    }

    return jsonify({
        "member": member,
        "contacts": contacts,
        "locations": locations,
        "emergency_contacts": emergency_contacts
    })
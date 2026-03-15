from flask import Blueprint, jsonify, session
from db import mysql
from utils.auth import login_required
from utils.rbac import is_admin

portfolio = Blueprint("portfolio", __name__)


@portfolio.route("/member/<int:member_id>/portfolio", methods=["GET"])
@login_required
def get_portfolio(member_id):

    actor_id = session["member_id"]

    # user can only view own profile unless admin
    if actor_id != member_id and not is_admin(actor_id):
        return {"error": "Access denied"},403

    cur = mysql.connection.cursor()

    # member info
    cur.execute("""
        SELECT full_name, designation
        FROM Members
        WHERE member_id=%s AND is_deleted=0
    """,(member_id,))
    member = cur.fetchone()

    # contacts
    cur.execute("""
        SELECT contact_type, contact_value
        FROM Contact_Details
        WHERE member_id=%s
    """,(member_id,))
    contacts = cur.fetchall()

    # locations
    cur.execute("""
        SELECT location_type, building_name, room_number
        FROM Locations
        WHERE member_id=%s
    """,(member_id,))
    locations = cur.fetchall()

    # emergency contacts
    cur.execute("""
        SELECT contact_person_name, relation, emergency_phone
        FROM Emergency_Contacts
        WHERE member_id=%s
    """,(member_id,))
    emergency = cur.fetchall()

    return jsonify({
        "member": member,
        "contacts": contacts,
        "locations": locations,
        "emergency_contacts": emergency
    })
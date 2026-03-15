from flask import Blueprint, jsonify, request, session
from db import mysql
from utils.auth import login_required
from utils.rbac import is_admin
from utils.logger import log_action

members = Blueprint("members", __name__)

# ----------------------------
# Get all members
# ----------------------------
@members.route("/members", methods=["GET"])
@login_required
def get_members():

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT member_id, full_name, designation
        FROM Members
        WHERE is_deleted = 0
    """)

    data = cur.fetchall()

    return jsonify(data)


# ----------------------------
# Create member (Admin only)
# ----------------------------
@members.route("/members", methods=["POST"])
@login_required
def create_member():

    actor_id = session["member_id"]

    if not is_admin(actor_id):
        return {"error": "Admin privileges required"},403

    data = request.json

    name = data["full_name"]
    age = data["age"]
    dept = data["dept_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO Members(full_name, age, dept_id)
        VALUES (%s,%s,%s)
    """,(name, age, dept))

    mysql.connection.commit()

    new_member_id = cur.lastrowid

    # log audit trail
    log_action(actor_id, "Members", new_member_id, "INSERT")

    return {"message":"Member created", "member_id": new_member_id}


# ----------------------------
# Soft delete member (Admin only)
# ----------------------------
@members.route("/members/<int:id>", methods=["DELETE"])
@login_required
def delete_member(id):

    actor_id = session["member_id"]

    if not is_admin(actor_id):
        return {"error": "Admin privileges required"},403

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


# ----------------------------
# Search members
# ----------------------------
@members.route("/search", methods=["GET"])
@login_required
def search_member():

    name = request.args.get("name")

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT member_id, full_name
        FROM Members
        WHERE full_name LIKE %s
        AND is_deleted = 0
    """,(f"%{name}%",))

    results = cur.fetchall()

    return jsonify(results)
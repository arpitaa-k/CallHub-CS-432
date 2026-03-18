from flask import Blueprint, request, jsonify, session
from db import mysql
import bcrypt

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=["POST"])
def login():

    data = request.json
    username = data["username"]
    password = data["password"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT user_id, member_id, password_hash
        FROM User_Credentials
        WHERE username=%s
    """,(username,))

    user = cur.fetchone()

    if not user:
        return jsonify({"error":"Invalid username"}),401

    user_id, member_id, password_hash = user

    if bcrypt.checkpw(password.encode(), password_hash.encode()):

        session["user_id"] = user_id
        session["member_id"] = member_id

        # Fetch role
        cur.execute("""
            SELECT r.role_title
            FROM Member_Role_Assignments mra
            JOIN Roles r ON mra.role_id = r.role_id
            WHERE mra.member_id = %s
            LIMIT 1
        """, (member_id,))

        role = cur.fetchone()
        if role:
            session["role"] = role[0]

        return jsonify({
            "message":"Login successful",
            "member_id":member_id
        })

    return jsonify({"error":"Invalid password"}),401



@auth.route("/check-admin")
def check_admin():

    if "member_id" not in session:
        return {"is_admin": False}

    from utils.rbac import can_edit_others

    role = session.get("role")
    return {"is_admin": can_edit_others(role)}

@auth.route("/register", methods=["POST"])
def register():

    data = request.json

    username = data["username"]
    password = data["password"]
    member_id = data["member_id"]

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO User_Credentials
        (member_id, username, password_hash)
        VALUES (%s,%s,%s)
    """,(member_id, username, hashed.decode()))

    mysql.connection.commit()

    return {"message":"User registered"}


@auth.route("/logout")
def logout():

    session.clear()

    return {"message":"logged out"}
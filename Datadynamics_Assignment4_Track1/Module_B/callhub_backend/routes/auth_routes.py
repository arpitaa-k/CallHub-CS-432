from flask import Blueprint, request, jsonify, session, redirect
from db import mysql
from MySQLdb import IntegrityError
import bcrypt
import uuid
from utils.auth import generate_jwt
from utils.logger import log_login_event

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=["POST"])
def login():

    # Clear any existing session
    session.clear()

    data = request.json or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        log_login_event(
            username=username or "<missing>",
            status="LOGIN_FAIL",
            reason="missing_credentials",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
        return jsonify({"error": "Username and password required"}), 400

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT user_id, member_id, password_hash
        FROM User_Credentials
        WHERE username=%s
    """,(username,))

    user = cur.fetchone()

    if not user:
        log_login_event(
            username=username,
            status="LOGIN_FAIL",
            reason="invalid_username",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
        return jsonify({"error":"Invalid username"}),401

    user_id, member_id, password_hash = user


    if bcrypt.checkpw(password.encode(), password_hash.encode()):
        session.permanent = True
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
        role_title = None
        if role:
            role_title = role[0]
            session["role"] = role_title

        jti = str(uuid.uuid4())
        session["jwt_jti"] = jti
        token = generate_jwt(user_id=user_id, member_id=member_id, role=role_title, jti=jti)

        log_login_event(
            username=username,
            status="LOGIN_SUCCESS",
            member_id=member_id,
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            jti=jti,
        )

        return jsonify({
            "message":"Login successful",
            "member_id":member_id,
            "token": token,
            "token_type": "Bearer",
            "expires_in_sec": 30 * 60,
        })

    log_login_event(
        username=username,
        status="LOGIN_FAIL",
        member_id=member_id,
        reason="invalid_password",
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
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
    member_id = data.get("member_id")

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    cur = mysql.connection.cursor()

    # Check username uniqueness
    cur.execute("SELECT 1 FROM User_Credentials WHERE username=%s", (username,))
    if cur.fetchone():
        return jsonify({"error": "username already registered"}), 409

    # If client provided member_id, ensure it's not already used
    if member_id is not None:
        cur.execute("SELECT 1 FROM User_Credentials WHERE member_id=%s", (member_id,))
        if cur.fetchone():
            return jsonify({"error": "member_id already registered"}), 409

    try:
        cur.execute("""
            INSERT INTO User_Credentials
            (member_id, username, password_hash)
            VALUES (%s,%s,%s)
        """, (member_id, username, hashed.decode()))
        mysql.connection.commit()
    except IntegrityError:
        return jsonify({"error": "duplicate member_id or constraint violation"}), 409

    return jsonify({"message": "User registered"})


@auth.route("/logout")
def logout():
    log_login_event(
        username=session.get("member_id") or "<unknown>",
        status="LOGOUT",
        member_id=session.get("member_id"),
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        jti=session.get("jwt_jti"),
    )
    session.clear()

    return redirect("/")


@auth.route('/keepalive', methods=['POST'])
def keepalive():
    """Endpoint the frontend can POST to when the user is active on the page.

    It refreshes the server-side `last_active` timestamp so the user is not logged out
    while interacting with the page.
    """
    if 'member_id' not in session:
        return jsonify({'error': 'not authenticated'}), 401
    from datetime import datetime
    session['last_active'] = int(datetime.utcnow().timestamp())
    session.modified = True
    return jsonify({'ok': True})
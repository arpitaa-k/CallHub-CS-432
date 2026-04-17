from flask import Blueprint, request, jsonify, session, redirect
import bcrypt
import uuid

from utils.auth import generate_jwt
from utils.logger import log_login_event
from utils.shard_manager import shard_manager


auth = Blueprint("auth", __name__)


def _find_user_by_username(username):
    for shard_id in shard_manager.get_available_shards():
        try:
            rows = shard_manager.execute_on_shard(
                shard_id,
                """
                SELECT user_id, member_id, password_hash
                FROM shard_{}_user_credentials
                WHERE username=%s
                LIMIT 1
                """.format(shard_id),
                (username,),
                fetch=True,
            )
        except Exception as exc:
            print(f"[SHARD] skipping shard {shard_id} during login search: {exc}")
            continue
        if rows:
            user_id, member_id, password_hash = rows[0]
            return shard_id, user_id, member_id, password_hash
    return None


def _role_for_member(member_id):
    shard_id = shard_manager.get_shard_id(member_id)
    rows = shard_manager.execute_on_shard(
        shard_id,
        """
        SELECT r.role_title
        FROM shard_{}_member_role_assignments mra
        JOIN shard_{}_roles r ON mra.role_id = r.role_id
        WHERE mra.member_id = %s
        LIMIT 1
        """.format(shard_id, shard_id),
        (member_id,),
        fetch=True,
    )
    return rows[0][0] if rows else None


@auth.route("/login", methods=["POST"])
def login():
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

    user = _find_user_by_username(username)
    if not user:
        log_login_event(
            username=username,
            status="LOGIN_FAIL",
            reason="invalid_username",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
        return jsonify({"error": "Invalid username"}), 401

    _, user_id, member_id, password_hash = user

    if bcrypt.checkpw(password.encode(), password_hash.encode()):
        session.permanent = True
        session["user_id"] = user_id
        session["member_id"] = member_id

        role_title = _role_for_member(member_id)
        if role_title:
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

        return jsonify(
            {
                "message": "Login successful",
                "member_id": member_id,
                "token": token,
                "token_type": "Bearer",
                "expires_in_sec": 30 * 60,
            }
        )

    log_login_event(
        username=username,
        status="LOGIN_FAIL",
        member_id=member_id,
        reason="invalid_password",
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    return jsonify({"error": "Invalid password"}), 401


@auth.route("/check-admin")
def check_admin():
    if "member_id" not in session:
        return {"is_admin": False}

    from utils.rbac import can_edit_others

    role = session.get("role")
    return {"is_admin": can_edit_others(role)}


@auth.route("/register", methods=["POST"])
def register():
    data = request.json or {}

    username = data.get("username")
    password = data.get("password")
    member_id = data.get("member_id")

    if not username or not password or member_id is None:
        return jsonify({"error": "username, password and member_id are required"}), 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Username must be globally unique across shards.
    existing_user = _find_user_by_username(username)
    if existing_user:
        return jsonify({"error": "username already registered"}), 409

    shard_id = shard_manager.get_shard_id(int(member_id))

    # Ensure member_id does not already have credentials on target shard.
    rows = shard_manager.execute_on_shard(
        shard_id,
        "SELECT 1 FROM shard_{}_user_credentials WHERE member_id=%s LIMIT 1".format(shard_id),
        (member_id,),
        fetch=True,
    )
    if rows:
        return jsonify({"error": "member_id already registered"}), 409

    try:
        shard_manager.execute_on_shard(
            shard_id,
            """
            INSERT INTO shard_{}_user_credentials (member_id, username, password_hash)
            VALUES (%s, %s, %s)
            """.format(shard_id),
            (member_id, username, hashed),
        )
    except Exception:
        return jsonify({"error": "duplicate member_id or constraint violation"}), 409

    return jsonify({"message": "User registered", "shard_id": shard_id})


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

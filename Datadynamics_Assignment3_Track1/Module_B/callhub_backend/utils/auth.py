from functools import wraps
from flask import session, jsonify, request
from datetime import datetime, timedelta, UTC
import os
import jwt


JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = 30


def _jwt_secret():
    return os.getenv("FLASK_SECRET", "supersecret")


def generate_jwt(user_id, member_id, role=None, jti=None):
    now = datetime.now(UTC)
    payload = {
        "sub": str(member_id),
        "user_id": user_id,
        "member_id": member_id,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_jwt(token):
    return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):

        # If bearer token is provided, validate JWT and cross-check with session when available.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = decode_jwt(token)
            except Exception:
                return jsonify({"error": "Invalid or expired token"}), 401

            token_member_id = payload.get("member_id")
            token_jti = payload.get("jti")
            if token_member_id is None:
                return jsonify({"error": "Invalid token payload"}), 401

            # Cross-validation: if session exists, token must match it.
            if "member_id" in session and int(session.get("member_id")) != int(token_member_id):
                return jsonify({"error": "Session-token mismatch"}), 401
            if "jwt_jti" in session and token_jti and str(session.get("jwt_jti")) != str(token_jti):
                return jsonify({"error": "Token session mismatch"}), 401

            return f(*args, **kwargs)

        # session uses `member_id` as the canonical authenticated key
        if "member_id" not in session:
            return jsonify({"error": "Login required"}),401

        return f(*args, **kwargs)

    return wrapper
"""Auth utilities — Heritage Pantry · FCG"""
import secrets
import re
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity


def generate_handover_code() -> str:
    """4-digit numeric verification code. Zero-padded. Avoids 0000."""
    code = secrets.randbelow(10000)
    if code == 0:
        code = 1234
    return f"{code:04d}"


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')


def role_required(*roles):
    """Decorator: require JWT + one of the given roles."""
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if claims.get('role') not in roles:
                return jsonify({'message': 'Insufficient permissions'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def current_user():
    from app.models import User
    user_id = get_jwt_identity()
    return User.query.get(user_id) if user_id else None

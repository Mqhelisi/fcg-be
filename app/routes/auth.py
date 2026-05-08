"""Auth routes — /api/auth"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db, bcrypt
from app.models import User

auth_bp = Blueprint('auth', __name__)


def _token_response(user):
    token = create_access_token(identity=user.id, additional_claims={'role': user.role})
    return jsonify({'token': token, 'user': user.to_dict()}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    for field in ['name', 'email', 'password']:
        if not data.get(field):
            return jsonify({'message': f'{field} is required'}), 400

    if User.query.filter_by(email=data['email'].lower().strip()).first():
        return jsonify({'message': 'An account with that email already exists'}), 409

    user = User(
        role            = 'customer',
        name            = data['name'].strip(),
        email           = data['email'].lower().strip(),
        phone           = (data.get('phone') or '').strip() or None,
        whatsapp_number = (data.get('whatsapp_number') or '').strip() or None,
        default_address = (data.get('default_address') or '').strip() or None,
        password_hash   = bcrypt.generate_password_hash(data['password']).decode('utf-8'),
    )
    db.session.add(user)
    db.session.commit()
    return _token_response(user)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    if not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password are required'}), 400

    user = User.query.filter_by(email=data['email'].lower().strip()).first()
    if not user or not user.password_hash:
        return jsonify({'message': 'Invalid email or password'}), 401
    if not bcrypt.check_password_hash(user.password_hash, data['password']):
        return jsonify({'message': 'Invalid email or password'}), 401
    if not user.is_active:
        return jsonify({'message': 'Account is disabled'}), 403

    return _token_response(user)


@auth_bp.route('/driver-login', methods=['POST'])
def driver_login():
    data = request.get_json(silent=True) or {}
    if not data.get('phone') or not data.get('pin'):
        return jsonify({'message': 'Phone and PIN are required'}), 400

    phone = ''.join(filter(str.isdigit, data['phone']))
    users = User.query.filter_by(role='driver', is_active=True).all()
    user = None
    for u in users:
        if u.phone:
            u_phone = ''.join(filter(str.isdigit, u.phone))
            if u_phone.endswith(phone[-9:]) or phone.endswith(u_phone[-9:]):
                user = u
                break

    if not user or not user.pin_hash:
        return jsonify({'message': 'Invalid phone or PIN'}), 401
    if not bcrypt.check_password_hash(user.pin_hash, data['pin']):
        return jsonify({'message': 'Invalid phone or PIN'}), 401

    return _token_response(user)


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify(user.to_dict()), 200

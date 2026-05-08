"""Customer routes — /api/customer (role=customer)"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import Order, User
from app.utils.auth import role_required
from app.utils.orders import log_status_change

customer_bp = Blueprint('customer', __name__)


@customer_bp.route('/profile', methods=['GET'])
@role_required('customer')
def get_profile():
    user = User.query.get(get_jwt_identity())
    return jsonify(user.to_dict()), 200


@customer_bp.route('/profile', methods=['PUT'])
@role_required('customer')
def update_profile():
    user = User.query.get(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    for f in ('name', 'phone', 'whatsapp_number', 'default_address'):
        if f in data:
            setattr(user, f, (data[f] or '').strip() or None)
    db.session.commit()
    return jsonify(user.to_dict()), 200


@customer_bp.route('/orders', methods=['GET'])
@role_required('customer')
def my_orders():
    user_id = get_jwt_identity()
    orders  = Order.query.filter_by(customer_id=user_id).order_by(Order.created_at.desc()).all()
    return jsonify([o.to_dict(role='customer') for o in orders]), 200


@customer_bp.route('/orders/<reference>/cancel', methods=['POST'])
@role_required('customer')
def cancel_order(reference):
    user_id = get_jwt_identity()
    order = Order.query.filter_by(reference=reference, customer_id=user_id).first_or_404()
    if order.status != 'received':
        return jsonify({'message': 'You can only cancel orders that haven’t been confirmed yet'}), 400
    log_status_change(order, order.status, 'cancelled', actor_id=user_id, note='Cancelled by customer')
    order.status = 'cancelled'
    db.session.commit()
    return jsonify(order.to_dict(role='customer')), 200

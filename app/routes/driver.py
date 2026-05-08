"""Driver routes — /api/driver (role=driver or admin)"""
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, get_jwt
from app import db, limiter
from app.models import Order
from app.utils.auth import role_required
from app.utils.orders import log_status_change

driver_bp = Blueprint('driver', __name__)


def _is_admin():
    return get_jwt().get('role') == 'admin'


@driver_bp.route('/assignments', methods=['GET'])
@role_required('driver', 'admin')
def list_assignments():
    """Orders for me that are packed or out_for_delivery."""
    user_id = get_jwt_identity()
    q = Order.query.filter(Order.status.in_(['packed', 'out_for_delivery']))
    if not _is_admin():
        q = q.filter(Order.driver_id == user_id)
    orders = q.order_by(Order.created_at.asc()).all()
    return jsonify([o.to_dict(role='driver') for o in orders]), 200


@driver_bp.route('/assignments/<id>', methods=['GET'])
@role_required('driver', 'admin')
def assignment_detail(id):
    user_id = get_jwt_identity()
    order = Order.query.get_or_404(id)
    if not _is_admin() and order.driver_id != user_id:
        return jsonify({'message': 'Not your assignment'}), 403
    return jsonify(order.to_dict(role='driver')), 200


@driver_bp.route('/orders/<id>/confirm-pickup', methods=['POST'])
@limiter.limit("10 per minute")
@role_required('driver', 'admin')
def confirm_pickup(id):
    user_id = get_jwt_identity()
    order = Order.query.get_or_404(id)
    if not _is_admin() and order.driver_id != user_id:
        return jsonify({'message': 'Not your assignment'}), 403
    if order.status != 'packed':
        return jsonify({'message': f'Cannot confirm pickup — order is {order.status}'}), 400
    if order.pickup_locked:
        return jsonify({'message': 'Pickup is locked. Contact admin to reset.'}), 423

    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code or not code.isdigit() or len(code) != 4:
        return jsonify({'message': 'Code must be 4 digits'}), 400

    if code != order.pickup_code:
        order.pickup_attempts += 1
        if order.pickup_attempts >= 8:
            order.pickup_locked = True
            log_status_change(order, order.status, order.status, actor_id=user_id,
                              note=f'Pickup locked after {order.pickup_attempts} failed attempts')
        db.session.commit()
        remaining = max(0, 8 - order.pickup_attempts)
        return jsonify({
            'message':            'That code does not match. Try again.',
            'attempts_remaining': remaining,
            'locked':             order.pickup_locked,
        }), 400

    log_status_change(order, 'packed', 'out_for_delivery', actor_id=user_id, note='Driver confirmed pickup')
    order.status       = 'out_for_delivery'
    order.picked_up_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True, 'order': order.to_dict(role='driver')}), 200


@driver_bp.route('/orders/<id>/confirm-delivery', methods=['POST'])
@limiter.limit("10 per minute")
@role_required('driver', 'admin')
def confirm_delivery(id):
    user_id = get_jwt_identity()
    order = Order.query.get_or_404(id)
    if not _is_admin() and order.driver_id != user_id:
        return jsonify({'message': 'Not your assignment'}), 403
    if order.status != 'out_for_delivery':
        return jsonify({'message': f'Cannot confirm delivery — order is {order.status}'}), 400
    if order.delivery_locked:
        return jsonify({'message': 'Delivery is locked. Contact admin to reset.'}), 423

    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code or not code.isdigit() or len(code) != 4:
        return jsonify({'message': 'Code must be 4 digits'}), 400

    if code != order.delivery_code:
        order.delivery_attempts += 1
        if order.delivery_attempts >= 8:
            order.delivery_locked = True
            log_status_change(order, order.status, order.status, actor_id=user_id,
                              note=f'Delivery locked after {order.delivery_attempts} failed attempts')
        db.session.commit()
        remaining = max(0, 8 - order.delivery_attempts)
        return jsonify({
            'message':            'That code does not match. Try again.',
            'attempts_remaining': remaining,
            'locked':             order.delivery_locked,
        }), 400

    log_status_change(order, 'out_for_delivery', 'delivered', actor_id=user_id, note='Driver confirmed delivery')
    order.status       = 'delivered'
    order.delivered_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True, 'order': order.to_dict(role='driver')}), 200

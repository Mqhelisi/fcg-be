"""Packer routes — /api/packer (role=packer or admin)"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, get_jwt
from app import db
from app.models import Order
from app.utils.auth import role_required
from app.utils.orders import log_status_change

packer_bp = Blueprint('packer', __name__)


@packer_bp.route('/orders', methods=['GET'])
@role_required('packer', 'admin')
def list_packing_orders():
    """Orders relevant to packing: confirmed | packing | packed."""
    orders = Order.query.filter(
        Order.status.in_(['confirmed', 'packing', 'packed'])
    ).order_by(Order.created_at.asc()).all()
    return jsonify([o.to_dict(role='packer') for o in orders]), 200


@packer_bp.route('/orders/<id>/start-packing', methods=['PUT'])
@role_required('packer', 'admin')
def start_packing(id):
    user_id = get_jwt_identity()
    order = Order.query.get_or_404(id)
    if order.status != 'confirmed':
        return jsonify({'message': f'Cannot start packing — order is {order.status}'}), 400
    log_status_change(order, 'confirmed', 'packing', actor_id=user_id, note='Packing started')
    order.status = 'packing'
    db.session.commit()
    return jsonify(order.to_dict(role='packer')), 200


@packer_bp.route('/orders/<id>/mark-packed', methods=['PUT'])
@role_required('packer', 'admin')
def mark_packed(id):
    user_id = get_jwt_identity()
    order = Order.query.get_or_404(id)
    if order.status != 'packing':
        return jsonify({'message': f'Cannot mark packed — order is {order.status}'}), 400
    log_status_change(order, 'packing', 'packed', actor_id=user_id, note='Order packed and ready for pickup')
    order.status = 'packed'
    db.session.commit()
    return jsonify(order.to_dict(role='packer')), 200

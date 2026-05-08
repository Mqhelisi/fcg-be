"""Admin routes — /api/admin (role=admin)"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from urllib.parse import quote
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func
from app import db, bcrypt
from app.models import Order, OrderStatusLog, Product, User, Setting, Department
from app.utils.auth import role_required
from app.utils.orders import log_status_change, can_transition, compute_zwg

admin_bp = Blueprint('admin', __name__)


# ── Dashboard ──────────────────────────────────────────────────────────
@admin_bp.route('/dashboard', methods=['GET'])
@role_required('admin')
def dashboard():
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = Order.query.filter(Order.created_at >= today_start).all()

    by_status = {}
    revenue_usd = Decimal('0.00')
    revenue_zwg = Decimal('0.00')
    for o in today_orders:
        by_status[o.status] = by_status.get(o.status, 0) + 1
        if o.status == 'delivered':
            revenue_usd += o.total_usd
            revenue_zwg += o.total_zwg

    pending_count = sum(by_status.get(s, 0) for s in ['received'])
    active_deliveries = Order.query.filter(Order.status.in_(['confirmed', 'packing', 'packed', 'out_for_delivery'])).count()

    recent = Order.query.order_by(Order.created_at.desc()).limit(8).all()

    return jsonify({
        'today': {
            'orders_count':  len(today_orders),
            'revenue_usd':   str(revenue_usd),
            'revenue_zwg':   str(revenue_zwg),
            'by_status':     by_status,
            'pending':       pending_count,
        },
        'active_deliveries': active_deliveries,
        'recent_orders':     [o.to_dict(role='admin') for o in recent],
        'zwg_rate':          Setting.get('zwg_rate'),
    }), 200


# ── Orders list & detail ──────────────────────────────────────────────
@admin_bp.route('/orders', methods=['GET'])
@role_required('admin')
def list_orders():
    q = Order.query
    status = request.args.get('status')
    if status:
        q = q.filter(Order.status == status)

    orders = q.order_by(Order.created_at.desc()).limit(200).all()
    return jsonify([o.to_dict(role='admin') for o in orders]), 200


@admin_bp.route('/orders/<id>', methods=['GET'])
@role_required('admin')
def get_order(id):
    order = Order.query.get_or_404(id)
    return jsonify(order.to_dict(role='admin')), 200


@admin_bp.route('/orders/<id>/status', methods=['PUT'])
@role_required('admin')
def update_status(id):
    user_id = get_jwt_identity()
    order   = Order.query.get_or_404(id)
    data    = request.get_json(silent=True) or {}
    new_status = data.get('status')
    note       = (data.get('note') or '').strip() or None

    if not new_status:
        return jsonify({'message': 'status is required'}), 400

    # Admin can move 'received' → confirmed/rejected/cancelled
    # Admin can also move 'confirmed' → cancelled
    allowed_admin = {'received': ['confirmed', 'rejected', 'cancelled'],
                     'confirmed': ['cancelled']}
    if new_status not in allowed_admin.get(order.status, []):
        return jsonify({'message': f'Cannot transition from {order.status} to {new_status}'}), 400

    log_status_change(order, order.status, new_status, actor_id=user_id, note=note)
    order.status = new_status
    db.session.commit()
    return jsonify(order.to_dict(role='admin')), 200


@admin_bp.route('/orders/<id>/assign-driver', methods=['PUT'])
@role_required('admin')
def assign_driver(id):
    user_id = get_jwt_identity()
    order   = Order.query.get_or_404(id)
    data    = request.get_json(silent=True) or {}
    driver_id = data.get('driver_id')

    if driver_id:
        driver = User.query.filter_by(id=driver_id, role='driver').first()
        if not driver:
            return jsonify({'message': 'Driver not found'}), 404
        order.driver_id = driver_id
        log_status_change(order, order.status, order.status, actor_id=user_id,
                          note=f'Driver assigned: {driver.name}')
    else:
        order.driver_id = None
        log_status_change(order, order.status, order.status, actor_id=user_id,
                          note='Driver unassigned')

    db.session.commit()
    return jsonify(order.to_dict(role='admin')), 200


@admin_bp.route('/orders/<id>/delivery-fee', methods=['PUT'])
@role_required('admin')
def override_delivery_fee(id):
    user_id = get_jwt_identity()
    order = Order.query.get_or_404(id)
    if order.status != 'received':
        return jsonify({'message': 'Delivery fee can only be adjusted before the order is confirmed'}), 400

    data = request.get_json(silent=True) or {}
    try:
        new_fee = Decimal(str(data.get('fee_usd', '')))
    except Exception:
        return jsonify({'message': 'Invalid fee'}), 400
    if new_fee < 0:
        return jsonify({'message': 'Fee cannot be negative'}), 400

    note    = (data.get('note') or '').strip() or None
    old_fee = order.delivery_fee_usd

    order.delivery_fee_usd  = new_fee
    order.delivery_fee_note = note
    order.total_usd = (order.subtotal_usd + new_fee).quantize(Decimal('0.01'))
    order.total_zwg = compute_zwg(order.total_usd, order.zwg_rate_at_order)

    log_status_change(order, order.status, order.status, actor_id=user_id,
                      note=f'Delivery fee adjusted from ${old_fee} to ${new_fee}.' + (f' Note: {note}' if note else ''))
    db.session.commit()
    return jsonify(order.to_dict(role='admin')), 200


@admin_bp.route('/orders/<id>/reset-handover-attempts', methods=['POST'])
@role_required('admin')
def reset_attempts(id):
    user_id = get_jwt_identity()
    order = Order.query.get_or_404(id)
    order.pickup_attempts   = 0
    order.delivery_attempts = 0
    order.pickup_locked     = False
    order.delivery_locked   = False
    log_status_change(order, order.status, order.status, actor_id=user_id, note='Handover attempts reset')
    db.session.commit()
    return jsonify(order.to_dict(role='admin')), 200


@admin_bp.route('/orders/<id>/whatsapp-dispatch-payload', methods=['GET'])
@role_required('admin')
def whatsapp_payload(id):
    order = Order.query.get_or_404(id)
    if not order.driver or not (order.driver.whatsapp_number or order.driver.phone):
        return jsonify({'message': 'No driver assigned or no WhatsApp number'}), 400

    customer = order.customer
    item_count = sum(i.quantity for i in order.items)
    msg = (
        f"Order {order.reference} ready for pickup.\n"
        f"Customer: {customer.name} · {customer.phone or 'no phone'}\n"
        f"Address: {order.delivery_address}\n"
        f"Items: {item_count}\n"
        f"Total: ${order.total_usd} / ZWG {order.total_zwg} — {order.payment_method.upper()}\n"
        f"Pickup at the shop, ask for the pickup code."
    )

    number = order.driver.whatsapp_number or order.driver.phone
    digits = ''.join(filter(str.isdigit, number))
    if digits.startswith('0'):
        digits = '263' + digits[1:]
    url = f"https://wa.me/{digits}?text={quote(msg)}"

    return jsonify({'url': url, 'message': msg}), 200


# ── Drivers ────────────────────────────────────────────────────────────
@admin_bp.route('/drivers', methods=['GET'])
@role_required('admin')
def list_drivers():
    drivers = User.query.filter_by(role='driver').order_by(User.created_at.desc()).all()
    out = []
    for d in drivers:
        active_count = Order.query.filter(
            Order.driver_id == d.id,
            Order.status.in_(['packed', 'out_for_delivery'])
        ).count()
        x = d.to_dict()
        x['active_assignments'] = active_count
        out.append(x)
    return jsonify(out), 200


@admin_bp.route('/drivers', methods=['POST'])
@role_required('admin')
def create_driver():
    data = request.get_json(silent=True) or {}
    if not data.get('name') or not data.get('phone') or not data.get('pin'):
        return jsonify({'message': 'name, phone and pin are required'}), 400

    pin = str(data['pin']).strip()
    if not pin.isdigit() or len(pin) != 4:
        return jsonify({'message': 'PIN must be 4 digits'}), 400

    driver = User(
        role            = 'driver',
        name            = data['name'].strip(),
        phone           = data['phone'].strip(),
        whatsapp_number = (data.get('whatsapp_number') or data['phone']).strip(),
        pin_hash        = bcrypt.generate_password_hash(pin).decode('utf-8'),
    )
    db.session.add(driver)
    db.session.commit()
    return jsonify(driver.to_dict()), 201


@admin_bp.route('/drivers/<id>', methods=['PUT'])
@role_required('admin')
def update_driver(id):
    driver = User.query.filter_by(id=id, role='driver').first_or_404()
    data = request.get_json(silent=True) or {}
    for f in ('name', 'phone', 'whatsapp_number', 'is_active'):
        if f in data:
            setattr(driver, f, data[f])
    db.session.commit()
    return jsonify(driver.to_dict()), 200


@admin_bp.route('/drivers/<id>/reset-pin', methods=['PUT'])
@role_required('admin')
def reset_pin(id):
    driver = User.query.filter_by(id=id, role='driver').first_or_404()
    data = request.get_json(silent=True) or {}
    pin = str(data.get('pin') or '').strip()
    if not pin.isdigit() or len(pin) != 4:
        return jsonify({'message': 'PIN must be 4 digits'}), 400
    driver.pin_hash = bcrypt.generate_password_hash(pin).decode('utf-8')
    db.session.commit()
    return jsonify({'ok': True}), 200


# ── Settings ───────────────────────────────────────────────────────────
@admin_bp.route('/settings', methods=['GET'])
@role_required('admin')
def get_settings():
    keys = ['shop_name', 'shop_phone', 'shop_whatsapp', 'shop_address',
            'delivery_fee_usd', 'minimum_order_usd', 'zwg_rate', 'zwg_rate_updated_at',
            'accepting_orders', 'vat_rate_pct', 'order_ref_prefix']
    return jsonify({k: Setting.get(k) for k in keys}), 200


@admin_bp.route('/settings', methods=['PUT'])
@role_required('admin')
def update_settings():
    user_id = get_jwt_identity()
    data    = request.get_json(silent=True) or {}
    for k, v in data.items():
        if k == 'zwg_rate':
            continue  # use dedicated endpoint
        Setting.set(k, v, actor_id=user_id)
    db.session.commit()
    return jsonify({'ok': True}), 200


@admin_bp.route('/settings/zwg-rate', methods=['PUT'])
@role_required('admin')
def update_zwg_rate():
    user_id = get_jwt_identity()
    data    = request.get_json(silent=True) or {}
    try:
        rate = Decimal(str(data.get('rate', '')))
    except Exception:
        return jsonify({'message': 'Invalid rate'}), 400
    if rate <= 0:
        return jsonify({'message': 'Rate must be positive'}), 400

    Setting.set('zwg_rate', str(rate), actor_id=user_id)
    Setting.set('zwg_rate_updated_at', datetime.now(timezone.utc).isoformat(), actor_id=user_id)
    db.session.commit()
    return jsonify({'rate': str(rate)}), 200


# ── Reports (basic) ────────────────────────────────────────────────────
@admin_bp.route('/reports/revenue', methods=['GET'])
@role_required('admin')
def report_revenue():
    days = int(request.args.get('days', '30'))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    delivered = Order.query.filter(Order.status == 'delivered', Order.created_at >= since).all()

    total_usd = sum((o.total_usd for o in delivered), Decimal('0.00'))
    total_zwg = sum((o.total_zwg for o in delivered), Decimal('0.00'))

    by_currency = {'USD': 0, 'ZWG': 0}
    for o in delivered:
        by_currency[o.currency_paid] = by_currency.get(o.currency_paid, 0) + 1

    return jsonify({
        'days':         days,
        'order_count':  len(delivered),
        'total_usd':    str(total_usd),
        'total_zwg':    str(total_zwg),
        'by_currency':  by_currency,
    }), 200

"""Public routes — /api/public"""
from decimal import Decimal
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Department, Product, Setting, Order, OrderItem, User
from app.utils.auth import generate_handover_code
from app.utils.orders import generate_order_reference, log_status_change, compute_zwg

public_bp = Blueprint('public', __name__)


def _zwg_rate():
    try:
        return Decimal(str(Setting.get('zwg_rate', '30.00')))
    except Exception:
        return Decimal('30.00')


@public_bp.route('/settings/public', methods=['GET'])
def public_settings():
    keys = ['zwg_rate', 'zwg_rate_updated_at', 'accepting_orders',
            'shop_phone', 'shop_whatsapp', 'shop_name', 'minimum_order_usd',
            'delivery_fee_usd', 'vat_rate_pct']
    return jsonify({k: Setting.get(k) for k in keys}), 200


@public_bp.route('/departments', methods=['GET'])
def get_departments():
    depts = Department.query.filter_by(is_active=True).order_by(Department.display_order).all()
    return jsonify([d.to_dict() for d in depts]), 200


@public_bp.route('/catalog', methods=['GET'])
def get_catalog():
    rate  = float(_zwg_rate())
    depts = Department.query.filter_by(is_active=True).order_by(Department.display_order).all()
    result = []
    for dept in depts:
        products = Product.query.filter_by(department_id=dept.id, is_available=True).all()
        d = dept.to_dict()
        d['products'] = [p.to_dict(zwg_rate=rate) for p in products]
        result.append(d)
    return jsonify(result), 200


@public_bp.route('/departments/<slug>/products', methods=['GET'])
def get_dept_products(slug):
    rate = float(_zwg_rate())
    dept = Department.query.filter_by(slug=slug, is_active=True).first_or_404()
    products = Product.query.filter_by(department_id=dept.id, is_available=True).all()
    return jsonify({
        'department': dept.to_dict(),
        'products':   [p.to_dict(zwg_rate=rate) for p in products],
        'zwg_rate':   str(rate),
    }), 200


@public_bp.route('/products/<id>', methods=['GET'])
def get_product(id):
    rate = float(_zwg_rate())
    p = Product.query.get_or_404(id)
    return jsonify(p.to_dict(zwg_rate=rate)), 200


@public_bp.route('/search', methods=['GET'])
def search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'products': [], 'query': q}), 200

    rate = float(_zwg_rate())
    pattern = f'%{q}%'
    products = Product.query.filter(
        Product.is_available == True,
        (Product.name.ilike(pattern)) | (Product.description.ilike(pattern)) | (Product.sku.ilike(pattern))
    ).limit(40).all()

    return jsonify({
        'products': [p.to_dict(zwg_rate=rate) for p in products],
        'query':    q,
        'count':    len(products),
        'zwg_rate': str(rate),
    }), 200


# ── Order placement (auth required) ───────────────────────────────────
@public_bp.route('/orders', methods=['POST'])
@jwt_required()
def place_order():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or user.role != 'customer':
        return jsonify({'message': 'Only customers can place orders'}), 403

    if Setting.get('accepting_orders', 'true') != 'true':
        return jsonify({'message': 'The shop is not accepting orders right now'}), 503

    data = request.get_json(silent=True) or {}
    items_in = data.get('items') or []
    if not items_in:
        return jsonify({'message': 'Your basket is empty'}), 400

    delivery_address = (data.get('delivery_address') or '').strip()
    if not delivery_address:
        return jsonify({'message': 'Delivery address is required'}), 400

    payment_method = data.get('payment_method', 'cash')
    if payment_method not in ('cash', 'ecocash'):
        return jsonify({'message': 'Invalid payment method'}), 400

    currency_paid = data.get('currency_paid', 'USD')
    if currency_paid not in ('USD', 'ZWG'):
        return jsonify({'message': 'Invalid currency'}), 400

    rate              = _zwg_rate()
    delivery_fee_usd  = Decimal(str(Setting.get('delivery_fee_usd', '2.00')))
    minimum_order_usd = Decimal(str(Setting.get('minimum_order_usd', '3.00')))

    # Build order items — snapshot product details at order time
    order_items = []
    subtotal_usd = Decimal('0.00')
    for it in items_in:
        product_id = it.get('product_id')
        qty        = int(it.get('quantity', 0))
        if qty <= 0:
            continue
        product = Product.query.get(product_id)
        if not product or not product.is_available:
            return jsonify({'message': f'Product unavailable: {product_id}'}), 400

        unit_price = Decimal(str(product.price_usd))
        line_total = (unit_price * qty).quantize(Decimal('0.01'))
        subtotal_usd += line_total

        order_items.append(OrderItem(
            product_id     = product.id,
            product_name   = product.name,
            product_sku    = product.sku,
            unit_label     = product.unit_label,
            unit_price_usd = unit_price,
            quantity       = qty,
            line_total_usd = line_total,
        ))

    if not order_items:
        return jsonify({'message': 'Your basket is empty'}), 400

    if subtotal_usd < minimum_order_usd:
        return jsonify({
            'message': f'Minimum order is ${minimum_order_usd}. Your subtotal is ${subtotal_usd}.'
        }), 400

    total_usd = (subtotal_usd + delivery_fee_usd).quantize(Decimal('0.01'))
    total_zwg = compute_zwg(total_usd, rate)

    order = Order(
        reference         = generate_order_reference(),
        customer_id       = user.id,
        status            = 'received',
        delivery_address  = delivery_address,
        payment_method    = payment_method,
        currency_paid     = currency_paid,
        notes             = (data.get('notes') or '').strip() or None,
        zwg_rate_at_order = rate,
        subtotal_usd      = subtotal_usd,
        delivery_fee_usd  = delivery_fee_usd,
        total_usd         = total_usd,
        total_zwg         = total_zwg,
        pickup_code       = generate_handover_code(),
        delivery_code     = generate_handover_code(),
    )
    order.items = order_items

    db.session.add(order)
    db.session.flush()
    log_status_change(order, None, 'received', actor_id=user.id, note='Order placed by customer')
    db.session.commit()

    return jsonify(order.to_dict(role='customer')), 201


# ── Public order tracker (by reference) ───────────────────────────────
@public_bp.route('/orders/<reference>/track', methods=['GET'])
def track_order(reference):
    order = Order.query.filter_by(reference=reference).first_or_404()
    return jsonify(order.to_dict(role='customer')), 200

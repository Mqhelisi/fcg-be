"""Order utilities — Heritage Pantry · FCG"""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import func, extract
from app import db
from app.models import Order, OrderStatusLog, Setting


def generate_order_reference():
    """Generate FCG-2026-0142 style reference based on yearly sequence."""
    prefix = Setting.get('order_ref_prefix', 'FCG')
    year   = datetime.now(timezone.utc).year
    count  = db.session.query(func.count(Order.id)).filter(
        extract('year', Order.created_at) == year
    ).scalar() or 0
    seq = count + 1
    return f"{prefix}-{year}-{seq:04d}"


def log_status_change(order, from_status, to_status, actor_id=None, note=None):
    log = OrderStatusLog(
        order_id    = order.id,
        from_status = from_status,
        to_status   = to_status,
        actor_id    = actor_id,
        note        = note,
    )
    db.session.add(log)
    return log


def compute_zwg(usd_amount, rate):
    return (Decimal(str(usd_amount)) * Decimal(str(rate))).quantize(Decimal('0.01'))


# Allowed status transitions
TRANSITIONS = {
    'received':         ['confirmed', 'rejected', 'cancelled'],
    'confirmed':        ['packing', 'cancelled'],
    'packing':          ['packed'],
    'packed':           ['out_for_delivery'],
    'out_for_delivery': ['delivered'],
}


def can_transition(from_status, to_status):
    return to_status in TRANSITIONS.get(from_status, [])

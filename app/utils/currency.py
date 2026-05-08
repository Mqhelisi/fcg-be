"""
Currency utilities — Heritage Pantry · FCG
"""
from decimal import Decimal, ROUND_HALF_UP


def usd_to_zwg(amount_usd: Decimal, rate: Decimal) -> Decimal:
    """Convert USD amount to ZWG using the given rate."""
    return (amount_usd * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def vat_breakdown(total_inclusive: Decimal, vat_rate_pct: int = 15):
    """
    Split a VAT-inclusive total into (net, vat) components.
    total_inclusive = net * (1 + rate/100)
    """
    rate   = Decimal(vat_rate_pct) / 100
    net    = (total_inclusive / (1 + rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    vat    = (total_inclusive - net).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return net, vat

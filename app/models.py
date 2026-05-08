"""
FCG — All SQLAlchemy models (Phase 1 full schema)
Heritage Pantry · First Class Groceries · Bulawayo, Zimbabwe
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from app import db


# ── Helpers ────────────────────────────────────────────────────────────────
def gen_uuid():
    return str(uuid.uuid4())

def now_utc():
    return datetime.now(timezone.utc)


# ── Users ──────────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'

    id               = db.Column(db.String(36),  primary_key=True, default=gen_uuid)
    role             = db.Column(db.String(20),  nullable=False)  # customer|admin|packer|driver
    name             = db.Column(db.String(200), nullable=False)
    email            = db.Column(db.String(255), unique=True, nullable=True)   # nullable for drivers
    phone            = db.Column(db.String(30),  nullable=True)
    whatsapp_number  = db.Column(db.String(30),  nullable=True)   # may differ from phone
    password_hash    = db.Column(db.String(255), nullable=True)   # null for drivers (PIN auth)
    pin_hash         = db.Column(db.String(255), nullable=True)   # drivers only
    default_address  = db.Column(db.Text,        nullable=True)
    notes            = db.Column(db.Text,        nullable=True)   # admin-facing internal notes
    is_active        = db.Column(db.Boolean,     default=True)
    created_at       = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at       = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    orders           = db.relationship('Order', foreign_keys='Order.customer_id', backref='customer', lazy='dynamic')
    driver_orders    = db.relationship('Order', foreign_keys='Order.driver_id',   backref='driver',   lazy='dynamic')
    uploads          = db.relationship('SpreadsheetUpload', backref='uploader', lazy='dynamic')

    def to_dict(self):
        return {
            'id':              self.id,
            'role':            self.role,
            'name':            self.name,
            'email':           self.email,
            'phone':           self.phone,
            'whatsapp_number': self.whatsapp_number,
            'default_address': self.default_address,
            'is_active':       self.is_active,
            'created_at':      self.created_at.isoformat() if self.created_at else None,
        }


# ── Departments ────────────────────────────────────────────────────────────
class Department(db.Model):
    __tablename__ = 'departments'

    id            = db.Column(db.String(36),  primary_key=True, default=gen_uuid)
    name          = db.Column(db.String(100), nullable=False, unique=True)
    slug          = db.Column(db.String(100), nullable=False, unique=True)   # URL-safe
    display_order = db.Column(db.Integer,     default=0)
    is_active     = db.Column(db.Boolean,     default=True)
    created_at    = db.Column(db.DateTime(timezone=True), default=now_utc)

    products      = db.relationship('Product', backref='department', lazy='dynamic')

    def to_dict(self):
        return {
            'id':            self.id,
            'name':          self.name,
            'slug':          self.slug,
            'display_order': self.display_order,
            'is_active':     self.is_active,
        }


# ── Products ───────────────────────────────────────────────────────────────
class Product(db.Model):
    __tablename__ = 'products'

    id            = db.Column(db.String(36),   primary_key=True, default=gen_uuid)
    sku           = db.Column(db.String(50),   unique=True, nullable=False)
    department_id = db.Column(db.String(36),   db.ForeignKey('departments.id'), nullable=False)
    name          = db.Column(db.String(200),  nullable=False)
    unit_label    = db.Column(db.String(50),   nullable=True)   # "10kg", "2L", "12-pack"
    description   = db.Column(db.Text,         nullable=True)
    price_usd     = db.Column(db.Numeric(10,2), nullable=False)
    image_url     = db.Column(db.String(500),  nullable=True)
    is_available  = db.Column(db.Boolean,      default=True)
    barcode       = db.Column(db.String(50),   nullable=True)   # v2 barcode scanning
    created_at    = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at    = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    order_items   = db.relationship('OrderItem', backref='product', lazy='dynamic')
    movements     = db.relationship('InventoryMovement', backref='product', lazy='dynamic')

    def to_dict(self, zwg_rate=None):
        d = {
            'id':            self.id,
            'sku':           self.sku,
            'department_id': self.department_id,
            'department':    self.department.to_dict() if self.department else None,
            'name':          self.name,
            'unit_label':    self.unit_label,
            'display_name':  f"{self.name} · {self.unit_label}" if self.unit_label else self.name,
            'description':   self.description,
            'price_usd':     str(self.price_usd),
            'image_url':     self.image_url,
            'is_available':  self.is_available,
        }
        if zwg_rate:
            d['price_zwg'] = str(round(float(self.price_usd) * float(zwg_rate), 2))
            d['zwg_rate']  = str(zwg_rate)
        return d


# ── Orders ─────────────────────────────────────────────────────────────────
class Order(db.Model):
    __tablename__ = 'orders'

    id                   = db.Column(db.String(36),   primary_key=True, default=gen_uuid)
    reference            = db.Column(db.String(30),   unique=True, nullable=False)  # FCG-2026-0001
    customer_id          = db.Column(db.String(36),   db.ForeignKey('users.id'), nullable=False)
    driver_id            = db.Column(db.String(36),   db.ForeignKey('users.id'), nullable=True)
    status               = db.Column(db.String(30),   nullable=False, default='received')
    # received | confirmed | packing | packed | out_for_delivery | delivered | rejected | cancelled

    delivery_address     = db.Column(db.Text,         nullable=False)
    payment_method       = db.Column(db.String(20),   nullable=False)  # cash | ecocash
    currency_paid        = db.Column(db.String(3),    nullable=False, default='USD')  # USD | ZWG
    notes                = db.Column(db.Text,         nullable=True)

    # Currency snapshot
    zwg_rate_at_order    = db.Column(db.Numeric(10,4), nullable=False)
    subtotal_usd         = db.Column(db.Numeric(10,2), nullable=False)
    delivery_fee_usd     = db.Column(db.Numeric(10,2), nullable=False, default=Decimal('2.00'))
    delivery_fee_note    = db.Column(db.Text,          nullable=True)
    total_usd            = db.Column(db.Numeric(10,2), nullable=False)
    total_zwg            = db.Column(db.Numeric(12,2), nullable=False)

    # Handover codes
    pickup_code          = db.Column(db.String(4),    nullable=False)
    delivery_code        = db.Column(db.String(4),    nullable=False)
    pickup_attempts      = db.Column(db.Integer,      default=0)
    delivery_attempts    = db.Column(db.Integer,      default=0)
    pickup_locked        = db.Column(db.Boolean,      default=False)
    delivery_locked      = db.Column(db.Boolean,      default=False)

    # Timestamps
    picked_up_at         = db.Column(db.DateTime(timezone=True), nullable=True)
    delivered_at         = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at           = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at           = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    items                = db.relationship('OrderItem',      backref='order', lazy='select', cascade='all, delete-orphan')
    status_log           = db.relationship('OrderStatusLog', backref='order', lazy='select', cascade='all, delete-orphan',
                                           order_by='OrderStatusLog.created_at')

    def to_dict(self, role='customer'):
        d = {
            'id':                self.id,
            'reference':         self.reference,
            'status':            self.status,
            'delivery_address':  self.delivery_address,
            'payment_method':    self.payment_method,
            'currency_paid':     self.currency_paid,
            'notes':             self.notes,
            'zwg_rate_at_order': str(self.zwg_rate_at_order),
            'subtotal_usd':      str(self.subtotal_usd),
            'delivery_fee_usd':  str(self.delivery_fee_usd),
            'delivery_fee_note': self.delivery_fee_note,
            'total_usd':         str(self.total_usd),
            'total_zwg':         str(self.total_zwg),
            'items':             [i.to_dict() for i in self.items],
            'status_log':        [l.to_dict() for l in self.status_log],
            'created_at':        self.created_at.isoformat() if self.created_at else None,
            'updated_at':        self.updated_at.isoformat() if self.updated_at else None,
            'picked_up_at':      self.picked_up_at.isoformat() if self.picked_up_at else None,
            'delivered_at':      self.delivered_at.isoformat() if self.delivered_at else None,
        }
        # Code visibility rules (spec §6.2)
        if role == 'customer':
            d['delivery_code'] = self.delivery_code   # customer always sees delivery code
            # pickup_code deliberately omitted
        elif role == 'packer':
            d['pickup_code']   = self.pickup_code     # packer sees pickup on packed orders
            d['customer']      = self.customer.to_dict() if self.customer else None
            # delivery_code deliberately omitted
        elif role == 'driver':
            # Driver sees customer info but NO codes — they enter codes blind
            d['customer'] = self.customer.to_dict() if self.customer else None
        elif role == 'admin':
            d['pickup_code']       = self.pickup_code
            d['delivery_code']     = self.delivery_code
            d['pickup_attempts']   = self.pickup_attempts
            d['delivery_attempts'] = self.delivery_attempts
            d['pickup_locked']     = self.pickup_locked
            d['delivery_locked']   = self.delivery_locked
            d['driver_id']         = self.driver_id
            d['customer']          = self.customer.to_dict() if self.customer else None
            d['driver']            = self.driver.to_dict()   if self.driver   else None
        return d


# ── Order Items ────────────────────────────────────────────────────────────
class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id            = db.Column(db.String(36),   primary_key=True, default=gen_uuid)
    order_id      = db.Column(db.String(36),   db.ForeignKey('orders.id'), nullable=False)
    product_id    = db.Column(db.String(36),   db.ForeignKey('products.id'), nullable=True)
    product_name  = db.Column(db.String(200),  nullable=False)   # snapshot at time of order
    product_sku   = db.Column(db.String(50),   nullable=True)
    unit_label    = db.Column(db.String(50),   nullable=True)
    unit_price_usd = db.Column(db.Numeric(10,2), nullable=False)
    quantity      = db.Column(db.Integer,      nullable=False)
    line_total_usd = db.Column(db.Numeric(10,2), nullable=False)

    def to_dict(self):
        return {
            'id':             self.id,
            'product_id':     self.product_id,
            'product_name':   self.product_name,
            'product_sku':    self.product_sku,
            'unit_label':     self.unit_label,
            'unit_price_usd': str(self.unit_price_usd),
            'quantity':       self.quantity,
            'line_total_usd': str(self.line_total_usd),
        }


# ── Order Status Log ───────────────────────────────────────────────────────
class OrderStatusLog(db.Model):
    __tablename__ = 'order_status_log'

    id          = db.Column(db.String(36),  primary_key=True, default=gen_uuid)
    order_id    = db.Column(db.String(36),  db.ForeignKey('orders.id'), nullable=False)
    from_status = db.Column(db.String(30),  nullable=True)
    to_status   = db.Column(db.String(30),  nullable=False)
    actor_id    = db.Column(db.String(36),  nullable=True)   # who triggered it
    note        = db.Column(db.Text,        nullable=True)
    created_at  = db.Column(db.DateTime(timezone=True), default=now_utc)

    def to_dict(self):
        return {
            'from_status': self.from_status,
            'to_status':   self.to_status,
            'note':        self.note,
            'created_at':  self.created_at.isoformat() if self.created_at else None,
        }


# ── Settings ───────────────────────────────────────────────────────────────
class Setting(db.Model):
    __tablename__ = 'settings'

    key        = db.Column(db.String(100), primary_key=True)
    value      = db.Column(db.Text,        nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    updated_by = db.Column(db.String(36),  nullable=True)   # user id

    @classmethod
    def get(cls, key, default=None):
        row = cls.query.filter_by(key=key).first()
        return row.value if row else default

    @classmethod
    def set(cls, key, value, actor_id=None):
        row = cls.query.filter_by(key=key).first()
        if row:
            row.value = str(value)
            row.updated_by = actor_id
        else:
            row = cls(key=key, value=str(value), updated_by=actor_id)
            db.session.add(row)


# ── Inventory Movements ────────────────────────────────────────────────────
class InventoryMovement(db.Model):
    __tablename__ = 'inventory_movements'

    id            = db.Column(db.String(36),   primary_key=True, default=gen_uuid)
    product_id    = db.Column(db.String(36),   db.ForeignKey('products.id'), nullable=False)
    movement_type = db.Column(db.String(20),   nullable=False)
    # stock_in | sale | adjustment
    quantity      = db.Column(db.Numeric(10,2), nullable=False)  # negative for sales / down-adjustments
    source        = db.Column(db.String(30),   nullable=False)   # spreadsheet | manual | online_order(v2)
    reference     = db.Column(db.String(100),  nullable=True)
    occurred_at   = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at    = db.Column(db.DateTime(timezone=True), default=now_utc)
    upload_id     = db.Column(db.String(36),   db.ForeignKey('spreadsheet_uploads.id'), nullable=True)
    notes         = db.Column(db.Text,         nullable=True)

    def to_dict(self):
        return {
            'id':            self.id,
            'product_id':    self.product_id,
            'movement_type': self.movement_type,
            'quantity':      str(self.quantity),
            'source':        self.source,
            'reference':     self.reference,
            'occurred_at':   self.occurred_at.isoformat() if self.occurred_at else None,
            'notes':         self.notes,
        }


# ── Spreadsheet Uploads ────────────────────────────────────────────────────
class SpreadsheetUpload(db.Model):
    __tablename__ = 'spreadsheet_uploads'

    id            = db.Column(db.String(36),   primary_key=True, default=gen_uuid)
    upload_type   = db.Column(db.String(20),   nullable=False)   # catalog | sales | stock_in
    filename      = db.Column(db.String(255),  nullable=False)
    uploaded_by   = db.Column(db.String(36),   db.ForeignKey('users.id'), nullable=False)
    row_count     = db.Column(db.Integer,      default=0)
    success_count = db.Column(db.Integer,      default=0)
    error_count   = db.Column(db.Integer,      default=0)
    error_log     = db.Column(db.Text,         nullable=True)   # JSON array [{row, message}]
    status        = db.Column(db.String(20),   default='pending')  # pending | processed | failed
    uploaded_at   = db.Column(db.DateTime(timezone=True), default=now_utc)
    processed_at  = db.Column(db.DateTime(timezone=True), nullable=True)

    movements     = db.relationship('InventoryMovement', backref='upload', lazy='dynamic')

    def to_dict(self):
        return {
            'id':            self.id,
            'upload_type':   self.upload_type,
            'filename':      self.filename,
            'row_count':     self.row_count,
            'success_count': self.success_count,
            'error_count':   self.error_count,
            'status':        self.status,
            'uploaded_at':   self.uploaded_at.isoformat() if self.uploaded_at else None,
            'processed_at':  self.processed_at.isoformat() if self.processed_at else None,
        }

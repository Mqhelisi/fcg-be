"""
FCG Seed Script — Phase 1
Run: python seed.py
Seeds: settings, 1 admin, 1 packer, 2 drivers, 2 demo customers
       7 departments, 30 products (~4-5 per department)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db, bcrypt
from app.models import User, Department, Product, Setting
from app.utils.auth import slugify, generate_handover_code
from datetime import datetime, timezone

app = create_app()

DEPARTMENTS = [
    {'name': 'Foodstuffs',            'slug': 'foodstuffs',             'order': 1},
    {'name': 'Beverages',             'slug': 'beverages',              'order': 2},
    {'name': 'Detergents & Cleaning', 'slug': 'detergents-cleaning',    'order': 3},
    {'name': 'Personal Care',         'slug': 'personal-care',          'order': 4},
    {'name': 'Bakery & Dairy',        'slug': 'bakery-dairy',           'order': 5},
    {'name': 'Snacks & Confectionery','slug': 'snacks-confectionery',   'order': 6},
    {'name': 'Household & Other',     'slug': 'household-other',        'order': 7},
]

PRODUCTS = [
    # ── Foodstuffs ──────────────────────────────────────────────────────
    {'sku':'FCG-FOOD-001','dept':'Foodstuffs',           'name':'Roller Meal',                 'unit':'10kg', 'price':'12.50'},
    {'sku':'FCG-FOOD-002','dept':'Foodstuffs',           'name':'Roller Meal',                 'unit':'5kg',  'price':'6.80'},
    {'sku':'FCG-FOOD-003','dept':'Foodstuffs',           'name':'Cooking Oil (Olivine)',        'unit':'2L',   'price':'4.20'},
    {'sku':'FCG-FOOD-004','dept':'Foodstuffs',           'name':'Cooking Oil (Olivine)',        'unit':'750ml','price':'2.10'},
    {'sku':'FCG-FOOD-005','dept':'Foodstuffs',           'name':'White Sugar',                 'unit':'2kg',  'price':'2.40'},

    # ── Beverages ────────────────────────────────────────────────────────
    {'sku':'FCG-BEV-001', 'dept':'Beverages',            'name':'Mazoe Orange Crush',          'unit':'2L',   'price':'3.50'},
    {'sku':'FCG-BEV-002', 'dept':'Beverages',            'name':'Nespray Whole Milk Powder',   'unit':'500g', 'price':'6.80'},
    {'sku':'FCG-BEV-003', 'dept':'Beverages',            'name':'Tanganda Black Tea',          'unit':'100 bags','price':'2.90'},
    {'sku':'FCG-BEV-004', 'dept':'Beverages',            'name':'Ricoffy Coffee',              'unit':'250g', 'price':'4.50'},
    {'sku':'FCG-BEV-005', 'dept':'Beverages',            'name':'Coca-Cola',                   'unit':'2L',   'price':'2.20'},

    # ── Detergents & Cleaning ────────────────────────────────────────────
    {'sku':'FCG-DET-001', 'dept':'Detergents & Cleaning','name':'Surf Washing Powder',         'unit':'2kg',  'price':'5.80'},
    {'sku':'FCG-DET-002', 'dept':'Detergents & Cleaning','name':'Sunlight Bar Soap',           'unit':'175g × 4','price':'2.40'},
    {'sku':'FCG-DET-003', 'dept':'Detergents & Cleaning','name':'Jik Bleach',                 'unit':'750ml','price':'2.10'},
    {'sku':'FCG-DET-004', 'dept':'Detergents & Cleaning','name':'Morning Fresh Dishwash',     'unit':'400ml','price':'1.80'},
    {'sku':'FCG-DET-005', 'dept':'Detergents & Cleaning','name':'Handy Andy Cream Cleaner',   'unit':'750ml','price':'2.50'},

    # ── Personal Care ────────────────────────────────────────────────────
    {'sku':'FCG-CARE-001','dept':'Personal Care',        'name':'Geisha Bathing Soap',        'unit':'120g',  'price':'0.80'},
    {'sku':'FCG-CARE-002','dept':'Personal Care',        'name':'Vaseline Body Lotion',       'unit':'400ml', 'price':'3.20'},
    {'sku':'FCG-CARE-003','dept':'Personal Care',        'name':'Close-Up Toothpaste',        'unit':'100ml', 'price':'1.50'},
    {'sku':'FCG-CARE-004','dept':'Personal Care',        'name':'Shield Deodorant',           'unit':'150ml', 'price':'2.80'},

    # ── Bakery & Dairy ───────────────────────────────────────────────────
    {'sku':'FCG-BAKE-001','dept':'Bakery & Dairy',       'name':'White Bread',                'unit':'Loaf',  'price':'1.20'},
    {'sku':'FCG-BAKE-002','dept':'Bakery & Dairy',       'name':'Brown Bread',                'unit':'Loaf',  'price':'1.30'},
    {'sku':'FCG-BAKE-003','dept':'Bakery & Dairy',       'name':'Full Cream Milk (Dairibord)','unit':'1L',    'price':'1.90'},
    {'sku':'FCG-BAKE-004','dept':'Bakery & Dairy',       'name':'Large Eggs',                 'unit':'30-tray','price':'5.50'},
    {'sku':'FCG-BAKE-005','dept':'Bakery & Dairy',       'name':'Dairibord Butter',           'unit':'250g',  'price':'2.80'},

    # ── Snacks & Confectionery ───────────────────────────────────────────
    {'sku':'FCG-SNCK-001','dept':'Snacks & Confectionery','name':'Ufd Biscuits (Cream)',      'unit':'200g',  'price':'1.10'},
    {'sku':'FCG-SNCK-002','dept':'Snacks & Confectionery','name':'Chompkins Crisps',          'unit':'125g',  'price':'1.40'},
    {'sku':'FCG-SNCK-003','dept':'Snacks & Confectionery','name':'Lunch Bar Chocolate',       'unit':'45g',   'price':'0.90'},

    # ── Household & Other ───────────────────────────────────────────────
    {'sku':'FCG-HH-001',  'dept':'Household & Other',    'name':'Candles (Paraffin)',         'unit':'Box × 6','price':'2.00'},
    {'sku':'FCG-HH-002',  'dept':'Household & Other',    'name':'Energizer AA Batteries',    'unit':'4-pack', 'price':'3.50'},
    {'sku':'FCG-HH-003',  'dept':'Household & Other',    'name':'Glad Wrap Cling Film',      'unit':'30m',    'price':'2.20'},
]

SETTINGS = {
    'shop_name':          'First Class Groceries',
    'shop_phone':         '',
    'shop_whatsapp':      '',
    'shop_address':       'Bulawayo, Zimbabwe',
    'delivery_fee_usd':   '2.00',
    'minimum_order_usd':  '3.00',
    'zwg_rate':           '30.00',
    'zwg_rate_updated_at': datetime.now(timezone.utc).isoformat(),
    'accepting_orders':   'true',
    'vat_rate_pct':       '15',
    'order_ref_prefix':   'FCG',
}


def seed():
    with app.app_context():
        print("🌱 FCG Seed — Heritage Pantry Phase 1")
        print("=" * 50)

        # ── Settings ──────────────────────────────────────────────────
        print("  • Seeding settings…")
        for k, v in SETTINGS.items():
            existing = Setting.query.filter_by(key=k).first()
            if not existing:
                db.session.add(Setting(key=k, value=v))
        db.session.commit()
        print(f"    ✓ {len(SETTINGS)} settings keys")

        # ── Users ─────────────────────────────────────────────────────
        print("  • Seeding demo accounts…")
        accounts = [
            {
                'role': 'admin', 'name': 'FCG Admin',
                'email': 'admin@fcg.co.zw', 'password': 'admin1234',
            },
            {
                'role': 'packer', 'name': 'Packing Station',
                'email': 'packer@fcg.co.zw', 'password': 'packer1234',
            },
            {
                'role': 'driver', 'name': 'Themba Moyo',
                'phone': '0771000001', 'pin': '1234',
                'whatsapp_number': '0771000001',
            },
            {
                'role': 'driver', 'name': 'Sibusiso Dube',
                'phone': '0772000002', 'pin': '5678',
                'whatsapp_number': '0772000002',
            },
            {
                'role': 'customer', 'name': 'Sipho Ndlovu',
                'email': 'sipho@demo.com', 'password': 'demo1234',
                'phone': '0773111222', 'default_address': '14 Selous Ave, Hillside, Bulawayo',
            },
            {
                'role': 'customer', 'name': 'Nomsa Dlamini',
                'email': 'nomsa@demo.com', 'password': 'demo1234',
                'phone': '0774333444', 'default_address': '5 Robert Mugabe Way, Suburbs, Bulawayo',
            },
        ]

        created = 0
        for acc in accounts:
            email = acc.get('email')
            phone = acc.get('phone')
            exists = False
            if email:
                exists = bool(User.query.filter_by(email=email).first())
            elif phone:
                exists = bool(User.query.filter_by(phone=phone, role=acc['role']).first())

            if exists:
                print(f"    – {acc['name']} already exists, skipping")
                continue

            user = User(
                role            = acc['role'],
                name            = acc['name'],
                email           = email,
                phone           = phone,
                whatsapp_number = acc.get('whatsapp_number'),
                default_address = acc.get('default_address'),
            )
            if acc.get('password'):
                user.password_hash = bcrypt.generate_password_hash(acc['password']).decode('utf-8')
            if acc.get('pin'):
                user.pin_hash = bcrypt.generate_password_hash(acc['pin']).decode('utf-8')

            db.session.add(user)
            created += 1

        db.session.commit()
        print(f"    ✓ {created} accounts created")

        # ── Departments ───────────────────────────────────────────────
        print("  • Seeding departments…")
        dept_map = {}
        for d in DEPARTMENTS:
            existing = Department.query.filter_by(slug=d['slug']).first()
            if not existing:
                dept = Department(
                    name=d['name'], slug=d['slug'], display_order=d['order'], is_active=True
                )
                db.session.add(dept)
                db.session.flush()
                dept_map[d['name']] = dept.id
                print(f"    + {d['name']}")
            else:
                dept_map[d['name']] = existing.id
        db.session.commit()

        # Refresh map from DB
        for dept in Department.query.all():
            dept_map[dept.name] = dept.id

        print(f"    ✓ {len(DEPARTMENTS)} departments")

        # ── Products ──────────────────────────────────────────────────
        print("  • Seeding products…")
        created_p = 0
        for p in PRODUCTS:
            if Product.query.filter_by(sku=p['sku']).first():
                continue
            dept_id = dept_map.get(p['dept'])
            if not dept_id:
                print(f"    ⚠ dept not found for {p['sku']}, skipping")
                continue
            product = Product(
                sku           = p['sku'],
                department_id = dept_id,
                name          = p['name'],
                unit_label    = p.get('unit'),
                price_usd     = p['price'],
                is_available  = True,
            )
            db.session.add(product)
            created_p += 1

        db.session.commit()
        print(f"    ✓ {created_p} products created")

        print()
        print("=" * 50)
        print("✅ Seed complete!")
        print()
        print("Demo credentials:")
        print("  Admin  : admin@fcg.co.zw        / admin1234")
        print("  Packer : packer@fcg.co.zw       / packer1234")
        print("  Driver : 0771000001  PIN: 1234")
        print("  Driver : 0772000002  PIN: 5678")
        print("  Customer: sipho@demo.com         / demo1234")
        print("  Customer: nomsa@demo.com         / demo1234")
        print()
        print("  ZWG rate : $1 USD = ZWG 30.00")
        print("  Min order: $3.00 USD")
        print("  Delivery : $2.00 USD flat")


if __name__ == '__main__':
    seed()

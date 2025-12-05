from email.policy import default

from . import db
from flask_sqlalchemy import SQLAlchemy
import datetime
from datetime import datetime,timezone


class User(db.Model):
    __tablename__ = 'toc_users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(45), nullable=True)
    password = db.Column(db.String(45), nullable=True)
    creation_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_date = db.Column(db.DateTime, nullable=True)
    first_name = db.Column(db.String(45), nullable=True)
    last_name = db.Column(db.String(45), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    shop = db.Column(db.String(45), nullable=True)
    role = db.Column(db.String(45), nullable=False, default='AGENT')
    company = db.Column(db.String(45), nullable=True)
    job = db.Column(db.String(45), nullable=True)
    phone = db.Column(db.String(45), nullable=True)
    about = db.Column(db.String(200), nullable=True)
    profile_image = db.Column(db.String(100), nullable=True)
    ip = db.Column(db.String(45), nullable=True)
    city = db.Column(db.String(45), nullable=True)
    county = db.Column(db.String(45), nullable=True)
    loc = db.Column(db.String(45), nullable=True)
    postal = db.Column(db.String(45), nullable=True)
    region = db.Column(db.String(45), nullable=True)
    timezone = db.Column(db.String(45), nullable=True)
    country_code = db.Column(db.String(45), nullable=True)
    country_calling_code = db.Column(db.String(45), nullable=True)

class TOC_SHOPS(db.Model):
    __tablename__ = 'toc_shops'

    blName = db.Column(db.String(255), primary_key=True)
    blId = db.Column(db.BigInteger)
    country = db.Column(db.String(2))
    timezone = db.Column(db.String(50))
    store = db.Column(db.String(10))
    customer = db.Column(db.String(10))
    mt_shop_name = db.Column(db.String(50))
    actv_ind = db.Column(db.Integer)
    tier =  db.Column(db.String(2))
    longitude = db.Column(db.String(20))
    latitude = db.Column(db.String(20))
    address = db.Column(db.String(100))
    phone = db.Column(db.String(15))
    zip = db.Column(db.String(5))
    city  = db.Column(db.String(20))
    state = db.Column(db.String(20))

class TocMessages(db.Model):
    __tablename__ = 'toc_messages'

    msg_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    msg_date = db.Column(db.DateTime)
    msg_from = db.Column(db.String(45), nullable=True)
    msg_to = db.Column(db.String(45), nullable=True)
    msg_subject = db.Column(db.String(100), nullable=True)
    msg_body = db.Column(db.String(400), nullable=True)
    msg_status = db.Column(db.String(45), nullable=True)

    def __init__(self, msg_date, msg_from, msg_to, msg_subject, msg_body, msg_status):
        self.msg_date = msg_date
        self.msg_from = msg_from
        self.msg_to = msg_to
        self.msg_subject = msg_subject
        self.msg_body = msg_body
        self.msg_status = msg_status

    def __repr__(self):
        return f'<TocMessages {self.msg_id}>'

class TocNotification(db.Model):
    __tablename__ = 'toc_notifications'

    not_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    not_date = db.Column(db.DateTime)
    not_address = db.Column(db.String(45), nullable=True)
    not_subject = db.Column(db.String(100), nullable=True)
    not_body = db.Column(db.String(300), nullable=True)
    not_status = db.Column(db.String(45), nullable=True)


class TocStockOrder(db.Model):
    __tablename__ = 'toc_stock_order'

    shop_id = db.Column(db.String(45), primary_key=True, nullable=False)
    order_open_date = db.Column(db.DateTime, primary_key=True, nullable=False)
    sku = db.Column(db.String(45), primary_key=True, nullable=False)
    order_id = db.Column(db.String(45))
    user = db.Column(db.String(45))
    item_name = db.Column(db.String(100))
    order_qty = db.Column(db.Float)
    comments = db.Column(db.String(100))
    order_status = db.Column(db.String(45))
    order_status_date = db.Column(db.DateTime)


class TocReplenishOrder(db.Model):
    __tablename__ = 'toc_replenish_order'

    shop_id = db.Column(db.String(45), primary_key=True, nullable=False)
    order_id = db.Column(db.String(45), primary_key=True, nullable=False)
    sku = db.Column(db.String(45), primary_key=True, nullable=False)
    order_open_date = db.Column(db.DateTime, nullable=True)
    user = db.Column(db.String(45), nullable=True)
    item_name = db.Column(db.String(100), nullable=True)
    replenish_qty = db.Column(db.Float, nullable=True)
    comments = db.Column(db.String(100), nullable=True)
    received_qty = db.Column(db.Float, nullable=True)
    rejected_qty = db.Column(db.Float, nullable=True)
    variance = db.Column(db.Float, nullable=True)
    received_date = db.Column(db.DateTime, nullable=True)
    received_by = db.Column(db.String(45), nullable=True)
    received_comment = db.Column(db.String(100), nullable=True)
    pastel_ind = db.Column(db.Integer, default=0)
    save_count = db.Column(db.Float, default=0)
    pastel_date = db.Column(db.DateTime, nullable=True)


class TocProduct(db.Model):
    __tablename__ = 'toc_product'

    # ----- CORE TOC FIELDS -----
    item_sku = db.Column(db.String(45), primary_key=True, nullable=False)
    item_type = db.Column(db.String(4), nullable=True)
    item_name = db.Column(db.String(200), nullable=True)
    stat_group = db.Column(db.String(45), nullable=True)
    acct_group = db.Column(db.String(45), nullable=True)

    retail_price = db.Column(db.Float, nullable=True)
    cost_price = db.Column(db.Float, nullable=True)
    wh_price = db.Column(db.Float, nullable=True)
    cann_cost_price = db.Column(db.Float, nullable=True)

    product_url = db.Column(db.String(200), nullable=True)
    image_url = db.Column(db.String(200), nullable=True)
    stock_ord_ind = db.Column(db.Integer, nullable=True)

    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    update_date = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    supplier_id = db.Column(db.Integer, nullable=True)

    # ----- EXTRA FIELDS REQUIRED FOR PURCHASE ORDERS & GRV -----
    barcode = db.Column(db.String(50), nullable=True)
    brand_name = db.Column(db.String(100), nullable=True)
    uom = db.Column(db.String(20), nullable=True)
    size = db.Column(db.String(50), nullable=True)

    is_expiry_tracked = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)

    supplier_product_code = db.Column(db.String(50), nullable=True)

    unit_price = db.Column(db.Numeric(10, 2), nullable=True)
    lead_time_days = db.Column(db.Integer, nullable=True)

    vat_exempt_ind = db.Column(db.Boolean, default=False)

    # ----- NEW BOM FIELDS -----
    is_manufacturable = db.Column(db.Boolean, default=False)  # Final product
    is_component = db.Column(db.Boolean, default=False)       # Raw material/component



class TOCReplenishCtrl(db.Model):
    __tablename__ = 'toc_replenish_ctrl'

    order_id = db.Column(db.String(45), primary_key=True)
    shop_id = db.Column(db.String(45), nullable=True)
    order_open_date = db.Column(db.DateTime, nullable=True)
    user = db.Column(db.String(45), nullable=True)
    order_status = db.Column(db.String(45), nullable=True)
    order_status_date = db.Column(db.DateTime, nullable=True)
    tracking_code = db.Column(db.String(45), nullable=True)
    sold_qty = db.Column(db.Integer, nullable=True)
    replenish_qty = db.Column(db.Integer, nullable=True)
    sent_from = db.Column(db.String(45), nullable=True)

class TocStock(db.Model):
    __tablename__ = 'toc_stock'

    shop_id = db.Column(db.String(20), primary_key=True, nullable=False)
    sku = db.Column(db.String(45), primary_key=True, nullable=False)
    stock_qty_date = db.Column(db.DateTime,  nullable=False)
    product_name = db.Column(db.String(100), nullable=True)
    stock_count = db.Column(db.Float, nullable=True)
    count_by = db.Column(db.String(45), nullable=True)
    last_stock_qty = db.Column(db.Float, nullable=True)
    calc_stock_qty = db.Column(db.Float, nullable=True)
    variance = db.Column(db.Float, nullable=False, default=0)
    variance_rsn = db.Column(db.String(45), nullable=True)
    stock_transfer = db.Column(db.Float, nullable=True, default=0)
    shop_name = db.Column(db.String(45), nullable=True)
    rejects_qty = db.Column(db.Float, nullable=True)
    rcv_damaged = db.Column(db.Float, nullable=True)
    final_stock_qty = db.Column(db.Float, nullable=True)
    replenish_id = db.Column(db.String(45), nullable=True)
    comments = db.Column(db.String(150), nullable=True)
    pastel_ind = db.Column(db.Integer, default=0, nullable=True)
    pastel_count = db.Column(db.Float, nullable=True)
    pastel_date =  db.Column(db.DateTime, nullable=True)
    audit_count = db.Column(db.Float, nullable=True)

class TocStockAudit(db.Model):
    __tablename__ = 'toc_stock_audit'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    shop_id = db.Column(db.String(20), nullable=False)
    sku = db.Column(db.String(45), nullable=False)
    product_name = db.Column(db.String(100))
    stock_count = db.Column(db.Float)
    shop_name = db.Column(db.String(45))
    comments = db.Column(db.String(150))

class TOCStockVariance(db.Model):
    __tablename__ = 'toc_stock_variance'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    creation_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))  # Use datetime.utcnow for default
    shop_id = db.Column(db.String(20), nullable=True)
    sku = db.Column(db.String(45), nullable=True)
    stock_qty_date = db.Column(db.DateTime, nullable=True)
    product_name = db.Column(db.String(100), nullable=True)
    stock_count = db.Column(db.Float, nullable=True)
    count_by = db.Column(db.String(45), nullable=True)
    last_stock_qty = db.Column(db.Float, nullable=True)
    calc_stock_qty = db.Column(db.Float, nullable=True)
    variance = db.Column(db.Float, default=0)  # Ensure default is numeric
    # variance_rsn = db.Column(db.String(45), nullable=True)
    stock_recount = db.Column(db.Float, nullable=True)
    shop_name = db.Column(db.String(45), nullable=True)
    rejects_qty = db.Column(db.Float, nullable=True)
    final_stock_qty = db.Column(db.Float, nullable=True)
    replenish_id = db.Column(db.String(45), nullable=True)
    comments = db.Column(db.String(150), nullable=True)


class TocRole(db.Model):
    __tablename__ = 'toc_roles'

    role = db.Column(db.String(20), primary_key=True, nullable=False)
    exclusions = db.Column(db.String(200), default=None)


class TOCUserActivity(db.Model):
    __tablename__ = 'toc_user_activity'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    actv_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
    user = db.Column(db.String(45), nullable=True)
    shop = db.Column(db.String(45), nullable=True)
    activity = db.Column(db.String(100), nullable=True)


class TocSalesLog(db.Model):
    __tablename__ = 'toc_sales_log'

    run_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    search_from = db.Column(db.String(40), nullable=True)
    num_of_sales = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(2), nullable=True)
    comment = db.Column(db.String(200), nullable=True)

class TOCWeeks(db.Model):
    __tablename__ = 'toc_weeks'

    week = db.Column(db.String(10), primary_key=True)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)

class TOCCasuals(db.Model):
    __tablename__ = 'toc_casuals'

    shop_id = db.Column(db.String(45), primary_key=True)
    week = db.Column(db.String(45), primary_key=True)
    date = db.Column(db.Date, primary_key=True)
    casuals = db.Column(db.String(200), nullable=True)
    confirmed_by = db.Column(db.String(45), nullable=True)
    confirmation_date = db.Column(db.DateTime, nullable=True)

class TOCCasualsCtrl(db.Model):
    __tablename__ = 'toc_casuals_ctrl'

    shop_id = db.Column(db.String(45), primary_key=True)
    week = db.Column(db.String(45), primary_key=True)
    status = db.Column(db.String(45), nullable=True)
    status_date = db.Column(db.DateTime,  nullable=True)
    confirmed_by = db.Column(db.String(45), nullable=True)

class TOCOpenAI(db.Model):
    __tablename__ = 'toc_openai'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    shop_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_query = db.Column(db.Text, nullable=False)

class TocCountCtrl(db.Model):
    __tablename__ = 'toc_count_ctrl'

    count_id = db.Column(db.String(45), primary_key=True)
    name = db.Column(db.String(45))
    username = db.Column(db.String(45))
    shop_id = db.Column(db.String(45))
    shop_name = db.Column(db.String(45))
    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    status = db.Column(db.Enum('Draft', 'Completed'), default='Draft')

class TocCount(db.Model):
    __tablename__ = 'toc_count'

    count_id = db.Column(db.String(45), db.ForeignKey('toc_count_ctrl.count_id'), primary_key=True)
    sku = db.Column(db.String(45), primary_key=True)
    stock_count = db.Column(db.Integer, default=0)
    damaged_stock = db.Column(db.Integer, default=0)
    comments = db.Column(db.Text)
    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    last_updated = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    count_ctrl = db.relationship('TocCountCtrl', backref=db.backref('counts', lazy=True))


class TocDamaged(db.Model):
    __tablename__ = 'toc_damaged'

    shop_id = db.Column(db.String(45), primary_key=True, nullable=False)
    order_id = db.Column(db.String(45), primary_key=True, nullable=False)
    sku = db.Column(db.String(45), primary_key=True, nullable=False)
    order_open_date = db.Column(db.DateTime, nullable=True)
    user = db.Column(db.String(45), nullable=True)
    item_name = db.Column(db.String(100), nullable=True)
    rejected_qty = db.Column(db.Float, nullable=True)  # Sent Damaged
    rcv_damaged = db.Column(db.Float, nullable=True)   # Received Damaged
    variance = db.Column(db.Float, nullable=True)      # Difference between sent and received damaged

class TocShipday(db.Model):
    __tablename__ = 'toc_shipday'

    wc_orderid = db.Column(db.String(20), primary_key=True)
    creation_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    wc_name = db.Column(db.String(100))
    wc_email = db.Column(db.String(100))
    wc_phone = db.Column(db.String(20))
    shop_name = db.Column(db.String(100))
    status = db.Column(db.String(20))
    update_date = db.Column(db.DateTime)
    ls_order_id = db.Column(db.String(20))
    shipday_id = db.Column(db.String(50))
    total_amt = db.Column(db.Float)
    shipday_distance_km = db.Column(db.Float)
    assigned_time = db.Column(db.DateTime)
    pickedup_time = db.Column(db.DateTime)
    delivery_time = db.Column(db.DateTime)
    driving_duration = db.Column(db.Integer)
    driver_id = db.Column(db.String(50))
    driver_base_fee = db.Column(db.Float)
    shipping_status = db.Column(db.String(50))
    payment_id = db.Column(db.Integer)



class TocShipdayDriver(db.Model):
    __tablename__ = 'toc_shipday_drivers'

    driver_id = db.Column(db.String(45), primary_key=True)  # Shipday ID
    full_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(45))
    email = db.Column(db.String(100))
    vehicle_type = db.Column(db.String(45))
    vehicle_number = db.Column(db.String(45))
    current_rating = db.Column(db.Float)
    active_status = db.Column(db.Boolean, default=True)
    creation_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    last_update = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())


class TocShipdayDriverPayment(db.Model):
    __tablename__ = 'toc_shipday_drivers_payments'

    payment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    driver_id = db.Column(db.String(45), db.ForeignKey('toc_shipday_drivers.driver_id'))
    total_amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='open')
    paid_date = db.Column(db.DateTime)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class TocShopsHours(db.Model):
    __tablename__ = 'toc_shops_hours'
    shop_name = db.Column(db.String(100), primary_key=True)
    day_of_week = db.Column(db.String(10), primary_key=True)
    open_hour = db.Column(db.Time, nullable=False)
    closing_hour = db.Column(db.Time, nullable=False)


###########  Purchase order CUSTOMIZED ####################

class BbSupplier(db.Model):
    __tablename__ = 'bb_suppliers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    vendor_code = db.Column(db.String(50))
    vat_registered = db.Column(db.Boolean, default=False)
    vat_number = db.Column(db.String(50))
    contact_person = db.Column(db.String(100))
    contact_email = db.Column(db.String(100))
    contact_phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    status = db.Column(db.Enum('Active', 'Inactive'), default='Active')
    payment_terms = db.Column(db.String(100))
    default_ship_to_store = db.Column(db.String(50))
    document_received = db.Column(db.Boolean, default=False)
    document_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # products = db.relationship("TocProduct", back_populates="supplier", lazy='dynamic')

class BbPurchaseOrder(db.Model):
    __tablename__ = 'bb_purchase_orders'

    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(20), unique=True, nullable=False)
    po_type = db.Column(db.String(50), default='Drop Ship')
    supplier_id = db.Column(db.Integer, nullable=False)
    ship_to_store = db.Column(db.String(50))
    created_by = db.Column(db.Integer, nullable=False)
    approved_by = db.Column(db.String(50))
    status = db.Column(db.Enum('Draft', 'Submitted', 'Approved', 'Sent', 'Partially Received', 'Completed', 'Short Closed', 'Cancelled'), default='Draft')
    status_date = db.Column(db.DateTime, default=datetime.now)
    expected_delivery_date = db.Column(db.Date)
    order_date = db.Column(db.DateTime, default=datetime.now)
    created_at = db.Column(db.DateTime, default=datetime.now)
    approved_at = db.Column(db.DateTime)
    short_closed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    cancel_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    po_terms = db.Column(db.String(100))
    subtotal = db.Column(db.Numeric(12, 2), default=0.00)
    freight = db.Column(db.Numeric(10, 2), default=0.00)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00)
    fee_type = db.Column(db.String(50))
    fee_amount = db.Column(db.Numeric(10, 2), default=0.00)
    vat_amount = db.Column(db.Numeric(10, 2), default=0.00)

class BbPurchaseOrderItem(db.Model):
    __tablename__ = 'bb_purchase_order_items'

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, nullable=False)
    sku = db.Column(db.String(45), nullable=False)
    description = db.Column(db.String(255))
    attribute = db.Column(db.String(50))
    size = db.Column(db.String(50))
    quantity_ordered = db.Column(db.Numeric(10, 2), nullable=False)
    case_qty = db.Column(db.Integer, default=0)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    product_size = db.Column(db.String(50))
    best_before_date = db.Column(db.Date, nullable=True)
    uom = db.Column(db.String(20))
    discount_percent = db.Column(db.Numeric(5, 2))
    net_cost = db.Column(db.Numeric(12, 2))
    tax_amount = db.Column(db.Numeric(10, 2))
    landed_cost = db.Column(db.Numeric(12, 2))
    notes = db.Column(db.Text)
    quantity_due = db.Column(db.Numeric(10, 2), default=0.00)
    cancelled_quantity = db.Column(db.Numeric(10, 2), default=0.00)
    total_amount = db.Column(db.Numeric(10, 2))


class BbGrv(db.Model):
    __tablename__ = 'bb_grv'

    id = db.Column(db.Integer, primary_key=True)
    grv_number = db.Column(db.String(50), unique=True, nullable=False)
    grv_reference = db.Column(db.String(50))
    po_id = db.Column(db.Integer, nullable=False)
    received_by = db.Column(db.Integer, nullable=False)
    received_at = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20))
    store_code = db.Column(db.String(50))
    reference = db.Column(db.String(100))
    comments = db.Column(db.Text)
    invoice_number = db.Column(db.String(50))
    document_received = db.Column(db.Boolean, default=False)
    delivery_note = db.Column(db.Text)
    is_complete = db.Column(db.Boolean, default=False)
    invoice_date = db.Column(db.Date)
    invoice_vat_total = db.Column(db.Numeric(10, 2), default=0.00)
    invoice_total_amount = db.Column(db.Numeric(10, 2), default=0.00)
    invoice_currency = db.Column(db.String(10), default='ZAR')
    invoice_uploaded_file = db.Column(db.String(255))

    # ✅ NEW summary fields
    po_vat_total = db.Column(db.Numeric(10, 2), default=0.00)
    po_total_amount = db.Column(db.Numeric(10, 2), default=0.00)
    diff_amount = db.Column(db.Numeric(10, 2), default=0.00)

    creation_date = db.Column(db.DateTime)
    update_date = db.Column(db.DateTime)

    damage_ind = db.Column(db.Boolean)
    mismatch_ind = db.Column(db.Boolean)


class BbGrvItem(db.Model):
    __tablename__ = 'bb_grv_items'

    id = db.Column(db.Integer, primary_key=True)
    grv_id = db.Column(db.Integer)
    grv_number = db.Column(db.String(50), nullable=False)
    po_item_id = db.Column(db.Integer, nullable=False)
    sku = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    cost_price = db.Column(db.Numeric(10, 2), default=0.00)
    quantity_ordered = db.Column(db.Integer, default=0)
    po_vat = db.Column(db.Numeric(10, 2), default=0.00)
    po_amount = db.Column(db.Numeric(10, 2), default=0.00)

    quantity_received = db.Column(db.Integer)
    damaged_quantity = db.Column(db.Integer, default=0)
    best_before_date = db.Column(db.Date)
    rejected_quantity = db.Column(db.Numeric(10, 2), default=0)

    invoice_quantity = db.Column(db.Integer)
    invoice_price = db.Column(db.Numeric(10, 2))
    invoice_vat = db.Column(db.Numeric(10, 2))
    invoice_amount = db.Column(db.Numeric(10, 2))

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)



class BbDebitNote(db.Model):
    __tablename__ = 'bb_debit_notes'

    id = db.Column(db.Integer, primary_key=True)
    grv_id = db.Column(db.Integer, nullable=False)
    sku = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(50))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class BbUploadedInvoice(db.Model):
    __tablename__ = 'bb_uploaded_invoices'

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, nullable=False)
    file_name = db.Column(db.String(255))
    uploaded_by = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, server_default=db.func.now())
    status = db.Column(db.String(50), default='Pending')  # 'Pending', 'Parsed', 'Error'
    ocr_json = db.Column(db.Text)  # Store raw OCR result as JSON string

class BbUploadedInvoiceItem(db.Model):
    __tablename__ = 'bb_uploaded_invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, nullable=False)
    line_number = db.Column(db.Integer)
    description = db.Column(db.String(255))
    sku = db.Column(db.String(50))
    quantity = db.Column(db.Numeric(10, 2))
    unit_price = db.Column(db.Numeric(10, 2))
    total_price = db.Column(db.Numeric(10, 2))
    matched_po_item_id = db.Column(db.Integer)
    match_confidence = db.Column(db.Numeric(5, 2))
    is_flagged = db.Column(db.Boolean, default=False)

class BbSupplierInvoiceItem(db.Model):
    __tablename__ = 'bb_supplier_invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, nullable=False)
    product_code = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    qty = db.Column(db.Numeric(10, 2))
    unit_price = db.Column(db.Numeric(10, 2))
    vat = db.Column(db.Numeric(10, 2))
    total_incl_vat = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=db.func.now())

##########  BILL OF MATERIALS  ####################

class TocBOMComponent(db.Model):
    __tablename__ = 'toc_bom_components'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    bom_id = db.Column(db.String(50), nullable=False, index=True)

    bom_name = db.Column(db.String(255), nullable=True)
    component_sku = db.Column(db.String(50), nullable=False)
    component_name = db.Column(db.String(255), nullable=True)

    quantity = db.Column(db.Float, nullable=False, default=1)
    cost = db.Column(db.Float, nullable=True)

    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    update_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TocManufacturingTransaction(db.Model):
    __tablename__ = 'toc_manufacturing_transaction'

    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('toc_bom_header.bom_id'), nullable=False)
    product_sku = db.Column(db.String(45), nullable=False)
    shop_id = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.Numeric(10,3), nullable=False)
    reference = db.Column(db.String(100))
    type = db.Column(db.Enum('manufacture', 'unmanufacture'), nullable=False)
    created_by = db.Column(db.Integer)
    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    components_used = db.relationship("TocManufacturingComponentUsed", backref="transaction", cascade="all, delete")

class TocManufacturingComponentUsed(db.Model):
    __tablename__ = 'toc_manufacturing_components_used'

    id = db.Column(db.Integer, primary_key=True)
    manufacturing_id = db.Column(db.Integer, db.ForeignKey('toc_manufacturing_transaction.id'), nullable=False)
    component_sku = db.Column(db.String(45), nullable=False)
    qty_used = db.Column(db.Numeric(10,3), nullable=False)
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, current_app, send_file
import pymysql
import json
import os
from sqlalchemy.exc import SQLAlchemyError
from .models import *
from . import db
from .db_queries import *
from datetime import datetime, timezone, timedelta, date
from flask import Flask, request, jsonify
from sqlalchemy import distinct, or_, text, desc, func
from flask import session, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import pandas as pd
import openai
import re
from app.tables_for_openAI import DATABASE_SCHEMA
import requests
from sqlalchemy.exc import IntegrityError
import unicodedata


from shipday import Shipday
from shipday.order import Address, Customer, Pickup, OrderItem, Order
from flask import g
from flask_login import current_user

shipday_api = Blueprint('shipday_api', __name__)

_entity_re = re.compile(r"&([^;]+);")
_filename_ascii_strip_re = re.compile(r"[^A-Za-z0-9_.-]")
_windows_device_files = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
}

import platform
IS_WINDOWS = platform.system().lower() == "windows"



# Set your Shipday API key
API_KEY = 'VXveiHsYGE.eLK6vIxvz1gQixI9tOvm'
shipday_obj = Shipday(api_key=API_KEY)

LIGHTSPEED_API_URL = "https://api.lsk.lightspeed.app/o/op/1/order/toGo"
LIGHTSPEED_ACCESS_TOKEN = "d03f8f2e-67df-4210-b388-8011be9e7bf6"



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
main = Blueprint('main', __name__)

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465
SENDER_EMAIL = 'algott.team@gmail.com'
SENDER_PASSWORD = 'xiyaxiztcekbkvtu'

DB_CONFIG = {
    'host': '176.58.117.107',
    'user': 'tasteofc_wp268',
    'password': ']44p7214)S',
    'database': 'tasteofc_wp268',
    'cursorclass': pymysql.cursors.DictCursor  # Return rows as dictionaries
}

def secure_filename(filename: str) -> str:
    r"""Pass it a filename and it will return a secure version of it.  This
    filename can then safely be stored on a regular file system and passed
    to :func:`os.path.join`.  The filename returned is an ASCII only string
    for maximum portability.

    On windows systems the function also makes sure that the file is not
    named after one of the special device files.

    >>> secure_filename("My cool movie.mov")
    'My_cool_movie.mov'
    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'
    >>> secure_filename('i contain cool \xfcml\xe4uts.txt')
    'i_contain_cool_umlauts.txt'

    The function might return an empty filename.  It's your responsibility
    to ensure that the filename is unique and that you abort or
    generate a random filename if the function returned an empty one.

    .. versionadded:: 0.5

    :param filename: the filename to secure
    """
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    for sep in os.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, " ")
    filename = str(_filename_ascii_strip_re.sub("", "_".join(filename.split()))).strip(
        "._"
    )

    # on nt a couple of special files are present in each folder.  We
    # have to ensure that the target file is not such a filename.  In
    # this case we prepend an underline
    if (
        os.name == "nt"
        and filename
        and filename.split(".")[0].upper() in _windows_device_files
    ):
        filename = f"_{filename}"

    return filename

def update_grv_flags(po_id):
    grv = BbGrv.query.filter_by(po_id=po_id).first()
    if not grv:
        return

    grv_items = BbGrvItem.query.join(BbPurchaseOrderItem, BbGrvItem.po_item_id == BbPurchaseOrderItem.id)\
                               .filter(BbPurchaseOrderItem.po_id == po_id).all()

    # Damage flag: any damaged qty > 0
    grv.damage_ind = any(item.damaged_quantity and item.damaged_quantity > 0 for item in grv_items)

    # Mismatch flag: check amount differences
    po_total = grv.po_total_amount or 0
    invoice_total = grv.invoice_total_amount or 0

    grv.mismatch_ind = round(po_total - invoice_total, 2) != 0

    grv.update_date = datetime.utcnow()
    db.session.commit()


# Function to send email
def send_email(recipients, subject, body):
    try:
        # Create the message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ', '.join(recipients)  # Send to multiple recipients
        msg['Subject'] = subject

        # Add the email body
        msg.attach(MIMEText(body, 'plain'))

        # Connect to the SMTP server and send the email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())

        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

def generate_vendor_specific_po_number(supplier_id):
    from app.models import BbSupplier, BbPurchaseOrder  # adjust import path if needed
    supplier = BbSupplier.query.get(supplier_id)
    vendor_code = supplier.vendor_code or f"SUP{supplier_id}"

    last_po = BbPurchaseOrder.query.filter_by(supplier_id=supplier_id) \
        .filter(BbPurchaseOrder.po_number.like(f"PO-{vendor_code}%")) \
        .order_by(BbPurchaseOrder.id.desc()).first()

    next_count = 1
    if last_po and last_po.po_number.startswith(f"PO-{vendor_code}"):
        try:
            number_part = last_po.po_number.replace(f"PO-{vendor_code}", "")
            next_count = int(number_part) + 1
        except ValueError:
            pass  # fallback to 1

    return f"PO-{vendor_code}{next_count:03d}"

def is_safe_sql(sql):
    """
    Check if a given SQL query is safe for execution (only SELECT allowed).
    """
    forbidden_keywords = ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'ALTER']
    for keyword in forbidden_keywords:
        if re.search(r'\b' + keyword + r'\b', sql, re.IGNORECASE):
            return False
    return sql.strip().upper().startswith('SELECT')

# ===============================
# Helper Function: Execute Safe SQL
# ===============================
def execute_sql(sql):
    """
    Executes a safe SELECT SQL query and returns columns and rows.
    """
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]  # Get column names
            rows = cursor.fetchall()  # Fetch all results
        return columns, rows
    finally:
        connection.close()

@main.route('/send_email', methods=['POST'])
def handle_send_email():
    try:
        # Get data from the client (list of recipients, subject, and body)
        data = request.get_json()
        recipients = data.get('recipients', [])
        subject = data.get('subject', '')
        body = data.get('body', '')

        # Validate input data
        if not recipients or not subject or not body:
            return jsonify({"error": "Missing required fields"}), 400

        # Call the function to send the email
        send_email(recipients, subject, body)

        return jsonify({"message": "Email sent successfully!"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to send email: {str(e)}"}), 500

# --- Stock Audit helper -------------------------------------------------------
def log_stock_audit_entry(*, shop_id, sku, product_name, stock_count, shop_name, comments):
    """
    Append a row to toc_stock_audit. Assumes TocStockAudit model exists.
    stock_count should reflect the new running stock (what you store in audit_count/final_stock_qty).
    """
    try:
        audit = TocStockAudit(
            shop_id=str(shop_id),
            sku=str(sku),
            product_name=product_name,
            stock_count=float(stock_count) if stock_count is not None else None,
            shop_name=shop_name,
            comments=(comments or "")[:150]  # safeguard max length
        )
        db.session.add(audit)
    except Exception as e:
        # Don't blow up the transaction just because of audit logging;
        # raise if you prefer a hard fail.
        logger.exception(f"Stock Audit insert failed for {shop_id}/{sku}: {e}")

@main.app_context_processor
def inject_360_defaults():
    """
    Provide defaults every template expects:
    - user: object with first_name/last_name
    - active_menu: for sidebar highlight
    - page_title: for <title> / breadcrumb
    """
    # Resolve user
    u = None
    try:
        if hasattr(current_user, "is_authenticated") and current_user.is_authenticated:
            u = current_user
    except Exception:
        u = None

    if u is None:
        # Lightweight fallback from session if available
        class _U: pass
        u = _U()
        u.first_name = session.get("first_name", "")
        u.last_name  = session.get("last_name", "")
        # Add any other fields your header might touch:
        # u.avatar_url = session.get("avatar_url", "")

    # Pick up per-request flags if set by a view
    active_menu = getattr(g, "active_menu", "")
    page_title  = getattr(g, "page_title", "Inventory")

    return dict(user=u, active_menu=active_menu, page_title=page_title)

@main.route('/')
def login():
    return render_template('login.html')

@main.route('/ChatGPT')
def ChatGPT():
    user_data = session.get('user')
    roles = TocRole.query.all()
    shops = TOC_SHOPS.query.all()

    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    list_of_shops = [shop.blName for shop in shops]

    if user_data:
        user = json.loads(user_data)
        return render_template('openAI.html', user=user, roles=roles_list, shops=list_of_shops)  # Pass as JSON
    else:
        return redirect(url_for('main.login'))


@main.route('/index')
def index():

    user_data = session.get('user')
    roles = TocRole.query.all()
    shops = TOC_SHOPS.query.all()

    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    list_of_shops = [shop.blName for shop in shops]

    if user_data:
        user = json.loads(user_data)
        return render_template('index.html', user=user, roles=roles_list, shops=list_of_shops)  # Pass as JSON
    else:
        return redirect(url_for('main.login'))


@main.route('/b2bIndex')
def b2bIndex():

    user_data = session.get('user')
    roles = TocRole.query.all()
    shops = TOC_SHOPS.query.all()

    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    list_of_shops = [shop.blName for shop in shops]

    if user_data:
        user = json.loads(user_data)
        return render_template('b2bDashboard.html', user=user, roles=roles_list, shops=list_of_shops)  # Pass as JSON
    else:
        return redirect(url_for('main.login'))



@main.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()


    if not user or user.password != password:
        flash('User/password invalid')
        return redirect(url_for('main.login'))

    # Serialize user object
    user_data = {
        'id': user.id,
        'username' : user.username,
        'password' : user.password,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'shop': user.shop,
        'role': user.role
    }
    session['user'] = json.dumps(user_data)

    #Save to the session shop data
    shop = TOC_SHOPS.query.filter_by(blName=user.shop).first()
    # print(f"shop: {shop.store}")
    shop_data = {
        'name' : shop.blName,
        'code' : shop.store,
        'customer' : shop.customer
    }
    session['shop'] = json.dumps(shop_data)

    # Create a new TOCUserActivity record
    new_activity = TOCUserActivity(
        user=user.username,  # Assuming the username is stored in user["username"]
        shop=shop.customer,  # Assuming the shop name is stored in shop["customer"]
        activity="User login"
    )

    # Add the record to the session and commit to the database
    db.session.add(new_activity)
    db.session.commit()


    return redirect(url_for('main.index'))

@main.route('/welcome/<username>')
def welcome(username):
    return f'Welcome {username}'

@main.route('/register')
def register():
    shops = TOC_SHOPS.query.all()
    # Fetch all roles from the TocRole table
    roles = TocRole.query.all()
    role_list = [role.role for role in roles]  # Extract roles as a list
    return render_template('register.html', shops=shops, roles = role_list)

@main.route('/faq')
def faq():
    return render_template('pages-faq.html')

@main.route('/template')
def template():
    return render_template('pages-blank.html')

@main.route('/admin_users')
def admin_users():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    users = User.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'user_admin.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        users=users
    )

@main.route('/admin_logs')
def admin_logs():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    users = User.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'log_admin.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        users=users
    )

@main.route('/user_activity')
def user_activity():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    users = User.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'user_activity.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        users=users
    )

@main.route('/change_shop', methods=['POST'])
def change_shop():
    selected_shop_name = request.form.get('shop')  # Get the shop name from the request
    shop = TOC_SHOPS.query.filter_by(blName=selected_shop_name).first()

    if not shop:
        flash('Invalid shop selection')
        return redirect(url_for('main.index'))

    # Update the session with the selected shop data
    shop_data = {
        'name': shop.blName,
        'code': shop.store,
        'customer': shop.customer
    }
    session['shop'] = json.dumps(shop_data)

    # Update the user data in the session
    user_data = session.get('user')
    user = json.loads(user_data)
    user['shop'] = shop.blName  # Update the user's shop
    session['user'] = json.dumps(user)  # Save the updated user object back to the session

    # Log the shop change activity
    new_activity = TOCUserActivity(
        user=user['username'],
        shop=shop.customer,
        activity=f"Changed shop to {shop.blName}"
    )
    db.session.add(new_activity)
    db.session.commit()

    return redirect(url_for('main.index'))  # Redirect to index





@main.route('/api/get_users')
def get_users():
    users = User.query.all()
    users_list = [{
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'shop': user.shop,
        'password': user.password,
        'role': user.role,
    } for user in users]
    return jsonify(users_list)

@main.route('/api/get_logs')
def get_logs():
    logs = TocSalesLog.query.order_by(desc(TocSalesLog.run_id)).limit(50).all()
    TocSalesLogs_list = [{
        'id': log.run_id,
        'start_date': log.start_date,
        'end_date': log.end_date,
        'search_from': log.search_from,
        'num_of_sales': log.num_of_sales,
        'source': log.source,
        'comment': log.comment,
    } for log in logs]
    return jsonify(TocSalesLogs_list)


@main.route('/api/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        # Retrieve the user object by user_id
        user = User.query.get(user_id)

        if user:
            # Delete the user if found
            db.session.delete(user)
            db.session.commit()
            return jsonify({"message": f"User {user_id} deleted successfully."}), 200
        else:
            # If user not found, return an error
            return jsonify({"error": f"User {user_id} not found."}), 404

    except Exception as e:
        # Handle any exceptions that occur during deletion
        print(f"Error occurred while deleting user: {e}")
        return jsonify({"error": "An error occurred while deleting the user."}), 500


@main.route('/api/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        # Get the user by ID
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Update fields with form data
        user.email = request.form.get('email')
        user.password = request.form.get('password')
        user.role = request.form.get('role')
        user.shop = request.form.get('shop')

        # Commit changes to the database
        db.session.commit()
        return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({"error": "An error occurred while updating the user"}), 500

@main.route('/api/update_password/<string:password>', methods=['PUT'])
def update_password(password):
    try:
        # Get the user by ID
        user_data = session.get('user')
        user = User.query.get(json.loads(user_data)["id"])
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Update fields with form data
        user.password = password

        # Commit changes to the database
        db.session.commit()
        return jsonify({"message": "User password updated successfully"}), 200
    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({"error": "An error occurred while updating the user"}), 500


##########################################    Product admin  ##########################################
@main.route('/admin_products')
def admin_products():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    products = TocProduct.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'product_admin.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        products=products
    )


@main.route('/api/products', methods=['GET'])
def get_products():
    products = TocProduct.query.all()

    products_data = [
        {
            "item_sku": product.item_sku,
            "item_name": product.item_name,
            "item_type": product.item_type,   # NEW
            "stat_group": product.stat_group,
            "acct_group": product.acct_group,
            "retail_price": product.retail_price,
            "cost_price": product.cost_price,
            "wh_price": product.wh_price,
            "cann_cost_price": product.cann_cost_price,
            "product_url": product.product_url,
            "image_url": product.image_url,
            "stock_ord_ind": product.stock_ord_ind,
            "is_component": product.is_component,
            "is_manufacturable": product.is_manufacturable
        }
        for product in products
    ]

    return jsonify(products_data)


@main.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()

    if not data or not data.get('item_sku') or not data.get('item_name'):
        return jsonify({"message": "Missing required fields: item_sku or item_name"}), 400

    try:
        item_type = data.get("item_type", "PR")  # default = Product

        # Auto assignment rules
        is_component = (item_type == "CO")
        is_manufacturable = (item_type == "PR")

        new_product = TocProduct(
            item_sku=data.get('item_sku'),
            item_name=data.get('item_name'),
            item_type=item_type,
            stat_group=data.get('stat_group'),
            acct_group=data.get('acct_group'),
            retail_price=data.get('retail_price'),
            cost_price=data.get('cost_price'),
            wh_price=data.get('wh_price'),
            cann_cost_price=data.get('cann_cost_price'),
            product_url=data.get('product_url'),
            image_url=data.get('image_url'),
            stock_ord_ind=data.get('stock_ord_ind'),

            # Auto fields
            is_component=is_component,
            is_manufacturable=is_manufacturable
        )

        db.session.add(new_product)
        db.session.commit()

        # Insert into toc_stock for all shops only product
        if item_type == "PR":
            distribute_product_to_shops(new_product.item_sku)
        elif item_type == "CO":
            distribute_component_to_canndo_holdings(new_product.item_sku)

        return jsonify({
            "message": "Product created successfully",
            "product": new_product.item_sku
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error creating product: {str(e)}"}), 500


@main.route('/api/products/<string:item_sku>', methods=['PUT'])
def update_product(item_sku):
    data = request.get_json()

    try:
        product = TocProduct.query.get(item_sku)
        if not product:
            return jsonify({"error": f"Product with ID {item_sku} not found"}), 404

        # If item_type is updated → enforce auto rules
        if "item_type" in data:
            product.item_type = data["item_type"]
            product.is_component = (product.item_type == "CO")
            product.is_manufacturable = (product.item_type == "PR")

        # Update other fields
        product.item_name = data.get('item_name', product.item_name)
        product.stat_group = data.get('stat_group', product.stat_group)
        product.acct_group = data.get('acct_group', product.acct_group)
        product.retail_price = data.get('retail_price', product.retail_price)
        product.cost_price = data.get('cost_price', product.cost_price)
        product.wh_price = data.get('wh_price', product.wh_price)
        product.cann_cost_price = data.get('cann_cost_price', product.cann_cost_price)
        product.product_url = data.get('product_url', product.product_url)
        product.image_url = data.get('image_url', product.image_url)
        product.stock_ord_ind = data.get('stock_ord_ind', product.stock_ord_ind)

        # Sync product_name in toc_stock
        TocStock.query.filter_by(sku=item_sku).update({
            "product_name": product.item_name
        })

        db.session.commit()

        return jsonify({"message": f"Product {item_sku} updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@main.route('/api/products/<string:item_sku>', methods=['DELETE'])
def delete_product(item_sku):
    product = TocProduct.query.get(item_sku)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    try:
        # Delete related stock records first
        TocStock.query.filter_by(sku=item_sku).delete()

        # Delete product
        db.session.delete(product)

        # Commit changes
        db.session.commit()

        return jsonify({"message": "Product and related stock records deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500





#######################################################################################################



@main.route('/count_stock')
def count_stock():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('count_stock.html', user=user, shop=shop , roles=roles_list)

@main.route('/spotcheck_count_stock')
def spotcheck_count_stock():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('spotcheck_count_stock.html', user=user, shop=shop , roles=roles_list)

@main.route('/user_profile')
def user_profile():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('users-profile.html', user=user, shop=shop, roles=roles_list)


@main.route('/receive_stock')
def receive_stock():
    try:
        # Get user and shop data
        user_data = session.get('user')
        user = json.loads(user_data)
        shop_data = session.get('shop')
        shop = json.loads(shop_data)
        roles = TocRole.query.all()
        roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

        # Query all records where order_status is 'New'
        replenish_orders_query = TOCReplenishCtrl.query.filter(
            or_(
                TOCReplenishCtrl.order_status == 'New',
                TOCReplenishCtrl.order_status == 'Submitted'
            ),
            TOCReplenishCtrl.shop_id == shop["customer"]
        ).all()

        # Convert query results into a list of dictionaries
        replenish_orders = [
            {
                "order_id": order.order_id,
                "shop_id": order.shop_id,
                "order_open_date": order.order_open_date.isoformat() if order.order_open_date else None,
                "user": order.user,
                "order_status": order.order_status,
                "order_status_date": order.order_status_date.isoformat() if order.order_status_date else None,
                "tracking_code": order.tracking_code,
                # "comments": order.comments,
            }
            for order in replenish_orders_query
        ]

        # Serialize replenish_orders as JSON
        replenish_orders_json = json.dumps(replenish_orders)

        # Pass JSON data to the template
        return render_template(
            'receive_stock.html',
            user=user,
            shop=shop,
            replenish_orders=replenish_orders_json,
            roles = roles_list
        )
    except Exception as e:
        print(f"Error in receive_stock route: {e}")
        return render_template('pages-error-404.html', message="Failed to load receive stock data")


@main.route('/order_stock')
def order_stock():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('order_stock.html', user=user, shop=shop , roles=roles_list)


@main.route('/view_orders')
def view_orders():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)

    # Get roles
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    # Get list of open orders
    distinct_orders = db.session.query(TocStockOrder.order_id) \
        .filter(TocStockOrder.order_status.in_(["New", "Updated"])) \
        .distinct() \
        .all()
    list_of_orders = [order[0] for order in distinct_orders]

    # Get all shops
    all_shops = TOC_SHOPS.query.all()
    shops_list = [{'blName': shop.blName, 'store': shop.store, 'customer': shop.customer} for shop in all_shops]

    return render_template(
        'view_orders.html',
        user=user,
        shop=shop,
        roles=roles_list,
        orders=list_of_orders,
        shops=shops_list
    )


@main.route('/get_order_details', methods=['GET'])
def get_order_details():
    order_id = request.args.get('order_id')
    if not order_id:
        return jsonify({'error': 'Missing order_id'}), 400

    # Query the database
    records = TocStockOrder.query.filter(TocStockOrder.order_id == order_id).all()

    # Format the data for response
    result = [{
        'order_open_date': record.order_open_date.strftime('%Y-%m-%d %H:%M:%S'),
        'sku': record.sku,
        'user': record.user,
        'item_name': record.item_name,
        'order_qty': record.order_qty,
        'comments': record.comments,
        'order_status': record.order_status,
        'order_status_date': record.order_status_date.strftime(
            '%Y-%m-%d %H:%M:%S') if record.order_status_date else None,
    } for record in records]

    return jsonify(result)

@main.route('/confirm_order/<string:order_id>', methods=['POST'])
def confirm_order(order_id):
    try:
        # Update the database records for the given order_id
        records_updated = (
            db.session.query(TocStockOrder)
            .filter(TocStockOrder.order_id == order_id)
            .update({
                TocStockOrder.order_status: "Confirm",
                TocStockOrder.order_status_date: datetime.utcnow()
            })
        )
        db.session.commit()
        if records_updated > 0:
            return jsonify({"message": "Order confirmed successfully."}), 200
        else:
            return jsonify({"error": "No records found for the given order ID."}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@main.route('/replenish_stock')
def replenish_stock():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]
    roles = TocRole.query.all()
    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('replenishment.html', user=user, shop=shop, shops=list_of_shops , roles=roles_list)

@main.route('/inter_replenish_stock')
def inter_replenish_stock():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != shop["code"]).all()
    list_of_shops = [shop.blName for shop in shops]
    roles = TocRole.query.all()
    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('inter_replenishment.html', user=user, shop=shop, shops=list_of_shops , roles=roles_list)



@main.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    shop = request.form.get('shop')
    role = request.form.get('role')

    user = User.query.filter_by(username=username).first()

    if user:
        flash('Username already exists')
        return redirect(url_for('main.register'))


    if not username or not password or not first_name or not last_name or not email or '@' not in email:
        flash('Please fill out all fields correctly')
        return redirect(url_for('main.register'))

    new_user = User(username=username, password=password, first_name=first_name, last_name=last_name, email=email, shop=shop, role=role)
    db.session.add(new_user)
    db.session.commit()

    # Create a new TOCUserActivity record
    new_activity = TOCUserActivity(
        user=username,  # Assuming the username is stored in user["username"]
        shop=shop,  # Assuming the shop name is stored in shop["customer"]
        activity="New registration"
    )

    # Add the record to the session and commit to the database
    db.session.add(new_activity)
    db.session.commit()

    # flash('User registered successfully')
    return redirect(url_for('main.admin_users'))


@main.route('/get_product_order_template', methods=['GET'])
def get_product_order_template():
    data = get_stock_order_template()
    formatted_data = [
        {
            "sku": row[0],
            "product_name": row[1],
            "stock_count": row[2],
            "last_stock_qty": row[3],
            "calc_stock_qty": row[4],
            "variance": row[5],
            "variance_rsn": row[6],
            "stock_recount": row[7],
            "rejects_qty": row[8],
            "comments": row[9]
        }
        for row in data
    ]
    return jsonify(formatted_data)


# @main.route('/get_product_order_form', methods=['GET'])
# def get_product_order_form():
#     try:
#         # Fetch the shop customer from the session
#         shop = json.loads(session.get('shop'))['name']  # Assuming 'shop.customer' is stored in the session
#
#         data = get_stock_count_per_shop(shop)
#
#         if not data:
#             return jsonify({"message": "Error fetching stock order form data"}), 500
#
#         # Format the data for the client
#         formatted_data = [
#             {
#                 "sku": row[0],
#                 "product_name": row[1],
#                 "stock_count": row[7],
#                 "last_stock_qty": row[4],
#                 "calc_stock_qty": row[7],
#                 "variance": 0,
#                 "variance_rsn": "NA",
#                 "stock_recount": 0,
#                 "rejects_qty": 0,
#                 "comments": "NA"
#             }
#             for row in data
#         ]
#
#         return jsonify(formatted_data)
#
#     except Exception as e:
#         print("Error in get_product_order_form:", e)
#         return jsonify({"message": "Internal server error"}), 500

@main.route('/get_product_order_form', methods=['GET'])
def get_product_order_form():
    try:
        shop = json.loads(session.get('shop'))['name']
        data = get_stock_count_per_shop(shop)

        if not data:
            return jsonify({"message": "Error fetching stock order form data"}), 500

        formatted_data = [
            {
                "sku": row[0],
                "product_name": row[1],
                "stock_count": row[8],     # was row[7]
                "last_stock_qty": row[5],  # was row[4]
                "calc_stock_qty": row[8],  # was row[7]
                "variance": 0,
                "variance_rsn": "NA",
                "stock_recount": 0,
                "rejects_qty": 0,
                "comments": "NA"
            }
            for row in data
        ]

        return jsonify(formatted_data)

    except Exception as e:
        print("Error in get_product_order_form:", e)
        return jsonify({"message": "Internal server error"}), 500


@main.route('/get_product_replenish_form', methods=['POST'])
def get_product_replenish_form():
    try:
        # Get the JSON data sent in the request
        data = request.get_json()
        # Access the shop value
        selected_shop = data.get('shop')
        history_sold = data.get('sold')
        replenish_qty = data.get('replenish')
        order_id = data.get('order_id')

        # Print the selected shop value
        print(f"Selected shop from client: {selected_shop}")

        data = get_replenish_order_form(order_id,selected_shop,history_sold,replenish_qty)
    #
        if not data:
            return jsonify({"message": "Error fetching stock order form data"}), 500
    #
        # Format the data for the client
        formatted_data = [
            {
                "sku": row[0],
                "product_name": row[1],
                "current_stock": row[9],
                "threshold_qty": row[4],
                "replenish_qty": row[5],
                "replenish_order": row[10]
            }
            for row in data
        ]

        return jsonify(formatted_data)

    except Exception as e:
        # Handle any errors
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/get_stock_count_form', methods=['GET'])
def get_stock_count_form():
    try:
        shop_data = json.loads(session.get('shop'))
        selected_shop = shop_data['name']
        print(f"Selected shop from client: {selected_shop}")

        data = get_stock_count_per_shop(selected_shop)

        if not data:
            return jsonify({"message": "Error fetching stock order form data"}), 500

        formatted_data = [
            {
                "sku": row[0],
                "product_name": row[1],
                "item_type": row[2],          # ✅ NEW
                "store_code": row[3],
                "last_stock_count": row[5],
                "last_stock_count_date": row[6],
                "sold_qty": row[7],
                "current_qty": row[8],
                "received_qty": row[9]
            }
            for row in data
        ]

        return jsonify(formatted_data)

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500



@main.route('/get_stock_order_form', methods=['GET'])
def get_stock_order_form():
    try:
        shop_data = json.loads(session.get('shop'))
        selected_shop = shop_data['name']
        # Print the selected shop value
        print(f"Selected shop from client: {selected_shop}")

        data = get_stock_order_per_shop(selected_shop)
    #
        if not data:
            return jsonify({"message": "Error fetching stock order form data"}), 500
    #
        # Format the data for the client
        formatted_data = [
            {
                "sku": row[0],
                "product_name": row[1],
                "store_code" :row[2],
                "last_stock_count": row[4],
                "last_stock_count_date": row[5],
                "sold_qty": row[6],
                "current_qty": row[7],
                "received_qty" : row[8]
            }
            for row in data
        ]

        return jsonify(formatted_data)

    except Exception as e:
        # Handle any errors
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/get_receive_stock_form', methods=['GET'])
def get_receive_stock_form():
    try:
        order_id = request.args.get('order_id')
        if not order_id:
            return jsonify({"message": "Order ID is required"}), 400

        shop_data = json.loads(session.get('shop'))
        selected_shop = shop_data['customer']
        print(f"Selected shop from client: {selected_shop}")
        print(f"Received order_id: {order_id}")

        data = get_receive_stock_order(selected_shop, order_id)

        if not data:
            return jsonify({"message": "Error fetching stock order form data"}), 500

        formatted_data = [
            {
                "sku": row[2],
                "replenish_date": row[3],
                "replenish_user": row[4],
                "item_name": row[5],
                "replenish_qty": row[6],
                "received_qty": row[8],
                "rejected_qty": row[9]  # Added field for "Received Damaged"
            }
            for row in data
        ]

        return jsonify(formatted_data)

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500



@main.route('/delete_order', methods=['POST'])
def delete_order():
    try:
        # Parse the request data
        shop = json.loads(session.get('shop'))['customer']

        # Query the database to find matching orders
        orders_to_delete = TocStockOrder.query.filter_by(order_status="New", shop_id=shop).all()

        if not orders_to_delete:
            return jsonify({"message": "No matching orders found to delete."}), 404

        # Delete the records
        for order in orders_to_delete:
            db.session.delete(order)

        # Commit the changes to the database
        db.session.commit()

        return jsonify({"message": "Orders successfully deleted."}), 200

    except Exception as e:
        # Log the error for debugging
        print("Error in /delete_order:", e)
        db.session.rollback()
        return jsonify({"message": "An error occurred while deleting the order."}), 500

@main.route('/delete_replenish_order', methods=['POST'])
def delete_replenish_order():
    try:
        # Parse the request data
        data = request.get_json()
        order_id = data.get('order_id')  # Get the shop parameter from the request body

        # Query the database to find matching orders
        orders_to_delete = TocReplenishOrder.query.filter_by(order_id=order_id).all()

        if not orders_to_delete:
            return jsonify({"message": "No matching orders found in toc_replenish_order to delete."}), 404

        # Delete orders
        for order in orders_to_delete:
            db.session.delete(order)
        db.session.commit()

        orders_to_delete = TOCReplenishCtrl.query.filter_by(order_id=order_id).all()

        if not orders_to_delete:
            return jsonify({"message": "No matching orders found in toc_replenish_ctrl to delete."}), 404

        # Delete orders
        for order in orders_to_delete:
            db.session.delete(order)
        db.session.commit()

        return jsonify({"message": "Orders deleted successfully."}), 200
    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500


@main.route('/save_csv', methods=['POST'])
def save_csv():
    data = request.get_json()
    csv_data = data['csv_data']
    shop_data = json.loads(session.get('shop'))
    shop = shop_data['name']
    shop_code = shop_data['customer']

    # Create directory if it doesn't exist
    directory = os.path.join('app/static', shop_code)
    print(f"save file to directory: {directory}")
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Save CSV file with current store and date as filename
    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    date_str = shop_code+"_"+date_str
    file_path = os.path.join(directory, f'{date_str}.csv')
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(csv_data)

    return jsonify({'message': 'CSV saved successfully', 'file_path': file_path})


@main.route('/create_message', methods=['POST'])
def create_message():
    data = request.get_json()

    new_message = TocMessages(
        msg_date=data.get('msg_date'),
        msg_from=data.get('msg_from'),
        msg_to=data.get('msg_to'),
        msg_subject=data.get('msg_subject'),
        msg_body=data.get('msg_body'),
        msg_status=data.get('msg_status')
    )

    db.session.add(new_message)
    db.session.commit()

    return jsonify({'message': 'Message created successfully!', 'msg_id': new_message.msg_id}), 201

@main.route('/create_notification', methods=['POST'])
def create_notification():
    data = request.get_json()

    new_notification = TocNotification(
        not_date=data.get('not_date'),
        not_address=data.get('not_address'),
        not_subject=data.get('not_subject'),
        not_body=data.get('not_body'),
        not_status=data.get('not_status')
    )

    db.session.add(new_notification)
    db.session.commit()

    return jsonify({'message': 'Notification created successfully!', 'not_id': new_notification.not_id}), 201

@main.route('/get_all_notifications', methods=['GET'])
def get_all_notifications():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    notifications = TocNotification.query.filter_by(not_address=shop_name).all()
    notifications_list = [
        {
            'not_date': notification.not_date,
            'not_id': notification.not_id,
            'not_address': notification.not_address,
            'not_subject': notification.not_subject,
            'not_body': notification.not_body,
            'not_status': notification.not_status
        }
        for notification in notifications
    ]
    return jsonify(notifications_list)

@main.route('/get_unread_notifications', methods=['GET'])
def get_unread_notifications():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    notifications = TocNotification.query.filter_by(not_address=shop_name, not_status="unread").all()
    notifications_list = [
        {
            'not_date' : notification.not_date,
            'not_id': notification.not_id,
            'not_address': notification.not_address,
            'not_subject': notification.not_subject,
            'not_body': notification.not_body,
            'not_status': notification.not_status
        }
        for notification in notifications
    ]
    return jsonify(notifications_list)

@main.route('/api/toc_shops', methods=['GET'])
def get_toc_shops():
    shops = TOC_SHOPS.query.all()  # Query all rows
    shops_data = [
        {
            "blName": shop.blName,
            "blId": shop.blId,
            "country": shop.country,
            "timezone": shop.timezone,
            "store": shop.store,
            "customer": shop.customer,
            "mt_shop_name": shop.mt_shop_name,
        }
        for shop in shops
    ]
    return jsonify(shops_data)



@main.route('/api/open_orders', methods=['GET'])
def open_orders():
    new_orders = TOCReplenishCtrl.query.filter_by(order_status='New').all()

    # Return an empty array if no records are found
    if not new_orders:
        return jsonify([])

    order_data = [
        {
            "order_id": order.order_id,
            "shop_id": order.shop_id,
            "order_open_date": order.order_open_date,
            "user": order.user,
            "order_status": order.order_status,
            "order_status_date": order.order_status_date,
            "tracking_code": order.tracking_code,
        }
        for order in new_orders
    ]
    return jsonify(order_data)


@main.route('/get_and_mark_notifications', methods=['GET'])
def get_and_mark_notifications():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']

    # Retrieve unread notifications
    notifications = TocNotification.query.filter_by(not_address=shop_name, not_status="unread").all()

    # Mark notifications as read
    for notification in notifications:
        notification.not_status = "read"

    # Commit the changes to the database
    db.session.commit()

    # Prepare the list of notifications to return
    notifications_list = [
        {
            'not_date': notification.not_date,
            'not_id': notification.not_id,
            'not_address': notification.not_address,
            'not_subject': notification.not_subject,
            'not_body': notification.not_body,
            'not_status': notification.not_status
        }
        for notification in notifications
    ]

    return jsonify(notifications_list)

@main.route('/save_order', methods=['POST'])
def save_order():
    try:
        data = request.get_json()

        # Extract table data and parameters
        table = data.get('table', [])
        order_id = data.get('order_id', '')
        shop = data.get('shop', '')
        user_name = data.get('user_name', '')
        date = data.get('date', '')

        # Print the received data for debugging
        # print("order_id:", order_id)
        # print("Shop:", shop)
        # print("User Name:", user_name)
        # print("Save Date:", date)
        # print("Table Data:")
        # for row in table:
        #     print(row)

        # Check for order_id and delete existing records
        if order_id:
            db.session.query(TocStockOrder).filter_by(order_id=order_id).delete()

        # Insert new records into the table
        for row in table:
            sku, item_name, last_stock_qty, last_count_date,qty_sold, qty_bfr_rcv, rcv_qty, stock_count, order_qty,  comments = row

            new_record = TocStockOrder(
                shop_id=shop,
                order_open_date=datetime.strptime(date, '%Y%m%d%H%M'),
                sku=sku,
                order_id=order_id,
                user=user_name,
                item_name=item_name,
                order_qty=float(order_qty) if order_qty else 0,
                comments=comments,
                order_status="New",
                order_status_date=datetime.now(),
            )
            db.session.add(new_record)

        # Commit changes to the database
        db.session.commit()

        return jsonify({"status": "success", "message": "Data saved successfully"})

    except SQLAlchemyError as e:
        db.session.rollback()
        print("Database error:", e)
        return jsonify({"status": "error", "message": "Failed to save data", "error": str(e)}), 500

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500


@main.route('/save_replenish', methods=['POST'])
def save_replenish():
    try:
        user_data = json.loads(session.get('user'))

        data = request.get_json()

        # Extract table data and parameters
        table = data.get('table', [])
        order_id = data.get('order_id', '')
        shop = data.get('shop', '')
        user_name = data.get('user_name', '')
        date = data.get('date', '')
        tracking_code = data.get('tracking_code', '')
        sold_qty = data.get('sold_qty', '')
        replenish_qty = data.get('replenish_qty', '')
        type = data.get('type', '')
        status = "New"

        # Remove existing records if updating
        if order_id:
            db.session.query(TocReplenishOrder).filter_by(order_id=order_id).delete()
            db.session.query(TOCReplenishCtrl).filter_by(order_id=order_id).delete()
            db.session.query(TocDamaged).filter_by(order_id=order_id).delete()
            status = "Saved"
        else:
            status = "New"

        # Insert new rows into TocReplenishOrder (and TocDamaged if applicable)
        for row in table:
            if type == 'hq':
                sku, item_name, current_stock_qty, qty_sold_period, calc_replenish, replenish_order, comments = row
                damaged_qty = 0
            else:
                sku = row.get('sku', '')
                item_name = row.get('product_name', '')
                replenish_order = row.get('send_qty', 0)
                damaged_qty = row.get('damaged_qty', 0)
                comments = row.get('comments', '')
                current_stock_qty = "0"
                qty_sold_period = "0"
                calc_replenish = "0"

            # Insert into replenish order table
            new_record = TocReplenishOrder(
                shop_id=shop,
                order_open_date=datetime.now(),
                sku=sku,
                order_id=order_id,
                user=user_name,
                item_name=item_name,
                replenish_qty=float(replenish_order) if replenish_order else 0,
                rejected_qty=float(damaged_qty) if damaged_qty else 0,
                comments=comments
            )
            db.session.add(new_record)

            # If damaged quantity > 0, insert into TocDamaged
            if float(damaged_qty) > 0:
                damaged_record = TocDamaged(
                    shop_id=user_data['shop'],
                    order_id=order_id,
                    sku=sku,
                    order_open_date=datetime.now(),
                    user=user_name,
                    item_name=item_name,
                    rejected_qty=float(damaged_qty)
                )
                db.session.add(damaged_record)

        # Insert control row (tracking header)
        shop_name = user_data["shop"]
        from_shop = TOC_SHOPS.query.filter_by(blName=shop_name).first()

        new_record = TOCReplenishCtrl(
            order_id=order_id,
            shop_id=shop,
            order_open_date=datetime.now(),
            user=user_name,
            order_status=status,
            order_status_date=datetime.now(),
            tracking_code=tracking_code,
            sold_qty=sold_qty,
            replenish_qty=replenish_qty,
            sent_from=from_shop.store
        )
        db.session.add(new_record)

        db.session.commit()
        return jsonify({"status": "success", "message": "Data saved successfully"})

    except SQLAlchemyError as e:
        db.session.rollback()
        print("Database error:", e)
        return jsonify({"status": "error", "message": "Failed to save data", "error": str(e)}), 500

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500





@main.route('/submit_replenish', methods=['POST'])
def submit_replenish():
    try:
        data = request.get_json()


        order_id = data.get('order_id', '')

        user_name = data.get('user_name', '')

        tracking_code = data.get('tracking_code', '')

        # Check for order_id and delete existing records
        rec = TOCReplenishCtrl.query.filter_by(order_id=order_id).first()

        rec.order_status_date = datetime.now()
        rec.tracking_code = tracking_code
        rec.user = user_name
        rec.order_status = "Submitted"

        # Commit changes to the database
        db.session.commit()

        return jsonify({"status": "success", "message": "Data submitted successfully"})

    except SQLAlchemyError as e:
        db.session.rollback()
        print("Database error:", e)
        return jsonify({"status": "error", "message": "Failed to save data", "error": str(e)}), 500

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500



@main.route('/fetch_recent_orders', methods=['GET'])
def fetch_recent_orders():
    user_data = json.loads(session.get('user'))
    # 2/3/25 Add internal transfer - source shop
    shop_name = user_data["shop"]
    # Get the store code
    user_shop = TOC_SHOPS.query.filter_by(blName=shop_name).first()
    shop_code = user_shop.store

    # Fetch the 20 most recent orders sorted by `order_open_date` in descending order
    recent_orders = (
        db.session.query(TOCReplenishCtrl)
        .filter(TOCReplenishCtrl.sent_from == shop_code)  # 2/3/2025 Internal transfer Add filter condition
        .order_by(TOCReplenishCtrl.order_open_date.desc())
        # .limit(20)
        .all()
    )

    # Convert records to JSON
    result = [
        {
            "order_id": order.order_id,
            "shop_id": order.shop_id,
            "order_open_date": order.order_open_date.strftime("%Y-%m-%d %H:%M:%S") if order.order_open_date else None,
            "user": order.user,
            "order_status": order.order_status,
            "order_status_date": order.order_status_date.strftime("%Y-%m-%d %H:%M:%S") if order.order_status_date else None,
            "sold_qty" : order.sold_qty,
            "replenish_qty" :order.replenish_qty
        }
        for order in recent_orders
    ]

    return jsonify(result)

@main.route('/fetch_history_orders', methods=['GET'])
def fetch_history_orders():
    user_data = json.loads(session.get('user'))

    # Get the shop_name from the request parameters (if provided)
    shop_name = request.args.get("replenishShop")  # Default to Cannafoods International shop if not provided

    # Get the store code
    if shop_name == '':
        shop_code = '001'
    else:
        user_shop = TOC_SHOPS.query.filter_by(blName=shop_name).first()
        shop_code = user_shop.store

    # Fetch the 20 most recent orders sorted by `order_open_date` in descending order
    recent_orders = (
        db.session.query(TOCReplenishCtrl)
        .filter(TOCReplenishCtrl.sent_from == shop_code)  # 2/3/2025 Internal transfer Add filter condition
        .order_by(TOCReplenishCtrl.order_open_date.desc())
        # .limit(100)
        .all()
    )

    # Convert records to JSON
    result = [
        {
            "order_id": order.order_id,
            "shop_id": order.shop_id,
            "order_open_date": order.order_open_date.strftime("%Y-%m-%d %H:%M:%S") if order.order_open_date else None,
            "user": order.user,
            "order_status": order.order_status,
            "order_status_date": order.order_status_date.strftime("%Y-%m-%d %H:%M:%S") if order.order_status_date else None,
            "sold_qty" : order.sold_qty,
            "replenish_qty" :order.replenish_qty
        }
        for order in recent_orders
    ]

    return jsonify(result)


@main.route('/update_count_stock', methods=['POST'])
def update_count_stock():
    try:
        user_data = json.loads(session.get('user'))
        username = user_data['username']
        data = request.get_json()

        table = data.get('table', [])
        shop = data.get('shop', '')
        shop_name = data.get('shop_name', '')
        user_name = data.get('user_name', '')
        date = data.get('date', '')
        replenish_order_id = data.get('replenish_order_id', '')

        for row in table:
            sku = row.get('sku', '')
            product_name = row.get('product_name', '')
            stock_count = row.get('stock_count', 0)
            variance = row.get('variance', 0)
            stock_rejected = row.get('stock_rejected', 0)
            comments = row.get('comments', '')
            calc_stock_qty = row.get('current_qty', 0)
            last_stock_count = row.get('last_stock_count', 0)

            existing_record = TocStock.query.filter_by(shop_id=shop, sku=sku).first()
            if not existing_record:
                raise Exception("Shop SKU combination does not exist")

            # Update stock record
            existing_record.stock_qty_date = datetime.now(timezone.utc)
            existing_record.product_name = product_name
            existing_record.last_stock_qty = last_stock_count
            existing_record.stock_count = float(stock_count)
            existing_record.variance = float(variance)
            existing_record.stock_transfer = 0
            existing_record.rejects_qty = float(stock_rejected)
            existing_record.comments = comments
            existing_record.count_by = user_name
            existing_record.calc_stock_qty = float(calc_stock_qty)
            existing_record.final_stock_qty = float(stock_count)           # running stock
            existing_record.audit_count = float(stock_count)               # mirror for audit
            existing_record.shop_name = shop_name
            existing_record.replenish_id = replenish_order_id
            existing_record.pastel_ind = 0
            existing_record.pastel_count = -99

            # Insert variance row only when comments supplied (your current rule)
            if comments != '':
                new_variance_record = TOCStockVariance(
                    shop_id=shop,
                    sku=sku,
                    stock_qty_date=datetime.strptime(date, '%Y%m%d%H%M'),
                    product_name=product_name,
                    stock_count=float(stock_count),
                    count_by=user_name,
                    last_stock_qty=float(last_stock_count),
                    calc_stock_qty=float(calc_stock_qty),
                    variance=float(variance),
                    stock_recount=0,
                    shop_name=shop_name,
                    rejects_qty=float(stock_rejected),
                    final_stock_qty=float(stock_count),
                    comments=comments,
                    replenish_id=replenish_order_id
                )
                db.session.add(new_variance_record)

            # 🔎 AUDIT: manual count event, running stock = stock_count
            audit_comment = (f"Reset Count: {float(stock_count)}")
            log_stock_audit_entry(
                shop_id=shop,
                sku=sku,
                product_name=product_name,
                stock_count=stock_count,
                shop_name=shop_name,
                comments=audit_comment
            )

        # Upsert toc_count_ctrl -> Completed
        existing_ctrl = TocCountCtrl.query.get(replenish_order_id)
        if existing_ctrl:
            existing_ctrl.status = 'Completed'
        else:
            new_count_ctrl = TocCountCtrl(
                count_id=replenish_order_id,
                name=user_name,
                username=username,
                shop_id=shop,
                shop_name=shop_name,
                status='Completed'
            )
            db.session.add(new_count_ctrl)

        # Deadlock-safe commit
        from sqlalchemy.exc import OperationalError
        import time
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                db.session.commit()
                return jsonify({"status": "success", "message": "Stock data updated successfully"})
            except OperationalError as e:
                if 'Deadlock found' in str(e):
                    logger.warning(f"⚠️ Deadlock detected (attempt {attempt + 1}/{MAX_RETRIES}), retrying...")
                    db.session.rollback()
                    time.sleep(2)
                else:
                    raise
            except Exception as e:
                db.session.rollback()
                logger.exception("Error committing:")
                return jsonify({"status": "error", "message": "Commit failed", "error": str(e)}), 500

        return jsonify({"status": "error", "message": "Deadlock: too many retries"}), 500

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error:")
        return jsonify({"status": "error", "message": "Failed to update stock data", "error": str(e)}), 500

    except Exception as e:
        logger.exception("Error in update_count_stock:")
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500


@main.route('/save_count_draft', methods=['POST'])
def save_count_draft():
    try:
        data = request.get_json()
        count_id = data.get('count_id')
        username = data.get('username')
        shop_id = data.get('shop_id')
        shop_name = data.get('shop_name')
        counted_by = data.get('counted_by')
        rows = data.get('table', [])

        if not count_id or not shop_id or not username:
            return jsonify({'error': 'Missing required parameters'}), 400

        # Upsert control row
        ctrl = TocCountCtrl.query.get(count_id)
        if not ctrl:
            ctrl = TocCountCtrl(
                count_id=count_id,
                name=counted_by,
                username=username,
                shop_id=shop_id,
                shop_name=shop_name,
                status='Draft'
            )
            db.session.add(ctrl)
        else:
            ctrl.status = 'Draft'

        # Delete existing line items for this draft
        TocCount.query.filter_by(count_id=count_id).delete()

        for row in rows:
            db.session.add(TocCount(
                count_id=count_id,
                sku=row['sku'],
                stock_count=row['stock_count'],
                damaged_stock=row['stock_rejected'],
                comments=row['comments']
            ))

        db.session.commit()
        return jsonify({'message': 'Draft saved'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/load_count_draft', methods=['POST'])
def load_count_draft():
    try:
        data = request.get_json()
        shop_id = data.get('shop_id')
        if not shop_id:
            return jsonify({'error': 'Missing shop_id'}), 400

        ctrl = TocCountCtrl.query.filter_by(shop_id=shop_id, status='Draft').order_by(TocCountCtrl.creation_date.desc()).first()
        if not ctrl:
            return jsonify({'message': 'No draft found'}), 404

        items = TocCount.query.filter_by(count_id=ctrl.count_id).all()
        item_list = [{
            'sku': i.sku,
            'stock_count': i.stock_count,
            'stock_rejected': i.damaged_stock,
            'comments': i.comments
        } for i in items]

        return jsonify({
            'count_id': ctrl.count_id,
            'counted_by': ctrl.name,
            'table': [{
                'sku': i.sku,
                'stock_count': i.stock_count,
                'stock_rejected': i.damaged_stock,
                'comments': i.comments
            } for i in items]
        })


    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/check_count_draft', methods=['POST'])
def check_count_draft():
    data = request.get_json()
    shop_id = data.get('shop_id')

    if not shop_id:
        return jsonify({'error': 'Missing shop_id'}), 400

    drafts = TocCountCtrl.query.filter_by(shop_id=shop_id, status='Draft').all()

    if not drafts:
        return jsonify({'exists': False, 'draft_ids': []})

    draft_ids = [d.count_id for d in drafts]
    return jsonify({'exists': True, 'draft_ids': draft_ids})


@main.route('/delete_count_draft', methods=['POST'])
def delete_count_draft():
    data = request.get_json()
    shop_id = data.get('shop_id')

    if not shop_id:
        return jsonify({'error': 'Missing shop_id'}), 400

    from app import db
    from app.models import TocCount, TocCountCtrl

    # Step 1: Get all draft count_ids for the given shop
    draft_ctrls = TocCountCtrl.query.filter_by(shop_id=shop_id, status='Draft').all()
    draft_ids = [ctrl.count_id for ctrl in draft_ctrls]

    if not draft_ids:
        return jsonify({'message': 'No drafts found to delete'}), 200

    # Step 2: Delete from toc_count (line items)
    TocCount.query.filter(TocCount.count_id.in_(draft_ids)).delete(synchronize_session=False)

    # Step 3: Delete from toc_count_ctrl (headers)
    TocCountCtrl.query.filter(TocCountCtrl.count_id.in_(draft_ids)).delete(synchronize_session=False)

    db.session.commit()

    return jsonify({'message': f'Deleted drafts: {draft_ids}'})


#
# @main.route('/update_count_receive_stock', methods=['POST'])
# def update_count_receive_stock():
#     try:
#         data = request.get_json()
#
#         table = data.get('table', [])
#         shop = data.get('shop', '')                # receiving shop_id (customer)
#         shop_name = data.get('shop_name', '')      # receiving blName
#         user_name = data.get('user_name', '')
#         replenish_order_id = data.get('replenish_order_id', '')
#
#         for row in table:
#             sku           = row.get('sku', '')
#             product_name  = row.get('product_name', '')
#             sent_qty      = float(row.get('sent_qty', 0) or 0)           # for info
#             received_qty  = float(row.get('received_qty', 0) or 0)       # <-- use this
#             rcv_damaged   = float(row.get('received_damaged', 0) or 0)
#             variance      = float(row.get('variance', 0) or 0)
#             comments      = row.get('comments', '')
#
#             # --- 1) Receiving shop record ---
#             recv_stock = TocStock.query.filter_by(shop_id=shop, sku=sku).first()
#             if not recv_stock:
#                 raise Exception(f"Receiving shop {shop} SKU {sku} not found in toc_stock")
#
#             # --- 2) Replenishment row (for meta) ---
#             repl_line = TocReplenishOrder.query.filter_by(order_id=replenish_order_id, sku=sku).first()
#             if not repl_line:
#                 raise Exception(f"toc_replenish_order not found for {sku}")
#
#             # --- 3) Sending shop record (using control header sent_from) ---
#             sending_stock = (
#                 db.session.query(TocStock)
#                 .join(TOC_SHOPS, TocStock.shop_id == TOC_SHOPS.customer)
#                 .join(TOCReplenishCtrl, TOC_SHOPS.store == TOCReplenishCtrl.sent_from)
#                 .filter(
#                     TOCReplenishCtrl.order_id == replenish_order_id,
#                     TocStock.sku == sku
#                 )
#                 .first()
#             )
#             if not sending_stock:
#                 raise Exception(f"Sending shop for order {replenish_order_id} SKU {sku} not found")
#
#             # --- 4) Compute deltas ---
#             net_in = max(received_qty - rcv_damaged, 0.0)  # units added to receiving
#             recv_prior = recv_stock.audit_count if recv_stock.audit_count is not None else (
#                 recv_stock.final_stock_qty if recv_stock.final_stock_qty is not None else 0.0
#             )
#             recv_new = recv_prior + net_in
#
#             send_prior = sending_stock.audit_count if sending_stock.audit_count is not None else (
#                 sending_stock.final_stock_qty if sending_stock.final_stock_qty is not None else 0.0
#             )
#             send_new = send_prior - received_qty  # shipping shop loses what was shipped
#
#             # --- 5) Apply receiving shop updates ---
#             # Treat stock_transfer as “movement since last count”
#             recv_stock.stock_transfer = (recv_stock.stock_transfer or 0) + received_qty
#             recv_stock.rcv_damaged = rcv_damaged
#             # Keep your rejected logic (line-level rejected_qty on repl_line)
#             recv_stock.rejects_qty = float(repl_line.rejected_qty or 0)
#
#             recv_stock.final_stock_qty = recv_new
#             recv_stock.audit_count = recv_new
#
#             # --- 6) Apply sending shop updates ---
#             sending_stock.stock_transfer = (sending_stock.stock_transfer or 0) - received_qty
#             # Be conservative with final_stock_qty at source; we adjust audit_count (your running number)
#             sending_stock.audit_count = send_new
#
#             # --- 7) Update the replenishment line ---
#             repl_line.received_date = datetime.now(timezone.utc)
#             repl_line.received_qty = received_qty
#             repl_line.variance = variance
#             repl_line.received_by = user_name
#             repl_line.received_comment = comments
#
#             # --- 8) Damaged table line (if exists) ---
#             damaged_record = TocDamaged.query.filter_by(order_id=replenish_order_id, sku=sku).first()
#             if damaged_record:
#                 damaged_record.rcv_damaged = rcv_damaged
#                 damaged_record.variance = float(damaged_record.rejected_qty or 0) - rcv_damaged
#
#             # --- 9) Variance logging (kept as-is) ---
#             if variance != 0:
#                 db.session.add(TOCStockVariance(
#                     shop_id=shop,
#                     sku=sku,
#                     product_name=product_name,
#                     stock_count=received_qty,
#                     count_by=user_name,
#                     last_stock_qty=received_qty,   # prior behavior kept
#                     calc_stock_qty=sent_qty,
#                     variance=variance,
#                     stock_recount=0,
#                     shop_name=shop_name,
#                     final_stock_qty=received_qty,
#                     comments=comments,
#                     replenish_id=replenish_order_id
#                 ))
#
#             # --- 10) AUDIT rows for both shops ---
#             # Receiving
#             log_stock_audit_entry(
#                 shop_id=shop,
#                 sku=sku,
#                 product_name=product_name,
#                 stock_count=recv_new,  # running after receipt
#                 shop_name=shop_name,
#                 comments=f"Transfer IN: +{received_qty} (damaged {rcv_damaged}) • order {replenish_order_id}"
#             )
#
#             # Sending
#             send_shop_name = sending_stock.shop_name or "Source"
#             log_stock_audit_entry(
#                 shop_id=sending_stock.shop_id,
#                 sku=sku,
#                 product_name=product_name,
#                 stock_count=send_new,  # running after shipment
#                 shop_name=send_shop_name,
#                 comments=f"Transfer OUT: -{received_qty} → {shop_name} • order {replenish_order_id}"
#             )
#
#         # --- 11) Close the control header ---
#         ctrl = TOCReplenishCtrl.query.filter(
#             or_(TOCReplenishCtrl.order_status == "New", TOCReplenishCtrl.order_status == "Submitted"),
#             TOCReplenishCtrl.order_id == replenish_order_id
#         ).first()
#         if ctrl:
#             ctrl.order_status = "Completed"
#             ctrl.order_status_date = datetime.now(timezone.utc)
#
#         db.session.commit()
#         return jsonify({"status": "success", "message": "Stock data updated successfully"})
#
#     except SQLAlchemyError as e:
#         db.session.rollback()
#         logger.exception("Database error:")
#         return jsonify({"status": "error", "message": "Failed to update stock data", "error": str(e)}), 500
#
#     except Exception as e:
#         db.session.rollback()
#         logger.exception("Error in update_count_receive_stock:")
#         return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500

@main.route('/update_count_receive_stock', methods=['POST'])
def update_count_receive_stock():
    try:
        data = request.get_json()

        table = data.get('table', [])
        shop = data.get('shop', '')                # receiving shop_id (customer)
        shop_name = data.get('shop_name', '')      # receiving blName
        user_name = data.get('user_name', '')
        replenish_order_id = data.get('replenish_order_id', '')

        for row in table:
            sku           = row.get('sku', '')
            product_name  = row.get('product_name', '')
            sent_qty      = float(row.get('sent_qty', 0) or 0)           # what left source
            received_qty  = float(row.get('received_qty', 0) or 0)       # what arrived at dest (may include damaged)
            rcv_damaged   = float(row.get('received_damaged', 0) or 0)
            variance      = float(row.get('variance', 0) or 0)
            comments      = row.get('comments', '')

            # Safety: sender should always lose SENT qty (including damaged)
            out_qty = sent_qty if sent_qty > 0 else received_qty

            # --- 1) Receiving shop record ---
            recv_stock = TocStock.query.filter_by(shop_id=shop, sku=sku).first()
            if not recv_stock:
                raise Exception(f"Receiving shop {shop} SKU {sku} not found in toc_stock")

            # --- 2) Replenishment row (for meta) ---
            repl_line = TocReplenishOrder.query.filter_by(order_id=replenish_order_id, sku=sku).first()
            if not repl_line:
                raise Exception(f"toc_replenish_order not found for {sku}")

            # --- 3) Sending shop record (using control header sent_from) ---
            sending_stock = (
                db.session.query(TocStock)
                .join(TOC_SHOPS, TocStock.shop_id == TOC_SHOPS.customer)
                .join(TOCReplenishCtrl, TOC_SHOPS.store == TOCReplenishCtrl.sent_from)
                .filter(
                    TOCReplenishCtrl.order_id == replenish_order_id,
                    TocStock.sku == sku
                )
                .first()
            )
            if not sending_stock:
                raise Exception(f"Sending shop for order {replenish_order_id} SKU {sku} not found")

            # --- 4) Compute deltas ---
            # Receiving gets NET after damaged
            net_in = max(received_qty - rcv_damaged, 0.0)

            recv_prior = recv_stock.audit_count if recv_stock.audit_count is not None else (
                recv_stock.final_stock_qty if recv_stock.final_stock_qty is not None else 0.0
            )
            recv_new = recv_prior + net_in

            send_prior = sending_stock.audit_count if sending_stock.audit_count is not None else (
                sending_stock.final_stock_qty if sending_stock.final_stock_qty is not None else 0.0
            )

            # ✅ FIX: sending shop loses FULL sent qty (including damaged)
            send_new = send_prior - out_qty

            # --- 5) Apply receiving shop updates ---
            # Keep original behavior: movement shown at receiver is received_qty (you already like this)
            recv_stock.stock_transfer = (recv_stock.stock_transfer or 0) + received_qty
            recv_stock.rcv_damaged = rcv_damaged
            recv_stock.rejects_qty = float(repl_line.rejected_qty or 0)

            recv_stock.final_stock_qty = recv_new
            recv_stock.audit_count = recv_new

            # --- 6) Apply sending shop updates ---
            # ✅ FIX: movement at sender must reflect full sent qty
            sending_stock.stock_transfer = (sending_stock.stock_transfer or 0) - out_qty
            sending_stock.audit_count = send_new

            # --- 7) Update the replenishment line ---
            repl_line.received_date = datetime.now(timezone.utc)
            repl_line.received_qty = received_qty
            repl_line.variance = variance
            repl_line.received_by = user_name
            repl_line.received_comment = comments

            # --- 8) Damaged table line (if exists) ---
            damaged_record = TocDamaged.query.filter_by(order_id=replenish_order_id, sku=sku).first()
            if damaged_record:
                damaged_record.rcv_damaged = rcv_damaged
                damaged_record.variance = float(damaged_record.rejected_qty or 0) - rcv_damaged

            # --- 9) Variance logging (kept as-is) ---
            if variance != 0:
                db.session.add(TOCStockVariance(
                    shop_id=shop,
                    sku=sku,
                    product_name=product_name,
                    stock_count=received_qty,
                    count_by=user_name,
                    last_stock_qty=received_qty,
                    calc_stock_qty=sent_qty,
                    variance=variance,
                    stock_recount=0,
                    shop_name=shop_name,
                    final_stock_qty=received_qty,
                    comments=comments,
                    replenish_id=replenish_order_id
                ))

            # --- 10) AUDIT rows for both shops ---
            # Receiving audit (shows running after receipt)
            log_stock_audit_entry(
                shop_id=shop,
                sku=sku,
                product_name=product_name,
                stock_count=recv_new,
                shop_name=shop_name,
                comments=f"Transfer IN: +{received_qty} (damaged {rcv_damaged}) • order {replenish_order_id}"
            )

            # Sending audit (shows running after shipment) ✅ uses out_qty
            send_shop_name = getattr(sending_stock, "shop_name", None) or "Source"
            log_stock_audit_entry(
                shop_id=sending_stock.shop_id,
                sku=sku,
                product_name=product_name,
                stock_count=send_new,
                shop_name=send_shop_name,
                comments=f"Transfer OUT: -{out_qty} → {shop_name} (damaged {rcv_damaged}) • order {replenish_order_id}"
            )

        # --- 11) Close the control header ---
        ctrl = TOCReplenishCtrl.query.filter(
            or_(TOCReplenishCtrl.order_status == "New", TOCReplenishCtrl.order_status == "Submitted"),
            TOCReplenishCtrl.order_id == replenish_order_id
        ).first()
        if ctrl:
            ctrl.order_status = "Completed"
            ctrl.order_status_date = datetime.now(timezone.utc)

        db.session.commit()
        return jsonify({"status": "success", "message": "Stock data updated successfully (v2)"})

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error:")
        return jsonify({"status": "error", "message": "Failed to update stock data", "error": str(e)}), 500

    except Exception as e:
        db.session.rollback()
        logger.exception("Error in update_count_receive_stock_v2:")
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500




@main.route('/save_count_receive_stock', methods=['POST'])
def save_count_receive_stock():
    try:
        # Get JSON data from the request
        data = request.get_json()

        # Extract relevant information
        table = data.get('table', [])
        shop = data.get('shop', '')
        shop_name = data.get('shop_name', '')
        user_name = data.get('user_name', '')
        date = data.get('date', '')
        replenish_order_id = data.get('replenish_order_id', '')

        # Process each row and update the database
        for row in table:
            sku = row.get('sku', '')
            product_name = row.get('product_name', '')
            stock_sent = row.get('sent_qty', 0)
            stock_count = row.get('received_qty', 0)
            variance = row.get('variance', 0)
            # variance_rsn = row.get('variance_reason', 'NA')
            # stock_rejected = row.get('rejected_qty', 0)
            comments = row.get('comments', '')

            # Check if the record exists in TocStock
            existing_record = TocReplenishOrder.query.filter_by(
                order_id=replenish_order_id,
                sku=sku
            ).first()

            if existing_record:
                existing_record.received_qty = stock_count
                existing_record.received_comment = comments
            else:
                raise Exception("Shop SKU combination does not exist")

        # Commit changes to the database
        db.session.commit()

        return jsonify({"status": "success", "message": "Stock saved successfully"})

    except SQLAlchemyError as e:
        db.session.rollback()
        print("Database error:", e)
        return jsonify({"status": "error", "message": "Failed to save stock data", "error": str(e)}), 500

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500
    finally:
        db.session.close()


from datetime import datetime

from flask import request

@main.route('/log_user_activity', methods=['POST'])
def log_user_activity():
    try:
        # Retrieve user and shop data from the session
        user_data = session.get('user')
        user = json.loads(user_data)
        shop_data = session.get('shop')
        shop = json.loads(shop_data)

        # Get the activity description from the client
        activity = request.json.get('activity')
        if not activity:
            return {"error": "Activity description is required"}, 400

        # Create a new TOCUserActivity record
        new_activity = TOCUserActivity(
            user=user["username"],  # Assuming the username is stored in user["username"]
            shop=shop["customer"],  # Assuming the shop name is stored in shop["customer"]
            activity=activity
        )

        # Add the record to the session and commit to the database
        db.session.add(new_activity)
        db.session.commit()

        return {"message": "User activity logged successfully"}, 200

    except Exception as e:
        print(f"Error logging user activity: {e}")
        return {"error": "Failed to log user activity"}, 500


#####################################  Reports Section

@main.route('/timesheet_history')
def timesheet_history():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('timesheet_history_report.html', user=user, shop=shop, shops=list_of_shops, roles=roles_list)

@main.route('/sales_report')
def sales_report():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('sales_report_by_shop.html', user=user, shop=shop, shops=list_of_shops, roles=roles_list)

@main.route('/shipday_report')
def shipday_report():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('shipday_reports.html', user=user, shop=shop, shops=list_of_shops, roles=roles_list)

@main.route("/get_shipday_report", methods=["GET"])
def get_shipday_report():
    from_date = request.args.get("fromDate")
    to_date = request.args.get("toDate")

    if not from_date or not to_date:
        return jsonify({"error": "Missing date range"}), 400

    query = text("""
            SELECT
                s.wc_orderid,
                s.wc_name,
                s.wc_phone,
                s.shop_name,
                s.total_amt AS order_amount,
                s.creation_date,
                s.assigned_time,
                s.pickedup_time,
                s.delivery_time,
                s.shipday_distance_km,
                ROUND(s.driving_duration / 60, 1) AS driving_minutes,
                s.status AS order_status,
                d.full_name AS driver_name,
                s.driver_base_fee,
                d.phone_number AS driver_phone,
                s.payment_id,
            
                -- Driver react time: from assigned to pickup
                TIMESTAMPDIFF(MINUTE, s.assigned_time, s.pickedup_time) AS driver_react_time,
            
                -- Driver travel time: from pickup to delivery
                TIMESTAMPDIFF(MINUTE, s.pickedup_time, s.delivery_time) AS driver_travel_time,
            
                -- Order total time: from creation to delivery
                TIMESTAMPDIFF(MINUTE, s.creation_date, s.delivery_time) AS order_total_time
            
            FROM toc_shipday s
            LEFT JOIN toc_shipday_drivers d ON s.driver_id = d.driver_id
            WHERE DATE(s.creation_date) BETWEEN :from_date AND :to_date
            ORDER BY s.creation_date DESC;
    """)

    with db.engine.connect() as conn:
        result = conn.execute(query, {"from_date": from_date, "to_date": to_date})
        rows = result.fetchall()
        columns = result.keys()

    data = [dict(zip(columns, row)) for row in rows]
    response = {
        "columns": [{"title": col} for col in columns],
        "data": data
    }
    return jsonify(response)




@main.route('/variance_report')
def variance_report():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    return render_template('variance_report.html', user=user, shop=shop, shops=list_of_shops, roles=roles_list)


from flask import request, jsonify

@main.route('/get_business_report')
def get_business_report():
    try:
        # Retrieve parameters from the request
        report_type = request.args.get('reportType')  # Selected report type
        group_by = request.args.get('groupBy')        # Grouping option
        from_date = request.args.get('fromDate')      # Start date
        to_date = request.args.get('toDate')          # End date

        # Log the received parameters (for debugging purposes)
        print(f"Received Parameters:")
        print(f"Report Type: {report_type}")
        print(f"Group By: {group_by}")
        print(f"From Date: {from_date}")
        print(f"To Date: {to_date}")

        # Fetch the data from the function
        if report_type == "Detailed Shop Stock Report":
            data = get_stock_value()
        elif report_type == "Consolidated Shop Stock Report":
            data = get_stock_value_per_shop()
        elif report_type == "Transactions Report":
            data = get_transactions(from_date, to_date)
        elif report_type == "Online Transactions Report":
            data = get_online_transactions(from_date, to_date)
        elif report_type == "Product Category Per Staff":
            data = get_product_category_per_staff(from_date, to_date)
        elif report_type == "Casuals Timesheet History Report":
            data = get_timesheet_history(from_date, to_date)
        else:
            data = get_sales_report(report_type, from_date, to_date, group_by)

        # Check if no data is returned
        if not data:
            return jsonify({"message": "Error fetching report"}), 500

        # Extract column titles dynamically
        columns = [{"title": key} for key in data[0].keys()] if data else []

        # Return the formatted data along with column titles as JSON
        return jsonify({"columns": columns, "data": data})

    except Exception as e:
        # Handle any errors
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@main.route('/get_variance_report')
def get_variance_report():
    try:
        # Retrieve parameters from the request
        report_type = request.args.get('reportType')  # Selected report type
        group_by = request.args.get('groupBy')        # Grouping option
        from_date = request.args.get('fromDate')      # Start date
        to_date = request.args.get('toDate')          # End date

        # Log the received parameters (for debugging purposes)
        print(f"Received Parameters:")
        print(f"Report Type: {report_type}")
        print(f"Group By: {group_by}")
        print(f"From Date: {from_date}")
        print(f"To Date: {to_date}")

        # Fetch the data from the function
        # Fetch the data from the function
        if report_type == "Detailed Shop Stock Report":
            data = get_stock_value()
        elif report_type == "Back Order Report":
            data = get_back_order()
        elif report_type == "Consolidated Shop Stock Report":
            data = get_stock_value_per_shop()
        elif report_type == "Detailed Damaged Returns":
            data = get_detailed_damaged_return(from_date, to_date)
        elif report_type == "Consolidated Damaged Returns":
            data = get_consolidated_damaged_return(from_date, to_date)
        elif report_type == "Spotcheck Count Variance":
            data = get_spotcheck_variance_report(from_date, to_date)
        elif report_type == "Consolidated Variance Report":
            conn = get_db_connection()

            # Run SQL query (return raw date)
            query = """
          
            SELECT 
                shop_name, 
                DATE_FORMAT(stock_qty_date, '%%Y-%%m-%%d') AS raw_date,  -- Fetch actual date in yyyy-mm-dd format
                ROUND(SUM(a.variance * b.cost_price)) AS total_variance
            FROM toc_stock_variance a
            JOIN toc_product b ON a.sku = b.item_sku
            WHERE stock_qty_date > %s
            AND replenish_id LIKE '%%C'
            GROUP BY shop_name, raw_date;
            
            """

            # Read query into DataFrame, parse raw_date as a datetime column
            df = pd.read_sql(query, conn, params=[from_date], parse_dates=["raw_date"])

            # Close DB connection
            conn.close()

            # Pivot DataFrame using raw_date for sorting
            pivot_table = df.pivot(index='shop_name', columns='raw_date', values='total_variance').fillna(0)

            # Sort columns chronologically
            pivot_table = pivot_table.reindex(sorted(pivot_table.columns), axis=1)

            # Rename columns to 'DD-MMM' format after sorting
            pivot_table.rename(columns={col: col.strftime("%d-%b") for col in pivot_table.columns}, inplace=True)

            # Convert to list of dictionaries
            result_as_dicts = pivot_table.reset_index().to_dict(orient="records")

            # Extract column titles dynamically
            columns = [{"title": col} for col in pivot_table.reset_index().columns]

            # Return as JSON
            return jsonify({"columns": columns, "data": result_as_dicts})

        elif report_type == "Consolidated Spotcheck Variance Report":
            conn = get_db_connection()

            # Run SQL query (return raw date)
            query = """

            SELECT 
                shop_name, 
                DATE_FORMAT(stock_qty_date, '%%Y-%%m-%%d') AS raw_date,  -- Fetch actual date in yyyy-mm-dd format
                ROUND(SUM(a.variance * b.cost_price)) AS total_variance
            FROM toc_stock_variance a
            JOIN toc_product b ON a.sku = b.item_sku
            WHERE a.creation_date > %s
            AND replenish_id LIKE '%%S'
            GROUP BY shop_name, raw_date;

            """

            # Read query into DataFrame, parse raw_date as a datetime column
            df = pd.read_sql(query, conn, params=[from_date], parse_dates=["raw_date"])

            # Close DB connection
            conn.close()

            # Pivot DataFrame using raw_date for sorting
            pivot_table = df.pivot(index='shop_name', columns='raw_date', values='total_variance').fillna(0)

            # Sort columns chronologically
            pivot_table = pivot_table.reindex(sorted(pivot_table.columns), axis=1)

            # Rename columns to 'DD-MMM' format after sorting
            pivot_table.rename(columns={col: col.strftime("%d-%b") for col in pivot_table.columns}, inplace=True)

            # Convert to list of dictionaries
            result_as_dicts = pivot_table.reset_index().to_dict(orient="records")

            # Extract column titles dynamically
            columns = [{"title": col} for col in pivot_table.reset_index().columns]

            # Return as JSON
            return jsonify({"columns": columns, "data": result_as_dicts})

        elif report_type == "Consolidated Receive Variance":
            conn = get_db_connection()

            # Run SQL query (return raw date)
            query = """
                SELECT
                  a.shop_name,
                  DATE_FORMAT(a.creation_date, '%%Y-%%m-%%d') AS raw_date,
                  ROUND(SUM(a.variance * b.cost_price)) AS total_variance
                FROM toc_stock_variance a
                JOIN toc_product b ON a.sku = b.item_sku
                WHERE DATE(a.creation_date) >= %s
                  AND (a.replenish_id LIKE '%%R' OR a.replenish_id LIKE '%%I')
                GROUP BY a.shop_name, raw_date;

            """

            # Read query into DataFrame, parse raw_date as a datetime column
            df = pd.read_sql(query, conn, params=[from_date], parse_dates=["raw_date"])

            # Close DB connection
            conn.close()

            # Pivot DataFrame using raw_date for sorting
            pivot_table = df.pivot(index='shop_name', columns='raw_date', values='total_variance').fillna(0)

            # Sort columns chronologically
            pivot_table = pivot_table.reindex(sorted(pivot_table.columns), axis=1)

            # Rename columns to 'DD-MMM' format after sorting
            pivot_table.rename(columns={col: col.strftime("%d-%b") for col in pivot_table.columns}, inplace=True)

            # Convert to list of dictionaries
            result_as_dicts = pivot_table.reset_index().to_dict(orient="records")

            # Extract column titles dynamically
            columns = [{"title": col} for col in pivot_table.reset_index().columns]

            # Return as JSON
            return jsonify({"columns": columns, "data": result_as_dicts})

        else:
            data = get_db_variance_report(report_type,from_date,to_date,group_by)

        # Check if no data is returned
        if not data:
            return jsonify({"message": "Error fetching sales report"}), 500

        # Extract column titles dynamically
        columns = [{"title": key} for key in data[0].keys()] if data else []

        # Return the formatted data along with column titles as JSON
        return jsonify({"columns": columns, "data": data})

    except Exception as e:
        # Handle any errors
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500



@main.route('/count_new_orders')
def count_new_orders():
    shop_data = session.get('shop')
    shop = json.loads(shop_data)

    # Use or_ to combine conditions for order_status
    count = TOCReplenishCtrl.query.filter(
        or_(
            TOCReplenishCtrl.order_status == 'New',
            TOCReplenishCtrl.order_status == 'Submitted'
        ),
        TOCReplenishCtrl.shop_id == shop["customer"]
    ).count()

    return jsonify({"count": count})


######################################    database model ###################################################

@main.route('/get_top_items', methods=['GET'])
def get_top_items_route():
    top_items = get_top_items()
    return jsonify({'top_items': top_items})

@main.route('/sales_summary', methods=['GET'])
def sales_summary():
    data = get_sales_summary()
    return jsonify(data)


@main.route('/sales_data', methods=['GET'])
def sales_data():
    data = get_sales_data_for_lineChart()
    return jsonify(data)

@main.route('/sales_three_months', methods=['GET'])
def sales_three_months():
    user_shop = json.loads(session.get('user'))['shop']
    data = get_sales_by_shop_last_three_months(user_shop)
    # print(data)
    return jsonify(data)

@main.route('/sales_three_months_b2b', methods=['GET'])
def sales_three_months_b2b():
    user_shop = json.loads(session.get('user'))['shop']
    data = get_sales_by_shop_last_three_months_b2b(user_shop)
    # print(data)
    return jsonify(data)



@main.route('/sales', methods=['GET'])
def sales():
    # Retrieve 'from_date' and 'to_date' from request arguments
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    # Ensure 'to_date' includes the entire day (add 1 day and exclude midnight of the next day)
    if to_date:
        to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Get user shop name from session
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']

    # Call the updated database query function
    column_names, data = get_sales_data(shop_name, from_date, to_date)

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/sales_b2b', methods=['GET'])
def sales_b2b():
    # Retrieve 'from_date' and 'to_date' from request arguments
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    # Ensure 'to_date' includes the entire day (add 1 day and exclude midnight of the next day)
    if to_date:
        to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Get user shop name from session
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']

    # Call the updated database query function
    column_names, data = get_b2b_sales_data(shop_name, from_date, to_date)

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/shipday_sales', methods=['GET'])
def shipday_sales():
    # Retrieve 'from_date' and 'to_date' from request arguments
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    # Ensure 'to_date' includes the entire day (add 1 day and exclude midnight of the next day)
    if to_date:
        to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Get user shop name from session
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']

    # Call the updated database query function
    column_names, data = get_60MIN_Sales(shop_name, from_date, to_date)

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/product_sales', methods=['GET'])
def product_sales():
    # Retrieve 'from_date' and 'to_date' from request arguments
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    # Ensure 'to_date' includes the entire day (add 1 day and exclude midnight of the next day)
    if to_date:
        to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Get user shop name from session
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']

    # Call the updated database query function
    column_names, data = get_product_sales_data(shop_name, from_date, to_date)

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/product_sales_b2b', methods=['GET'])
def product_sales_b2b():
    # Retrieve 'from_date' and 'to_date' from request arguments
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    # Ensure 'to_date' includes the entire day (add 1 day and exclude midnight of the next day)
    if to_date:
        to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Get user shop name from session
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']

    # Call the updated database query function
    column_names, data = get_product_sales_data_b2b("b2b", from_date, to_date)

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })


@main.route('/recent_sales', methods=['GET'])
def recent_sales():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Simulated function to get columns and rows
    column_names, data = get_recent_sales(shop_name,from_date,to_date)  # Adjust to return column names and rows

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/recent_sales_b2b', methods=['GET'])
def recent_sales_b2b():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Simulated function to get columns and rows
    column_names, data = get_recent_sales_b2b("b2b",from_date,to_date)  # Adjust to return column names and rows

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/top_sellers', methods=['GET'])
def top_sellers():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Simulated function to get columns and rows
    column_names, data = get_top_sellers(shop_name,from_date,to_date)  # Adjust to return column names and rows

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/top_specials', methods=['GET'])
def top_specials():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Simulated function to get columns and rows
    column_names, data = get_top_specials (shop_name,from_date,to_date)  # Adjust to return column names and rows

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/top_brand', methods=['GET'])
def top_brand():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    to_date = (datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Simulated function to get columns and rows
    column_names, data = get_top_brand (shop_name,from_date,to_date)  # Adjust to return column names and rows

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/top-products/<timeframe>', methods=['GET'])
def get_top_products(timeframe):
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    data = get_product_sales(timeframe, shop_name)
    return jsonify(data)


@main.route('/hourly_sales/<timeframe>', methods=['GET'])
def hourly_sales(timeframe):
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    data = get_hourly_sales(shop_name, timeframe)
    return jsonify(data)

@main.route('/top_agent/<timeframe>', methods=['GET'])
def top_agent(timeframe):
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    column_names, data = get_top_agents(shop_name, timeframe)

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/recent_sales_product/<timeframe>', methods=['GET'])
def recent_sales_product(timeframe):
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    column_names, data = get_recent_product_sales(timeframe, shop_name)

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })


@main.route('/get_last_update', methods=['GET'])
def get_last_update():
    try:
        # SQL query to get the max end_date formatted as HH:mm
        query = text("SELECT DATE_FORMAT(DATE_ADD(MAX(end_date), INTERVAL 2 HOUR), '%H:%i') AS max_time FROM toc_sales_log WHERE source = 'LS' and comment like 'Compl%';")

        # Execute the query
        result = db.session.execute(query)

        # Fetch the result
        max_time = result.fetchone()[0]  # Assuming the result has a single row and single column

        # Return the result as JSON
        return jsonify({'success': True, 'last_update_time': max_time})

    except Exception as e:
        # Handle any errors
        return jsonify({'success': False, 'error': str(e)}), 500


@main.route('/get_user_activity', methods=['GET'])
def get_user_activity():

    # Simulated function to get columns and rows
    column_names, data = get_user_activities()  # Adjust to return column names and rows

    return jsonify({
        "columns": column_names,  # List of column names
        "rows": data  # List of row data
    })

@main.route('/get_replenish_data', methods=['GET'])
def get_replenish_data():

    order_id = request.args.get('order_id')

    # Simulated function to get columns and rows
    column_names, data = get_replenishment_data(order_id)  # Adjust to return column names and rows

    return jsonify({
        "columns": column_names,  # List of column names
        "data": data  # List of row data
    })

@main.route('/verify_order', methods=['POST'])
def verify_order():
    data = request.get_json()
    order_id = data.get('order_id')

    if not order_id:
        return jsonify({"success": False, "message": "Order ID is required"}), 400

    # Fetch the order from the database
    order = TOCReplenishCtrl.query.filter_by(order_id=order_id).first()

    if not order:
        return jsonify({"success": False, "message": "Order not found"}), 404

    try:
        # Update order status
        order.order_status = "Verified"
        order.order_status_date = datetime.utcnow()
        db.session.commit()

        return jsonify({"success": True, "message": "Order verified successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@main.route('/casual_timesheet')
def casual_timesheet():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    products = TocProduct.query.all()
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'casual_timesheet.html',
        user=user,
        shop = shop,
        shops=list_of_shops,
        roles=roles_list,
        products=products
    )


@main.route("/get_weeks", methods=["GET"])
def get_weeks():
    # Get today's date and determine the current week
    today = date.today()

    # Get the current week's record
    current_week = db.session.query(TOCWeeks).filter(TOCWeeks.from_date <= today, TOCWeeks.to_date >= today).first()

    if not current_week:
        return jsonify({"error": "Current week not found in toc_weeks"}), 404

    # Get the last 10 weeks including the current week, ordered in descending order
    weeks = (
        db.session.query(TOCWeeks)
        .filter(TOCWeeks.from_date <= current_week.from_date)
        .order_by(TOCWeeks.from_date.desc())
        .limit(11)  # Current week + last 10 weeks
        .all()
    )

    # Convert the results to JSON format
    data = [
        {
            "week": week.week,
            "from_date": week.from_date.strftime("%Y-%m-%d"),
            "to_date": week.to_date.strftime("%Y-%m-%d"),
        }
        for week in weeks
    ]

    return jsonify(data)

@main.route("/get_week_dates/<selected_week>", methods=["GET"])
def get_week_dates(selected_week):
    # Fetch the week data from the toc_weeks table
    week_data = TOCWeeks.query.filter_by(week=selected_week).first()

    if week_data is None:
        return jsonify({"error": "Week not found in the database"}), 404

    from_date = week_data.from_date
    to_date = week_data.to_date

    # Generate a list of dates from from_date to to_date (inclusive)
    dates = [(from_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((to_date - from_date).days + 1)]

    return jsonify(dates)

@main.route("/save_timesheet", methods=["POST"])
def save_timesheet():
    data = request.json
    shop_id = data.get("shop_id")
    week = data.get("week")
    manager = data.get("manager")
    timesheet = data.get("timesheet", [])

    print("Received Data:", data)  # Debugging

    for entry in timesheet:
        try:
            date = datetime.strptime(entry['date'], "%Y-%m-%d")  # Format: "09-Mar-2025"
        except ValueError as e:
            print(f"Date format error: {e}")
            continue  # Skip invalid dates

        casuals = entry.get("casuals", "")

        # **Check if TOCCasuals entry already exists**
        existing_entry = TOCCasuals.query.filter_by(shop_id=shop_id, date=date).first()

        if existing_entry:
            # **Update existing entry**
            existing_entry.casuals = casuals
            existing_entry.confirmed_by = manager
            existing_entry.confirmation_date = datetime.utcnow()
        else:
            # **Insert new entry if not found**
            new_entry = TOCCasuals(
                shop_id=shop_id,
                week=week,
                date=date,
                casuals=casuals,
                confirmed_by=manager,
                confirmation_date=datetime.utcnow()
            )
            db.session.add(new_entry)

    # **Check if TOCCasualsCtrl entry exists**
    existing_ctrl = TOCCasualsCtrl.query.filter_by(shop_id=shop_id, week=week).first()

    if existing_ctrl:
        # **Update existing status**
        existing_ctrl.status = "Updated"
        existing_ctrl.status_date = datetime.utcnow()
        existing_ctrl.confirmed_by = manager
    else:
        # **Insert new control entry**
        new_ctrl = TOCCasualsCtrl(
            shop_id=shop_id,
            week=week,
            status="Saved",
            status_date=datetime.utcnow(),
            confirmed_by=manager
        )
        db.session.add(new_ctrl)

    db.session.commit()
    return jsonify({"message": "Timesheet updated successfully"}), 200

@main.route("/confirm_timesheet", methods=["POST"])
def confirm_timesheet():
    data = request.json
    shop_id = data.get("shop_id")
    week = data.get("week")
    manager = data.get("manager")

    # Check if the entry exists in TOCCasualsCtrl
    existing_ctrl = TOCCasualsCtrl.query.filter_by(shop_id=shop_id, week=week).first()

    if existing_ctrl:
        # Update status to "Confirmed"
        existing_ctrl.status = "Confirmed"
        existing_ctrl.status_date = datetime.utcnow()
        existing_ctrl.confirmed_by = manager
        db.session.commit()
        return jsonify({"message": "Timesheet confirmed successfully"}), 200
    else:
        return jsonify({"error": "Timesheet not found"}), 404


@main.route("/get_timesheet_status/<shop_id>/<week>")
def get_timesheet_status(shop_id, week):
    entry = TOCCasualsCtrl.query.filter_by(shop_id=shop_id, week=week).first()

    if entry:
        return jsonify({"status": entry.status, "confirmed_by": entry.confirmed_by})

    # If no entry found, return status "Empty"
    return jsonify({"status": "Empty"}), 200


@main.route("/get_week_casuals/<shop_id>/<week>")
def get_week_casuals(shop_id, week):
    casuals = TOCCasuals.query.filter_by(shop_id=shop_id, week=week).all()

    if not casuals:
        return jsonify([])  # Return empty list if no casuals found

    return jsonify([
        {
            "date": casual.date.strftime("%Y-%m-%d"),
            "casuals": casual.casuals
        } for casual in casuals
    ])

@main.route("/update_user_login", methods=["POST"])
def update_user_login():
    user_data = session.get('user')
    user = json.loads(user_data)
    user_id = user["id"]
    user = User.query.get(user_id)

    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    data = request.get_json()

    try:
        user.last_login_date = datetime.now(timezone.utc)
        user.ip = data.get("ip")
        user.city = data.get("city")
        user.county = data.get("county")
        user.loc = data.get("loc")
        user.postal = data.get("postal")
        user.region = data.get("region")
        user.timezone = data.get("timezone")
        user.country_code = data.get("country_code")
        user.country_calling_code = data.get("country_calling_code")

        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

######################  SHIPDAY implementation ############################

import math

# Helper function to calculate the distance between two coordinates using the Haversine formula
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c  # Distance in kilometers
    return distance

@main.route('/get_closest_shop', methods=['GET'])
def get_closest_shop():
    try:
        order_id = request.args.get('order_id')
        if order_id:
            record = TocShipday.query.filter_by(wc_orderid=int(order_id)).first()
            if record and record.closest_shop_json:
                return jsonify(record.closest_shop_json), 200  # ✅ always jsonify with status
            else:
                return jsonify({"error": "No closest shop found for this order"}), 404

        # Fallback: legacy lat/lng logic
        customer_lat = float(request.args.get('latitude'))
        customer_lng = float(request.args.get('longitude'))

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Define the SQL query to get shop name, longitude, and latitude where longitude is not null
        query = """
            SELECT blName, longitude, latitude
            FROM toc_shops 
            WHERE longitude IS NOT NULL;
        """
        cursor.execute(query)
        shops = cursor.fetchall()
        cursor.close()
        conn.close()

        # Check if no data was returned
        if not shops:
            return jsonify({"status": "error", "message": "No shops found with longitude"}), 404

        # Find the closest shop using the Haversine formula
        closest_shop = None
        min_distance = float('inf')  # Start with an infinite distance

        for shop in shops:
            shop_name, shop_lng, shop_lat = shop  # Unpack the shop tuple

            # Ensure shop latitude and longitude are floats
            try:
                shop_lat = float(shop_lat)
                shop_lng = float(shop_lng)
            except ValueError as ve:
                print(f"Error converting shop coordinates: {ve}")
                continue  # Skip this shop if conversion fails

            # Calculate the distance using the haversine function
            distance = haversine(customer_lat, customer_lng, shop_lat, shop_lng)
            # print(f"Shop: {shop_name}, distance from customer address: {distance:.2f} Km")

            # Update the closest shop if this one is closer
            if distance < min_distance:
                min_distance = distance
                closest_shop = {
                    'shop_name': shop_name,
                    'longitude': shop_lng,
                    'latitude': shop_lat,
                    'distance': round(distance, 2)
                }

        # Return the closest shop information as JSON
        if closest_shop:
            return jsonify(closest_shop)

        return jsonify({"status": "error", "message": "No closest shop found"}), 500

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@main.route('/shipday_create_order', methods=['POST'])
def shipday_create_order():
    try:
        data = request.get_json()

        # Extract WooCommerce order details
        order_number = data.get('order_number')  # e.g., "WC420431"
        wc_orderid = int(order_number.replace("WC", ""))  # Strip prefix
        total_amt = data.get('total_amt') or 0

        customer_info = data.get('customer')
        pickup_info = data.get('pickup')
        items_info = data.get('items')
        delivery_note = data.get('delivery_instruction', '')
        pickup_note = data.get('pickup_instruction', '')
        payment_method = data.get('payment_method', 'ONLINE')

        # Insert basic record into toc_shipday
        new_record = TocShipday(
            wc_orderid=wc_orderid,
            wc_name=customer_info['name'],
            wc_email=customer_info['email'],
            wc_phone=customer_info['phone_number'],
            shop_name=pickup_info['name'],
            status='pending',
            total_amt=float(total_amt)
        )
        db.session.add(new_record)
        db.session.commit()

        # Build customer object
        customer_address = Address(**customer_info['address'])
        customer = Customer(
            name=customer_info['name'],
            address=customer_address,
            phone_number=customer_info['phone_number'],
            email=customer_info['email']
        )

        # ✅ Fetch shop info from the database using blName (shop_name)
        shop = TOC_SHOPS.query.filter_by(blName=pickup_info['name']).first()
        if not shop:
            raise Exception(f"Shop '{pickup_info['name']}' not found in database")

        # ✅ Use fields from TOC_SHOPS model
        pickup_address = Address(
            street=shop.address or "",
            city=shop.city or "",
            state=shop.state or "GP",
            country=shop.country or "South Africa",
            zip=shop.zip or "",
            latitude=float(shop.latitude),
            longitude=float(shop.longitude)
        )

        pickup = Pickup(
            name=shop.blName,
            phone_number=shop.phone,
            address=pickup_address
        )

        # Build order
        order_items = [OrderItem(**item) for item in items_info]
        new_order = Order(
            order_number=order_number,
            customer=customer,
            pickup=pickup,
            order_items=order_items,
            delivery_instruction=delivery_note,
            pickup_instruction=pickup_note,
            payment_method=payment_method
        )

        # 🧠 Only overwrite if present
        if 'latitude' in customer_info['address']:
            new_order.customer.address.latitude = customer_info['address']['latitude']
            new_order.customer.address.longitude = customer_info['address']['longitude']

        # ✅ Don't overwrite pickup coords — already pulled from DB
        # (skip setting pickup address.lat/lng here)

        # 🚀 Send to Shipday
        result = shipday_obj.OrderService.insert_order(new_order)
        shipday_id = result.get("orderId")

        # Update order with Shipday ID
        TocShipday.query.filter_by(wc_orderid=wc_orderid).update({
            "status": "completed",
            "shipday_id": shipday_id,
            "update_date": datetime.utcnow()
        })
        db.session.commit()

        return jsonify({"status": "success", "message": "Order accepted", "shipday_id": shipday_id}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/save_closest_shop', methods=['POST'])
def save_closest_shop():
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        shop = data.get('shop')
        print(f"order id {order_id}, shop {shop} XXXXXXXXXXXXXXXX")

        if not order_id or not shop:
            return jsonify({'error': 'Missing order_id or shop'}), 400

        record = TocShipday.query.filter_by(wc_orderid=order_id).first()
        if record:
            record.closest_shop_json = shop
            record.shop_name = shop.get("shop_name") or "Unknown"
            db.session.commit()
            return jsonify({'status': 'ok', 'message': f'Saved shop for order {order_id}'})
        else:
            return jsonify({'error': f'Order {order_id} not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500



@main.route('/check_shop_stock', methods=['POST'])
def check_shop_stock():
    try:
        from sqlalchemy.sql import text
        data = request.get_json()
        shop_name = data.get('shop_name')
        skus = data.get('skus')

        if not shop_name or not skus:
            return jsonify({"available": False, "error": "Missing shop_name or skus"}), 400

        # Prepare dynamic SKU placeholders
        placeholders = ','.join([f":sku_{i}" for i in range(len(skus))])
        sku_params = {f'sku_{i}': sku for i, sku in enumerate(skus)}

        # logger.warning(f"Check stock skus: {placeholders}")
        # logger.warning(f"Check stock sku_params: {sku_params}")

        sql = text(f"""
            WITH sales_data AS (
                SELECT
                    d.item_sku,
                    d.item_name,
                    b.store_customer,
                    c.blName AS shop_name,
                    COALESCE(SUM(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.quantity END), 0) AS sales_since_stock_read
                FROM toc_product d
                JOIN toc_ls_sales_item a ON d.item_sku = a.item_sku
                JOIN toc_ls_sales b ON a.sales_id = b.sales_id
                JOIN toc_shops c ON b.store_customer = c.customer
                JOIN toc_stock st ON d.item_sku = st.sku AND b.store_customer = st.shop_id
                WHERE d.acct_group <> 'Specials'
                    AND c.blName = :shop_name
                    AND d.item_sku <> '9568'
                    AND d.item_sku IN ({placeholders})
                GROUP BY d.item_sku, d.item_name, b.store_customer, c.blName, st.stock_qty_date

                UNION ALL

                SELECT
                    st.sku AS item_sku,
                    d.item_name,
                    st.shop_id AS store_customer,
                    c.blName AS shop_name,
                    0 AS sales_since_stock_read
                FROM toc_stock st
                JOIN toc_product d ON st.sku = d.item_sku AND d.acct_group <> 'Specials' AND d.item_sku <> '9568'
                JOIN toc_shops c ON st.shop_id = c.customer
                WHERE c.blName = :shop_name
                    AND st.sku IN ({placeholders})
                    AND NOT EXISTS (
                        SELECT 1
                        FROM toc_ls_sales_item a
                        JOIN toc_ls_sales b ON a.sales_id = b.sales_id
                        WHERE a.item_sku = st.sku AND b.store_customer = st.shop_id
                    )
            )
            SELECT
                s.item_sku,
                st.final_stock_qty,
                s.sales_since_stock_read,
                st.stock_transfer,
                (st.final_stock_qty - s.sales_since_stock_read + st.stock_transfer) AS current_stock_qty
            FROM sales_data s
            LEFT JOIN toc_stock st ON s.item_sku = st.sku AND s.store_customer = st.shop_id
        """)

        params = {'shop_name': shop_name}
        params.update(sku_params)

        # logger.warning(f"Check stock sku_params: {sql}")

        result = db.session.execute(sql, params).mappings().all()
        # logger.warning(f"✅ Rows returned from stock check: {len(result)}")

        if not result:
            return jsonify({
                "available": False,
                "out_of_stock_sku": skus[0],
                "reason": "SKU not found in stock data"
            })

        # Check if any item is out of stock
        for row in result:
            current_stock = row['current_stock_qty']
            # logger.warning(f"Check stock current stock: {current_stock}")
            if current_stock is None or current_stock <= 0:
                return jsonify({
                    "available": False,
                    "out_of_stock_sku": row['item_sku'],
                    "current_stock": current_stock
                })

        return jsonify({"available": True})


    except Exception as e:
        print(f"❌ Error in check_shop_stock: {e}")
        return jsonify({ "available": False, "error": str(e) }), 500

@main.route('/check_shop_stock_test', methods=['POST'])
def check_shop_stock_test():
    try:
        from sqlalchemy.sql import text
        data = request.get_json() or {}
        shop_name = data.get('shop_name')
        skus = data.get('skus')

        if not shop_name or not skus or not isinstance(skus, list):
            return jsonify({
                "error": "Missing or invalid payload. Expecting {shop_name: str, skus: [..]}."
            }), 400

        # Build placeholders for IN (...)
        placeholders = ','.join([f":sku_{i}" for i in range(len(skus))])
        sku_params = {f'sku_{i}': sku for i, sku in enumerate(skus)}

        sql = text(f"""
            WITH sales_data AS (
                SELECT 
                    d.item_sku,
                    d.item_name,
                    b.store_customer,
                    c.blName AS shop_name,
                    COALESCE(SUM(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.quantity END), 0) AS sales_since_stock_read
                FROM toc_product d
                JOIN toc_ls_sales_item a ON d.item_sku = a.item_sku
                JOIN toc_ls_sales b ON a.sales_id = b.sales_id
                JOIN toc_shops c ON b.store_customer = c.customer
                JOIN toc_stock st ON d.item_sku = st.sku AND b.store_customer = st.shop_id
                WHERE d.acct_group <> 'Specials'
                  AND c.blName = :shop_name
                  AND d.item_sku <> '9568'
                  AND d.item_sku IN ({placeholders})
                GROUP BY d.item_sku, d.item_name, b.store_customer, c.blName, st.stock_qty_date

                UNION ALL

                SELECT 
                    st.sku AS item_sku,
                    d.item_name,
                    st.shop_id AS store_customer,
                    c.blName AS shop_name,
                    0 AS sales_since_stock_read
                FROM toc_stock st
                JOIN toc_product d 
                  ON st.sku = d.item_sku 
                 AND d.acct_group <> 'Specials' 
                 AND d.item_sku <> '9568'
                JOIN toc_shops c ON st.shop_id = c.customer
                WHERE c.blName = :shop_name
                  AND st.sku IN ({placeholders})
                  AND NOT EXISTS (
                      SELECT 1
                      FROM toc_ls_sales_item a
                      JOIN toc_ls_sales b ON a.sales_id = b.sales_id
                      WHERE a.item_sku = st.sku AND b.store_customer = st.shop_id
                  )
            )
            SELECT 
                s.item_sku,
                COALESCE(st.final_stock_qty, 0)            AS final_stock_qty,
                COALESCE(s.sales_since_stock_read, 0)      AS sales_since_stock_read,                
                COALESCE(st.stock_transfer, 0)             AS stock_transfer,
                (COALESCE(st.final_stock_qty, 0)
                 - COALESCE(s.sales_since_stock_read, 0)
                 + COALESCE(st.stock_transfer, 0))         AS current_stock_qty
            FROM sales_data s
            LEFT JOIN toc_stock st 
              ON s.item_sku = st.sku 
             AND s.store_customer = st.shop_id
        """)

        params = {'shop_name': shop_name}
        params.update(sku_params)

        rows = db.session.execute(sql, params).mappings().all()

        # Build mapping from requested SKUs → current_stock_qty (default 0 if not returned)
        stocks = {sku: 0 for sku in skus}
        for r in rows:
            sku = r['item_sku']
            if sku in stocks:
                # If duplicates ever occur, last one wins (they should be identical for a given sku/shop)
                stocks[sku] = int(r.get('current_stock_qty') or 0)

        # Which SKUs didn’t show up in the result set at all? (Still report them as 0, but call them out)
        returned_skus = {r['item_sku'] for r in rows}
        not_found = [sku for sku in skus if sku not in returned_skus]

        logger.warning(f"check_shop_stock | shop='{shop_name}' | stocks={stocks} | not_found={not_found}")

        return jsonify({
            "shop_name": shop_name,
            "stocks": stocks,
            "not_found": not_found
        }), 200

    except Exception as e:
        print(f"❌ Error in check_shop_stock: {e}")
        return jsonify({"error": str(e)}), 500


@main.route('/create_lightspeed_order', methods=['POST'])
def create_lightspeed_order():
    from app.models import TocShipday, TOC_SHOPS  # your actual imports
    from datetime import datetime, timedelta, timezone

    try:
        data = request.get_json()
        wc_orderid = int(data.get('wc_orderid'))

        record = TocShipday.query.filter_by(wc_orderid=wc_orderid).first()
        if not record:
            return jsonify({"error": "Order not found"}), 404

        shop = TOC_SHOPS.query.filter_by(blName=record.shop_name).first()
        if not shop:
            return jsonify({"error": "Shop not found"}), 404

        tz = timezone(timedelta(hours=2))
        timestamp = datetime.now(tz).isoformat(timespec="seconds")

        # 🛒 Build items list
        # Build initial items list
        items = data.get("items", [])

        # ✅ Add required item
        items.append({
            "quantity": 1,
            "sku": "3401/001",
            "subItems": []
        })

        order_payload = {
            "businessLocationId": str(shop.blId),
            "thirdPartyReference": f"WC{wc_orderid}",
            "endpointId": "TEST",
            "customerInfo": {
                "firstName": record.wc_name.split()[0],
                "lastName": record.wc_name.split()[-1],
                "email": record.wc_email,
                "contactNumberAsE164": record.wc_phone
            },
            "deliveryAddress": {
                "addressLine1": record.wc_email,
                "addressLine2": record.shop_name
            },
            "accountProfileCode": "ONLINE",
            "payment": {
                "paymentMethod": "Online",
                "paymentAmount": f"{record.total_amt:.2f}"
            },
            "orderNote": "LOCAL PICKUP",
            "tableNumber": 1,
            "items": items
        }

        # #
        # # Send to Lightspeed
        headers = {
            "Authorization": f"Bearer {LIGHTSPEED_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }



        # TEST working payload from Heemal. Change the reference each time.

        # order_payload = {
        #     "businessLocationId": "195051644848426",
        #     "thirdPartyReference": "final test 5",
        #     "endpointId": "TEST",
        #     "customerInfo": {
        #         "firstName": "Tomer",
        #         "lastName": "Traub",
        #         "email": "tomer.traub@gmail.com",
        #         "contactNumberAsE164": "+2723456789"
        #     },
        #     "deliveryAddress": {
        #         "addressLine1": "test@gmail.com",
        #         "addressLine2": "Addressline2"
        #     },
        #     "accountProfileCode": "ONLINE",
        #     "payment": {
        #         "paymentMethod": "Online",
        #         "paymentAmount": "150.00"
        #     },
        #     "orderNote": "LOCAL PICKUP",
        #     "tableNumber": 1,
        #     "items": [
        #         {
        #             "quantity": 1,
        #             "sku": "4880",
        #             "subItems": []
        #         }
        #     ]
        # }

        logger = logging.getLogger(__name__)
        logger.warning(f"Lightspeed order: {order_payload}")

        res = requests.post("https://api.lsk.lightspeed.app/o/op/1/order/toGo",
                            headers=headers, json=order_payload)

        logger.warning(f"Lightspeed status: {res.status_code}")

        if res.status_code == 200:
            TocShipday.query.filter_by(wc_orderid=wc_orderid).update({
                "ls_order_id": f"{wc_orderid}"
            })
            db.session.commit()
            return jsonify({"status": "success", "ls_order_id": f"{wc_orderid}"})

        return jsonify({"error": res.text}), res.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main.route('/webhook/shipday', methods=['POST'])
def shipday_webhook():
    from datetime import datetime

    logger = logging.getLogger(__name__)
    logger.warning("🚨 Shipday webhook called")

    payload = request.get_json(force=True)
    logger.warning(f"📦 Raw payload: {payload}")

    order = payload.get("order", {})
    carrier = payload.get("carrier", {})
    event = payload.get("event")
    tracking_url = payload.get("trackingUrl")
    shipday_id = str(order.get("id"))
    logger.warning(f"🔎 Extracted shipday_id: {shipday_id}")

    shipday = db.session.query(TocShipday).filter_by(shipday_id=shipday_id).first()
    if not shipday:
        logger.warning(f"❌ Order {shipday_id} not found in toc_shipday")
        return "Order not found", 404

    def parse_epoch(ms):
        return datetime.fromtimestamp(ms / 1000.0) if ms else None

    if event == "ORDER_ACCEPTED_AND_STARTED":
        shipday.shipday_distance_km = order.get("driving_distance", 0) / 1000.0
        shipday.assigned_time = parse_epoch(order.get("assigned_time"))

        # 🚚 Driver base fee = 50 for first 5km, then 10/km
        distance_km = shipday.shipday_distance_km or 0
        shipday.driver_base_fee = 50 if distance_km <= 5 else round(50 + (distance_km - 5) * 10, 2)

        # Get correct driver info from carrier
        driver_id = str(carrier.get("id"))
        full_name = carrier.get("name", "").strip()
        phone_number = carrier.get("phone", "").strip()
        email = carrier.get("email", "").strip()

        existing_driver = db.session.query(TocShipdayDriver).filter_by(driver_id=driver_id).first()
        if not existing_driver:
            new_driver = TocShipdayDriver(
                driver_id=driver_id,
                full_name=full_name,
                phone_number=phone_number,
                email=email,
                active_status=1
            )
            db.session.add(new_driver)
            logger.warning(f"👤 Created driver {full_name}")
        else:
            # Optional: update contact info if it changed
            if (
                    existing_driver.full_name != full_name or
                    existing_driver.phone_number != phone_number or
                    existing_driver.email != email
            ):
                existing_driver.full_name = full_name
                existing_driver.phone_number = phone_number
                existing_driver.email = email
                existing_driver.last_update = datetime.utcnow()
                logger.warning(f"✏️ Updated driver info for {driver_id} - {full_name}")

        shipday.driver_id = driver_id


    # elif event == "ORDER_PICKEDUP":
    #     shipday.pickedup_time = parse_epoch(order.get("pickedup_time"))
    #     logger.warning(f"Event Pickudup. get pickup time: {shipday.pickedup_time}")
    elif event in ["ORDER_PICKEDUP", "ORDER_PIKEDUP"]:  # 👈 Add both
        shipday.pickedup_time = parse_epoch(order.get("pickedup_time"))
        logger.warning(f"📦 Picked up time set to: {shipday.pickedup_time}")

    elif event == "ORDER_COMPLETED":
        shipday.delivery_time = parse_epoch(order.get("delivery_time"))
        shipday.driving_duration = order.get("driving_duration", 0)

    # Set order status in WooCommerce to completed
    # 🔄 Sync to WooCommerce: mark as completed
    wc_order_id = shipday.wc_orderid.replace("WC", "")  # Strip 'WC' if it exists

    try:
        wc_api_url = f"https://tasteofcannabis.co.za/wp-json/wc/v3/orders/{wc_order_id}"
        wc_auth = (
            'ck_ff071fa1ba0d5e8b86a5d292591b13bdb7fcd9af',
            'cs_dcaf67ca6281e4ed724e10a5cc3aba3a836fd7d3'
        )
        payload = {"status": "completed"}

        response = requests.put(wc_api_url, auth=wc_auth, json=payload, timeout=10)

        if response.status_code == 200:
            logger.warning(f"✅ WooCommerce order {wc_order_id} marked as completed.")
        else:
            logger.warning(f"❌ Failed to update WooCommerce order {wc_order_id}. Status {response.status_code}: {response.text}")
    except Exception as e:
        logger.exception(f"🔥 Exception while updating WooCommerce order {wc_order_id}: {e}")

    shipday.shipping_status = order.get("status") or order.get("order_status")
    shipday.update_date = datetime.utcnow()

    db.session.commit()
    logger.warning(f"✅ Webhook update committed for order {shipday_id}")
    return "OK", 200


@main.route('/shipday/drivers', methods=['GET'])
def shipday_drivers_page():
    user_data = session.get('user')
    user = json.loads(user_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    drivers = TocShipdayDriver.query.all()
    return render_template('shipday-drivers.html', drivers=drivers, user=user, roles=roles_list)



@main.route('/shipday/driver/<int:driver_id>/payments', methods=['GET'])
def get_driver_payments(driver_id):
    payments = TocShipdayDriverPayment.query.filter_by(driver_id=driver_id).order_by(TocShipdayDriverPayment.created_at.desc()).all()
    results = [
        {
            'payment_id': p.payment_id,
            'total_amount': p.total_amount,
            'status': p.status,
            'note': p.note,  # 👈 Add this line
            'created_at': p.created_at.strftime('%Y-%m-%d %H:%M')
        }
        for p in payments
    ]
    return jsonify(results)



@main.route('/shipday/driver/<int:driver_id>/rides', methods=['GET'])
def get_driver_rides(driver_id):
    payment_id = request.args.get('payment_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = TocShipday.query.filter_by(driver_id=driver_id)
    if payment_id:
        query = query.filter_by(payment_id=payment_id)
    if start_date:
        query = query.filter(TocShipday.assigned_time >= start_date)
    if end_date:
        query = query.filter(TocShipday.assigned_time <= end_date)

    rides = query.order_by(TocShipday.assigned_time.desc()).all()
    results = [
        {
            'wc_orderid': r.wc_orderid,
            'assigned_time': r.assigned_time.strftime('%Y-%m-%d %H:%M') if r.assigned_time else '',
            'driver_base_fee': r.driver_base_fee,
            'status': r.status,
            'payment_id': r.payment_id,
        }
        for r in rides
    ]
    return jsonify(results)


@main.route('/shipday/driver/<int:driver_id>/pay', methods=['POST'])
def pay_driver(driver_id):
    unpaid_orders = TocShipday.query.filter_by(driver_id=driver_id, payment_id=None).all()
    if not unpaid_orders:
        return jsonify({'message': 'No unpaid orders found'}), 400

    note = request.form.get('note', '').strip()
    if not note:
        return jsonify({'message': 'Payment reference is required'}), 400

    total_amount = sum([o.driver_base_fee for o in unpaid_orders if o.driver_base_fee])
    new_payment = TocShipdayDriverPayment(
        driver_id=driver_id,
        total_amount=total_amount,
        status='paid',
        note=note,
        created_at=datetime.now()
    )
    db.session.add(new_payment)
    db.session.commit()

    for order in unpaid_orders:
        order.payment_id = new_payment.payment_id

    db.session.commit()
    return jsonify({'message': 'Driver paid successfully', 'payment_id': new_payment.payment_id})


@main.route("/shop_hours", methods=["GET", "POST"])
def shop_hours():
    try:
        import json
        from datetime import datetime
        from sqlalchemy import or_, case

        # ===============================
        # Standard TOC context
        # ===============================
        user_data = session.get("user")
        user = json.loads(user_data) if user_data else None

        shop_data = session.get("shop")
        shop = json.loads(shop_data) if shop_data else None

        roles = TocRole.query.all()
        roles_list = [
            {"role": r.role, "exclusions": r.exclusions}
            for r in roles
        ]

        # ===============================
        # Handle UPDATE
        # ===============================
        if request.method == "POST":
            shop_name   = request.form["shop_name"]
            day_of_week = request.form["day_of_week"]
            open_hour   = request.form["open_hour"]
            close_hour  = request.form["closing_hour"]

            row = TocShopsHours.query.filter_by(
                shop_name=shop_name,
                day_of_week=day_of_week
            ).first()

            if not row:
                raise Exception("Shop hours row not found")

            row.open_hour = datetime.strptime(open_hour, "%H:%M").time()
            row.closing_hour = datetime.strptime(close_hour, "%H:%M").time()

            db.session.commit()

            return redirect(
                url_for("main.shop_hours", shop_name=shop_name)
            )

        # ===============================
        # Handle VIEW
        # ===============================
        selected_shop = request.args.get("shop_name")

        shops = (
            db.session.query(TocShopsHours.shop_name)
            .distinct()
            .order_by(TocShopsHours.shop_name)
            .all()
        )

        q = TocShopsHours.query
        if selected_shop:
            q = q.filter(TocShopsHours.shop_name == selected_shop)

        hours = q.order_by(
            TocShopsHours.shop_name,
            case(
                (TocShopsHours.day_of_week == "Monday", 1),
                (TocShopsHours.day_of_week == "Tuesday", 2),
                (TocShopsHours.day_of_week == "Wednesday", 3),
                (TocShopsHours.day_of_week == "Thursday", 4),
                (TocShopsHours.day_of_week == "Friday", 5),
                (TocShopsHours.day_of_week == "Saturday", 6),
                (TocShopsHours.day_of_week == "Sunday", 7),
            )
        ).all()

        return render_template(
            "shop_hours.html",
            user=user,
            shop=shop,
            roles=roles_list,
            hours=hours,
            shops=[s[0] for s in shops],
            selected_shop=selected_shop
        )

    except Exception as e:
        print(f"Error in shop_hours route: {e}")
        return render_template(
            "pages-error-404.html",
            message="Failed to load shop hours"
        )




@main.route('/get_shop_hours', methods=['GET'])
def get_shop_hours():
    shop_name = request.args.get('shop_name')
    # logger.warning(f"👤 In get shop hours for shop:  {shop_name}")
    if not shop_name:
        return jsonify({'error': 'Missing shop_name parameter'}), 400

    today = datetime.now()
    day_of_week = today.strftime('%A')  # e.g., 'Monday'
    # logger.warning(f"Today's day of the week is:  {day_of_week}")

    try:
        record = TocShopsHours.query.filter_by(
            shop_name=shop_name.strip(),
            day_of_week=day_of_week
        ).first()

        # logger.warning(f"Return to client: {shop_name}, {day_of_week}, open hour: {record.open_hour.strftime('%H:%M')}, closing hour: {record.closing_hour.strftime('%H:%M')}")

        if not record:
            return jsonify({'error': 'Shop hours not found'}), 404

        return jsonify({
            'shop_name': shop_name,
            'day_of_week': day_of_week,
            'open_hour': record.open_hour.strftime('%H:%M'),
            'closing_hour': record.closing_hour.strftime('%H:%M')
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


#########################  OPENAI section  #####################
@main.route('/api/ask_business', methods=['POST'])
def ask_business():
    try:

        openai.api_key = current_app.config["OPENAI_KEY"]
        # Get the user question and username from frontend
        data = request.get_json()
        user_question = data.get('question')
        user_name = data.get('username')  # NEW: capture username

        user_data = json.loads(session.get('user'))
        username = user_data['username']
        shop_name = user_data['shop']

        if not user_question or not username:
            return jsonify({'error': 'Username and question are required.'}), 400

        # Build the system prompt
        system_prompt = f"""
You are a business data analyst working on an ERP system called "360".
ONLY respond with a clean MySQL SELECT query based on the database schema provided below.

Database Schema:
{DATABASE_SCHEMA}

Strict Rules:
- Only generate SELECT queries.
- Never modify, delete, insert, or drop anything.
- Never use ALTER, DELETE, UPDATE, DROP, INSERT commands.
- Always use MySQL syntax.
- Limit the results to 100 rows unless user explicitly says otherwise.
- **If more than one table is used, always prefix field names with the table name.**
- Reply ONLY with the SQL inside triple backticks (```) and nothing else.

User's Question:
"{user_question}"

Example format you must use:
```sql
SELECT * FROM toc_ls_sales LIMIT 10;
"""
        # Send prompt to OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # or "gpt-4-turbo" if you prefer
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0
        )

        # Extract SQL from OpenAI response
        chat_response = response['choices'][0]['message']['content']
        match = re.search(r'```sql\s*(.*?)\s*```', chat_response, re.DOTALL)
        if not match:
            return jsonify({'error': 'Failed to extract SQL from AI response.'}), 500

        generated_sql = match.group(1).strip()

        # Validate SQL (only SELECT allowed)
        if not is_safe_sql(generated_sql):
            return jsonify({'error': 'Generated SQL is unsafe or invalid.'}), 400

        # Execute the safe SQL query
        columns, rows = execute_sql(generated_sql)

        # Format the result into HTML Bootstrap table
        table_html = '<table class="table table-striped table-bordered table-hover table-sm">'
        table_html += '<thead><tr>' + ''.join(f'<th>{col}</th>' for col in columns) + '</tr></thead><tbody>'
        for row in rows:
            table_html += '<tr>' + ''.join(f'<td>{row[col]}</td>' for col in columns) + '</tr>'
        table_html += '</tbody></table>'

        # NEW: Save user query into toc_openai
        from app.models import TOCOpenAI  # Import your model
        from app import db  # Import your db object

        new_record = TOCOpenAI(
            username=username,
            name=user_name,        # Optional until you provide better info
            shop_name=shop_name,
            user_query=user_question
        )
        db.session.add(new_record)
        db.session.commit()

        # Return SQL + results to frontend
        return jsonify({
            'generated_sql': generated_sql,
            'result_html': table_html
        })

    except Exception as e:
        logger.exception("💥 Error in /api/ask_business:")  # DEBUG print
        return jsonify({'error': str(e)}), 500


############################## END OPENAI section######################################

#####  ONLINE SALES WITH GOOGLE API
# ---------- Online Sales Heat Map ----------

@main.route('/online_sales')
def online_sales():
    # Same pattern as your other pages: pass user/roles/shops to template
    user_data = session.get('user')
    if not user_data:
        return redirect(url_for('main.login'))
    user = json.loads(user_data)

    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]

    # Browser key for JS Maps API (keep this restricted to HTTP referrers)
    google_maps_key = os.getenv('GOOGLE_MAPS_API_KEY', '')

    return render_template(
        'online_sales.html',
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        GOOGLE_MAPS_API_KEY=google_maps_key
    )


@main.route('/api_online_sales_regions')
def api_online_sales_regions():
    sql = text("""
        SELECT DISTINCT shipping_state
        FROM toc_wc_sales_order
        WHERE shipping_state IS NOT NULL AND shipping_state <> ''
        ORDER BY shipping_state
    """)
    rows = db.session.execute(sql).fetchall()
    return jsonify([{'shipping_state': r[0]} for r in rows])


@main.route('/api_online_sales_heatmap')
def api_online_sales_heatmap():
    # expected query params from the page JS
    from_date = request.args.get('from')  # 'YYYY-MM-DD'
    to_date   = request.args.get('to')    # 'YYYY-MM-DD'
    region    = request.args.get('region', '')

    # Default to MTD if dates missing
    if not from_date or not to_date:
        today = datetime.utcnow().date()
        from_date = today.replace(day=1).strftime('%Y-%m-%d')
        to_date   = today.strftime('%Y-%m-%d')

    sql = text("""
        SELECT
          order_id,
          order_date,
          customer_name,
          total_amount,
          shipping_city,
          shipping_state,
          shipping_latitude,
          shipping_longitude
        FROM toc_wc_sales_order
        WHERE order_date >= :from_date
          AND order_date < DATE_ADD(:to_date, INTERVAL 1 DAY)
          AND (:region = '' OR shipping_state = :region)
        ORDER BY order_date DESC
    """)

    rows = db.session.execute(sql, {
        'from_date': from_date,
        'to_date': to_date,
        'region': region
    }).mappings().all()

    out = []
    for r in rows:
        out.append({
            'order_id': r['order_id'],
            'order_date': (r['order_date'].isoformat()
                           if hasattr(r['order_date'], 'isoformat')
                           else str(r['order_date'])),
            'customer_name': r['customer_name'],
            'total_amount': float(r['total_amount'] or 0),
            'shipping_city': r['shipping_city'],
            'shipping_state': r['shipping_state'],
            'shipping_latitude': (float(r['shipping_latitude'])
                                  if r['shipping_latitude'] is not None else None),
            'shipping_longitude': (float(r['shipping_longitude'])
                                   if r['shipping_longitude'] is not None else None),
        })
    return jsonify(out)

####f Audit Stock movement
@main.route("/stock_movement")
def stock_movement():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    # Load shops and items
    shops = db.session.execute(text("SELECT customer, blName FROM toc_shops ORDER BY blName")).fetchall()
    items = db.session.execute(text("""
        SELECT item_sku, item_name 
        FROM toc_product 
        WHERE acct_group not in ( 'Specials','Non stock Item' )
        ORDER BY item_name
    """)).fetchall()

    return render_template(
        "stock_movement.html",
        user=user,
        shop=shop,
        roles=roles_list,
        shops=shops,
        items=items
    )


from sqlalchemy import bindparam

from datetime import datetime, timedelta
from sqlalchemy import bindparam, text

@main.route("/get_stock_movement")
def get_stock_movement():
    shop = request.args.get("shop")
    items = tuple(request.args.get("items").split(","))
    fromDate = request.args.get("fromDate")      # 'YYYY-MM-DD'
    toDate = request.args.get("toDate")          # 'YYYY-MM-DD'

    # Make the "to" date inclusive: use next day as an exclusive upper bound
    toDate_exclusive = (datetime.strptime(toDate, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    sql = text("""
        SELECT id, creation_date, shop_id, sku, product_name, stock_count, shop_name, comments
        FROM toc_stock_audit
        WHERE shop_id = :shop
          AND sku IN :items
          AND creation_date >= :fromDate
          AND creation_date < :toDateExclusive
        ORDER BY sku ASC, creation_date DESC
    """).bindparams(bindparam("items", expanding=True))

    result = db.session.execute(sql, {
        "shop": shop,
        "items": items,
        "fromDate": fromDate,
        "toDateExclusive": toDate_exclusive
    }).mappings().all()

    rows = [dict(r) for r in result]
    if not rows:
        return jsonify({"columns": [], "data": []})

    columns = [{"title": col} for col in rows[0].keys()]
    return jsonify({"columns": columns, "data": rows})


############################## END ONLINE SALES GOOGLE API section######################################

###########################  System Tables  #####################


def _get_toc_tables():
    sql = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
          AND table_name LIKE 'toc%'
        ORDER BY table_name
    """)
    rows = db.session.execute(sql).fetchall()
    return [r[0] for r in rows]

@main.route("/system_tables")
def system_tables():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    # Load shops and items
    shops = db.session.execute(text("SELECT customer, blName FROM toc_shops ORDER BY blName")).fetchall()
    toc_tables = _get_toc_tables()
    return render_template("system_tables.html", toc_tables=toc_tables,user=user,
        shop=shop,
        roles=roles_list,
        shops=shops)

@main.route("/api/system_table_data")
def api_system_table_data():
    table = request.args.get("table", "", type=str)
    row_limit = request.args.get("limit", default=5000, type=int)
    if row_limit <= 0:
        row_limit = 5000

    # Allow only known toc% tables
    allowed = set(_get_toc_tables())
    if table not in allowed:
        return jsonify({"error": f"Table '{table}' is not allowed."}), 400

    # Run the select
    sql = text(f"SELECT * FROM `{table}` LIMIT :limit_val")
    result = db.session.execute(sql, {"limit_val": row_limit})

    # Columns
    cols = list(result.keys())

    # Rows -> list of dicts; coerce non-JSON types to strings
    data = []
    for row in result.mappings():
        rec = {}
        for c in cols:
            v = row[c]
            if isinstance(v, (bytes, bytearray)):
                v = f"<{len(v)} bytes>"
            # Convert unsupported types to string
            if v is not None and not isinstance(v, (str, int, float, bool)):
                v = str(v)
            rec[c] = v
        data.append(rec)

    return jsonify({"columns": cols, "data": data})


#############################  Best Before Customization ##############################

#### Handle Suppliers

def supplier_to_dict(s):
    return {
        'id': s.id,
        'name': s.name,
        'vendor_code': s.vendor_code,
        'vat_registered': s.vat_registered,
        'vat_number': s.vat_number,
        'contact_person': s.contact_person,
        'contact_email': s.contact_email,
        'contact_phone': s.contact_phone,
        'address': s.address,
        'status': s.status,
        'payment_terms': s.payment_terms,
        'default_ship_to_store': s.default_ship_to_store,
        'document_received': s.document_received,
        'document_notes': s.document_notes,
    }


@main.route('/suppliers', methods=['GET', 'POST'])
def suppliers():
    if request.method == 'POST':
        mode = request.form.get('form_mode')
        supplier_id = request.form.get('supplier_id')

        if mode == 'add':
            supplier = BbSupplier()
            db.session.add(supplier)
            flash('Supplier added successfully.', 'success')
        else:
            supplier = BbSupplier.query.get_or_404(supplier_id)
            flash('Supplier updated successfully.', 'success')

        supplier.name = request.form['name']
        supplier.vendor_code = request.form.get('vendor_code')
        supplier.vat_registered = 'vat_registered' in request.form
        supplier.vat_number = request.form.get('vat_number')
        supplier.contact_person = request.form.get('contact_person')
        supplier.contact_email = request.form.get('contact_email')
        supplier.contact_phone = request.form.get('contact_phone')
        supplier.address = request.form.get('address')
        supplier.status = request.form.get('status', 'Active')
        supplier.payment_terms = request.form.get('payment_terms')
        supplier.default_ship_to_store = request.form.get('default_ship_to_store')
        supplier.document_received = 'document_received' in request.form
        supplier.document_notes = request.form.get('document_notes')
        supplier.updated_at = datetime.utcnow()

        db.session.commit()
        return redirect(url_for('main.suppliers'))

    # --------------------------
    # Restore application context
    # --------------------------
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}
    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]
    products = TocProduct.query.all()

    supplier_list = BbSupplier.query.order_by(BbSupplier.name).all()
    suppliers_dicts = [supplier_to_dict(s) for s in supplier_list]

    return render_template('supplier_list.html',
        suppliers=supplier_list,
        suppliers_dicts=suppliers_dicts,
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        products=products
    )



@main.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
def delete_supplier(supplier_id):
    supplier = BbSupplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    flash('Supplier deleted.', 'warning')
    return redirect(url_for('main.suppliers'))

#############  Handle product

def product_to_dict(product):
    return {
        'item_sku': product.item_sku,
        'item_name': product.item_name,
        'supplier_id': product.supplier_id,
        'cost_price': str(product.cost_price or ''),
        'retail_price': str(product.retail_price or ''),
        'uom': product.uom or '',
        'size': product.size or '',
        'is_active': product.is_active,
        'vat_exempt_ind': product.vat_exempt_ind  # NEW
    }


@main.route('/products', methods=['GET', 'POST'])
def admin_products_po():
    if request.method == 'POST':
        form_mode = request.form.get('form_mode')
        sku = request.form.get('item_sku')
        vat_exempt = 'vat_exempt_ind' in request.form  # NEW

        if form_mode == 'add':
            product = TocProduct(
                item_sku=sku,
                item_name=request.form.get('item_name'),
                supplier_id=request.form.get('supplier_id'),
                cost_price=request.form.get('cost_price'),
                retail_price=request.form.get('retail_price'),
                uom=request.form.get('uom'),
                size=request.form.get('size'),
                is_active='is_active' in request.form,
                vat_exempt_ind=vat_exempt  # NEW
            )
            db.session.add(product)
            flash('Product added successfully.', 'success')

        elif form_mode == 'edit':
            product = TocProduct.query.get(sku)
            if product:
                product.item_name = request.form.get('item_name')
                product.supplier_id = request.form.get('supplier_id')
                product.cost_price = request.form.get('cost_price')
                product.retail_price = request.form.get('retail_price')
                product.uom = request.form.get('uom')
                product.size = request.form.get('size')
                product.is_active = 'is_active' in request.form
                product.vat_exempt_ind = vat_exempt  # NEW
                flash('Product updated successfully.', 'success')
            else:
                flash('Product not found.', 'danger')

        db.session.commit()
        return redirect(url_for('main.admin_products'))

    # GET request handling
    products_raw = TocProduct.query.order_by(TocProduct.item_name).all()
    product_dicts = [product_to_dict(p) for p in products_raw]
    suppliers = BbSupplier.query.filter_by(status='Active').order_by(BbSupplier.name).all()
    suppliers_dicts = [supplier_to_dict(s) for s in suppliers]

    # Restore session context
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}
    roles = TocRole.query.all()
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]

    return render_template(
        'product_list.html',
        products=products_raw,
        product_dicts=product_dicts,
        suppliers=suppliers,
        suppliers_dicts=suppliers_dicts,
        user=user,
        shops=list_of_shops,
        roles=roles_list
    )

@main.route('/products/delete/<string:sku>', methods=['POST'])
def delete_product_po(sku):
    product = TocProduct.query.get_or_404(sku)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted.', 'warning')
    return redirect(url_for('main.admin_products'))

###### Handle Purchase Order ######

def status_color(status):
    return {
        'Draft': 'secondary',
        'Submitted': 'primary',
        'Approved': 'success',
        'Sent': 'info',
        'Partially Received': 'warning',
        'Completed': 'dark',
        'Short Closed': 'warning',
        'Cancelled': 'danger',
    }.get(status, 'secondary')


@main.route('/purchase_orders', methods=['GET', 'POST'])
def purchase_orders():
    from .models import BbPurchaseOrder, BbSupplier, TocProduct, TocRole, TOC_SHOPS, User

    if request.method == 'POST':
        form = request.form
        supplier_id = form.get('supplier_id')
        approved_by = form.get('approved_by')
        ship_to_store = form.get('ship_to_store')
        expected_delivery_date = form.get('expected_delivery_date')
        po_terms = form.get('po_terms')
        notes = form.get('notes')

        if not approved_by:
            flash("Approval is required to create a PO.", "danger")
            return redirect(url_for('main.purchase_orders'))

        # Generate PO number: <YEAR><MONTH><DAY><HOUR><MIN><Supplier Code>
        now = datetime.utcnow()
        timestamp = now.strftime("%Y%m%d%H%M")
        supplier = BbSupplier.query.get(supplier_id)
        vendor_code = supplier.vendor_code or f"S{supplier_id}"
        po_number = generate_vendor_specific_po_number(supplier_id)

        po = BbPurchaseOrder(
            po_number=po_number,
            supplier_id=supplier_id,
            ship_to_store=ship_to_store,
            created_by=session.get('user_id'),  # assumed to be saved on login
            approved_by=approved_by,
            expected_delivery_date=expected_delivery_date,
            order_date=now,
            po_terms=po_terms,
            notes=notes,
            status='Approved',  # Defaulting to Approved after form submission
            approved_at=now
        )
        db.session.add(po)
        db.session.commit()

        flash(f"PO {po_number} created successfully.", "success")
        return redirect(url_for('main.purchase_orders'))

    # --------------------------
    # Restore application context
    # --------------------------
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}
    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]
    products = TocProduct.query.all()
    supplier_list = BbSupplier.query.order_by(BbSupplier.name).all()

    pos = BbPurchaseOrder.query.order_by(BbPurchaseOrder.created_at.desc()).all()

    for po in pos:
        po.items = BbPurchaseOrderItem.query.filter_by(po_id=po.id).all()
        po.supplier = BbSupplier.query.get(po.supplier_id)
        po.created_by_user = User.query.get(po.created_by)
        po.approved_by_user = User.query.get(po.approved_by) if po.approved_by else None

    return render_template('po_list.html',
        pos=pos,
        suppliers=supplier_list,
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        products=products,
        status_color=status_color
    )



@main.route('/po_create', methods=['GET', 'POST'])
def po_create():
    if request.method == 'POST':
        try:
            po_id = request.form.get('po_id')
            supplier_id = request.form['supplier_id']
            approved_by = session.get('user_id') or 1
            note = request.form.get('note') or ''
            status = request.form.get('status', 'Draft')
            status_date = datetime.now(timezone.utc)
            vat_amount = float(request.form.get('vat_amount', 0))

            now = datetime.now()

            if po_id:
                po = BbPurchaseOrder.query.get(po_id)
                po.supplier_id = supplier_id
                po.status = status
                po.status_date = status_date
                po.notes = note
                po.approved_by = approved_by
                po.approved_at = now
                po.subtotal = 0
                po.vat_amount = vat_amount
                BbPurchaseOrderItem.query.filter_by(po_id=po.id).delete()
            else:
                supplier = BbSupplier.query.get(supplier_id)
                supplier_code = supplier.vendor_code or f"SUP{supplier_id}"
                po_number = generate_vendor_specific_po_number(supplier_id)

                po = BbPurchaseOrder(
                    po_number=po_number,
                    supplier_id=supplier_id,
                    created_by=approved_by,
                    approved_by=approved_by,
                    status=status,
                    status_date=status_date,
                    order_date=now,
                    created_at=now,
                    approved_at=now,
                    notes=note
                )
                db.session.add(po)
                db.session.flush()

            # Extract item fields
            skus = request.form.getlist('sku[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            # raw_dates = request.form.getlist('best_before[]')
            tax_amounts = request.form.getlist('vat[]')
            line_totals = request.form.getlist('line_total[]')

            # best_before_dates = [
            #     datetime.strptime(d, '%Y-%m-%d').date() if d else None for d in raw_dates
            # ]

            subtotal = 0
            for i in range(len(skus)):
                if skus[i] and quantities[i]:
                    qty = float(quantities[i])
                    price = float(unit_prices[i])
                    tax = float(tax_amounts[i]) if i < len(tax_amounts) else 0
                    total = float(line_totals[i]) if i < len(line_totals) else qty * price

                    subtotal += qty * price

                    item = BbPurchaseOrderItem(
                        po_id=po.id,
                        sku=skus[i],
                        quantity_ordered=qty,
                        unit_price=price,
                        # best_before_date=best_before_dates[i],
                        tax_amount=tax,
                        total_amount=total
                    )
                    db.session.add(item)

            po.subtotal = subtotal
            po.vat_amount = vat_amount

            db.session.commit()
            flash(f"PO {'updated' if po_id else 'created'} successfully as {status}.", 'success')
            return redirect(url_for('main.purchase_orders'))

        except IntegrityError as e:
            db.session.rollback()
            flash(f'Database integrity error: {e}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Unexpected error: {e}', 'danger')

    # ---- GET context ----
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}
    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]

    supplier_models = BbSupplier.query.filter_by(status='Active').order_by(BbSupplier.name).all()
    suppliers = [{
        'id': s.id,
        'name': s.name,
        'vendor_code': s.vendor_code,
        'vat_registered': s.vat_registered
    } for s in supplier_models]

    users = User.query.order_by(User.first_name).all()
    products_raw = TocProduct.query.order_by(TocProduct.item_name).all()
    products_dicts = [product_to_dict(p) for p in products_raw]

    return render_template('po_create.html',
        suppliers=suppliers,
        users=users,
        products=products_dicts,
        user=user,
        shops=list_of_shops,
        roles=roles_list
    )

# @main.route('/purchase_orders/create', methods=['GET', 'POST'])
# def po_create():
#     if request.method == 'POST':
#         try:
#             po_id = request.form.get('po_id')
#             supplier_id = request.form['supplier_id']
#             approved_by = session.get('user_id') or 1
#             expected_delivery_date = request.form.get('expected_delivery_date')
#             note = request.form.get('note') or ''
#             status = request.form.get('status', 'Draft')
#             status_date = datetime.now(timezone.utc)
#             vat_amount = float(request.form.get('vat_amount', 0))
#
#
#             now = datetime.now()
#             if po_id:  # Edit Mode
#                 po = BbPurchaseOrder.query.get(po_id)
#                 po.supplier_id = supplier_id
#                 po.status = status
#                 po.status_date = status_date
#                 po.notes = note
#                 po.expected_delivery_date = expected_delivery_date
#                 # po.order_date = now
#                 po.approved_by = approved_by
#                 po.approved_at = now
#                 po.subtotal = 0  # will recalculate below
#                 po.vat_amount = vat_amount
#
#                 BbPurchaseOrderItem.query.filter_by(po_id=po.id).delete()
#             else:
#                 supplier = BbSupplier.query.get(supplier_id)
#                 supplier_code = supplier.vendor_code or f"SUP{supplier_id}"
#                 po_number = generate_vendor_specific_po_number(supplier_id)
#
#                 po = BbPurchaseOrder(
#                     po_number=po_number,
#                     supplier_id=supplier_id,
#                     created_by=approved_by,
#                     approved_by=approved_by,
#                     status=status,
#                     status_date=status_date,
#                     expected_delivery_date=expected_delivery_date,
#                     order_date=now,
#                     created_at=now,
#                     approved_at=now,
#                     notes=note
#                 )
#                 db.session.add(po)
#                 db.session.flush()
#
#             skus = request.form.getlist('sku[]')
#             quantities = request.form.getlist('quantity[]')
#             unit_prices = request.form.getlist('unit_price[]')
#             raw_dates = request.form.getlist('best_before[]')
#             best_before_dates = [datetime.strptime(d, '%Y-%m-%d').date() if d else None for d in raw_dates]
#
#             subtotal = 0
#             for i in range(len(skus)):
#                 if skus[i] and quantities[i]:
#                     quantity = float(quantities[i])
#                     price = float(unit_prices[i])
#                     subtotal += quantity * price
#
#                     item = BbPurchaseOrderItem(
#                         po_id=po.id,
#                         sku=skus[i],
#                         quantity_ordered=quantity,
#                         unit_price=price,
#                         best_before_date=best_before_dates[i]
#                     )
#                     db.session.add(item)
#
#             po.subtotal = subtotal
#
#             db.session.commit()
#
#             flash(f"PO {'updated' if po_id else 'created'} successfully as {status}.", 'success')
#             return redirect(url_for('main.purchase_orders'))
#
#         except IntegrityError as e:
#             db.session.rollback()
#             flash(f'Database integrity error: {e}', 'danger')
#         except Exception as e:
#             db.session.rollback()
#             flash(f'Unexpected error: {e}', 'danger')
#
#     # ---- Context for GET ----
#     user_data = session.get('user')
#     user = json.loads(user_data) if user_data else {}
#     shop_data = session.get('shop')
#     shop = json.loads(shop_data) if shop_data else {}
#     roles = TocRole.query.all()
#     roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]
#     shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
#     list_of_shops = [s.blName for s in shops]
#
#     supplier_models = BbSupplier.query.filter_by(status='Active').order_by(BbSupplier.name).all()
#     suppliers = [{
#         'id': s.id,
#         'name': s.name,
#         'vendor_code': s.vendor_code,
#         'vat_registered': s.vat_registered
#     } for s in supplier_models]
#
#     users = User.query.order_by(User.first_name).all()
#     products_raw = TocProduct.query.order_by(TocProduct.item_name).all()
#     products_dicts = [product_to_dict(p) for p in products_raw]
#
#     return render_template('po_create.html',
#         suppliers=suppliers,
#         users=users,
#         products=products_dicts,
#         user=user,
#         shops=list_of_shops,
#         roles=roles_list
#     )



@main.route('/purchase_orders/<int:po_id>')
def po_detail(po_id):
    po = BbPurchaseOrder.query.get_or_404(po_id)
    items = BbPurchaseOrderItem.query.filter_by(po_id=po_id).all()
    suppliers = BbSupplier.query.all()
    products = TocProduct.query.all()
    products_dicts = [product_to_dict(p) for p in products]

    # context user/shop/roles same as in po_create GET
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}
    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]
    users = User.query.order_by(User.first_name).all()

    return render_template(
        'po_create.html',
        po=po,
        items=items,
        suppliers=suppliers,
        users=users,
        products=products_dicts,
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        edit_mode=True,
        view_only=True
    )

@main.route('/purchase_orders/<int:po_id>/update_status', methods=['POST'])
def update_po_status(po_id):
    po = BbPurchaseOrder.query.get_or_404(po_id)

    # Parse incoming status value
    data = request.get_json()
    new_status = data.get('status')

    if new_status not in ['Draft', 'Submitted', 'Approved', 'Sent', 'Partially Received', 'Completed', 'Short Closed', 'Cancelled']:
        return jsonify({"success": False, "message": f"Invalid status: {new_status}"}), 400

    # Parse user
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    username = user.get('username', 'system')

    # Set status and update timestamps
    now = datetime.now()
    po.status = new_status
    po.status_date = now

    if new_status == 'Approved':
        po.approved_by = username
        po.approved_at = now
    elif new_status == 'Cancelled':
        po.cancelled_at = now
    elif new_status == 'Short Closed':
        po.short_closed_at = now

    db.session.commit()
    return jsonify({"success": True, "message": f"PO {po.po_number} status updated to {new_status}."})




@main.route('/purchase_orders/<int:po_id>/approve')
def po_approve(po_id):
    po = BbPurchaseOrder.query.get_or_404(po_id)
    po.status = 'Approved'
    po.status_date = datetime.utcnow()
    db.session.commit()
    flash(f'PO {po.po_number} approved.', 'success')
    return redirect(url_for('main.purchase_orders'))

@main.route('/purchase_orders/<int:po_id>/delete')
def po_delete(po_id):
    po = BbPurchaseOrder.query.get_or_404(po_id)

    # Delete PO items
    BbPurchaseOrderItem.query.filter_by(po_id=po.id).delete()

    # Find GRV number if exists
    grv_row = db.session.execute(text("SELECT grv_number FROM bb_grv WHERE po_id = :po_id"), {'po_id': po_id}).fetchone()
    if grv_row:
        grv_number = grv_row[0]

        # Delete GRV items first
        db.session.execute(text("DELETE FROM bb_grv_items WHERE grv_number = :grv_number"), {'grv_number': grv_number})

        # Then delete the GRV header
        db.session.execute(text("DELETE FROM bb_grv WHERE po_id = :po_id"), {'po_id': po_id})

    # Delete the PO header
    db.session.delete(po)
    db.session.commit()

    flash(f'PO {po.po_number} and all related records deleted.', 'warning')
    return redirect(url_for('main.purchase_orders'))


@main.route('/purchase_orders/<int:po_id>/edit')
def po_edit(po_id):
    po = BbPurchaseOrder.query.get_or_404(po_id)
    po.supplier = BbSupplier.query.get(po.supplier_id)
    items = BbPurchaseOrderItem.query.filter_by(po_id=po.id).all()

    # Enrich each item with product data (name, size, barcode)
    for item in items:
        product = TocProduct.query.filter_by(item_sku=item.sku).first()
        item.item_name = product.item_name if product else ''
        item.size = product.size if product else ''
        item.barcode = product.barcode if product else ''

    suppliers_raw = BbSupplier.query.all()
    suppliers = [{
        'id': s.id,
        'name': s.name,
        'email': s.email,
        'vat_registered': s.vat_registered  # ✅ Add this line
    } for s in suppliers_raw]

    products_raw = TocProduct.query.all()
    products = [product_to_dict(p) for p in products_raw]

    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}

    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    shops = TOC_SHOPS.query.all()
    list_of_shops = [s.blName for s in shops]

    users = User.query.order_by(User.first_name).all()

    return render_template(
        'po_create.html',
        po=po,
        items=items,
        suppliers=suppliers,
        users=users,
        products=products,
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        edit_mode=True,
        view_only=False
    )

from decimal import Decimal

@main.route('/purchase_orders/<int:po_id>/view')
def po_view(po_id):
    from decimal import Decimal

    po = BbPurchaseOrder.query.get_or_404(po_id)
    po.supplier = BbSupplier.query.get(po.supplier_id)

    items = BbPurchaseOrderItem.query.filter_by(po_id=po.id).all()

    # Enrich line items with product details
    for item in items:
        product = TocProduct.query.filter_by(item_sku=item.sku).first()
        item.item_name = product.item_name if product else ''
        item.size = product.size if product else ''
        item.barcode = product.barcode if product else ''
        item.cost_price = product.cost_price if product else 0
        item.retail_price = product.retail_price if product else 0
        item.vat_exempt_ind = product.vat_exempt_ind if product else 0

    # Calculate PO total
    po_total = Decimal("0.00")
    for item in items:
        qty = Decimal(str(item.quantity_ordered or 0))
        price = Decimal(str(item.unit_price or 0))
        po_total += qty * price

    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    # Load ALL shops (includes Canndo Holdings)
    shops = TOC_SHOPS.query.all()

    users = User.query.order_by(User.first_name).all()
    suppliers = BbSupplier.query.order_by(BbSupplier.name).all()

    return render_template(
        'po_view.html',
        po=po,
        items=items,
        users=users,
        suppliers=suppliers,
        user=user,
        shops=shops,
        roles=roles_list,
        Decimal=Decimal,
        po_total=po_total
    )

@main.route('/purchase_orders/<int:po_id>/mark_sent')
def mark_po_sent(po_id):
    po = BbPurchaseOrder.query.get_or_404(po_id)
    if po.status == 'Approved':
        po.status = 'Sent'
        po.status_date = datetime.now()
        db.session.commit()
        flash(f"PO {po.po_number} marked as Sent.", "success")
    else:
        flash("Only Approved POs can be marked as Sent.", "warning")
    return redirect(url_for('main.purchase_orders'))

@main.route('/purchase_orders/<int:po_id>/cancel')
def cancel_po(po_id):
    po = BbPurchaseOrder.query.get_or_404(po_id)
    if po.status not in ['Completed', 'Cancelled']:
        po.status = 'Cancelled'
        po.status_date = datetime.now()
        db.session.commit()
        flash(f"PO {po.po_number} has been cancelled.", "info")
    else:
        flash("Cannot cancel a completed or already cancelled PO.", "warning")
    return redirect(url_for('main.purchase_orders'))

##############  Handle Receive Goods

@main.route('/receive_goods', methods=['GET'])
def receive_goods():
    # Application context
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    user_id = user.get('user_id')

    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}
    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]
    users = User.query.order_by(User.first_name).all()

    # Include damage_ind and mismatch_ind explicitly
    pos = db.session.execute(text("""
        SELECT 
            po.id, 
            po.po_number, 
            s.name AS supplier_name, 
            po.status AS po_status, 
            grv.status AS grv_status,
            grv.damage_ind,
            grv.mismatch_ind
        FROM bb_purchase_orders po
        JOIN bb_suppliers s ON s.id = po.supplier_id
        LEFT JOIN bb_grv grv ON grv.po_id = po.id
        WHERE po.status IN ('Approved', 'Sent', 'Partially Received')
        ORDER BY po.created_at DESC
    """)).fetchall()

    return render_template('receive_goods.html',
                           user=user,
                           roles=roles_list,
                           shop=shop,
                           users=users,
                           shops=list_of_shops,
                           pos=pos)



@main.route('/receive_grv/<int:po_id>', methods=['GET'])
def receive_grv_form(po_id):
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    user_id = user.get('user_id')

    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}
    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]
    users = User.query.order_by(User.first_name).all()

    po = db.session.execute(text("""
        SELECT 
            po.id, 
            po.po_number, 
            s.name AS supplier_name, 
            po.status AS po_status, 
            grv.status AS grv_status,
            grv.damage_ind,
            grv.mismatch_ind
        FROM bb_purchase_orders po
        JOIN bb_suppliers s ON s.id = po.supplier_id
        LEFT JOIN bb_grv grv ON grv.po_id = po.id
        WHERE po.id = :po_id
    """), {'po_id': po_id}).fetchone()

    # Fetch the GRV if it exists
    grv = db.session.execute(text("""
        SELECT
            invoice_number,
            invoice_date,
            status,
            update_date,
            invoice_vat_total,
            invoice_total_amount,
            diff_amount,
            po_total_amount,
            po_vat_total
        FROM bb_grv
        WHERE po_id = :po_id
    """), {'po_id': po_id}).fetchone()

    invoice_date = ''
    if grv and hasattr(grv, 'invoice_date') and grv.invoice_date:
        try:
            invoice_date = grv.invoice_date.strftime('%Y-%m-%d')
        except:
            invoice_date = str(grv.invoice_date)

    grv_status = grv.status if grv and hasattr(grv, 'status') else 'Draft'
    readonly = grv_status in ['Received', 'Completed']

    items = db.session.execute(text("""
        SELECT i.id, i.sku, p.item_name, p.size, i.quantity_ordered, p.cost_price,
               i.tax_amount, i.total_amount
        FROM bb_purchase_order_items i
        JOIN toc_product p ON p.item_sku = i.sku
        WHERE i.po_id = :po_id
    """), {'po_id': po_id}).fetchall()

    # Fetch latest GRV items per PO item
    grv_items = db.session.execute(text("""
        SELECT bi.po_item_id,
               bi.quantity_received,
         --      bi.best_before_date,
               bi.damaged_quantity,
               bi.invoice_quantity,
               bi.invoice_price,
               bi.invoice_vat,
               bi.invoice_amount,
               bi.rejected_quantity
        FROM bb_grv_items bi
        JOIN bb_grv bg ON bg.id = bi.grv_id
        WHERE bg.po_id = :po_id
          AND bi.id IN (
              SELECT MAX(bi2.id)
              FROM bb_grv_items bi2
              JOIN bb_grv bg2 ON bg2.id = bi2.grv_id
              WHERE bg2.po_id = :po_id
              GROUP BY bi2.po_item_id
          )
    """), {'po_id': po_id}).fetchall()

    # Build GRV item dict for template
    grv_items_dict = {}
    for row in grv_items:
        grv_items_dict[row.po_item_id] = {
            'quantity_received': row.quantity_received,
            # 'best_before_date': row.best_before_date,
            'damaged_quantity': row.damaged_quantity,
            'invoice_quantity': row.invoice_quantity,
            'invoice_price': row.invoice_price,
            'invoice_vat': row.invoice_vat,
            'invoice_amount': row.invoice_amount,
            'rejected_quantity': row.rejected_quantity
        }

    # If no existing GRV items, pre-fill invoice_quantity = quantity_ordered
    if not grv_items_dict:
        for item in items:
            grv_items_dict[item.id] = {
                'quantity_received': item.quantity_ordered,
                # 'best_before_date': '',
                'damaged_quantity': 0,
                'invoice_quantity': item.quantity_ordered,
                'invoice_price': '',
                'invoice_vat': '',
                'invoice_amount': '',
                'rejected_quantity': 0
            }

    return render_template('receive_grv_form.html',
                           user=user,
                           roles=roles_list,
                           shop=shop,
                           users=users,
                           shops=list_of_shops,
                           po=po,
                           items=items,
                           grv_items_dict=grv_items_dict,
                           grv=grv,
                           readonly=readonly,
                           invoice_date=invoice_date)


@main.route("/receive_grv/<int:po_id>/submit", methods=["POST"])
def submit_grv(po_id):
    from datetime import datetime

    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    user_id = user.get('username')

    po = BbPurchaseOrder.query.get_or_404(po_id)

    # Find or create GRV header
    grv = BbGrv.query.filter_by(po_id=po_id).first()
    if not grv:
        grv = BbGrv(
            po_id=po_id,
            status="Draft",
            received_by=user_id,
            received_at=datetime.utcnow(),
            grv_number=f"GRV-{po.po_number}"  # Or whatever format you use
        )
        db.session.add(grv)
        db.session.flush()

    # Update GRV header fields
    grv.invoice_number = request.form.get("invoice_number")
    grv.invoice_date = request.form.get("invoice_date")
    grv.note = request.form.get("note")
    grv.update_date = datetime.utcnow()
    grv.status = "Saved"

    invoice_total_sum = 0
    invoice_vat_sum = 0

    items = BbPurchaseOrderItem.query.filter_by(po_id=po_id).all()

    grv_items = BbGrvItem.query.filter_by(grv_id=grv.id).all()

    for item in items:
        grv_item = BbGrvItem.query.filter_by(grv_id=grv.id, po_item_id=item.id).first()

        if not grv_item:
            grv_item = BbGrvItem(
                grv_id=grv.id,
                grv_number=grv.grv_number,
                po_item_id=item.id,
                sku=item.sku,
                description=item.description,
                cost_price=item.unit_price,
                quantity_ordered=item.quantity_ordered,
                po_vat=item.tax_amount,
                po_amount=item.total_amount,
            )
            db.session.add(grv_item)
        else:
            # ensure required fields are not NULL
            grv_item.grv_number = grv.grv_number
            grv_item.sku = item.sku
            grv_item.description = item.description

        # Read posted fields
        rec_qty = float(request.form.get(f"received_{item.id}", 0))
        dmg_qty = float(request.form.get(f"damaged_{item.id}", 0))
        inv_qty = float(request.form.get(f"invoice_qty_{item.id}", 0))
        inv_vat = float(request.form.get(f"invoice_vat_{item.id}", 0))
        inv_amt = float(request.form.get(f"invoice_total_{item.id}", 0))

        grv_item.quantity_received = rec_qty
        grv_item.damaged_quantity = dmg_qty
        grv_item.invoice_quantity = inv_qty
        grv_item.invoice_vat = inv_vat
        grv_item.invoice_amount = inv_amt

    # Save totals on GRV header
    grv.invoice_total_amount = invoice_total_sum
    grv.invoice_vat_total = invoice_vat_sum

    # PO total
    po_total = sum(float(i.total_amount or 0) for i in items)
    grv.diff_amount = invoice_total_sum - po_total

    # Indicators
    # --- Indicators ---
    grv.damage_ind = any((i.damaged_quantity or 0) > 0 for i in grv_items)
    grv.mismatch_ind = (grv.diff_amount or 0) != 0

    db.session.commit()

    return jsonify({"message": "GRV saved successfully"})

@main.route("/confirm_grv/<int:po_id>", methods=["POST"])
def confirm_grv(po_id):
    from datetime import datetime

    po = BbPurchaseOrder.query.get_or_404(po_id)

    # ----------------------------------------------------
    # Resolve PO shop from logged-in user
    # ----------------------------------------------------
    user_data = session.get("user")
    user = json.loads(user_data) if user_data else {}

    canna_store = "888"
    shop = TOC_SHOPS.query.filter_by(store=canna_store).first()

    # Optional fallback (if some env uses only blName)
    if not shop:
        shop = TOC_SHOPS.query.filter_by(blName="Canna Holdings").first()

    if not shop:
        return jsonify({"error": "Manufacturing shop not found (store=888 / Canna Holdings)"}), 400

    shop_id = f"TOC{shop.store}"  # => "TOC888"

    grv = BbGrv.query.filter_by(po_id=po_id).first()

    if not grv:
        return jsonify({"error": "GRV not found"}), 404

    if grv.status != "Saved":
        return jsonify({"error": "GRV must be saved before confirming"}), 400

    # ----------------------------------------------------
    # 0. Get PO items + calculate PO total
    # ----------------------------------------------------
    po_items = BbPurchaseOrderItem.query.filter_by(po_id=po_id).all()

    po_total = sum([
        float(item.unit_price or 0) * float(item.quantity_ordered or 0)
        for item in po_items
    ])

    # ----------------------------------------------------
    # 1. Create Supplier Invoice Header
    # ----------------------------------------------------
    invoice_total = float(grv.invoice_total_amount or 0)
    invoice_vat = float(grv.invoice_vat_total or 0)

    supplier_invoice = BbSupplierInvoice(
        po_id=po.id,
        supplier_id=po.supplier_id,
        invoice_number=grv.invoice_number,
        invoice_date=grv.invoice_date,
        vat_amount=invoice_vat,
        total_amount=invoice_total,
        difference_amount=invoice_total - po_total,
        status="Open"
    )

    db.session.add(supplier_invoice)
    db.session.flush()  # Need supplier_invoice.id for items

    # ----------------------------------------------------
    # 2. Load GRV Items
    # ----------------------------------------------------
    grv_items = BbGrvItem.query.filter_by(grv_id=grv.id).all()
    cost_update_items = []

    # ----------------------------------------------------
    # 3. Supplier Invoice Items + Cost Price Updates
    # ----------------------------------------------------
    for gi in grv_items:

        po_item = BbPurchaseOrderItem.query.get(gi.po_item_id)
        if not po_item:
            continue

        invoice_qty = float(gi.invoice_quantity or 0)
        invoice_amt = float(gi.invoice_amount or 0)
        po_unit_price = float(po_item.unit_price or 0)

        invoice_unit_price = invoice_amt / invoice_qty if invoice_qty > 0 else 0

        # Detect cost price change
        product = TocProduct.query.filter_by(item_sku=po_item.sku).first()
        if product and round(invoice_unit_price, 4) != round(po_unit_price, 4):

            cost_update_items.append({
                "sku": po_item.sku,
                "name": po_item.description,
                "old": float(product.cost_price or 0),
                "new": invoice_unit_price
            })

            # Update cost price
            product.cost_price = invoice_unit_price

        # Add invoice item
        sii = BbSupplierInvoiceItem(
            invoice_id=supplier_invoice.id,
            sku=po_item.sku,
            description=po_item.description,
            qty=invoice_qty,
            unit_price=invoice_unit_price,
            vat=float(gi.invoice_vat or 0),
            total_incl_vat=invoice_amt
        )

        db.session.add(sii)

    # ----------------------------------------------------
    # 4. Update Stock
    # ----------------------------------------------------
    for gi in grv_items:

        po_item = BbPurchaseOrderItem.query.get(gi.po_item_id)
        if not po_item:
            continue

        received_qty = float(gi.quantity_received or 0) - float(gi.damaged_quantity or 0)
        if received_qty <= 0:
            continue

        # Find existing stock row (must exist)
        stock = TocStock.query.filter_by(
            shop_id=shop_id,
            sku=po_item.sku
        ).first()

        if not stock:
            db.session.rollback()
            return jsonify({
                "error": (
                    f"Stock record missing for SKU {po_item.sku} in shop {shop.blName} ({shop_id}). "
                    "Please populate toc_stock and try again."
                )
            }), 400

        # ✅ Update final stock
        stock.final_stock_qty = (stock.final_stock_qty or 0) + received_qty

        # ✅ Update stock transfer (NEW)
        stock.stock_transfer = (stock.stock_transfer or 0) + received_qty

        # Update timestamp
        stock.stock_qty_date = datetime.utcnow()

    # ----------------------------------------------------
    # 5. Update GRV Header Status
    # ----------------------------------------------------
    grv.status = "Completed"
    grv.update_date = datetime.utcnow()

    grv.damage_ind = any((gi.damaged_quantity or 0) > 0 for gi in grv_items)
    grv.mismatch_ind = (invoice_total - po_total) != 0

    db.session.commit()

    # ----------------------------------------------------
    # 6. Return cost-update list (UI modal uses it)
    # ----------------------------------------------------
    if cost_update_items:
        return jsonify({
            "message": "cost_updates",
            "items": cost_update_items
        }), 200

    return jsonify({
        "message": "GRV successfully confirmed"
    }), 200


@main.route("/create_debit_note/<int:po_id>", methods=["POST"])
def create_debit_note(po_id):
    grv = BbGrv.query.filter_by(po_id=po_id).first()
    if not grv:
        return jsonify({"error": "GRV not found"}), 404

    grv.status = "Completed"
    db.session.commit()
    return jsonify({"message": "Debit Note created successfully. GRV is now completed."})




# upload suppliers invoices
@main.route('/upload_invoice/<int:po_id>', methods=['POST'])
def upload_invoice(po_id):
    uploaded_file = request.files.get('invoice_file')
    if not uploaded_file or uploaded_file.filename == '':
        flash('No file uploaded.', 'danger')
        return redirect(request.referrer)

    from werkzeug.utils import secure_filename
    filename = secure_filename(uploaded_file.filename)

    # Adjust this path to your actual project directory
    save_path = os.path.join(os.getcwd(), 'uploads', 'invoices', filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    uploaded_file.save(save_path)
    flash(f'{filename} uploaded successfully to {save_path}', 'success')
    return redirect(request.referrer)


@main.route('/test_upload', methods=['GET', 'POST'])
def test_upload():
    if request.method == 'POST':
        file = request.files.get('invoice_file')
        print("Got file:", file.filename if file else "None")
        if file:
            path = os.path.join('uploads', 'invoices', secure_filename(file.filename))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            file.save(path)
            return "File uploaded!"
        return "No file found"
    return '''
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="invoice_file">
            <input type="submit">
        </form>
    '''


##########################  Bill Of Materials   ####################################

@main.route('/bom')
def bom_list():

    # Restore context
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}

    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]

    # -----------------------------------------------------
    # SUPER FAST QUERY — Groups by bom_id (product SKU)
    # -----------------------------------------------------
    sql = """
        SELECT 
            c.bom_id,
            c.bom_name,
            COUNT(c.id) AS component_count,
            p.cost_price
        FROM toc_bom_components c
        JOIN toc_product p 
            ON p.item_sku COLLATE utf8mb4_unicode_ci =
               c.bom_id COLLATE utf8mb4_unicode_ci
        GROUP BY 
            c.bom_id, c.bom_name, p.cost_price
        ORDER BY 
            c.bom_name
    """
    result = db.session.execute(db.text(sql)).mappings().all()

    # Convert into list of dicts for Jinja
    boms = [{
        "bom_id": row["bom_id"],
        "bom_name": row["bom_name"],
        "components": row["component_count"],
        "cost_price": row["cost_price"]
    } for row in result]

    return render_template(
        "bom_list.html",
        boms=boms,
        user=user,
        shops=list_of_shops,
        roles=roles_list
    )

@main.route('/bom/create', methods=['GET', 'POST'])
def bom_create():

    # ---------------------------------------------------
    # Restore application context (REQUIRED for UI header)
    # ---------------------------------------------------
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}

    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]

    # ---------------------------------------------------
    # Load products
    # ---------------------------------------------------
    all_products = TocProduct.query.filter_by(is_active=True).all()

    # All BOM parent IDs already in use
    existing_bom_ids = {row[0] for row in db.session.query(TocBOMComponent.bom_id).distinct()}

    # PR products without BOM
    products_pr = [
        p for p in all_products
        if p.item_type == 'PR' and p.item_sku not in existing_bom_ids
    ]

    # CO component list
    components = [p for p in all_products if p.item_type == 'CO']

    # ---------------------------------------------------
    # SERIALIZE for template
    # ---------------------------------------------------
    products_json = [{
        "item_sku": p.item_sku,
        "item_name": p.item_name,
        "cost_price": float(p.cost_price or 0)
    } for p in products_pr]

    components_json = [{
        "item_sku": p.item_sku,
        "item_name": p.item_name,
        "cost_price": float(p.cost_price or 0)
    } for p in components]

    # ---------------------------------------------------
    # POST — Save new BOM
    # ---------------------------------------------------
    if request.method == 'POST':
        bom_id = request.form.get('product_sku')

        # --------------------------------------------
        # 🔒 SAFETY CHECK: Does this BOM already exist?
        # --------------------------------------------
        if TocBOMComponent.query.filter_by(bom_id=bom_id).first():
            flash("This product already has a BOM defined.", "warning")
            return redirect(url_for('main.bom_list'))


        product = TocProduct.query.get(bom_id)
        bom_name = product.item_name if product else None

        comp_skus = request.form.getlist('component_sku[]')
        comp_qtys = request.form.getlist('quantity[]')

        for sku, qty in zip(comp_skus, comp_qtys):
            if not sku:
                continue
            qty = float(qty or 0)
            if qty <= 0:
                continue

            comp = TocProduct.query.get(sku)

            db.session.add(TocBOMComponent(
                bom_id=bom_id,
                bom_name=bom_name,
                component_sku=sku,
                component_name=comp.item_name if comp else None,
                quantity=qty,
                cost=qty * float(comp.cost_price or 0)
            ))

        db.session.commit()
        flash("BOM created successfully", "success")
        return redirect(url_for('main.bom_list'))

    # ---------------------------------------------------
    # Render template
    # ---------------------------------------------------
    return render_template(
        "bom_create.html",
        edit_mode=False,
        products=products_json,
        components=components_json,
        user=user,
        shops=list_of_shops,
        roles=roles_list
    )



@main.route('/bom/<string:bom_id>/edit', methods=['GET', 'POST'])
def bom_edit(bom_id):

    # Load context
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]

    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    # Ensure the BOM exists
    components = TocBOMComponent.query.filter_by(bom_id=bom_id).all()
    if not components:
        flash(f"BOM {bom_id} not found.", "danger")
        return redirect(url_for('main.bom_list'))

    # Get product info
    product = TocProduct.query.filter_by(item_sku=bom_id).first()
    bom_name = product.item_name if product else ""
    product_cost = product.cost_price if product else 0

    existing_components = [
        {
            "component_sku": c.component_sku,
            "component_name": c.component_name,
            "quantity": float(c.quantity)
        }
        for c in components
    ]

    # Product + component lists
    manufacturable_products = TocProduct.query.filter_by(
        is_active=True, item_type='PR'
    ).order_by(TocProduct.item_name).all()

    component_products = TocProduct.query.filter_by(
        is_active=True, item_type='CO'
    ).order_by(TocProduct.item_name).all()

    # POST: save updates
    if request.method == "POST":

        TocBOMComponent.query.filter_by(bom_id=bom_id).delete()

        component_skus = request.form.getlist("component_sku[]")
        quantities = request.form.getlist("quantity[]")

        for sku, qty in zip(component_skus, quantities):
            if sku and qty:
                p = TocProduct.query.filter_by(item_sku=sku).first()
                component_name = p.item_name if p else ""
                cost = (p.cost_price or 0) * float(qty)

                db.session.add(TocBOMComponent(
                    bom_id=bom_id,
                    bom_name=bom_name,
                    component_sku=sku,
                    component_name=component_name,
                    quantity=qty,
                    cost=cost
                ))

        db.session.commit()
        flash("BOM updated successfully!", "success")
        return redirect(url_for("main.bom_list"))

    return render_template(
        "bom_create.html",
        edit_mode=True,
        bom_id=bom_id,
        bom_name=bom_name,
        product_cost=product_cost,
        existing_components=existing_components,
        products=[{"item_sku": p.item_sku, "item_name": p.item_name} for p in manufacturable_products],
        components=[{"item_sku": p.item_sku, "item_name": p.item_name, "cost_price": p.cost_price}
                    for p in component_products],
        user=user,
        shops=list_of_shops,
        roles=roles_list
    )


@main.route('/bom/<string:bom_id>/delete', methods=['POST'])
def bom_delete(bom_id):
    try:
        # 1. Delete all components belonging to this BOM
        deleted = TocBOMComponent.query.filter_by(bom_id=bom_id).delete()

        if deleted == 0:
            flash(f"No BOM found for product SKU {bom_id}.", "warning")
            return redirect(url_for('main.bom_list'))

        # 2. Commit deletion
        db.session.commit()

        flash(f"BOM for product SKU {bom_id} deleted successfully.", "success")
        return redirect(url_for('main.bom_list'))

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting BOM {bom_id}: {str(e)}", "danger")
        return redirect(url_for('main.bom_list'))



######################  BOM MANUFACTURE  #################################
######################  BOM MANUFACTURE  #################################
@main.route('/bom/manufacture')
def bom_manufacture():

    # ---------------------------------------------------
    # Restore application context (REQUIRED for UI header)
    # ---------------------------------------------------
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}

    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    # List of shops for top-bar shop selector
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]

    # ---------------------------------------------------
    # Manufacturing shop (Canndo Holdings)
    # ---------------------------------------------------
    manufacture_shop = TOC_SHOPS.query.filter_by(blName="Canndo Holdings").first()

    # ---------------------------------------------------
    # Finished products = all bom_id values
    # ---------------------------------------------------
    finished_products = (
        db.session.query(
            TocBOMComponent.bom_id.label("sku"),
            func.max(TocBOMComponent.bom_name).label("name")
        )
        .group_by(TocBOMComponent.bom_id)
        .order_by(TocBOMComponent.bom_id)
        .all()
    )

    # ---------------------------------------------------
    # Render template
    # ---------------------------------------------------
    return render_template(
        "bom_manufacture.html",

        # Context (required by header)
        user=user,
        shops=list_of_shops,
        roles=roles_list,
        shop=shop,
        active_shop=manufacture_shop.blName if manufacture_shop else None,

        # Data
        finished_products=finished_products
    )


@main.route('/bom/manufacture/components/<bom_id>')
def bom_manufacture_components(bom_id):

    # ---------------------------------------------------
    # Restore application context (required for header)
    # ---------------------------------------------------
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}

    shop_data = session.get('shop')
    shop = json.loads(shop_data) if shop_data else {}

    roles = TocRole.query.all()
    roles_list = [{'role': r.role, 'exclusions': r.exclusions} for r in roles]

    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [s.blName for s in shops]

    # Manufacturing shop (store='888' in toc_shops, but shop_id='TOC888' in toc_stock)
    canna_store = "888"
    canna_shop_id = "TOC888"
    canna_shop = TOC_SHOPS.query.filter_by(store=canna_store).first()
    if not canna_shop:
        canna_shop = TOC_SHOPS.query.filter_by(blName="Canna Holdings").first()

    # ---------------------------------------------------
    # Get components for this BOM
    # ---------------------------------------------------
    components = TocBOMComponent.query.filter_by(bom_id=bom_id).all()

    results = []
    for c in components:
        stock_row = (
            TocStock.query
                .filter_by(sku=c.component_sku, shop_id=canna_shop_id)
                .first()
        )
        available_qty = float(stock_row.final_stock_qty or 0) if stock_row else 0

        results.append({
            "component_sku": c.component_sku,
            "component_name": c.component_name,
            "qty_per_unit": float(c.quantity or 0),
            "available_qty": available_qty
        })

    return jsonify({
        "bom_id": bom_id,
        "components": results,
        "user": user,
        "shops": list_of_shops,
        "roles": roles_list,
        "active_shop": canna_shop.blName if canna_shop else None
    })


@main.route('/bom/manufacture/submit', methods=['POST'])
def bom_manufacture_submit():
    """
    Manufacture finished goods from a BOM:
    - Deduct component stock (toc_stock.final_stock_qty) for the manufacturing shop (TOC888)
    - Increase finished product stock for the same shop
    - Update stock_transfer:
        * +finished qty
        * -component qty
    - Write header + lines to toc_bom_manufacture / toc_bom_manufacture_items
    """
    from datetime import datetime

    data = request.get_json(silent=True) or {}
    bom_id = (data.get('bom_id') or '').strip()
    qty_to_build = float(data.get('qty') or 0)

    if not bom_id or qty_to_build <= 0:
        return jsonify({"status": "error", "message": "Invalid parameters"}), 400

    # ---------------------------------------------------
    # Restore user
    # ---------------------------------------------------
    user_data = session.get('user')
    user = json.loads(user_data) if user_data else {}
    user_id = user.get("id") or 0

    # ---------------------------------------------------
    # HARD-CODE manufacturing shop to TOC888
    # ---------------------------------------------------
    canna_store = "888"
    canna_shop = TOC_SHOPS.query.filter_by(store=canna_store).first()
    if not canna_shop:
        canna_shop = TOC_SHOPS.query.filter_by(blName="Canna Holdings").first()

    if not canna_shop:
        return jsonify({"status": "error", "message": "Manufacturing shop not found (store=888 / Canna Holdings)"}), 400

    canna_shop_id = f"TOC{canna_shop.store}"  # => TOC888

    # ---------------------------------------------------
    # Load components for this BOM (bom_id is finished SKU)
    # ---------------------------------------------------
    components = TocBOMComponent.query.filter_by(bom_id=bom_id).all()
    if not components:
        return jsonify({"status": "error", "message": f"No BOM components found for finished SKU {bom_id}"}), 400

    try:
        # ---------------------------------------------------
        # Create manufacturing header row
        # ---------------------------------------------------
        man = TocBOMManufacture(
            item_sku=bom_id,
            qty=qty_to_build,
            shop_id=canna_shop_id,
            created_by=user_id,
            creation_date=datetime.utcnow()
        )
        db.session.add(man)
        db.session.flush()  # get manufacture_id

        # ---------------------------------------------------
        # Process each component: deduct stock + transfer + log line
        # ---------------------------------------------------
        for comp in components:
            required_qty = float(comp.quantity or 0) * qty_to_build
            if required_qty <= 0:
                continue

            stock_row = TocStock.query.filter_by(
                sku=comp.component_sku,
                shop_id=canna_shop_id
            ).first()

            # If missing, create row with zeros
            if not stock_row:
                stock_row = TocStock(
                    sku=comp.component_sku,
                    shop_id=canna_shop_id,
                    final_stock_qty=0,
                    stock_transfer=0,
                    stock_qty_date=datetime.utcnow()
                )
                db.session.add(stock_row)
                db.session.flush()

            # Deduct component final stock
            stock_row.final_stock_qty = float(stock_row.final_stock_qty or 0) - required_qty

            # ✅ Deduct component transfer (your requirement)
            stock_row.stock_transfer = float(stock_row.stock_transfer or 0) - required_qty

            stock_row.stock_qty_date = datetime.utcnow()

            db.session.add(TocBOMManufactureItem(
                manufacture_id=man.manufacture_id,
                component_sku=comp.component_sku,
                required_qty=required_qty,
                deducted_qty=required_qty
            ))

        # ---------------------------------------------------
        # Add finished product stock + transfer
        # ---------------------------------------------------
        fp_row = TocStock.query.filter_by(
            sku=bom_id,
            shop_id=canna_shop_id
        ).first()

        if not fp_row:
            fp_row = TocStock(
                sku=bom_id,
                shop_id=canna_shop_id,
                final_stock_qty=0,
                stock_transfer=0,
                stock_qty_date=datetime.utcnow()
            )
            db.session.add(fp_row)
            db.session.flush()

        fp_row.final_stock_qty = float(fp_row.final_stock_qty or 0) + qty_to_build

        # ✅ Add finished product transfer (your requirement)
        fp_row.stock_transfer = float(fp_row.stock_transfer or 0) + qty_to_build

        fp_row.stock_qty_date = datetime.utcnow()

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Manufactured {qty_to_build} units of {bom_id} in {canna_shop_id}.",
            "manufacture_id": man.manufacture_id,
            "shop_id": canna_shop_id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Manufacture failed: {str(e)}"
        }), 500


#######################    INTER TRANSFER INVOICE  ##########################


VAT_PCT_DEFAULT = 15.0


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return None


def _money2(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.00


def _num3(v):
    try:
        return round(float(v or 0), 3)
    except Exception:
        return 0.000


def _generate_invoice_no(prefix="INV"):
    # Example: INV-20260130-104512-8342
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rnd = str(int(datetime.now().timestamp()))[-4:]
    return f"{prefix}-{ts}-{rnd}"


@main.route("/invoice/inter-transfer/create", methods=["POST"])
def create_invoice_inter_transfer():
    """
    Creates:
      - toc_invoice
      - toc_invoice_item(s)   (including COMMISSION as a line item if pct>0)
      - toc_invoice_commission (optional, still recorded for tracking)
    for Inter Transfer source.
    """

    import json
    from datetime import date

    payload = request.get_json(silent=True) or {}

    # ---------------------------
    # Required payload fields
    # ---------------------------
    source_id = (payload.get("source_id") or "").strip()   # ✅ VARCHAR
    buyer_blname = (payload.get("buyer_blname") or "").strip()
    items = payload.get("items") or []

    # Commission (optional)
    commission_pct = payload.get("commission_pct")  # can be None/""/0

    if not source_id:
        return jsonify({"status": "error", "message": "Missing source_id"}), 400

    if not buyer_blname:
        return jsonify({"status": "error", "message": "Missing buyer_blname"}), 400

    if not isinstance(items, list) or len(items) == 0:
        return jsonify({"status": "error", "message": "No invoice items provided"}), 400

    # ---------------------------
    # Resolve seller details from session
    # IMPORTANT: session shop uses "customer" like TOC999
    # ---------------------------
    shop_data = session.get("shop")
    seller_customer_code = None  # e.g. "TOC999"
    seller_blname = None         # e.g. "TOC - Nicolway"

    if shop_data:
        try:
            s = json.loads(shop_data)
            seller_customer_code = (s.get("customer") or "").strip() or None
            seller_blname = (s.get("blName") or "").strip() or None
        except Exception:
            pass

    # Prefer customer code lookup (what you actually have: TOC999)
    seller_row = None
    if seller_customer_code:
        seller_row = TOC_SHOPS.query.filter_by(customer=seller_customer_code).first()

    # Fallback: if session actually has blName
    if not seller_row and seller_blname:
        seller_row = TOC_SHOPS.query.filter_by(blName=seller_blname).first()

    if not seller_row:
        tried = seller_customer_code or seller_blname or "(none)"
        return jsonify({
            "status": "error",
            "message": f"Seller shop not found in toc_shops (customer/blName): {tried}"
        }), 404

    # Buyer is selected by blName (dropdown)
    buyer_row = TOC_SHOPS.query.filter_by(blName=buyer_blname).first()
    if not buyer_row:
        return jsonify({"status": "error", "message": f"Buyer shop not found in toc_shops: {buyer_blname}"}), 404

    seller_name = seller_row.blName
    seller_vat_no = str(getattr(seller_row, "vat_no", None)) if getattr(seller_row, "vat_no", None) else None

    bill_to_name = buyer_row.blName
    bill_to_address = getattr(buyer_row, "address", None)
    bill_to_vat_no = str(getattr(buyer_row, "vat_no", None)) if getattr(buyer_row, "vat_no", None) else None

    # ---------------------------
    # created_by from session (if available)
    # ---------------------------
    created_by = payload.get("created_by") or None
    user_data = session.get("user")
    session_user_id = None
    session_username = None

    if user_data:
        try:
            u = json.loads(user_data)
            session_user_id = u.get("id")
            session_username = u.get("username")
            created_by = created_by or session_user_id
        except Exception:
            pass

    # ---------------------------
    # Build invoice header (matches your toc_invoice DDL fields)
    # ---------------------------
    inv = TocInvoice(
        invoice_no=_generate_invoice_no("INV"),
        source_type="INTER_TRANSFER",
        source_id=source_id,          # ✅ VARCHAR
        invoice_date=date.today(),
        due_date=None,

        seller_name=seller_name,
        seller_vat_no=seller_vat_no,

        bill_to_name=bill_to_name,
        bill_to_address=bill_to_address,
        bill_to_vat_no=bill_to_vat_no,

        from_shop_name=seller_name,
        to_shop_name=bill_to_name,

        status="Draft",
        notes=(payload.get("notes") or None),
        created_by=created_by
    )

    # ---------------------------
    # Build invoice items (GOODS)
    # ---------------------------
    vat_pct = float(payload.get("vat_pct") or VAT_PCT_DEFAULT)
    line_no = 1

    for it in items:
        sku = (it.get("sku") or "").strip() or None
        desc = (it.get("description") or "").strip()
        qty = _num3(it.get("qty"))
        unit_price_excl = _money2(it.get("unit_price_excl"))

        if not desc:
            return jsonify({"status": "error", "message": f"Missing description on line {line_no}"}), 400
        if qty <= 0:
            return jsonify({"status": "error", "message": f"Qty must be > 0 on line {line_no}"}), 400

        item = TocInvoiceItem(
            line_no=line_no,
            code=(it.get("code") or None),
            sku=sku,
            description=desc,

            qty=qty,
            unit=(it.get("unit") or None),

            unit_price_excl=unit_price_excl,
            discount_pct=_money2(it.get("discount_pct") or 0),
            tax_pct=vat_pct,
        )

        item.recalc_line()
        inv.items.append(item)
        line_no += 1

    # ---------------------------
    # Commission as INVOICE LINE ITEM (EXCL VAT)
    # - Commission is now just another invoice item
    # - We still keep toc_invoice_commission for tracking/payments
    # ---------------------------
    pct_val = None
    try:
        pct_val = float(commission_pct) if commission_pct not in [None, ""] else None
    except Exception:
        pct_val = None

    commission_excl = 0.0
    if pct_val is not None and pct_val > 0:
        # goods subtotal excl vat (net_excl already excludes VAT)
        goods_subtotal_excl = sum([float(i.net_excl or 0) for i in inv.items])
        commission_excl = round(goods_subtotal_excl * (pct_val / 100.0), 2)

        # Add commission as a normal invoice row
        comm_item = TocInvoiceItem(
            line_no=line_no,
            code="COMMISSION",
            sku=None,
            description=f"Commission ({pct_val:.2f}%)",
            qty=_num3(1),
            unit=None,
            unit_price_excl=_money2(commission_excl),
            discount_pct=_money2(0),
            tax_pct=vat_pct,
        )
        comm_item.recalc_line()
        inv.items.append(comm_item)
        line_no += 1

    # Totals now include commission line item
    inv.recalc_totals()

    # ---------------------------
    # Commission tracking row (optional) - still works
    # Store pct + amount (amount == commission_excl here)
    # ---------------------------
    if pct_val is not None and pct_val > 0:
        if not session_user_id:
            return jsonify({"status": "error", "message": "Cannot set commission: missing session user id"}), 400

        comm = TocInvoiceCommission(
            agent_user_id=session_user_id,
            commission_pct=pct_val,
            commission_amount=_money2(commission_excl),
            status="Open",
            note="Commission stored as invoice line item (EXCL VAT)"
        )
        inv.commissions.append(comm)

    # ---------------------------
    # Commit
    # ---------------------------
    try:
        db.session.add(inv)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({
        "status": "success",
        "invoice_id": inv.invoice_id,
        "invoice_no": inv.invoice_no,
        "sub_total_excl": float(inv.sub_total_excl or 0),
        "tax_total": float(inv.tax_total or 0),
        "total_incl": float(inv.total_incl or 0),
        # still returned for UI display, but UI will treat it as a line item now
        "commission_amount": float(inv.commissions[0].commission_amount) if inv.commissions else 0.0,
    }), 200



@main.route("/invoice/lookup", methods=["GET"])
def invoice_lookup():
    source_type = (request.args.get("source_type") or "").strip().upper()
    source_id   = (request.args.get("source_id") or "").strip()

    if not source_type or not source_id:
        return jsonify({"status": "error", "message": "Missing source_type or source_id"}), 400

    inv = (TocInvoice.query
           .filter(TocInvoice.source_type == source_type,
                   TocInvoice.source_id == source_id)
           .order_by(TocInvoice.invoice_id.desc())
           .first())

    if not inv:
        return jsonify({"status": "error", "message": "Invoice not found"}), 404

    return jsonify({
        "status": "success",
        "invoice": {
            "invoice_id": inv.invoice_id,
            "invoice_no": inv.invoice_no,
            "source_type": inv.source_type,
            "source_id": inv.source_id,
            "invoice_date": inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else None
        }
    })

from flask import render_template_string

@main.route("/invoice/<int:invoice_id>/print", methods=["GET"])
def invoice_print(invoice_id):
    inv = TocInvoice.query.get_or_404(invoice_id)
    items = (TocInvoiceItem.query
             .filter_by(invoice_id=invoice_id)
             .order_by(TocInvoiceItem.line_no.asc())
             .all())

    # If you want to re-pull addresses/VAT from toc_shops (optional, but good):
    seller_shop = TOC_SHOPS.query.filter_by(blName=inv.seller_name).first()
    buyer_shop  = TOC_SHOPS.query.filter_by(blName=inv.bill_to_name).first()

    seller_address = (getattr(seller_shop, "address", None) if seller_shop else None) or ""
    buyer_address  = (getattr(buyer_shop, "address", None) if buyer_shop else None) or (inv.bill_to_address or "")

    seller_vat = (str(getattr(seller_shop, "vat_no", "")) if seller_shop and getattr(seller_shop, "vat_no", None) else (inv.seller_vat_no or ""))
    buyer_vat  = (str(getattr(buyer_shop, "vat_no", "")) if buyer_shop and getattr(buyer_shop, "vat_no", None) else (inv.bill_to_vat_no or ""))

    html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Invoice {{ inv.invoice_no }}</title>
  <style>
    body { font-family: Arial, sans-serif; font-size: 12px; margin: 20px; color:#111; }
    .top { display:flex; justify-content:space-between; align-items:flex-start; }
    .title { font-size: 22px; font-weight: 700; }
    .invno { font-size: 20px; font-weight: 700; }
    .row { display:flex; gap:40px; margin-top: 10px; }
    .box { width: 48%; }
    .box h4 { margin: 0 0 6px 0; font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }
    .muted { color:#555; }
    table { width:100%; border-collapse: collapse; margin-top: 12px; }
    th, td { border-bottom: 1px solid #ddd; padding: 6px 6px; vertical-align: top; }
    th { text-align:left; font-weight: 700; }
    td.num, th.num { text-align:right; }
    .totals { width: 320px; margin-left:auto; margin-top: 16px; }
    .totals td { border: none; padding: 3px 0; }
    .totals .label { text-align:right; padding-right: 10px; color:#333; }
    .totals .val { text-align:right; font-weight:700; }
    .hr { border-top: 2px solid #111; margin: 10px 0 0 0; }
    @media print {
      .noprint { display:none; }
      body { margin: 10mm; }
    }
  </style>
</head>
<body>
  <div class="top">
    <div>
      <div class="title">Tax Invoice</div>
      <div class="muted">Date: {{ inv.invoice_date.strftime("%d/%m/%Y") if inv.invoice_date else "" }}</div>
    </div>
    <div class="invno">{{ inv.invoice_no }}</div>
  </div>

  <div class="hr"></div>

  <div class="row">
    <div class="box">
      <h4>Seller</h4>
      <div><b>{{ inv.seller_name }}</b></div>
      <div class="muted">{{ seller_address }}</div>
      {% if seller_vat %}<div class="muted">VAT: {{ seller_vat }}</div>{% endif %}
    </div>

    <div class="box">
      <h4>Buyer</h4>
      <div><b>{{ inv.bill_to_name }}</b></div>
      <div class="muted">{{ buyer_address }}</div>
      {% if buyer_vat %}<div class="muted">VAT: {{ buyer_vat }}</div>{% endif %}
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th style="width:90px;">Code/SKU</th>
        <th>Description</th>
        <th class="num" style="width:70px;">Qty</th>
        <th class="num" style="width:90px;">Unit Price</th>
        <th class="num" style="width:90px;">Net</th>
        <th class="num" style="width:70px;">Tax</th>
        <th class="num" style="width:100px;">Total</th>
      </tr>
    </thead>
    <tbody>
      {% for it in items %}
      <tr>
        <td>{{ it.code or it.sku or "" }}</td>
        <td>{{ it.description }}</td>
        <td class="num">{{ "%.3f"|format(it.qty or 0) }}</td>
        <td class="num">{{ "%.2f"|format(it.unit_price_excl or 0) }}</td>
        <td class="num">{{ "%.2f"|format(it.net_excl or 0) }}</td>
        <td class="num">{{ "%.2f"|format(it.tax_amount or 0) }}</td>
        <td class="num">{{ "%.2f"|format(it.total_incl or 0) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <table class="totals">
    <tr><td class="label">Sub Total</td><td class="val">{{ "%.2f"|format(inv.sub_total_excl or 0) }}</td></tr>
    <tr><td class="label">Discount</td><td class="val">{{ "%.2f"|format(inv.discount_total or 0) }}</td></tr>
    <tr><td class="label">Tax</td><td class="val">{{ "%.2f"|format(inv.tax_total or 0) }}</td></tr>
    <tr><td class="label" style="font-size:13px;">Total</td><td class="val" style="font-size:13px;">{{ "%.2f"|format(inv.total_incl or 0) }}</td></tr>
  </table>

  <div class="noprint" style="margin-top:18px;">
    <button onclick="window.print()">Print</button>
  </div>

  <script>
    // Optional: auto-open print dialog
    // window.onload = () => setTimeout(() => window.print(), 300);
  </script>
</body>
</html>
"""
    return render_template_string(
        html,
        inv=inv,
        items=items,
        seller_address=seller_address,
        buyer_address=buyer_address,
        seller_vat=seller_vat,
        buyer_vat=buyer_vat
    )



if __name__ == '__main__':
    app.run(debug=True)






from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
import pymysql
import json
import os
from sqlalchemy.exc import SQLAlchemyError
from .models import *
from . import db
from .db_queries import *
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from sqlalchemy import distinct, or_, text, desc
from flask import session, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import pandas as pd
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
main = Blueprint('main', __name__)

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465
SENDER_EMAIL = 'algott.team@gmail.com'
SENDER_PASSWORD = 'ebzdcpdiilrurexz'


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

@main.route('/')
def login():
    return render_template('login.html')


@main.route('/index')
def index():
    # Send email when the page loads
    print("Trying to send email to myself")

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
    print(f"shop: {shop.store}")
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
    # Query all products from the database
    products = TocProduct.query.all()

    # Serialize the data
    products_data = [
        {
            "item_sku": product.item_sku,
            "item_name": product.item_name,
            "stat_group": product.stat_group,
            "acct_group": product.acct_group,
            "retail_price": product.retail_price,
            "cost_price": product.cost_price,
            "wh_price": product.wh_price,
            "cann_cost_price": product.cann_cost_price,
            "product_url": product.product_url,
            "image_url": product.image_url,
            "stock_ord_ind": product.stock_ord_ind,
        }
        for product in products
    ]

    # Return the serialized data as JSON
    return jsonify(products_data)

@main.route('/api/products', methods=['POST'])
def create_product():
    # Get data from the request (assuming JSON format)
    data = request.get_json()

    # Ensure all required fields are in the request
    if not data or not data.get('item_sku') or not data.get('item_name'):
        return jsonify({"message": "Missing required fields: item_sku or item_name"}), 400

    try:
        # Create a new product instance
        new_product = TocProduct(
            item_sku=data.get('item_sku'),
            item_name=data.get('item_name'),
            stat_group=data.get('stat_group'),
            acct_group=data.get('acct_group'),
            retail_price=data.get('retail_price'),
            cost_price=data.get('cost_price'),
            wh_price=data.get('wh_price'),
            cann_cost_price=data.get('cann_cost_price'),
            product_url=data.get('product_url'),
            image_url=data.get('image_url'),
            stock_ord_ind=data.get('stock_ord_ind')
        )

        # Add the new product to the session and commit to the database
        db.session.add(new_product)
        db.session.commit()

        # Call the function to distribute the product to all shops
        distribute_product_to_shops(new_product.item_sku)

        # Return a success message
        return jsonify({"message": "Product created and distributed to shops successfully", "product": new_product.item_sku}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error creating product: {str(e)}"}), 500



@main.route('/api/products/<string:item_sku>', methods=['DELETE'])
def delete_product(item_sku):
    product = TocProduct.query.get(item_sku)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    try:
        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "Product deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@main.route('/api/products/<string:item_sku>', methods=['PUT'])
def update_product(item_sku):
    data = request.get_json()

    try:
        # Find the product by item_sku
        product = TocProduct.query.get(item_sku)
        if not product:
            return jsonify({"error": f"Product with ID {item_sku} not found"}), 404

        # Update fields
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

        # Commit changes
        db.session.commit()
        return jsonify({"message": f"Product {item_sku} updated successfully"}), 200
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


@main.route('/get_product_order_form', methods=['GET'])
def get_product_order_form():
    try:
        # Fetch the shop customer from the session
        shop = json.loads(session.get('shop'))['name']  # Assuming 'shop.customer' is stored in the session

        data = get_stock_count_per_shop(shop)

        if not data:
            return jsonify({"message": "Error fetching stock order form data"}), 500

        # Format the data for the client
        formatted_data = [
            {
                "sku": row[0],
                "product_name": row[1],
                "stock_count": row[7],
                "last_stock_qty": row[4],
                "calc_stock_qty": row[7],
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

        # Print the selected shop value
        print(f"Selected shop from client: {selected_shop}")

        data = get_replenish_order_form(selected_shop,history_sold,replenish_qty)
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
        # Print the selected shop value
        print(f"Selected shop from client: {selected_shop}")

        data = get_stock_count_per_shop(selected_shop)
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
        # Retrieve the order_id parameter from the query string
        order_id = request.args.get('order_id')  # This will get the order_id from the URL query parameter
        if not order_id:
            return jsonify({"message": "Order ID is required"}), 400  # Return an error if no order_id is provided

        # Retrieve the shop data from session
        shop_data = json.loads(session.get('shop'))
        selected_shop = shop_data['customer']
        print(f"Selected shop from client: {selected_shop}")
        print(f"Received order_id: {order_id}")

        # Assuming get_receive_stock_order is a function that now accepts order_id
        data = get_receive_stock_order(selected_shop, order_id)

        # If no data is returned, respond with an error
        if not data:
            return jsonify({"message": "Error fetching stock order form data"}), 500

        # Format the data for the client
        formatted_data = [
            {
                "sku": row[2],
                "replenish_date": row[3],
                "replenish_user": row[4],
                "item_name": row[5],
                "replenish_qty": row[6],
                "received_qty" : row[8]
            }
            for row in data
        ]

        # Return the formatted data as a JSON response
        return jsonify(formatted_data)

    except Exception as e:
        # Handle any errors that occur during execution
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
        print("order_id:", order_id)
        print("Shop:", shop)
        print("User Name:", user_name)
        print("Save Date:", date)
        print("Table Data:")
        for row in table:
            print(row)

        # Check for order_id and delete existing records
        if order_id:
            db.session.query(TocStockOrder).filter_by(order_id=order_id).delete()

        # Insert new records into the table
        for row in table:
            sku, item_name, last_stock_qty, last_count_date,qty_sold, qty_bfr_rcv, rcv_qty, stock_count, order_qty,  comments = row

            new_record = TocStockOrder(
                shop_id=shop,
                order_open_date=datetime.strptime(date, '%Y%m%d'),
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
        status = "New"

        # Print the received data for debugging
        print("order_id:", order_id)
        print("Shop:", shop)
        print("User Name:", user_name)
        print("Save Date:", date)
        print("Table Data:")
        for row in table:
            print(row)

        # Check for order_id and delete existing records
        if order_id:
            db.session.query(TocReplenishOrder).filter_by(order_id=order_id).delete()
            db.session.query(TOCReplenishCtrl).filter_by(order_id=order_id).delete()
            status = "Saved"
        else:
            status = "New"

        # Insert new records into the table
        for row in table:
            sku, item_name, current_stock_qty, qty_sold_period, calc_replenish, replenish_order,  comments = row

            new_record = TocReplenishOrder(
                shop_id=shop,
                order_open_date=datetime.now(),
                sku=sku,
                order_id=order_id,
                user=user_name,
                item_name=item_name,
                replenish_qty = float(replenish_order) if replenish_order else 0,
                comments=comments
            )
            db.session.add(new_record)

        #Add tracking code

        new_record = TOCReplenishCtrl(
            order_id = order_id,
            shop_id = shop,
            order_open_date=date,
            user=user_name,
            order_status = status,
            order_status_date = datetime.now(),
            tracking_code = tracking_code,
            sold_qty=sold_qty,
            replenish_qty=replenish_qty,
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
    # Fetch the 20 most recent orders sorted by `order_open_date` in descending order
    recent_orders = (
        db.session.query(TOCReplenishCtrl)
        .order_by(TOCReplenishCtrl.order_open_date.desc())
        .limit(20)
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
        # Get JSON data from the request
        data = request.get_json()

        # Extract relevant information
        table = data.get('table', [])
        shop = data.get('shop', '')
        shop_name = data.get('shop_name', '')
        user_name = data.get('user_name', '')
        date = data.get('date', '')
        replenish_order_id = data.get('replenish_order_id', '')

        # Print the received data for debugging purposes
        print("Shop:", shop)
        print("User Name:", user_name)
        print("Update Date:", date)
        print("Table Data:", table)

        # Process each row and update the database
        for row in table:
            sku = row.get('sku', '')
            product_name = row.get('product_name', '')
            stock_count = row.get('stock_count', 0)
            variance = row.get('variance', 0)
            # variance_rsn = row.get('variance_reason', 'NA')
            stock_rejected = row.get('stock_rejected', 0)
            comments = row.get('comments', '')
            calc_stock_qty = row.get('current_qty', 0)
            last_stock_count = row.get('last_stock_count', 0)

            # Check if the record exists in TocStock
            existing_record = TocStock.query.filter_by(
                shop_id=shop,
                sku=sku
            ).first()

            if existing_record:
                # Update the existing record in TocStock
                existing_record.stock_qty_date = datetime.now(timezone.utc)
                existing_record.product_name = product_name
                existing_record.last_stock_qty = last_stock_count
                existing_record.stock_count = float(stock_count)
                existing_record.variance = float(variance)
                # existing_record.variance_rsn = variance_rsn
                existing_record.rejects_qty = float(stock_rejected)
                existing_record.comments = comments
                existing_record.count_by = user_name
                existing_record.calc_stock_qty = float(calc_stock_qty)
                existing_record.final_stock_qty = float(stock_count)
                existing_record.shop_name = shop_name
                existing_record.replenish_id = replenish_order_id
                existing_record.pastel_ind = 0
                existing_record.pastel_count = -99
            else:
                raise Exception("Shop SKU combination does not exist")

            # Insert into TOCStockVariance if Variance > 0
            if comments != '': #Assuming comments entered in client form only when there is variance
                new_variance_record = TOCStockVariance(
                    shop_id=shop,
                    sku=sku,
                    stock_qty_date=datetime.strptime(date, '%Y%m%d'),
                    product_name=product_name,
                    stock_count=float(stock_count),
                    count_by=user_name,
                    last_stock_qty=float(last_stock_count),
                    calc_stock_qty=float(calc_stock_qty),
                    variance=float(variance),
                    # variance_rsn=variance_rsn,
                    stock_recount=0,  # Add a default value if not provided
                    shop_name=shop_name,
                    rejects_qty=float(stock_rejected),
                    final_stock_qty=float(stock_count),
                    comments=comments,
                    replenish_id=replenish_order_id
                )
                db.session.add(new_variance_record)


        # Commit changes to the database
        db.session.commit()

        return jsonify({"status": "success", "message": "Stock data updated successfully"})

    except SQLAlchemyError as e:
        db.session.rollback()
        print("Database error:", e)
        return jsonify({"status": "error", "message": "Failed to update stock data", "error": str(e)}), 500

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500

@main.route('/update_count_receive_stock', methods=['POST'])
def update_count_receive_stock():
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
                # Update the existing record in TocStock
                existing_record.received_date = datetime.now(timezone.utc)
                existing_record.received_qty = stock_count
                # existing_record.rejected_qty = stock_rejected
                existing_record.variance = variance
                existing_record.received_by = user_name
                existing_record.received_comment = comments
            else:
                raise Exception("Shop SKU combination does not exist")

            # Insert into TOCStockVariance if Variance > 0
            if variance != 0:
                new_variance_record = TOCStockVariance(
                    shop_id=shop,
                    sku=sku,
                    stock_qty_date=datetime.strptime(date, '%Y%m%d'),
                    product_name=product_name,
                    stock_count=float(stock_count),
                    count_by=user_name,
                    last_stock_qty=float(stock_count),
                    calc_stock_qty=float(stock_sent),
                    variance=float(variance),
                    # variance_rsn=variance_rsn,
                    stock_recount=0,  # Add a default value if not provided
                    shop_name=shop_name,
                    # rejects_qty=float(stock_rejected),
                    final_stock_qty=float(stock_count),
                    comments=comments,
                    replenish_id = replenish_order_id
                )
                db.session.add(new_variance_record)

        # Update stock control
        toc_replenish_ctrl = TOCReplenishCtrl.query.filter(
            or_(TOCReplenishCtrl.order_status == "New", TOCReplenishCtrl.order_status == "Submitted"),
            TOCReplenishCtrl.order_id == replenish_order_id,
        ).first()

        toc_replenish_ctrl.order_status = "Completed"
        toc_replenish_ctrl.order_status_date = datetime.now(timezone.utc)

        # Commit changes to the database
        db.session.commit()

        return jsonify({"status": "success", "message": "Stock data updated successfully"})

    except SQLAlchemyError as e:
        db.session.rollback()
        print("Database error:", e)
        return jsonify({"status": "error", "message": "Failed to update stock data", "error": str(e)}), 500

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(e)}), 500
    finally:
        db.session.close()

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
        else:
            data = get_sales_report(report_type, from_date, to_date, group_by)

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
        elif report_type == "Consolidated Shop Stock Report":
            data = get_stock_value_per_shop()
        elif report_type == "Consolidated Variance Report":
            conn = get_db_connection()

            # Run SQL query (return raw date)
            query = """
            SELECT shop_name, 
                   stock_qty_date AS raw_date,  -- Fetch actual date
                   ROUND(SUM(a.variance * b.cost_price)) AS total_variance
            FROM toc_stock_variance a
            JOIN toc_product b ON a.sku = b.item_sku
            WHERE stock_qty_date > %s
            GROUP BY shop_name, stock_qty_date;
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
    print(data)
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

if __name__ == '__main__':
    app.run(debug=True)






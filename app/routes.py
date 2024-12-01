from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
import pymysql
import json
import os
import datetime
from app.models import  TocMessages, TocNotification, TOC_SHOPS
from sqlalchemy.exc import SQLAlchemyError
from .models import *
from . import db
from .db_queries import *
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)
main = Blueprint('main', __name__)

@main.route('/')
def login():
    return render_template('login.html')


@main.route('/index')
def index():
    user_data = session.get('user')
    roles = TocRole.query.all()

    # Convert the roles to a list of dictionaries
    roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

    if user_data:
        user = json.loads(user_data)
        return render_template('index.html', user=user, roles=roles_list)
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
    # Database connection details
    # hostname = "176.58.117.107"
    # username = "tasteofc_wp268"
    # password = "]44p7214)S"
    # database = "tasteofc_wp268" # Route to display the content of the toc_products table @app.route('/template') def template():
    # conn = pymysql.connect( host=hostname, user=username, password=password, database=database )
    # cursor = conn.cursor()
    # cursor.execute("SELECT * FROM toc_products")
    # products = cursor.fetchall()
    # cursor.close()
    # conn.close()
    return render_template('pages-blank.html')

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
    return render_template('users-profile.html', user=user, shop=shop)


@main.route('/receive_stock')
def receive_stock():
    try:
        # Get user and shop data
        user_data = session.get('user')
        user = json.loads(user_data)
        shop_data = session.get('shop')
        shop = json.loads(shop_data)
        roles = TocRole.query.all()
        # Convert the roles to a list of dictionaries
        roles_list = [{'role': role.role, 'exclusions': role.exclusions} for role in roles]

        # Query all records where order_status is 'New'
        replenish_orders_query = TOCReplenishCtrl.query.filter_by(order_status='New').all()

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
                "comments": order.comments,
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

    flash('User registered successfully')
    return redirect(url_for('main.login'))


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
        shop = json.loads(session.get('shop'))['customer']  # Assuming 'shop.customer' is stored in the session

        # Query tocStockOrder to check if there is any "New" order for the customer
        existing_order = TocStockOrder.query.filter_by(shop_id=shop, order_status="New").first()

        if not existing_order:
            # If no "New" order exists, return an empty array with a 200 status
            return jsonify([]), 200

        # Proceed with fetching the stock order form if an existing order is found
        data = get_stock_order_form()

        if not data:
            return jsonify({"message": "Error fetching stock order form data"}), 500

        # Format the data for the client
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

@main.route('/api/products', methods=['GET'])
def get_products():
    products = TocProduct.query.all()  # Query all rows from the table
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
    return jsonify(products_data)


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
            sku, item_name, count_qty, last_stock_qty, calc_stock_qty, variance_qty, variance_rsn, rejected_qty, order_qty, comments = row

            new_record = TocStockOrder(
                shop_id=shop,
                order_open_date=datetime.strptime(date, '%Y%m%d'),
                sku=sku,
                order_id=order_id,
                user=user_name,
                item_name=item_name,
                count_qty=float(count_qty) if count_qty else 0,
                variance_rsn=variance_rsn,
                rejected_qty=float(rejected_qty) if rejected_qty else 0,
                order_qty=float(order_qty) if order_qty else 0,
                comments=comments,
                order_status="New",
                order_status_date=datetime.now(),
                variance_qty=float(variance_qty) if variance_qty else 0
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

        status = "New"
        comment = "NA"

        new_record = TOCReplenishCtrl(
            order_id = order_id,
            shop_id = shop,
            order_open_date=datetime.now(),
            user=user_name,
            order_status = status,
            order_status_date = datetime.now(),
            tracking_code = tracking_code,
            comments=comment
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
            variance_rsn = row.get('variance_reason', 'NA')
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
                existing_record.variance_rsn = variance_rsn
                existing_record.rejects_qty = float(stock_rejected)
                existing_record.comments = comments
                existing_record.count_by = user_name
                existing_record.calc_stock_qty = float(calc_stock_qty)
                existing_record.final_stock_qty = float(stock_count)
                existing_record.shop_name = shop_name
                existing_record.replenish_id = replenish_order_id
            else:
                raise Exception("Shop SKU combination does not exist")

            # Insert into TOCStockVariance if Variance > 0
            if calc_stock_qty != stock_count:
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
                    variance_rsn=variance_rsn,
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
            variance_rsn = row.get('variance_reason', 'NA')
            stock_rejected = row.get('rejected_qty', 0)
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
                existing_record.rejected_qty = stock_rejected
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
                    variance_rsn=variance_rsn,
                    stock_recount=0,  # Add a default value if not provided
                    shop_name=shop_name,
                    rejects_qty=float(stock_rejected),
                    final_stock_qty=float(stock_count),
                    comments=comments,
                    replenish_id = replenish_order_id
                )
                db.session.add(new_variance_record)

        # Update stock control
        toc_replenish_ctrl = TOCReplenishCtrl.query.filter_by(
            order_id=replenish_order_id,
            order_status="New"
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


#####################################  Reports Section

@main.route('/sales_report')
def sales_report():
    user_data = session.get('user')
    user = json.loads(user_data)
    shop_data = session.get('shop')
    shop = json.loads(shop_data)
    shops = TOC_SHOPS.query.filter(TOC_SHOPS.store != '001').all()
    list_of_shops = [shop.blName for shop in shops]
    return render_template('sales_report_by_shop.html', user=user, shop=shop, shops=list_of_shops)


@main.route('/get_sales_per_shop_report')
def get_sales_per_shop_report():
    try:
        # Fetch the data from the function
        data = get_sales_by_shop()

        # Check if no data is returned
        if not data:
            return jsonify({"message": "Error fetching sales report"}), 500

        # Return the formatted data as JSON
        return jsonify(data)

    except Exception as e:
        # Handle any errors
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500




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
    data = get_sales_by_shop_last_three_months()
    return jsonify(data)

@main.route('/recent_sales', methods=['GET'])
def recent_sales():
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    data = get_recent_sales(shop_name)
    return jsonify(data)

@main.route('/top-products/<timeframe>', methods=['GET'])
def get_top_products(timeframe):
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    data = get_product_sales(timeframe, shop_name)
    return jsonify(data)

# routes.py
from flask import session, jsonify

@main.route('/hourly_sales/<timeframe>', methods=['GET'])
def hourly_sales(timeframe):
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    data = get_hourly_sales(shop_name, timeframe)
    return jsonify(data)

@main.route('/recent_sales_product/<timeframe>', methods=['GET'])
def recent_sales_product(timeframe):
    user_data = json.loads(session.get('user'))
    shop_name = user_data['shop']
    data = get_recent_product_sales(timeframe, shop_name)
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)






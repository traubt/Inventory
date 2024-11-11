from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
import json


from .models import User, TOC_SHOPS
from . import db
from .db_queries import  get_top_items, get_sales_summary, get_sales_data_for_lineChart, get_recent_sales, get_product_sales, get_hourly_sales

main = Blueprint('main', __name__)

@main.route('/')
def login():
    return render_template('login.html')

@main.route('/index')
def index():
    user_data = session.get('user')
    if user_data:
        user = json.loads(user_data)
        return render_template('index.html', user=user)
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
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'shop': user.shop,
        'role': user.role
    }
    session['user'] = json.dumps(user_data)
    return redirect(url_for('main.index'))

@main.route('/welcome/<username>')
def welcome(username):
    return f'Welcome {username}'

@main.route('/register')
def register():
    shops = TOC_SHOPS.query.all()
    return render_template('register.html', shops=shops)

@main.route('/faq')
def faq():
    return render_template('pages-faq.html')

@main.route('/template')
def template():
    # Database connection details
    hostname = "176.58.117.107"
    username = "tasteofc_wp268"
    password = "]44p7214)S"
    database = "tasteofc_wp268" # Route to display the content of the toc_products table @app.route('/template') def template():
    conn = pymysql.connect( host=hostname, user=username, password=password, database=database )
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM toc_products")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('pages-blank.html', products=products)


@main.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    shop = request.form.get('shop')
    role = 'Agent'

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




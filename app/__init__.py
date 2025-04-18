from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://tasteofc_wp268:]44p7214)S@176.58.117.107/tasteofc_wp268'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
    }
    db.init_app(app)

    # SMTP server configuration
    SMTP_SERVER = 'mail.tasteofcannabis.co.za'
    SMTP_PORT = 465
    SENDER_EMAIL = 'dashboard@tasteofcannabis.co.za'
    SENDER_PASSWORD = 'Plmokn098!@'
    RECIPIENT_EMAIL = 'traub.tomer@outlook.com'

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app

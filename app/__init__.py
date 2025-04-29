from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    # Core Configs
    app.config['SECRET_KEY'] = 'your_secret_key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://tasteofc_wp268:]44p7214)S@176.58.117.107/tasteofc_wp268'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
    }

    # OpenAI Key from Environment
    app.config["OPENAI_KEY"] = os.getenv("OPENAI_API_KEY")

    # Initialize DB
    db.init_app(app)

    # SMTP Email Config (optional for notifications)
    app.config['SMTP_SERVER'] = 'mail.tasteofcannabis.co.za'
    app.config['SMTP_PORT'] = 465
    app.config['SENDER_EMAIL'] = 'dashboard@tasteofcannabis.co.za'
    app.config['SENDER_PASSWORD'] = 'Plmokn098!@'
    app.config['RECIPIENT_EMAIL'] = 'traub.tomer@outlook.com'

    # Register Blueprints
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app

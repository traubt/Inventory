import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://tasteofc_wp268:]44p7214)S@176.58.117.107/tasteofc_wp268'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

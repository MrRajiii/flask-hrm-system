import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'secret_hr_key_12345'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///hrms.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

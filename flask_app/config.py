"""Class-based Flask app configuration."""
from os import environ, path
from dotenv import load_dotenv


basedir = path.abspath(path.dirname(path.dirname(__file__)))
load_dotenv(path.join(basedir, '.env'))


class Config:
    """Configuration from environment variables."""

    SECRET_KEY = environ.get('SECRET_KEY')
    FLASK_ENV = environ.get('FLASK_ENV')
    FLASK_APP = environ.get('FLASK_APP')
    SESSION_COOKIE_SECURE = environ.get('SESSION_COOKIE_SECURE', '').lower() == 'true'

    # Static Assets
    STATIC_FOLDER = 'static'
    TEMPLATES_FOLDER = 'templates'
    COMPRESSOR_DEBUG = True
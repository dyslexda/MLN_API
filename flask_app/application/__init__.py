import sys, os, logging, time
import connexion
from logging.handlers import RotatingFileHandler
from os import path
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from flask import Flask, session, g, request, has_request_context
from flask_assets import Environment
from flask_cors import CORS
from shared.api_models import db

def create_app():
    basedir = os.path.abspath(os.path.dirname(__file__))
    connex_app = connexion.FlaskApp(__name__,specification_dir='api/')
    connex_app.add_api('specification.yml')
    app = connex_app.app
    CORS(app)
    logging.basicConfig(level=logging.ERROR)
    app.config.from_object('config.Config')
    assets = Environment()
    assets.init_app(app)

    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        logger = logging.getLogger("baseball")
        logger.setLevel(logging.INFO)
        error_handler = RotatingFileHandler(filename='logs/baseball.log', maxBytes=10240, backupCount=10)
        error_handler.addFilter(LevelFilter(40,50))
        access_handler = RotatingFileHandler(filename='logs/access.log', maxBytes=10240, backupCount=10)
        access_handler.addFilter(LevelFilter(20,20))
        logger.addHandler(error_handler)
        logger.addHandler(access_handler)

    with app.app_context():
        from .index import index
        from .api import api

        app.register_blueprint(index.index_bp)
        app.register_blueprint(api.api_bp)

        @app.before_request
        def before_request():
            db.connect(reuse_if_open=True)
            if not app.debug: 
                if not request.environ['RAW_URI'].endswith(tuple(['.css','.js','.png','.ico'])):
                    report = access_log(request)
                    logger.info(report)
        @app.teardown_request
        def after_request(response):
            db.close()
            return response
        return app

def access_log(request):
    if 'HTTP_X_FORWARDED_FOR' in request.environ: ip = request.environ['HTTP_X_FORWARDED_FOR']
    else: ip = request.environ['REMOTE_ADDR']
    uri = request.environ['RAW_URI']
    if request.method == 'POST':
        payload = request.get_json(force=True)
    else: payload = ''
    report = (f"{time.asctime()}	{ip}	{uri}	{payload}")
    return(report)

class LevelFilter(logging.Filter):
    def __init__(self, low, high):
        self._low = low
        self._high = high
        logging.Filter.__init__(self)
    def filter(self,record):
        if self._low <= record.levelno <=self._high:
            return True
        return False

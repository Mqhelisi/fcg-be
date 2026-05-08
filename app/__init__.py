from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config

db      = SQLAlchemy()
migrate = Migrate()
jwt     = JWTManager()
bcrypt  = Bcrypt()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    CORS(app, origins=[
        'http://localhost:5173',
        'http://localhost:3000',
        'http://127.0.0.1:5173',
    ])
    limiter.init_app(app)

    from app.routes.auth     import auth_bp
    from app.routes.public   import public_bp
    from app.routes.customer import customer_bp
    from app.routes.admin    import admin_bp
    from app.routes.packer   import packer_bp
    from app.routes.driver   import driver_bp

    app.register_blueprint(auth_bp,     url_prefix='/api/auth')
    app.register_blueprint(public_bp,   url_prefix='/api/public')
    app.register_blueprint(customer_bp, url_prefix='/api/customer')
    app.register_blueprint(admin_bp,    url_prefix='/api/admin')
    app.register_blueprint(packer_bp,   url_prefix='/api/packer')
    app.register_blueprint(driver_bp,   url_prefix='/api/driver')

    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'app': 'First Class Groceries API', 'phase': '1-4'}

    return app

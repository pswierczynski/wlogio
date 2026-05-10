import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_name='default'):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static'),
    )
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Zaloguj się aby uzyskać dostęp.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from wlogio_app.models import User
        return User.query.get(int(user_id))

    from wlogio_app.routes.auth import auth_bp
    from wlogio_app.routes.dashboard import dashboard_bp
    from wlogio_app.routes.entries import entries_bp
    from wlogio_app.routes.settings import settings_bp
    from wlogio_app.routes.welcome import welcome_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(entries_bp, url_prefix='/entries')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(welcome_bp, url_prefix='/welcome')

    return app

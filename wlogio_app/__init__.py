import os
from flask import Flask, send_from_directory
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
    # Wyłącz automatyczny flash "Zaloguj się aby uzyskać dostęp"
    # — strona logowania nie potrzebuje tego komunikatu
    login_manager.login_message = None

    @login_manager.user_loader
    def load_user(user_id):
        from wlogio_app.models import User
        return User.query.get(int(user_id))

    from wlogio_app.routes.auth import auth_bp
    from wlogio_app.routes.dashboard import dashboard_bp
    from wlogio_app.routes.entries import entries_bp
    from wlogio_app.routes.settings import settings_bp
    from wlogio_app.routes.welcome import welcome_bp

    # UWAGA: nazwy endpointów (np. 'auth.login', 'dashboard.index') się NIE zmieniają —
    # zmienia się tylko prefiks URL, więc wszystkie url_for() w szablonach działają bez zmian.
    app.register_blueprint(auth_bp, url_prefix='')
    app.register_blueprint(dashboard_bp, url_prefix='/app')
    app.register_blueprint(entries_bp, url_prefix='/entries')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(welcome_bp, url_prefix='/terminal')

    # --- Landing page (statyczna strona www.wlogio.pl, folder /landing w korzeniu repo) ---
    landing_dir = os.path.join(base_dir, '..', 'landing')

    @app.route('/')
    def landing_index():
        return send_from_directory(landing_dir, 'index.html')

    @app.route('/rejestracja.html')
    def landing_rejestracja():
        return send_from_directory(landing_dir, 'rejestracja.html')

    @app.route('/assets/<path:filename>')
    def landing_assets(filename):
        return send_from_directory(os.path.join(landing_dir, 'assets'), filename)

    return app

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
    from wlogio_app.routes.welcome import welcome_bp, kiosk_bp
    from wlogio_app.routes.export import export_bp

    # UWAGA: nazwy endpointów (np. 'auth.login', 'dashboard.index') się NIE zmieniają —
    # zmienia się tylko prefiks URL, więc wszystkie url_for() w szablonach działają bez zmian.
    app.register_blueprint(auth_bp, url_prefix='')
    app.register_blueprint(dashboard_bp, url_prefix='/app')
    app.register_blueprint(entries_bp, url_prefix='/entries')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(welcome_bp, url_prefix='/terminal')
    app.register_blueprint(kiosk_bp, url_prefix='/kiosk')
    app.register_blueprint(export_bp, url_prefix='/app/export')

    @app.context_processor
    def inject_nav_context():
        """
        Udostępnia szablonom (base.html) informację o koncie, którego dane
        są aktualnie przeglądane — dla konta firmowego to wybrany pracownik
        (albo None, jeśli żaden nie jest jeszcze wybrany), dla pozostałych
        kont zawsze ono samo. Pozwala np. ukryć przycisk "Dodaj dzień", gdy
        nie ma kogo edytować, bez przekazywania tego ręcznie z każdej route.
        """
        from flask_login import current_user as _current_user
        if not _current_user.is_authenticated:
            return {}

        if _current_user.account_type == 'company':
            from wlogio_app.scope import get_effective_user
            nav_effective_user = get_effective_user()
        else:
            nav_effective_user = _current_user

        nav_display_name = _current_user.name or _current_user.email or _current_user.login or '?'

        return {
            'nav_effective_user': nav_effective_user,
            'nav_display_name': nav_display_name,
            'nav_account_label': _current_user.account_type_label,
        }

    # --- Landing page (statyczna strona www.wlogio.pl, folder /landing w korzeniu repo) ---
    landing_dir = os.path.join(base_dir, '..', 'landing')

    @app.route('/')
    @app.route('/index.html')
    def landing_index():
        return send_from_directory(landing_dir, 'index.html')

    # Podstrony strony marketingowej (linki w landing/ są względne: rejestracja.html itd.)
    for _page in ('regulamin', 'polityka-prywatnosci'):
        def _make(page):
            def view():
                return send_from_directory(landing_dir, page + '.html')
            view.__name__ = 'landing_' + page.replace('-', '_')
            return view
        app.add_url_rule('/' + _page + '.html', view_func=_make(_page))

    @app.route('/assets/<path:filename>')
    def landing_assets(filename):
        return send_from_directory(os.path.join(landing_dir, 'assets'), filename)

    return app

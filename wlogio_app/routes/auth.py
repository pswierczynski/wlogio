from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_, func
from wlogio_app import db
from wlogio_app.models import User, REGISTRATION_ACCOUNT_TYPES, COMPANY_SIZES

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        # Konta indywidualne/firmowe logują się emailem, konta pracownicze —
        # loginem nadanym przez administratora konta firmowego.
        user = User.query.filter(
            or_(
                func.lower(User.email) == identifier,
                func.lower(User.login) == identifier,
            )
        ).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))

        flash('Nieprawidłowy email/login lub hasło.', 'error')

    # Wejście z wlogio.pl/kiosk/ — od razu zakładka terminala i powrót do kiosku.
    kiosk = request.args.get('next') == '/kiosk/'
    return render_template('auth/login.html', kiosk=kiosk)


# Mapowanie parametrów z linków na stronie (cennik) na wartości formularza.
_TYP_MAP = {'indywidualna': 'individual', 'firmowa': 'company'}
_PLAN_MAP = {'mala': 'small', 'srednia': 'medium', 'duza': 'large'}


def _register_error(message, form):
    return render_template(
        'site/rejestracja.html', error=message,
        form={
            'account_type': form.get('account_type') if form.get('account_type') in REGISTRATION_ACCOUNT_TYPES else 'individual',
            'company_size': form.get('company_size') if form.get('company_size') in COMPANY_SIZES else 'small',
            'name': form.get('name', ''),
            'email': form.get('email', ''),
        },
    ), 400


@auth_bp.route('/rejestracja', methods=['GET', 'POST'])
def register():
    """Rejestracja konta — jedyny formularz (strona wlogio.pl/rejestracja)."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        f = request.form
        email = f.get('email', '').strip().lower()
        password = f.get('password', '')
        password2 = f.get('password2', '')
        terminal_password = f.get('terminal_password', '')
        terminal_password2 = f.get('terminal_password2', '')
        name = f.get('name', '').strip()
        account_type = f.get('account_type', '')
        company_size = f.get('company_size', '')

        if not email or not password:
            return _register_error('Email i hasło są wymagane.', f)
        if account_type not in REGISTRATION_ACCOUNT_TYPES:
            return _register_error('Wybierz typ konta.', f)
        if account_type == 'company' and not name:
            return _register_error('Nazwa firmy jest wymagana.', f)
        if account_type == 'company' and company_size not in COMPANY_SIZES:
            return _register_error('Wybierz wielkość firmy.', f)
        if password != password2:
            return _register_error('Hasła nie są identyczne.', f)
        if len(password) < 6:
            return _register_error('Hasło musi mieć minimum 6 znaków.', f)
        if len(terminal_password) < 6:
            return _register_error('Hasło do terminala musi mieć minimum 6 znaków.', f)
        if terminal_password != terminal_password2:
            return _register_error('Hasła do terminala nie są identyczne.', f)
        if terminal_password == password:
            return _register_error('Hasło do terminala musi być inne niż hasło do panelu pracy.', f)
        if User.query.filter_by(email=email).first():
            return _register_error('Ten adres email jest już zarejestrowany.', f)

        user = User(email=email, name=name, account_type=account_type,
                    company_size=company_size if account_type == 'company' else None)
        user.set_password(password)
        user.set_terminal_password(terminal_password)
        user.generate_pin()
        db.session.add(user)
        db.session.commit()

        from wlogio_app.models import VacationBalance
        from datetime import date
        balance = VacationBalance(
            user_id=user.id,
            year=date.today().year,
            vacation_total=26,
            on_demand_total=4,
            remote_total=24,
        )
        db.session.add(balance)
        db.session.commit()

        flash('Konto utworzone. Możesz się zalogować.', 'success')
        return redirect(url_for('auth.login'))

    # GET — wstępny wybór planu z linków w cenniku (?typ=firmowa&plan=srednia)
    account_type = _TYP_MAP.get(request.args.get('typ', ''), 'individual')
    company_size = _PLAN_MAP.get(request.args.get('plan', ''), 'small')
    return render_template('site/rejestracja.html', error=None, form={
        'account_type': account_type, 'company_size': company_size, 'name': '', 'email': '',
    })


@auth_bp.route('/register/')
@auth_bp.route('/rejestracja.html')
def register_legacy():
    """Stare adresy rejestracji — przekierowanie na /rejestracja (zachowuje parametry)."""
    return redirect(url_for('auth.register', **request.args), code=301)


@auth_bp.route('/logout/')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

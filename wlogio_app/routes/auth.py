from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from wlogio_app import db
from wlogio_app.models import User

auth_bp = Blueprint('auth', __name__)

WELCOME_PASSWORD = 'Przemek121!'


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))

        if not email and password == WELCOME_PASSWORD:
            return redirect(url_for('welcome.index'))

        flash('Nieprawidłowy email lub hasło.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        name = request.form.get('name', '').strip()

        if not email or not password:
            flash('Email i hasło są wymagane.', 'error')
            return render_template('auth/register.html')
        if password != password2:
            flash('Hasła nie są identyczne.', 'error')
            return render_template('auth/register.html')
        if len(password) < 6:
            flash('Hasło musi mieć minimum 6 znaków.', 'error')
            return render_template('auth/register.html')
        if User.query.filter_by(email=email).first():
            flash('Ten adres email jest już zarejestrowany.', 'error')
            return render_template('auth/register.html')

        user = User(email=email, name=name)
        user.set_password(password)
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

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

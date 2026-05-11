import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from decimal import Decimal

from wlogio_app import db
from wlogio_app.models import MonthConfig, VacationBalance, User
from wlogio_app.calculator import get_working_days_in_billing_period, get_or_create_vacation_balance

settings_bp = Blueprint('settings', __name__)

MONTH_NAMES = {
    1: 'Styczeń', 2: 'Luty', 3: 'Marzec', 4: 'Kwiecień',
    5: 'Maj', 6: 'Czerwiec', 7: 'Lipiec', 8: 'Sierpień',
    9: 'Wrzesień', 10: 'Październik', 11: 'Listopad', 12: 'Grudzień'
}

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_avatar_to_supabase(file_data, user_id, filename, content_type):
    import requests
    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key = os.environ.get('SUPABASE_SERVICE_KEY', '')
    bucket = 'avatars'

    if not supabase_url or not service_key:
        return None, 'Brak konfiguracji SUPABASE_URL lub SUPABASE_SERVICE_KEY'

    headers = {
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
    }

    # Usuń stare pliki we wszystkich rozszerzeniach
    for ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        requests.delete(
            f'{supabase_url}/storage/v1/object/{bucket}/{user_id}.{ext}',
            headers=headers
        )

    upload_headers = {**headers, 'Content-Type': content_type, 'x-upsert': 'true'}

    # Próbuj PUT, fallback POST
    for method in ('PUT', 'POST'):
        r = getattr(requests, method.lower())(
            f'{supabase_url}/storage/v1/object/{bucket}/{filename}',
            headers=upload_headers,
            data=file_data
        )
        if r.status_code in (200, 201):
            return f'{supabase_url}/storage/v1/object/public/{bucket}/{filename}', None

    return None, f'HTTP {r.status_code}: {r.text[:200]}'


def delete_avatar_from_supabase(user_id):
    import requests
    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key = os.environ.get('SUPABASE_SERVICE_KEY', '')
    bucket = 'avatars'

    if not supabase_url or not service_key:
        return False

    headers = {
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
    }

    deleted = False
    for ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        r = requests.delete(
            f'{supabase_url}/storage/v1/object/{bucket}/{user_id}.{ext}',
            headers=headers
        )
        if r.status_code in (200, 204):
            deleted = True
    return deleted


@settings_bp.route('/')
@login_required
def index():
    configs = (
        MonthConfig.query
        .filter_by(user_id=current_user.id)
        .order_by(MonthConfig.billing_year.desc(), MonthConfig.billing_month.desc())
        .all()
    )
    balance = get_or_create_vacation_balance(current_user.id, db.session)
    return render_template('settings/index.html', configs=configs, balance=balance, MONTH_NAMES=MONTH_NAMES)


@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'upload_avatar':
            if 'avatar' not in request.files:
                flash('Nie wybrano pliku.', 'error')
                return redirect(url_for('settings.profile'))

            file = request.files['avatar']
            if not file or file.filename == '':
                flash('Nie wybrano pliku.', 'error')
                return redirect(url_for('settings.profile'))

            if not allowed_file(file.filename):
                flash('Dozwolone formaty: PNG, JPG, GIF, WebP.', 'error')
                return redirect(url_for('settings.profile'))

            file_data = file.read()
            if len(file_data) > MAX_FILE_SIZE:
                flash('Plik jest za duży (max 5MB).', 'error')
                return redirect(url_for('settings.profile'))

            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f'{current_user.id}.{ext}'
            content_type = file.content_type or f'image/{ext}'

            url, error = upload_avatar_to_supabase(file_data, current_user.id, filename, content_type)

            if url:
                current_user.avatar = url
                db.session.commit()
                flash('Zdjęcie profilowe zaktualizowane.', 'success')
            else:
                flash(f'Błąd wgrywania zdjęcia: {error}', 'error')

        elif action == 'delete_avatar':
            if current_user.avatar:
                delete_avatar_from_supabase(current_user.id)
                current_user.avatar = None
                db.session.commit()
                flash('Zdjęcie profilowe usunięte.', 'success')
            else:
                flash('Brak zdjęcia do usunięcia.', 'error')

        elif action == 'update_name':
            name = request.form.get('name', '').strip()
            if name:
                current_user.name = name
                db.session.commit()
                flash('Imię i nazwisko zaktualizowane.', 'success')

        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            new_password2 = request.form.get('new_password2', '')

            if not current_user.check_password(current_password):
                flash('Nieprawidłowe aktualne hasło.', 'error')
            elif len(new_password) < 6:
                flash('Nowe hasło musi mieć minimum 6 znaków.', 'error')
            elif new_password != new_password2:
                flash('Nowe hasła nie są identyczne.', 'error')
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash('Hasło zmienione.', 'success')

        return redirect(url_for('settings.profile'))

    return render_template('settings/profile.html')


@settings_bp.route('/month/<int:year>/<int:month>', methods=['GET', 'POST'])
@login_required
def month_config(year, month):
    config = MonthConfig.query.filter_by(
        user_id=current_user.id, billing_year=year, billing_month=month
    ).first_or_404()

    working_days = get_working_days_in_billing_period(year, month)
    expected_hours = working_days * 8

    if request.method == 'POST':
        try:
            config.hourly_rate = Decimal(request.form.get('hourly_rate', '0').replace(',', '.'))
            config.expected_hours = Decimal(str(expected_hours))
            bonus_str = request.form.get('bonus', '0').replace(',', '.').strip()
            config.bonus = Decimal(bonus_str) if bonus_str else Decimal('0')
            config.notes = request.form.get('notes', '').strip() or None
            db.session.commit()
            flash('Konfiguracja miesiąca zapisana.', 'success')
        except Exception as e:
            flash(f'Błąd: {e}', 'error')
        return redirect(url_for('settings.index'))

    return render_template('settings/month_config.html', config=config,
                           expected_hours=expected_hours, working_days=working_days,
                           MONTH_NAMES=MONTH_NAMES)


@settings_bp.route('/vacation', methods=['GET', 'POST'])
@login_required
def vacation_balance():
    balance = get_or_create_vacation_balance(current_user.id, db.session)

    if request.method == 'POST':
        try:
            balance.vacation_total = int(request.form.get('vacation_total', 26))
            balance.on_demand_total = int(request.form.get('on_demand_total', 4))
            balance.remote_total = int(request.form.get('remote_total', 24))
            db.session.commit()
            flash('Bilans urlopowy zapisany.', 'success')
        except Exception as e:
            flash(f'Błąd: {e}', 'error')
        return redirect(url_for('settings.index'))

    return render_template('settings/vacation_balance.html', balance=balance)

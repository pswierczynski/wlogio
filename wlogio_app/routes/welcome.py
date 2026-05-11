"""
welcome.py - Ekran powitalny (kiosk biurowy)

Obsługa pracy przez północ:
- clock_in zawsze tworzy wpis na dzień ROZPOCZĘCIA pracy
- clock_out, break_start, break_end szukają AKTYWNEGO wpisu (clock_in bez clock_out)
  niezależnie od daty - praca przez północ przypisana do dnia rozpoczęcia
"""

from flask import Blueprint, render_template, request, jsonify, session
from datetime import datetime, date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Europe/Warsaw')

from wlogio_app import db
from wlogio_app.models import User, WorkEntry
from wlogio_app.calculator import get_billing_period

welcome_bp = Blueprint('welcome', __name__)

WELCOME_PASSWORD = 'Przemek121!'


def get_active_entry(user_id):
    """
    Zwraca aktywny wpis użytkownika - taki który ma clock_in ale nie ma clock_out.
    Przeszukuje dzisiaj i wczoraj (obsługa pracy przez północ).
    """
    today = datetime.now(TIMEZONE).date()
    yesterday = today - timedelta(days=1)

    # Szukaj aktywnego wpisu (clock_in bez clock_out) - najpierw dzisiaj, potem wczoraj
    for check_date in [today, yesterday]:
        entry = WorkEntry.query.filter_by(user_id=user_id, date=check_date).first()
        if entry and entry.clock_in and not entry.clock_out:
            return entry

    return None


def get_user_status(user_id):
    """
    Zwraca status użytkownika: 'idle', 'working', 'break'
    Uwzględnia pracę przez północ.
    """
    entry = get_active_entry(user_id)
    if not entry:
        return 'idle'
    if entry.break_clock_start and not entry.break_clock_end:
        return 'break'
    return 'working'


@welcome_bp.route('/')
def index():
    """Ekran powitalny z siatką avatarów."""
    users = User.query.filter(
        User.is_active == True,
        User.avatar.isnot(None)
    ).all()

    user_statuses = {user.id: get_user_status(user.id) for user in users}

    return render_template('welcome/index.html', users=users, user_statuses=user_statuses)


@welcome_bp.route('/verify-password', methods=['POST'])
def verify_password():
    data = request.get_json()
    if data.get('password', '') == WELCOME_PASSWORD:
        session['welcome_access'] = True
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 401


@welcome_bp.route('/verify-pin', methods=['POST'])
def verify_pin():
    data = request.get_json()
    user_id = data.get('user_id')
    pin = data.get('pin', '')

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        return jsonify({'ok': False}), 401

    today = datetime.now(TIMEZONE).date()

    # Szukaj aktywnego wpisu (praca przez północ) lub dzisiejszego
    entry = get_active_entry(user_id)
    if not entry:
        entry = WorkEntry.query.filter_by(user_id=user.id, date=today).first()

    return jsonify({
        'ok': True,
        'user_id': user.id,
        'user_name': user.name or user.email,
        'date': (entry.date if entry else today).strftime('%d.%m.%Y'),
        'clock_in': entry.clock_in.strftime('%H:%M') if entry and entry.clock_in else None,
        'clock_out': entry.clock_out.strftime('%H:%M') if entry and entry.clock_out else None,
        'break_start': entry.break_clock_start.strftime('%H:%M') if entry and entry.break_clock_start else None,
        'break_end': entry.break_clock_end.strftime('%H:%M') if entry and entry.break_clock_end else None,
    })


@welcome_bp.route('/clock', methods=['POST'])
def clock():
    data = request.get_json()
    user_id = data.get('user_id')
    action = data.get('action')
    pin = data.get('pin', '')

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        return jsonify({'ok': False, 'error': 'Nieautoryzowany'}), 401

    now_dt = datetime.now(TIMEZONE)
    now = now_dt.time()
    today = now_dt.date()

    if action == 'clock_in':
        # Sprawdź czy już jest aktywny wpis
        active = get_active_entry(user_id)
        if active:
            return jsonify({'ok': False, 'error': 'Już zarejestrowano przyjście'}), 400

        # Sprawdź wpis na dzisiaj
        entry = WorkEntry.query.filter_by(user_id=user_id, date=today).first()
        if entry and entry.clock_in:
            return jsonify({'ok': False, 'error': 'Już zarejestrowano przyjście'}), 400

        if not entry:
            billing_year, billing_month = get_billing_period(today)
            entry = WorkEntry(
                user_id=user_id,
                date=today,
                billing_year=billing_year,
                billing_month=billing_month,
                entry_type='work',
                hours_worked=Decimal('0'),
                hours_billed=Decimal('0'),
            )
            db.session.add(entry)

        entry.clock_in = now
        entry.time_start = now
        label = f'Przyjście: {now.strftime("%H:%M")}'

    elif action in ('clock_out', 'break_start', 'break_end'):
        # Szukaj aktywnego wpisu (obsługa pracy przez północ)
        entry = get_active_entry(user_id)
        if not entry:
            # Fallback: wpis na dziś
            entry = WorkEntry.query.filter_by(user_id=user_id, date=today).first()

        if not entry or not entry.clock_in:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400

        if action == 'clock_out':
            if entry.clock_out:
                return jsonify({'ok': False, 'error': 'Już zarejestrowano wyjście'}), 400

            # Aktywna przerwa - zakończ automatycznie
            if entry.break_clock_start and not entry.break_clock_end:
                entry.break_clock_end = now
                entry.break_end = now

            entry.clock_out = now
            entry.time_end = now

            # Przelicz godziny z obsługą pracy przez północ
            if entry.time_start:
                from wlogio_app.calculator import calculate_hours
                calc = calculate_hours(
                    entry.time_start, entry.time_end,
                    entry.break_clock_start, entry.break_clock_end
                )
                entry.hours_worked = Decimal(str(calc['hours_worked']))
                entry.hours_billed = Decimal(str(calc['hours_billed']))
                entry.extra_break_minutes = calc['extra_break_minutes']
            label = f'Wyjście: {now.strftime("%H:%M")}'

        elif action == 'break_start':
            if entry.break_clock_start:
                return jsonify({'ok': False, 'error': 'Przerwa już rozpoczęta'}), 400
            entry.break_clock_start = now
            entry.break_start = now
            label = f'Przerwa od: {now.strftime("%H:%M")}'

        elif action == 'break_end':
            if not entry.break_clock_start:
                return jsonify({'ok': False, 'error': 'Najpierw rozpocznij przerwę'}), 400
            if entry.break_clock_end:
                return jsonify({'ok': False, 'error': 'Przerwa już zakończona'}), 400
            entry.break_clock_end = now
            entry.break_end = now
            label = f'Przerwa do: {now.strftime("%H:%M")}'

    else:
        return jsonify({'ok': False, 'error': 'Nieznana akcja'}), 400

    db.session.commit()

    return jsonify({
        'ok': True,
        'label': label,
        'time': now.strftime('%H:%M'),
        'clock_in': entry.clock_in.strftime('%H:%M') if entry.clock_in else None,
        'clock_out': entry.clock_out.strftime('%H:%M') if entry.clock_out else None,
        'break_start': entry.break_clock_start.strftime('%H:%M') if entry.break_clock_start else None,
        'break_end': entry.break_clock_end.strftime('%H:%M') if entry.break_clock_end else None,
    })


@welcome_bp.route('/avatar/<int:user_id>')
def avatar(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({'url': user.avatar})

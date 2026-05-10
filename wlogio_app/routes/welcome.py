"""
welcome.py - Ekran powitalny (kiosk biurowy)
Dostępny po wpisaniu hasła Przemek121! na ekranie logowania.
"""

from flask import Blueprint, render_template, request, jsonify, session, current_app
from datetime import datetime, date
from decimal import Decimal

from wlogio_app import db
from wlogio_app.models import User, WorkEntry
from wlogio_app.calculator import get_billing_period

welcome_bp = Blueprint('welcome', __name__)

WELCOME_PASSWORD = 'Przemek121!'


@welcome_bp.route('/')
def index():
    """Ekran powitalny z siatką avatarów."""
    # Tylko użytkownicy z avatarem
    users = User.query.filter(
        User.is_active == True,
        User.avatar.isnot(None)
    ).all()

    return render_template('welcome/index.html', users=users)


@welcome_bp.route('/verify-password', methods=['POST'])
def verify_password():
    """Weryfikacja hasła ekranu powitalnego."""
    data = request.get_json()
    password = data.get('password', '')

    if password == WELCOME_PASSWORD:
        session['welcome_access'] = True
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 401


@welcome_bp.route('/verify-pin', methods=['POST'])
def verify_pin():
    """Weryfikacja PIN użytkownika."""
    data = request.get_json()
    user_id = data.get('user_id')
    pin = data.get('pin', '')

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        return jsonify({'ok': False}), 401

    today = date.today()

    # Znajdź lub utwórz wpis na dziś
    entry = WorkEntry.query.filter_by(
        user_id=user.id,
        date=today
    ).first()

    # Status przycisków
    status = {
        'ok': True,
        'user_id': user.id,
        'user_name': user.name or user.email,
        'date': today.strftime('%d.%m.%Y'),
        'clock_in': entry.clock_in.strftime('%H:%M') if entry and entry.clock_in else None,
        'clock_out': entry.clock_out.strftime('%H:%M') if entry and entry.clock_out else None,
        'break_start': entry.break_clock_start.strftime('%H:%M') if entry and entry.break_clock_start else None,
        'break_end': entry.break_clock_end.strftime('%H:%M') if entry and entry.break_clock_end else None,
    }

    return jsonify(status)


@welcome_bp.route('/clock', methods=['POST'])
def clock():
    """
    Obsługuje przyciski czasu pracy.
    action: 'clock_in', 'clock_out', 'break_start', 'break_end'
    """
    data = request.get_json()
    user_id = data.get('user_id')
    action = data.get('action')
    pin = data.get('pin', '')

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        return jsonify({'ok': False, 'error': 'Nieautoryzowany'}), 401

    now = datetime.now().time()
    today = date.today()

    # Pobierz lub utwórz wpis
    entry = WorkEntry.query.filter_by(user_id=user.id, date=today).first()

    if not entry:
        billing_year, billing_month = get_billing_period(today)
        entry = WorkEntry(
            user_id=user.id,
            date=today,
            billing_year=billing_year,
            billing_month=billing_month,
            entry_type='work',
            hours_worked=Decimal('0'),
            hours_billed=Decimal('0'),
        )
        db.session.add(entry)

    # Każdy przycisk można wcisnąć tylko raz dziennie
    if action == 'clock_in':
        if entry.clock_in:
            return jsonify({'ok': False, 'error': 'Już zarejestrowano przyjście'}), 400
        entry.clock_in = now
        entry.time_start = now
        label = f'Przyjście: {now.strftime("%H:%M")}'

    elif action == 'clock_out':
        if not entry.clock_in:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400
        if entry.clock_out:
            return jsonify({'ok': False, 'error': 'Już zarejestrowano wyjście'}), 400
        entry.clock_out = now
        entry.time_end = now

        # Przelicz godziny
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
        if not entry.clock_in:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400
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
    """Zwraca URL avatara użytkownika z Supabase Storage."""
    user = User.query.get_or_404(user_id)
    if not user.avatar:
        return jsonify({'url': None})
    return jsonify({'url': user.avatar})

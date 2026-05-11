"""
welcome.py - Ekran powitalny (kiosk biurowy)

Logika statusów użytkownika (uwzględnia dane z dashboardu i ekranu powitalnego):

Status 'working' gdy:
  - clock_in bez clock_out (ekran powitalny), LUB
  - time_start bez time_end ustawione dziś (dashboard), jeśli aktualna godzina >= time_start

Status 'break' gdy:
  - break_clock_start bez break_clock_end (ekran powitalny), LUB
  - break_start bez break_end ustawione dziś, jeśli aktualna godzina >= break_start

Status 'idle' gdy:
  - clock_out ustawiony (ekran powitalny), LUB
  - time_end ustawiony i aktualna godzina >= time_end (dashboard), LUB
  - brak clock_in i brak time_start

Obsługa pracy przez północ:
  Szukamy aktywnego wpisu (clock_in bez clock_out) również z poprzedniego dnia.
"""

from flask import Blueprint, render_template, request, jsonify, session
from datetime import datetime, date, timedelta, time as dt_time
from decimal import Decimal
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Europe/Warsaw')

from wlogio_app import db
from wlogio_app.models import User, WorkEntry
from wlogio_app.calculator import get_billing_period

welcome_bp = Blueprint('welcome', __name__)

WELCOME_PASSWORD = 'Przemek121!'


def time_to_minutes(t):
    """Konwertuje datetime.time na minuty od północy."""
    return t.hour * 60 + t.minute


def get_active_entry(user_id):
    """
    Zwraca aktywny wpis (clock_in bez clock_out).
    Szuka dzisiaj i wczoraj (obsługa pracy przez północ).
    """
    today = datetime.now(TIMEZONE).date()
    yesterday = today - timedelta(days=1)

    for check_date in [today, yesterday]:
        entry = WorkEntry.query.filter_by(user_id=user_id, date=check_date).first()
        if entry and entry.clock_in and not entry.clock_out:
            return entry
    return None


def compute_user_status(user_id):
    """
    Oblicza status użytkownika uwzględniając:
    1. Dane z ekranu powitalnego (clock_in, clock_out, break_clock_*)
    2. Dane z dashboardu (time_start, time_end, break_start, break_end)
    3. Aktualną godzinę
    4. Pracę przez północ

    Zwraca: 'idle' | 'working' | 'break'
    """
    now_dt = datetime.now(TIMEZONE)
    now_min = now_dt.hour * 60 + now_dt.minute
    today = now_dt.date()
    yesterday = today - timedelta(days=1)

    # Zbierz wpisy z dziś i wczoraj
    entries = []
    for check_date in [today, yesterday]:
        entry = WorkEntry.query.filter_by(user_id=user_id, date=check_date).first()
        if entry:
            entries.append(entry)

    for entry in entries:
        # --- Dane z ekranu powitalnego mają pierwszeństwo ---
        if entry.clock_in and not entry.clock_out:
            # Praca aktywna przez ekran powitalny
            if entry.break_clock_start and not entry.break_clock_end:
                return 'break'
            return 'working'

        if entry.clock_out:
            # Zakończono przez ekran powitalny
            # Ale sprawdź czy to nie wpis z wczoraj (praca przez północ zakończona)
            # W takim razie dziś jest idle
            return 'idle'

        # --- Dane z dashboardu (time_start/time_end) ---
        if entry.date == today and entry.time_start:
            start_min = time_to_minutes(entry.time_start)

            # Sprawdź zakończenie pracy
            if entry.time_end:
                end_min = time_to_minutes(entry.time_end)
                # Obsługa przez północ
                if end_min < start_min:
                    end_min += 24 * 60

                if now_min >= end_min:
                    return 'idle'
            elif now_min < start_min:
                # Praca jeszcze nie zaczęta
                continue

            # Praca trwa - sprawdź przerwę
            if entry.break_start:
                bs_min = time_to_minutes(entry.break_start)
                if now_min >= bs_min:
                    if entry.break_end:
                        be_min = time_to_minutes(entry.break_end)
                        if be_min < bs_min:
                            be_min += 24 * 60
                        if now_min >= be_min:
                            return 'working'
                    return 'break'

            return 'working'

    return 'idle'


def get_entry_clock_status(user_id):
    """
    Zwraca słownik z danymi clock dla użytkownika.
    Uwzględnia dane z dashboardu jako fallback.
    """
    now_dt = datetime.now(TIMEZONE)
    now_min = now_dt.hour * 60 + now_dt.minute
    today = now_dt.date()

    active = get_active_entry(user_id)
    if active:
        entry = active
    else:
        entry = WorkEntry.query.filter_by(user_id=user_id, date=today).first()

    if not entry:
        return {
            'clock_in': None, 'clock_out': None,
            'break_start': None, 'break_end': None,
        }

    # Preferuj dane z ekranu powitalnego, fallback na dashboard
    clock_in = entry.clock_in or entry.time_start
    clock_out = entry.clock_out or entry.time_end
    break_start = entry.break_clock_start or entry.break_start
    break_end = entry.break_clock_end or entry.break_end

    # Dla danych z dashboardu - uwzględnij aktualny czas
    if not entry.clock_in and entry.time_start:
        start_min = time_to_minutes(entry.time_start)
        if now_min < start_min:
            clock_in = None  # Praca jeszcze nie zaczęta

    if not entry.clock_out and entry.time_end and clock_in:
        end_min = time_to_minutes(entry.time_end)
        start_min = time_to_minutes(clock_in)
        if end_min < start_min:
            end_min += 24 * 60
        if now_min < end_min:
            clock_out = None  # Praca jeszcze nie zakończona

    return {
        'clock_in': clock_in.strftime('%H:%M') if clock_in else None,
        'clock_out': clock_out.strftime('%H:%M') if clock_out else None,
        'break_start': break_start.strftime('%H:%M') if break_start else None,
        'break_end': break_end.strftime('%H:%M') if break_end else None,
        'date': entry.date.strftime('%d.%m.%Y'),
    }


@welcome_bp.route('/')
def index():
    """Ekran powitalny z siatką avatarów."""
    users = User.query.filter(User.is_active == True).all()
    user_statuses = {user.id: compute_user_status(user.id) for user in users}

    return render_template('welcome/index.html', users=users, user_statuses=user_statuses)


@welcome_bp.route('/statuses')
def statuses():
    """
    Endpoint JSON ze statusami wszystkich użytkowników.
    Używany do pollingu co 10s na ekranie powitalnym.
    """
    users = User.query.filter(User.is_active == True).all()
    result = {}
    for user in users:
        result[str(user.id)] = compute_user_status(user.id)
    return jsonify(result)


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

    clock_data = get_entry_clock_status(user_id)

    return jsonify({
        'ok': True,
        'user_id': user.id,
        'user_name': user.name or user.email,
        **clock_data,
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
        active = get_active_entry(user_id)
        if active:
            return jsonify({'ok': False, 'error': 'Już zarejestrowano przyjście'}), 400

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
        entry = get_active_entry(user_id)
        if not entry:
            entry = WorkEntry.query.filter_by(user_id=user_id, date=today).first()

        if not entry or not entry.clock_in:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400

        if action == 'clock_out':
            if entry.clock_out:
                return jsonify({'ok': False, 'error': 'Już zarejestrowano wyjście'}), 400

            if entry.break_clock_start and not entry.break_clock_end:
                entry.break_clock_end = now
                entry.break_end = now

            entry.clock_out = now
            entry.time_end = now

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

"""
welcome.py - Ekran powitalny

Logika statusów (na podstawie time_start/time_end/break_start/break_end):

'working' = time_start ustawiony ORAZ (brak time_end LUB aktualna godzina < time_end)
'break'   = warunek 'working' spełniony ORAZ break_start ustawiony
            ORAZ (brak break_end LUB aktualna godzina < break_end)
'idle'    = wszystkie pozostałe przypadki
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


def now_minutes():
    """Aktualna godzina w minutach od północy (strefa Warsaw)."""
    t = datetime.now(TIMEZONE)
    return t.hour * 60 + t.minute


def to_min(t):
    """datetime.time -> minuty od północy."""
    if t is None:
        return None
    return t.hour * 60 + t.minute


def compute_status(entry):
    """
    Oblicza status na podstawie wpisu WorkEntry i aktualnej godziny.
    Zwraca: 'idle' | 'working' | 'break'

    Reguły:
    - Brak time_start                          → idle
    - time_start, brak time_end                → working bezterminowo (do odwołania)
    - time_start + time_end, now >= time_end   → idle
    - working + break_start, brak break_end    → break bezterminowo (do odwołania)
    - working + break_start + break_end        → break tylko gdy now < break_end

    Uwaga: warunek "przez północ" to ŚCIŚLE end < start (nie <=).
    Równe godziny (np. break_start == break_end) oznaczają zerową przerwę → working.
    """
    if entry is None:
        return 'idle'

    now = now_minutes()
    start_min = to_min(entry.time_start)
    end_min   = to_min(entry.time_end)
    bs_min    = to_min(entry.break_start)
    be_min    = to_min(entry.break_end)

    # Brak godziny przyjścia → idle
    if start_min is None:
        return 'idle'

    # Obsługa pracy przez północ (ŚCIŚLE end < start)
    if end_min is not None and end_min < start_min:
        end_min += 24 * 60

    # Przed przyjściem → idle
    if now < start_min:
        return 'idle'

    # Po wyjściu (jeśli ustawione) → idle
    if end_min is not None and now >= end_min:
        return 'idle'

    # Jesteśmy w czasie pracy — sprawdź przerwę
    if bs_min is not None:
        # Obsługa przerwy przez północ (ŚCIŚLE be < bs)
        if be_min is not None and be_min < bs_min:
            be_min += 24 * 60

        # Równe godziny (break_start == break_end) = zerowa przerwa = working
        after_break_start = now >= bs_min
        before_break_end  = (be_min is None) or (now < be_min)

        if after_break_start and before_break_end:
            # Jeśli be_min == bs_min (zerowa przerwa) — before_break_end = (now < bs_min) = False
            # bo now >= bs_min → poprawnie nie wchodzimy w break
            return 'break'

    return 'working'


def get_today_entry(user_id):
    """Pobiera wpis na dziś lub wczoraj (dla pracy przez północ)."""
    today     = datetime.now(TIMEZONE).date()
    yesterday = today - timedelta(days=1)

    entry_yesterday = WorkEntry.query.filter_by(user_id=user_id, date=yesterday).first()
    if entry_yesterday and entry_yesterday.time_start:
        s = to_min(entry_yesterday.time_start)
        e = to_min(entry_yesterday.time_end)
        now = now_minutes()
        # Praca przez północ: start wieczorem, end rano (e < s)
        if e is not None and e < s and now < e:
            return entry_yesterday

    return WorkEntry.query.filter_by(user_id=user_id, date=today).first()


@welcome_bp.route('/')
def index():
    users = User.query.filter(User.is_active == True).order_by(User.name).all()
    today = datetime.now(TIMEZONE).date()

    user_statuses = {}
    for user in users:
        entry = WorkEntry.query.filter_by(user_id=user.id, date=today).first()
        user_statuses[user.id] = compute_status(entry)

    return render_template('welcome/index.html', users=users, user_statuses=user_statuses)


@welcome_bp.route('/statuses')
def statuses():
    """Polling endpoint — zwraca aktualne statusy wszystkich użytkowników."""
    today = datetime.now(TIMEZONE).date()
    users = User.query.filter(User.is_active == True).all()
    result = {}
    for user in users:
        entry = WorkEntry.query.filter_by(user_id=user.id, date=today).first()
        result[str(user.id)] = compute_status(entry)
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

    today = datetime.now(TIMEZONE).date()
    entry = get_today_entry(user_id)

    return jsonify({
        'ok': True,
        'user_name': user.name or user.email,
        'status': compute_status(entry),
        'date': (entry.date if entry else today).strftime('%d.%m.%Y'),
        'clock_in':    entry.time_start.strftime('%H:%M')  if entry and entry.time_start  else None,
        'clock_out':   entry.time_end.strftime('%H:%M')    if entry and entry.time_end    else None,
        'break_start': entry.break_start.strftime('%H:%M') if entry and entry.break_start else None,
        'break_end':   entry.break_end.strftime('%H:%M')   if entry and entry.break_end   else None,
    })


@welcome_bp.route('/clock', methods=['POST'])
def clock():
    data = request.get_json()
    user_id = data.get('user_id')
    action  = data.get('action')
    pin     = data.get('pin', '')

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        return jsonify({'ok': False, 'error': 'Nieautoryzowany'}), 401

    now_dt = datetime.now(TIMEZONE)
    now    = now_dt.time()
    today  = now_dt.date()

    entry = get_today_entry(user_id)

    if action == 'clock_in':
        if entry and entry.time_start:
            return jsonify({'ok': False, 'error': 'Już zarejestrowano przyjście'}), 400
        if not entry:
            by, bm = get_billing_period(today)
            entry = WorkEntry(
                user_id=user_id, date=today,
                billing_year=by, billing_month=bm,
                entry_type='work',
                hours_worked=Decimal('0'), hours_billed=Decimal('0'),
            )
            db.session.add(entry)
        entry.time_start = now
        label = f'Przyjście: {now.strftime("%H:%M")}'

    elif action == 'clock_out':
        if not entry or not entry.time_start:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400
        if entry.time_end:
            return jsonify({'ok': False, 'error': 'Już zarejestrowano wyjście'}), 400
        # Zakończ aktywną przerwę jeśli trwa
        if entry.break_start and not entry.break_end:
            entry.break_end = now
        entry.time_end = now
        # Przelicz godziny
        from wlogio_app.calculator import calculate_hours
        calc = calculate_hours(entry.time_start, entry.time_end,
                               entry.break_start, entry.break_end)
        entry.hours_worked        = Decimal(str(calc['hours_worked']))
        entry.hours_billed        = Decimal(str(calc['hours_billed']))
        entry.extra_break_minutes = calc['extra_break_minutes']
        label = f'Wyjście: {now.strftime("%H:%M")}'

    elif action == 'break_start':
        if not entry or not entry.time_start:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400
        if entry.break_start:
            return jsonify({'ok': False, 'error': 'Przerwa już rozpoczęta'}), 400
        entry.break_start = now
        label = f'Przerwa od: {now.strftime("%H:%M")}'

    elif action == 'break_end':
        if not entry or not entry.break_start:
            return jsonify({'ok': False, 'error': 'Najpierw rozpocznij przerwę'}), 400
        if entry.break_end:
            return jsonify({'ok': False, 'error': 'Przerwa już zakończona'}), 400
        entry.break_end = now
        label = f'Przerwa do: {now.strftime("%H:%M")}'

    else:
        return jsonify({'ok': False, 'error': 'Nieznana akcja'}), 400

    db.session.commit()

    return jsonify({
        'ok': True,
        'label': label,
        'status': compute_status(entry),
        'clock_in':    entry.time_start.strftime('%H:%M')  if entry.time_start  else None,
        'clock_out':   entry.time_end.strftime('%H:%M')    if entry.time_end    else None,
        'break_start': entry.break_start.strftime('%H:%M') if entry.break_start else None,
        'break_end':   entry.break_end.strftime('%H:%M')   if entry.break_end   else None,
    })

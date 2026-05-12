"""
welcome.py - Ekran powitalny

Logika statusów (TYLKO na podstawie time_start/time_end/break_start/break_end z WorkEntry):

'working' = aktualna godzina >= time_start ORAZ < time_end (obie muszą być ustawione)
'break'   = warunek 'working' spełniony ORAZ aktualna godzina >= break_start ORAZ < break_end
'idle'    = wszystkie pozostałe przypadki

clock_in/clock_out z ekranu powitalnego nadpisuje time_start/time_end.
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

    Priorytet: clock_* (ekran powitalny) > time_* (dashboard)
    """
    if entry is None:
        return 'idle'

    now = now_minutes()

    # Użyj clock_in/clock_out jeśli ustawione, inaczej time_start/time_end
    start = entry.clock_in or entry.time_start
    end   = entry.clock_out or entry.time_end
    bs    = entry.break_clock_start or entry.break_start
    be    = entry.break_clock_end or entry.break_end

    start_min = to_min(start)
    end_min   = to_min(end)
    bs_min    = to_min(bs)
    be_min    = to_min(be)

    # Obie godziny (start i end) muszą być ustawione
    if start_min is None or end_min is None:
        return 'idle'

    # Obsługa pracy przez północ
    if end_min <= start_min:
        end_min += 24 * 60

    # Czy jesteśmy w czasie pracy?
    in_work = start_min <= now < end_min
    if not in_work:
        return 'idle'

    # Czy jesteśmy w czasie przerwy?
    if bs_min is not None and be_min is not None:
        if be_min <= bs_min:
            be_min += 24 * 60
        if bs_min <= now < be_min:
            return 'break'

    return 'working'


def get_today_entry(user_id):
    """Pobiera wpis na dziś lub wczoraj (dla pracy przez północ)."""
    today = datetime.now(TIMEZONE).date()
    yesterday = today - timedelta(days=1)

    # Sprawdź czy wczorajszy wpis jest nadal aktywny (praca przez północ)
    entry_yesterday = WorkEntry.query.filter_by(user_id=user_id, date=yesterday).first()
    if entry_yesterday:
        s = to_min(entry_yesterday.clock_in or entry_yesterday.time_start)
        e = to_min(entry_yesterday.clock_out or entry_yesterday.time_end)
        if s is not None and e is not None:
            e_adj = e if e > s else e + 24 * 60
            now = now_minutes()
            # Praca przez północ: now < e_adj - 24*60 + 24*60 = e_adj gdy now < s
            if now < e_adj - 24 * 60 + 24 * 60 and s > now:
                pass  # nie aktywna już w nowym dniu
            elif s > e_adj % (24 * 60):
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
    """Polling endpoint - zwraca aktualne statusy wszystkich użytkowników."""
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

    clock_in   = entry.clock_in or entry.time_start if entry else None
    clock_out  = entry.clock_out or entry.time_end if entry else None
    break_start = entry.break_clock_start or entry.break_start if entry else None
    break_end   = entry.break_clock_end or entry.break_end if entry else None

    return jsonify({
        'ok': True,
        'user_name': user.name or user.email,
        'date': (entry.date if entry else today).strftime('%d.%m.%Y'),
        'clock_in':    clock_in.strftime('%H:%M') if clock_in else None,
        'clock_out':   clock_out.strftime('%H:%M') if clock_out else None,
        'break_start': break_start.strftime('%H:%M') if break_start else None,
        'break_end':   break_end.strftime('%H:%M') if break_end else None,
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
        if entry and entry.clock_in:
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
        entry.clock_in = now
        entry.time_start = now
        label = f'Przyjście: {now.strftime("%H:%M")}'

    elif action == 'clock_out':
        if not entry or not entry.clock_in:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400
        if entry.clock_out:
            return jsonify({'ok': False, 'error': 'Już zarejestrowano wyjście'}), 400
        # Zakończ aktywną przerwę
        if entry.break_clock_start and not entry.break_clock_end:
            entry.break_clock_end = now
            entry.break_end = now
        entry.clock_out = now
        entry.time_end  = now
        if entry.time_start:
            from wlogio_app.calculator import calculate_hours
            calc = calculate_hours(entry.time_start, entry.time_end,
                                   entry.break_clock_start, entry.break_clock_end)
            entry.hours_worked = Decimal(str(calc['hours_worked']))
            entry.hours_billed = Decimal(str(calc['hours_billed']))
            entry.extra_break_minutes = calc['extra_break_minutes']
        label = f'Wyjście: {now.strftime("%H:%M")}'

    elif action == 'break_start':
        if not entry or not entry.clock_in:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400
        if entry.break_clock_start:
            return jsonify({'ok': False, 'error': 'Przerwa już rozpoczęta'}), 400
        entry.break_clock_start = now
        entry.break_start = now
        label = f'Przerwa od: {now.strftime("%H:%M")}'

    elif action == 'break_end':
        if not entry or not entry.break_clock_start:
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
        'ok': True, 'label': label,
        'clock_in':    entry.clock_in.strftime('%H:%M') if entry.clock_in else None,
        'clock_out':   entry.clock_out.strftime('%H:%M') if entry.clock_out else None,
        'break_start': entry.break_clock_start.strftime('%H:%M') if entry.break_clock_start else None,
        'break_end':   entry.break_clock_end.strftime('%H:%M') if entry.break_clock_end else None,
    })

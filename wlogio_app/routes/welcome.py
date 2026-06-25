"""
welcome.py - Ekran powitalny

Logika statusów (na podstawie time_start/time_end/breaks):

'working' = time_start ustawiony ORAZ (brak time_end LUB aktualna godzina < time_end)
'break'   = warunek 'working' spełniony ORAZ ostatnia przerwa w `breaks` ma start
            ORAZ (brak end tej przerwy LUB aktualna godzina < end)
'idle'    = wszystkie pozostałe przypadki

Przerwy są przechowywane jako string "HH:MM-HH:MM;HH:MM-HH:MM" w kolumnie `breaks`.
Każde kliknięcie "Przerwa" na ekranie powitalnym dodaje nowy segment "HH:MM-" (otwarty),
każde kliknięcie "Koniec przerwy" domyka ostatni otwarty segment.
"""

from flask import Blueprint, render_template, request, jsonify, session
from datetime import datetime, date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Europe/Warsaw')

from wlogio_app import db
from wlogio_app.models import User, WorkEntry
from wlogio_app.calculator import get_billing_period, parse_breaks, format_breaks

welcome_bp = Blueprint('welcome', __name__)
WELCOME_PASSWORD = 'Przemek121!'


def now_minutes():
    t = datetime.now(TIMEZONE)
    return t.hour * 60 + t.minute


def to_min(t):
    if t is None:
        return None
    return t.hour * 60 + t.minute


def get_last_break(entry):
    """
    Zwraca ostatnią przerwę z entry.breaks jako (start_time, end_time_or_None).
    end_time_or_None to None gdy ostatnia przerwa nie ma jeszcze końca
    (reprezentowana w stringu jako "HH:MM-" bez końca).
    """
    if not entry or not entry.breaks:
        return None, None

    segments = [s.strip() for s in entry.breaks.split(';') if s.strip()]
    if not segments:
        return None, None

    last = segments[-1]
    if '-' not in last:
        return None, None

    start_str, end_str = last.split('-', 1)
    start_str = start_str.strip()
    end_str = end_str.strip()

    try:
        start_t = datetime.strptime(start_str, '%H:%M').time() if start_str else None
    except ValueError:
        start_t = None

    end_t = None
    if end_str:
        try:
            end_t = datetime.strptime(end_str, '%H:%M').time()
        except ValueError:
            end_t = None

    return start_t, end_t


def compute_status(entry):
    """
    Oblicza status na podstawie wpisu WorkEntry i aktualnej godziny.
    Zwraca: 'idle' | 'working' | 'break'
    """
    if entry is None:
        return 'idle'

    now = now_minutes()
    start_min = to_min(entry.time_start)
    end_min   = to_min(entry.time_end)

    if start_min is None:
        return 'idle'

    if end_min is not None and end_min < start_min:
        end_min += 24 * 60

    if now < start_min:
        return 'idle'

    if end_min is not None and now >= end_min:
        return 'idle'

    # Sprawdź ostatnią przerwę
    bs, be = get_last_break(entry)
    if bs is not None:
        bs_min = to_min(bs)
        be_min = to_min(be)

        if bs_min < start_min:
            bs_min += 24 * 60
        if be_min is not None and be_min < bs_min:
            be_min += 24 * 60

        after_break_start = now >= bs_min
        before_break_end = (be_min is None) or (now < be_min)

        if after_break_start and before_break_end:
            return 'break'

    return 'working'


def get_today_entry(user_id):
    today     = datetime.now(TIMEZONE).date()
    yesterday = today - timedelta(days=1)

    entry_yesterday = WorkEntry.query.filter_by(user_id=user_id, date=yesterday).first()
    if entry_yesterday and entry_yesterday.time_start:
        s = to_min(entry_yesterday.time_start)
        e = to_min(entry_yesterday.time_end)
        now = now_minutes()
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


def auto_close_stale_entries():
    """
    Zamyka wpisy gdzie time_start ustawiony ale time_end brak
    i od time_start minęło >= 24 godziny. Domyka też ostatnią otwartą przerwę.
    """
    from wlogio_app.calculator import calculate_hours

    now_dt   = datetime.now(TIMEZONE)
    now_time = now_dt.time()

    today     = now_dt.date()
    yesterday = today - timedelta(days=1)

    stale = WorkEntry.query.filter(
        WorkEntry.time_start.isnot(None),
        WorkEntry.time_end.is_(None),
        WorkEntry.date.in_([today, yesterday]),
    ).all()

    changed = False
    for entry in stale:
        start_naive = datetime.combine(entry.date, entry.time_start)
        start_aware = start_naive.replace(tzinfo=TIMEZONE)
        if (now_dt - start_aware).total_seconds() >= 24 * 3600:
            # Domknij ostatnią otwartą przerwę jeśli istnieje
            breaks_list = parse_open_breaks(entry.breaks)
            if breaks_list and breaks_list[-1][1] is None:
                breaks_list[-1] = (breaks_list[-1][0], now_time)
                entry.breaks = format_breaks_with_open(breaks_list)

            entry.time_end = now_time

            closed_breaks = parse_breaks(entry.breaks)
            calc = calculate_hours(entry.time_start, entry.time_end, closed_breaks)
            entry.hours_worked        = Decimal(str(calc['hours_worked']))
            entry.hours_billed        = Decimal(str(calc['hours_billed']))
            entry.extra_break_minutes = calc['extra_break_minutes']
            changed = True

    if changed:
        db.session.commit()


def parse_open_breaks(breaks_str):
    """
    Jak parse_breaks, ale zachowuje ostatni segment otwarty (bez końca) jako (start, None).
    Używane wewnętrznie przy edycji breaks z ekranu powitalnego.
    """
    if not breaks_str or not breaks_str.strip():
        return []
    result = []
    segments = [s.strip() for s in breaks_str.split(';') if s.strip()]
    for idx, seg in enumerate(segments):
        if '-' not in seg:
            continue
        start_str, end_str = seg.split('-', 1)
        start_str = start_str.strip()
        end_str = end_str.strip()
        try:
            start_t = datetime.strptime(start_str, '%H:%M').time()
        except ValueError:
            continue
        if end_str:
            try:
                end_t = datetime.strptime(end_str, '%H:%M').time()
            except ValueError:
                end_t = None
        else:
            end_t = None
        result.append((start_t, end_t))
    return result


def format_breaks_with_open(breaks_list):
    """Jak format_breaks, ale akceptuje (start, None) dla otwartej przerwy."""
    if not breaks_list:
        return None
    segments = []
    for start_t, end_t in breaks_list:
        start_str = start_t.strftime('%H:%M') if start_t else ''
        end_str = end_t.strftime('%H:%M') if end_t else ''
        segments.append(f'{start_str}-{end_str}')
    return ';'.join(segments)


@welcome_bp.route('/statuses')
def statuses():
    auto_close_stale_entries()

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

    last_bs, last_be = get_last_break(entry) if entry else (None, None)

    return jsonify({
        'ok': True,
        'user_name': user.name or user.email,
        'status': compute_status(entry),
        'date': (entry.date if entry else today).strftime('%d.%m.%Y'),
        'clock_in':    entry.time_start.strftime('%H:%M')  if entry and entry.time_start  else None,
        'clock_out':   entry.time_end.strftime('%H:%M')    if entry and entry.time_end    else None,
        'break_start': last_bs.strftime('%H:%M') if last_bs else None,
        'break_end':   last_be.strftime('%H:%M') if last_be else None,
        'breaks_count': len(parse_breaks(entry.breaks)) if entry and entry.breaks else 0,
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

        # Domknij ostatnią otwartą przerwę jeśli istnieje
        breaks_list = parse_open_breaks(entry.breaks)
        if breaks_list and breaks_list[-1][1] is None:
            breaks_list[-1] = (breaks_list[-1][0], now)
            entry.breaks = format_breaks_with_open(breaks_list)

        entry.time_end = now

        from wlogio_app.calculator import calculate_hours
        closed_breaks = parse_breaks(entry.breaks)
        calc = calculate_hours(entry.time_start, entry.time_end, closed_breaks)
        entry.hours_worked        = Decimal(str(calc['hours_worked']))
        entry.hours_billed        = Decimal(str(calc['hours_billed']))
        entry.extra_break_minutes = calc['extra_break_minutes']
        label = f'Wyjście: {now.strftime("%H:%M")}'

    elif action == 'break_start':
        if not entry or not entry.time_start:
            return jsonify({'ok': False, 'error': 'Najpierw zarejestruj przyjście'}), 400

        # Sprawdź czy jest już otwarta przerwa
        breaks_list = parse_open_breaks(entry.breaks)
        if breaks_list and breaks_list[-1][1] is None:
            return jsonify({'ok': False, 'error': 'Przerwa już rozpoczęta'}), 400

        breaks_list.append((now, None))
        entry.breaks = format_breaks_with_open(breaks_list)
        label = f'Przerwa od: {now.strftime("%H:%M")}'

    elif action == 'break_end':
        if not entry:
            return jsonify({'ok': False, 'error': 'Najpierw rozpocznij przerwę'}), 400

        breaks_list = parse_open_breaks(entry.breaks)
        if not breaks_list or breaks_list[-1][1] is not None:
            return jsonify({'ok': False, 'error': 'Najpierw rozpocznij przerwę'}), 400

        breaks_list[-1] = (breaks_list[-1][0], now)
        entry.breaks = format_breaks_with_open(breaks_list)
        label = f'Przerwa do: {now.strftime("%H:%M")}'

    else:
        return jsonify({'ok': False, 'error': 'Nieznana akcja'}), 400

    db.session.commit()

    last_bs, last_be = get_last_break(entry)

    return jsonify({
        'ok': True,
        'label': label,
        'status': compute_status(entry),
        'clock_in':    entry.time_start.strftime('%H:%M')  if entry.time_start  else None,
        'clock_out':   entry.time_end.strftime('%H:%M')    if entry.time_end    else None,
        'break_start': last_bs.strftime('%H:%M') if last_bs else None,
        'break_end':   last_be.strftime('%H:%M') if last_be else None,
        'breaks_count': len(parse_breaks(entry.breaks)) if entry.breaks else 0,
    })

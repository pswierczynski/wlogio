from flask import Blueprint, render_template, request, jsonify
from datetime import date, datetime
from wlogio_app import db
from wlogio_app.models import User, WorkEntry
from wlogio_app.calculator import get_billing_period

welcome_bp = Blueprint('welcome', __name__)


@welcome_bp.route('/')
def index():
    users = User.query.filter(
        User.avatar.isnot(None),
        User.is_active == True
    ).all()
    return render_template('welcome/index.html', users=users)


@welcome_bp.route('/verify_pin', methods=['POST'])
def verify_pin():
    data = request.get_json()
    user_id = data.get('user_id')
    pin = data.get('pin', '')
    user = User.query.get(user_id)
    if not user or user.pin != pin:
        return jsonify({'ok': False, 'error': 'Nieprawidłowy PIN'})

    today = date.today()
    entry = WorkEntry.query.filter_by(user_id=user.id, date=today).first()

    return jsonify({
        'ok': True,
        'user_name': user.name or user.email,
        'entry': {
            'has_entry': entry is not None,
            'time_start': entry.time_start.strftime('%H:%M') if entry and entry.time_start else None,
            'time_end': entry.time_end.strftime('%H:%M') if entry and entry.time_end else None,
            'break_start': entry.break_start.strftime('%H:%M') if entry and entry.break_start else None,
            'break_end': entry.break_end.strftime('%H:%M') if entry and entry.break_end else None,
        } if entry else {
            'has_entry': False,
            'time_start': None, 'time_end': None,
            'break_start': None, 'break_end': None,
        }
    })


@welcome_bp.route('/clock_action', methods=['POST'])
def clock_action():
    data = request.get_json()
    user_id = data.get('user_id')
    pin = data.get('pin', '')
    action = data.get('action')  # start_work, end_work, start_break, end_break

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        return jsonify({'ok': False, 'error': 'Nieprawidłowy PIN'})

    today = date.today()
    now = datetime.now().time()
    billing_year, billing_month = get_billing_period(today)

    entry = WorkEntry.query.filter_by(user_id=user.id, date=today).first()

    if not entry:
        entry = WorkEntry(
            user_id=user.id,
            date=today,
            billing_year=billing_year,
            billing_month=billing_month,
            entry_type='work',
            hours_worked=0,
            hours_billed=0,
        )
        db.session.add(entry)

    if action == 'start_work' and not entry.time_start:
        entry.time_start = now
    elif action == 'end_work' and entry.time_start and not entry.time_end:
        entry.time_end = now
        # Przelicz godziny
        from wlogio_app.calculator import calculate_hours
        calc = calculate_hours(entry.time_start, entry.time_end,
                               entry.break_start, entry.break_end)
        from decimal import Decimal
        entry.hours_worked = Decimal(str(calc['hours_worked']))
        entry.hours_billed = Decimal(str(calc['hours_billed']))
        entry.extra_break_minutes = calc['extra_break_minutes']
    elif action == 'start_break' and entry.time_start and not entry.break_start:
        entry.break_start = now
    elif action == 'end_break' and entry.break_start and not entry.break_end:
        entry.break_end = now
    else:
        return jsonify({'ok': False, 'error': 'Akcja niedozwolona lub już wykonana'})

    db.session.commit()

    return jsonify({
        'ok': True,
        'time': now.strftime('%H:%M'),
        'entry': {
            'time_start': entry.time_start.strftime('%H:%M') if entry.time_start else None,
            'time_end': entry.time_end.strftime('%H:%M') if entry.time_end else None,
            'break_start': entry.break_start.strftime('%H:%M') if entry.break_start else None,
            'break_end': entry.break_end.strftime('%H:%M') if entry.break_end else None,
        }
    })

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from decimal import Decimal

from wlogio_app import db
from wlogio_app.models import WorkEntry, MonthConfig
from wlogio_app.calculator import (
    calculate_hours, get_billing_period,
    get_next_vacation_number, get_next_remote_number,
    get_or_create_vacation_balance, calculate_vacation_used
)

entries_bp = Blueprint('entries', __name__)

ENTRY_TYPES = {
    'work': 'Praca',
    'vacation': 'Urlop',
    'on_demand': 'Urlop na żądanie',
    'unpaid': 'Urlop bezpłatny',
    'holiday': 'Święto',
    'sick_leave': 'Zwolnienie lekarskie',
}


def get_or_create_month_config(user_id, billing_year, billing_month):
    config = MonthConfig.query.filter_by(
        user_id=user_id,
        billing_year=billing_year,
        billing_month=billing_month
    ).first()

    if not config:
        prev_month = billing_month - 1
        prev_year = billing_year
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1

        prev_config = MonthConfig.query.filter_by(
            user_id=user_id,
            billing_year=prev_year,
            billing_month=prev_month
        ).first()

        from wlogio_app.calculator import get_working_days_in_billing_period
        working_days = get_working_days_in_billing_period(billing_year, billing_month)

        config = MonthConfig(
            user_id=user_id,
            billing_year=billing_year,
            billing_month=billing_month,
            hourly_rate=prev_config.hourly_rate if prev_config else Decimal('0'),
            expected_hours=Decimal(str(working_days * 8)),
            bonus=Decimal('0'),
        )
        db.session.add(config)
        db.session.commit()

    return config


def get_working_days_in_range(date_from, date_to):
    """Zwraca listę dni roboczych (pon-pt) między date_from a date_to włącznie."""
    days = []
    current = date_from
    while current <= date_to:
        if current.weekday() < 5:  # 0=pon, 4=pt, 5=sob, 6=nie
            days.append(current)
        current += timedelta(days=1)
    return days


@entries_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    today = date.today()

    if request.method == 'POST':
        entry_date_str = request.form.get('date', '')
        entry_type = request.form.get('entry_type', 'work')

        try:
            entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Nieprawidłowy format daty.', 'error')
            return redirect(url_for('entries.add'))

        existing = WorkEntry.query.filter_by(
            user_id=current_user.id,
            date=entry_date
        ).first()
        if existing:
            flash(f'Wpis dla {entry_date.strftime("%d.%m.%Y")} już istnieje.', 'error')
            return redirect(url_for('entries.add'))

        billing_year, billing_month = get_billing_period(entry_date)
        get_or_create_month_config(current_user.id, billing_year, billing_month)

        entry = WorkEntry(
            user_id=current_user.id,
            date=entry_date,
            billing_year=billing_year,
            billing_month=billing_month,
            entry_type=entry_type,
        )

        if entry_type == 'work':
            ok, msg = _fill_work_entry(entry, request.form)
            if not ok:
                flash(msg, 'error')
                return redirect(url_for('entries.add'))
            entry.is_remote = request.form.get('is_remote') == 'on'
            if entry.is_remote:
                entry.remote_trip_number = get_next_remote_number(
                    current_user.id, entry_date.year, db.session
                )
        elif entry_type == 'unpaid':
            entry.hours_worked = Decimal('0')
            entry.hours_billed = Decimal('0')
        else:
            entry.hours_worked = Decimal('8')
            entry.hours_billed = Decimal('8')

        if entry_type in ('vacation', 'on_demand'):
            entry.vacation_day_number = get_next_vacation_number(
                current_user.id, entry_date.year, db.session
            )

        entry.notes = request.form.get('notes', '').strip() or None

        db.session.add(entry)
        db.session.commit()

        flash(f'Dodano wpis dla {entry_date.strftime("%d.%m.%Y")}.', 'success')
        return redirect(url_for('dashboard.index'))

    next_vacation = get_next_vacation_number(current_user.id, today.year, db.session)
    next_remote = get_next_remote_number(current_user.id, today.year, db.session)

    # Dostępne urlopy na dziś
    balance = get_or_create_vacation_balance(current_user.id, db.session)
    used = calculate_vacation_used(current_user.id, today.year, db.session)
    remaining_vacation = balance.vacation_total - used['used_vacation']

    return render_template('entries/form.html',
                           entry=None,
                           entry_types=ENTRY_TYPES,
                           today=today.strftime('%Y-%m-%d'),
                           next_vacation=next_vacation,
                           next_remote=next_remote,
                           remaining_vacation=max(0, remaining_vacation))


@entries_bp.route('/range-preview', methods=['POST'])
@login_required
def range_preview():
    """
    Zwraca podgląd zakresu urlopów (JSON).
    Sprawdza kolizje z istniejącymi wpisami i dzieli dni na vacation/unpaid.
    """
    data = request.get_json()
    date_from_str = data.get('date_from', '')
    date_to_str   = data.get('date_to', '')
    range_type    = data.get('range_type', 'vacation')  # 'vacation' | 'unpaid'

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        date_to   = datetime.strptime(date_to_str,   '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'ok': False, 'error': 'Nieprawidłowy format daty.'}), 400

    if date_from > date_to:
        return jsonify({'ok': False, 'error': 'Data początkowa musi być wcześniejsza niż końcowa.'}), 400

    if (date_to - date_from).days > 365:
        return jsonify({'ok': False, 'error': 'Zakres nie może przekraczać 365 dni.'}), 400

    working_days = get_working_days_in_range(date_from, date_to)

    if not working_days:
        return jsonify({'ok': False, 'error': 'Wybrany zakres nie zawiera dni roboczych.'}), 400

    # Sprawdź kolizje z istniejącymi wpisami
    existing = WorkEntry.query.filter(
        WorkEntry.user_id == current_user.id,
        WorkEntry.date >= date_from,
        WorkEntry.date <= date_to,
        WorkEntry.date.in_(working_days)
    ).all()

    if existing:
        collision_dates = ', '.join(e.date.strftime('%d.%m.%Y') for e in existing)
        return jsonify({
            'ok': False,
            'error': f'W wybranym zakresie istnieją już wpisy: {collision_dates}.'
        }), 400

    today = date.today()

    if range_type == 'vacation':
        # Policz dostępne urlopy
        balance = get_or_create_vacation_balance(current_user.id, db.session)
        used = calculate_vacation_used(current_user.id, today.year, db.session)
        remaining = balance.vacation_total - used['used_vacation']
        remaining = max(0, remaining)

        total_days = len(working_days)
        vacation_days = min(total_days, remaining)
        unpaid_days   = total_days - vacation_days

        days_detail = []
        for i, d in enumerate(working_days):
            days_detail.append({
                'date': d.strftime('%d.%m.%Y'),
                'type': 'vacation' if i < vacation_days else 'unpaid',
            })

        return jsonify({
            'ok': True,
            'total_days': total_days,
            'vacation_days': vacation_days,
            'unpaid_days': unpaid_days,
            'remaining_before': remaining,
            'days': days_detail,
        })

    else:  # unpaid
        days_detail = [{'date': d.strftime('%d.%m.%Y'), 'type': 'unpaid'} for d in working_days]
        return jsonify({
            'ok': True,
            'total_days': len(working_days),
            'vacation_days': 0,
            'unpaid_days': len(working_days),
            'remaining_before': 0,
            'days': days_detail,
        })


@entries_bp.route('/add-range', methods=['POST'])
@login_required
def add_range():
    """Zapisuje zakres urlopów do bazy."""
    date_from_str = request.form.get('date_from', '')
    date_to_str   = request.form.get('date_to', '')
    range_type    = request.form.get('range_type', 'vacation')
    notes         = request.form.get('notes', '').strip() or None

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        date_to   = datetime.strptime(date_to_str,   '%Y-%m-%d').date()
    except ValueError:
        flash('Nieprawidłowy format daty.', 'error')
        return redirect(url_for('entries.add'))

    if date_from > date_to:
        flash('Data początkowa musi być wcześniejsza niż końcowa.', 'error')
        return redirect(url_for('entries.add'))

    working_days = get_working_days_in_range(date_from, date_to)

    if not working_days:
        flash('Wybrany zakres nie zawiera dni roboczych.', 'error')
        return redirect(url_for('entries.add'))

    # Sprawdź kolizje
    existing = WorkEntry.query.filter(
        WorkEntry.user_id == current_user.id,
        WorkEntry.date >= date_from,
        WorkEntry.date <= date_to,
        WorkEntry.date.in_(working_days)
    ).all()

    if existing:
        collision_dates = ', '.join(e.date.strftime('%d.%m.%Y') for e in existing)
        flash(f'W wybranym zakresie istnieją już wpisy: {collision_dates}.', 'error')
        return redirect(url_for('entries.add'))

    today = date.today()

    # Policz dostępne urlopy (tylko dla vacation)
    remaining = 0
    if range_type == 'vacation':
        balance = get_or_create_vacation_balance(current_user.id, db.session)
        used = calculate_vacation_used(current_user.id, today.year, db.session)
        remaining = max(0, balance.vacation_total - used['used_vacation'])

    added = 0
    for i, entry_date in enumerate(working_days):
        # Wyznacz typ wpisu
        if range_type == 'vacation':
            entry_type = 'vacation' if i < remaining else 'unpaid'
        else:
            entry_type = 'unpaid'

        billing_year, billing_month = get_billing_period(entry_date)
        get_or_create_month_config(current_user.id, billing_year, billing_month)

        entry = WorkEntry(
            user_id=current_user.id,
            date=entry_date,
            billing_year=billing_year,
            billing_month=billing_month,
            entry_type=entry_type,
            hours_worked=Decimal('0') if entry_type == 'unpaid' else Decimal('8'),
            hours_billed=Decimal('0') if entry_type == 'unpaid' else Decimal('8'),
            notes=notes,
        )

        if entry_type in ('vacation', 'on_demand'):
            entry.vacation_day_number = get_next_vacation_number(
                current_user.id, entry_date.year, db.session
            )

        db.session.add(entry)
        db.session.flush()  # żeby get_next_vacation_number widział poprzednie wpisy
        added += 1

    db.session.commit()
    flash(f'Dodano {added} dni ({date_from.strftime("%d.%m.%Y")} – {date_to.strftime("%d.%m.%Y")}).', 'success')
    return redirect(url_for('dashboard.index'))


@entries_bp.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit(entry_id):
    entry = WorkEntry.query.filter_by(
        id=entry_id, user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        entry_type = request.form.get('entry_type', 'work')
        entry.entry_type = entry_type

        if entry_type == 'work':
            ok, msg = _fill_work_entry(entry, request.form)
            if not ok:
                flash(msg, 'error')
                return redirect(url_for('entries.edit', entry_id=entry_id))
            entry.is_remote = request.form.get('is_remote') == 'on'
        elif entry_type == 'unpaid':
            entry.time_start = None
            entry.time_end = None
            entry.break_start = None
            entry.break_end = None
            entry.extra_break_minutes = 0
            entry.hours_worked = Decimal('0')
            entry.hours_billed = Decimal('0')
            entry.is_remote = False
        else:
            entry.time_start = None
            entry.time_end = None
            entry.break_start = None
            entry.break_end = None
            entry.extra_break_minutes = 0
            entry.hours_worked = Decimal('8')
            entry.hours_billed = Decimal('8')
            entry.is_remote = False

        entry.notes = request.form.get('notes', '').strip() or None
        db.session.commit()

        flash(f'Zaktualizowano wpis dla {entry.date.strftime("%d.%m.%Y")}.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('entries/form.html',
                           entry=entry,
                           entry_types=ENTRY_TYPES,
                           today=entry.date.strftime('%Y-%m-%d'),
                           next_vacation=entry.vacation_day_number,
                           next_remote=entry.remote_trip_number,
                           remaining_vacation=0)


@entries_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete(entry_id):
    entry = WorkEntry.query.filter_by(
        id=entry_id, user_id=current_user.id
    ).first_or_404()

    date_str = entry.date.strftime('%d.%m.%Y')
    db.session.delete(entry)
    db.session.commit()

    flash(f'Usunięto wpis dla {date_str}.', 'success')
    return redirect(url_for('dashboard.index'))


def _fill_work_entry(entry, form):
    """
    Wypełnia pola czasowe wpisu z danych formularza.
    Zwraca (True, None) gdy OK, (False, komunikat) gdy błąd.
    """

    def parse_time(val):
        if not val or not val.strip():
            return None
        try:
            return datetime.strptime(val.strip(), '%H:%M').time()
        except ValueError:
            return None

    def to_min(t):
        if t is None:
            return None
        return t.hour * 60 + t.minute

    time_start  = parse_time(form.get('time_start', ''))
    time_end    = parse_time(form.get('time_end', ''))
    break_start = parse_time(form.get('break_start', ''))
    break_end   = parse_time(form.get('break_end', ''))

    if time_start is None:
        return False, 'Godzina przyjścia jest wymagana.'

    if time_end is not None:
        ts = to_min(time_start)
        te = to_min(time_end)
        if te < ts:
            te += 24 * 60
        if te == ts:
            return False, 'Godzina wyjścia musi być różna od godziny przyjścia.'

    if break_start is not None:
        ts = to_min(time_start)
        bs = to_min(break_start)
        if bs < ts:
            return False, 'Godzina rozpoczęcia przerwy musi być równa lub późniejsza niż godzina przyjścia.'
        if time_end is not None:
            te = to_min(time_end)
            if te < ts:
                te += 24 * 60
            if bs >= te:
                return False, 'Godzina rozpoczęcia przerwy musi być wcześniejsza niż godzina wyjścia.'

    if break_end is not None:
        if break_start is None:
            return False, 'Aby ustawić koniec przerwy, najpierw ustaw godzinę rozpoczęcia przerwy.'
        bs = to_min(break_start)
        be = to_min(break_end)
        if be < bs:
            be += 24 * 60
        if be == bs:
            return False, 'Godzina końca przerwy musi być różna od godziny rozpoczęcia przerwy.'
        if time_end is not None:
            ts = to_min(time_start)
            te = to_min(time_end)
            if te < ts:
                te += 24 * 60
            if be > te:
                return False, 'Godzina końca przerwy nie może być późniejsza niż godzina wyjścia.'

    entry.time_start  = time_start
    entry.time_end    = time_end
    entry.break_start = break_start
    entry.break_end   = break_end

    if time_start and time_end:
        calc = calculate_hours(time_start, time_end, break_start, break_end)
        entry.extra_break_minutes = calc['extra_break_minutes']
        entry.hours_worked = Decimal(str(calc['hours_worked']))
        entry.hours_billed = Decimal(str(calc['hours_billed']))
    else:
        entry.extra_break_minutes = 0
        entry.hours_worked = Decimal('0')
        entry.hours_billed = Decimal('0')

    return True, None

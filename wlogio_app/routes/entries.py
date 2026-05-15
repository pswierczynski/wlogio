from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from decimal import Decimal

from wlogio_app import db
from wlogio_app.models import WorkEntry, MonthConfig
from wlogio_app.calculator import (
    calculate_hours, get_billing_period,
    get_next_vacation_number, get_next_remote_number
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

    return render_template('entries/form.html',
                           entry=None,
                           entry_types=ENTRY_TYPES,
                           today=today.strftime('%Y-%m-%d'),
                           next_vacation=next_vacation,
                           next_remote=next_remote)


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
                           next_remote=entry.remote_trip_number)


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

    Reguły walidacji:
    - time_start jest wymagany
    - time_end jest opcjonalny (brak = praca do odwołania)
    - jeśli oba ustawione: time_end musi być różny od time_start
    - break_start jest opcjonalny, ale wymaga time_start
    - break_start musi być >= time_start
    - break_end jest opcjonalny (brak = przerwa do odwołania), ale wymaga break_start
    - jeśli break_start i break_end oba ustawione: break_end > break_start
    - jeśli time_end ustawiony: break_start < time_end
    - jeśli time_end i break_end oba ustawione: break_end <= time_end

    Zwraca (True, None) gdy OK, (False, komunikat) gdy błąd.
    """

    def parse_time(val):
        """Parsuje 'HH:MM' → datetime.time lub None."""
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

    time_start = parse_time(form.get('time_start', ''))
    time_end   = parse_time(form.get('time_end', ''))
    break_start = parse_time(form.get('break_start', ''))
    break_end   = parse_time(form.get('break_end', ''))

    # --- Walidacja time_start ---
    if time_start is None:
        return False, 'Godzina przyjścia jest wymagana.'

    # --- Walidacja time_end (opcjonalny) ---
    if time_end is not None:
        ts = to_min(time_start)
        te = to_min(time_end)
        # Obsługa pracy przez północ
        if te <= ts:
            te += 24 * 60
        if te == ts:
            return False, 'Godzina wyjścia musi być różna od godziny przyjścia.'

    # --- Walidacja break_start (opcjonalny) ---
    if break_start is not None:
        ts = to_min(time_start)
        bs = to_min(break_start)
        # break_start musi być >= time_start
        if bs < ts:
            return False, 'Godzina rozpoczęcia przerwy musi być równa lub późniejsza niż godzina przyjścia.'
        # jeśli time_end ustawiony: break_start < time_end
        if time_end is not None:
            te = to_min(time_end)
            if te <= ts:
                te += 24 * 60
            if bs >= te:
                return False, 'Godzina rozpoczęcia przerwy musi być wcześniejsza niż godzina wyjścia.'

    # --- Walidacja break_end (wymaga break_start) ---
    if break_end is not None:
        if break_start is None:
            return False, 'Aby ustawić koniec przerwy, najpierw ustaw godzinę rozpoczęcia przerwy.'
        bs = to_min(break_start)
        be = to_min(break_end)
        if be <= bs:
            be += 24 * 60
        if be == bs:
            return False, 'Godzina końca przerwy musi być różna od godziny rozpoczęcia przerwy.'
        # jeśli time_end ustawiony: break_end <= time_end
        if time_end is not None:
            ts = to_min(time_start)
            te = to_min(time_end)
            if te <= ts:
                te += 24 * 60
            if be > te:
                return False, 'Godzina końca przerwy nie może być późniejsza niż godzina wyjścia.'

    # --- Zapis ---
    entry.time_start  = time_start
    entry.time_end    = time_end
    entry.break_start = break_start
    entry.break_end   = break_end

    # Oblicz godziny tylko jeśli mamy kompletny czas pracy
    if time_start and time_end:
        calc = calculate_hours(time_start, time_end, break_start, break_end)
        entry.extra_break_minutes = calc['extra_break_minutes']
        entry.hours_worked = Decimal(str(calc['hours_worked']))
        entry.hours_billed = Decimal(str(calc['hours_billed']))
    else:
        # Brak time_end — godziny nieznane do momentu wyjścia
        entry.extra_break_minutes = 0
        entry.hours_worked = Decimal('0')
        entry.hours_billed = Decimal('0')

    return True, None

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from decimal import Decimal

from app import db
from app.models import WorkEntry, MonthConfig
from app.calculator import calculate_hours, get_billing_period

entries_bp = Blueprint('entries', __name__)

ENTRY_TYPES = {
    'work': 'Praca',
    'vacation': 'Urlop',
    'on_demand': 'Urlop na żądanie',
    'holiday': 'Święto',
    'sick_leave': 'Zwolnienie lekarskie',
}


def get_or_create_month_config(user_id, billing_year, billing_month):
    """
    Pobiera lub tworzy konfigurację miesiąca.
    Nowy miesiąc dziedziczy stawkę z poprzedniego.
    """
    config = MonthConfig.query.filter_by(
        user_id=user_id,
        billing_year=billing_year,
        billing_month=billing_month
    ).first()

    if not config:
        # Szukaj poprzedniego miesiąca
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

        inherited_rate = prev_config.hourly_rate if prev_config else Decimal('0')

        config = MonthConfig(
            user_id=user_id,
            billing_year=billing_year,
            billing_month=billing_month,
            hourly_rate=inherited_rate,
            bonus=Decimal('0'),
        )
        db.session.add(config)
        db.session.commit()

    return config


@entries_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        entry_date_str = request.form.get('date', '')
        entry_type = request.form.get('entry_type', 'work')

        try:
            entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Nieprawidłowy format daty.', 'error')
            return redirect(url_for('entries.add'))

        # Sprawdź czy wpis na ten dzień już istnieje
        existing = WorkEntry.query.filter_by(
            user_id=current_user.id,
            date=entry_date
        ).first()
        if existing:
            flash(f'Wpis dla dnia {entry_date.strftime("%d.%m.%Y")} już istnieje.', 'error')
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
            _fill_work_entry(entry, request.form)
        else:
            # Urlop, święto, zwolnienie = 8h z automatu
            entry.hours_worked = Decimal('8')
            entry.hours_billed = Decimal('8')

        # Metadane
        entry.vacation_day_number = request.form.get('vacation_day_number') or None
        entry.is_remote = request.form.get('is_remote') == 'on'
        entry.remote_trip_number = request.form.get('remote_trip_number') or None
        entry.notes = request.form.get('notes', '').strip() or None

        db.session.add(entry)
        db.session.commit()

        flash(f'Dodano wpis dla {entry_date.strftime("%d.%m.%Y")}.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('entries/form.html',
                           entry=None,
                           entry_types=ENTRY_TYPES,
                           today=date.today().strftime('%Y-%m-%d'))


@entries_bp.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit(entry_id):
    entry = WorkEntry.query.filter_by(
        id=entry_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        entry_type = request.form.get('entry_type', 'work')
        entry.entry_type = entry_type

        if entry_type == 'work':
            _fill_work_entry(entry, request.form)
        else:
            entry.time_start = None
            entry.time_end = None
            entry.break_start = None
            entry.break_end = None
            entry.extra_break_minutes = 0
            entry.hours_worked = Decimal('8')
            entry.hours_billed = Decimal('8')

        entry.vacation_day_number = request.form.get('vacation_day_number') or None
        entry.is_remote = request.form.get('is_remote') == 'on'
        entry.remote_trip_number = request.form.get('remote_trip_number') or None
        entry.notes = request.form.get('notes', '').strip() or None

        db.session.commit()
        flash(f'Zaktualizowano wpis dla {entry.date.strftime("%d.%m.%Y")}.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('entries/form.html',
                           entry=entry,
                           entry_types=ENTRY_TYPES)


@entries_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete(entry_id):
    entry = WorkEntry.query.filter_by(
        id=entry_id,
        user_id=current_user.id
    ).first_or_404()

    date_str = entry.date.strftime('%d.%m.%Y')
    db.session.delete(entry)
    db.session.commit()

    flash(f'Usunięto wpis dla {date_str}.', 'success')
    return redirect(url_for('dashboard.index'))


def _fill_work_entry(entry, form):
    """Wypełnia pola godzinowe wpisu na podstawie danych z formularza."""
    time_start_str = form.get('time_start', '')
    time_end_str = form.get('time_end', '')
    break_start_str = form.get('break_start', '')
    break_end_str = form.get('break_end', '')

    try:
        entry.time_start = datetime.strptime(time_start_str, '%H:%M').time()
        entry.time_end = datetime.strptime(time_end_str, '%H:%M').time()
    except ValueError:
        flash('Podaj poprawne godziny pracy.', 'error')
        return

    if break_start_str and break_end_str:
        try:
            entry.break_start = datetime.strptime(break_start_str, '%H:%M').time()
            entry.break_end = datetime.strptime(break_end_str, '%H:%M').time()
        except ValueError:
            entry.break_start = None
            entry.break_end = None
    else:
        entry.break_start = None
        entry.break_end = None

    calc = calculate_hours(
        entry.time_start,
        entry.time_end,
        entry.break_start,
        entry.break_end,
    )

    entry.extra_break_minutes = calc['extra_break_minutes']
    entry.hours_worked = Decimal(str(calc['hours_worked']))
    entry.hours_billed = Decimal(str(calc['hours_billed']))

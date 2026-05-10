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
            _fill_work_entry(entry, request.form)
            entry.is_remote = request.form.get('is_remote') == 'on'
            if entry.is_remote:
                entry.remote_trip_number = get_next_remote_number(
                    current_user.id, entry_date.year, db.session
                )
        elif entry_type == 'unpaid':
            # Urlop bezpłatny = 0h
            entry.hours_worked = Decimal('0')
            entry.hours_billed = Decimal('0')
        else:
            entry.hours_worked = Decimal('8')
            entry.hours_billed = Decimal('8')

        # Numer urlopu - automatyczny
        if entry_type in ('vacation', 'on_demand'):
            entry.vacation_day_number = get_next_vacation_number(
                current_user.id, entry_date.year, db.session
            )

        entry.notes = request.form.get('notes', '').strip() or None

        db.session.add(entry)
        db.session.commit()

        flash(f'Dodano wpis dla {entry_date.strftime("%d.%m.%Y")}.', 'success')
        return redirect(url_for('dashboard.index'))

    # Podpowiedź numeru urlopu i pracy zdalnej
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
            _fill_work_entry(entry, request.form)
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
    time_start_str = form.get('time_start', '')
    time_end_str = form.get('time_end', '')

    try:
        entry.time_start = datetime.strptime(time_start_str, '%H:%M').time()
        entry.time_end = datetime.strptime(time_end_str, '%H:%M').time()
    except ValueError:
        flash('Podaj poprawne godziny pracy.', 'error')
        return

    break_start_str = form.get('break_start', '')
    break_end_str = form.get('break_end', '')

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
        entry.time_start, entry.time_end,
        entry.break_start, entry.break_end,
    )
    entry.extra_break_minutes = calc['extra_break_minutes']
    entry.hours_worked = Decimal(str(calc['hours_worked']))
    entry.hours_billed = Decimal(str(calc['hours_billed']))

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from collections import defaultdict
from datetime import date
from decimal import Decimal

from wlogio_app import db
from wlogio_app.models import User, WorkEntry, MonthConfig, VacationBalance
from wlogio_app.scope import get_effective_user, set_viewing_employee, clear_viewing_employee
from wlogio_app.calculator import (
    calculate_month_summary,
    calculate_vacation_used,
    get_billing_period,
    get_or_create_vacation_balance,
    format_hours,
    format_currency,
    parse_breaks,
    calculate_hours,
    get_working_days_in_billing_period,
    _get_config_value,
    DEFAULT_ROUND_MINUTES,
    DEFAULT_PAID_BREAK_MINUTES,
    DEFAULT_HOURS_PER_DAY,
    DEFAULT_OVERTIME_RATE,
    DEFAULT_OFFDAY_RATE,
    DEFAULT_BILLING_START_DAY,
    DEFAULT_BILLING_END_DAY,
)

dashboard_bp = Blueprint('dashboard', __name__)

MONTH_NAMES = {
    1: 'Styczeń', 2: 'Luty', 3: 'Marzec', 4: 'Kwiecień',
    5: 'Maj', 6: 'Czerwiec', 7: 'Lipiec', 8: 'Sierpień',
    9: 'Wrzesień', 10: 'Październik', 11: 'Listopad', 12: 'Grudzień'
}


def calculate_forecast(expected_hours, overtime_hours, hourly_rate, bonus,
                       overtime_rate=None):
    if overtime_rate is None:
        overtime_rate = DEFAULT_OVERTIME_RATE
    rate    = Decimal(str(hourly_rate))
    exp     = Decimal(str(expected_hours))
    ot      = Decimal(str(overtime_hours))
    bon     = Decimal(str(bonus or 0))
    ot_mult = Decimal(str(overtime_rate)) / Decimal('100')
    ot_value = ot * rate * ot_mult if ot >= 0 else ot * rate
    return float(exp * rate + ot_value + bon)


def recalc_entry_hours(entry, round_minutes, paid_break_minutes):
    """
    Przelicza hours_billed i extra_break_minutes dla wpisu na żywo
    wg aktualnych ustawień konfiguracji miesiąca.

    Zwraca (hours_billed, extra_break_minutes) jako floaty.
    Nie modyfikuje obiektu entry — tylko zwraca wartości do wyświetlenia.

    Używane wyłącznie przez dashboard — baza danych nie jest zmieniana.
    """
    if entry.entry_type != 'work' or not entry.time_start or not entry.time_end:
        return float(entry.hours_billed), entry.extra_break_minutes

    breaks = parse_breaks(entry.breaks) if entry.breaks else []
    calc = calculate_hours(
        entry.time_start, entry.time_end, breaks,
        round_minutes=round_minutes,
        paid_break_minutes=paid_break_minutes,
    )
    return calc['hours_billed'], calc['extra_break_minutes']


class EntryView:
    """
    Lekki wrapper na WorkEntry z nadpisanymi hours_billed i extra_break_minutes
    przeliczonymi na żywo wg aktualnego config. Pozostałe atrybuty delegowane
    do oryginalnego obiektu entry.

    Dzięki temu Jinja2 i calculate_month_summary używają aktualnych wartości
    bez modyfikowania bazy danych.
    """
    def __init__(self, entry, hours_billed, extra_break_minutes):
        self._entry = entry
        self.hours_billed = hours_billed
        self.extra_break_minutes = extra_break_minutes

    def __getattr__(self, name):
        return getattr(self._entry, name)


def build_months_data(user_id, date_from=None, date_to=None, include_empty_current=True):
    """
    Buduje listę danych miesięcy rozliczeniowych (dokładnie te same obliczenia
    co panel pracy) — opcjonalnie ograniczoną do wpisów w zakresie dat
    [date_from, date_to]. Współdzielone przez dashboard i eksport, żeby nie
    duplikować logiki liczenia godzin/wynagrodzenia.

    Zwraca (months_data, current_key).
    """
    today = date.today()
    current_billing_year, current_billing_month = get_billing_period(today)

    query = WorkEntry.query.filter_by(user_id=user_id)
    if date_from is not None:
        query = query.filter(WorkEntry.date >= date_from)
    if date_to is not None:
        query = query.filter(WorkEntry.date <= date_to)

    all_entries = (
        query
        .order_by(
            WorkEntry.billing_year.desc(),
            WorkEntry.billing_month.desc(),
            WorkEntry.date.asc()
        )
        .all()
    )

    periods = defaultdict(list)
    for entry in all_entries:
        periods[(entry.billing_year, entry.billing_month)].append(entry)

    configs = {
        (c.billing_year, c.billing_month): c
        for c in MonthConfig.query.filter_by(user_id=user_id).all()
    }

    sorted_keys = sorted(periods.keys(), key=lambda x: (x[0], x[1]), reverse=True)

    current_key = (current_billing_year, current_billing_month)
    if include_empty_current and current_key not in periods:
        periods[current_key] = []
        if current_key not in sorted_keys:
            sorted_keys.insert(0, current_key)

    months_data = []
    for key in sorted_keys:
        year, month = key
        entries = periods[key]
        config  = configs.get(key)

        hourly_rate    = float(config.hourly_rate) if config else 0.0
        bonus          = float(config.bonus) if config and config.bonus else 0.0

        # Pobierz parametry z config
        round_minutes      = int(_get_config_value(config, 'round_minutes',      DEFAULT_ROUND_MINUTES))
        paid_break_minutes = int(_get_config_value(config, 'paid_break_minutes', DEFAULT_PAID_BREAK_MINUTES))
        hours_per_day      = float(_get_config_value(config, 'hours_per_day',    DEFAULT_HOURS_PER_DAY))
        overtime_rate      = int(_get_config_value(config, 'overtime_rate',      DEFAULT_OVERTIME_RATE))
        offday_rate        = int(_get_config_value(config, 'offday_rate',        DEFAULT_OFFDAY_RATE))
        work_days          = _get_config_value(config, 'work_days', None)
        start_day          = int(_get_config_value(config, 'billing_start_day',  DEFAULT_BILLING_START_DAY))
        end_day            = int(_get_config_value(config, 'billing_end_day',    DEFAULT_BILLING_END_DAY))

        # Liczba dni roboczych z uwzględnieniem nowych ustawień
        from wlogio_app.calculator import _parse_work_days, get_billing_period_dates
        work_days_list = _parse_work_days(work_days) if work_days else [0,1,2,3,4]
        from datetime import timedelta
        period_date_from, period_date_to = get_billing_period_dates(year, month, start_day, end_day)
        working_days = 0
        cur = period_date_from
        while cur <= period_date_to:
            if cur.weekday() in work_days_list:
                working_days += 1
            cur += timedelta(days=1)

        expected_hours = working_days * hours_per_day

        # Przelicz hours_billed i extra_break_minutes na żywo dla każdego wpisu
        entry_views = []
        for entry in entries:
            hb, ebm = recalc_entry_hours(entry, round_minutes, paid_break_minutes)
            entry_views.append(EntryView(entry, hb, ebm))

        summary = calculate_month_summary(
            entry_views, hourly_rate, expected_hours, bonus,
            hours_per_day=hours_per_day,
            overtime_rate=overtime_rate,
            work_days=work_days,
            offday_rate=offday_rate,
        )

        forecast = calculate_forecast(
            expected_hours,
            summary['overtime_hours'],
            hourly_rate,
            bonus,
            overtime_rate=overtime_rate,
        )

        months_data.append({
            'year':          year,
            'month':         month,
            'month_name':    MONTH_NAMES.get(month, str(month)),
            'is_current':    key == current_key,
            'entries':       entry_views,
            'config':        config,
            'summary':       summary,
            'hourly_rate':   hourly_rate,
            'working_days':  working_days,
            'forecast':      forecast,
            'hours_per_day': hours_per_day,
        })

    return months_data, current_key


def get_company_employees(company_id):
    return (
        User.query
        .filter_by(company_id=company_id, account_type='employee')
        .order_by(User.name)
        .all()
    )


def get_last_employee_defaults(company_id):
    """
    Konfiguracja i bilans urlopowy ostatnio dodanego pracownika danej firmy
    — używane jako wartości domyślne przy dodawaniu kolejnego pracownika.
    """
    last_employee = (
        User.query
        .filter_by(company_id=company_id, account_type='employee')
        .order_by(User.id.desc())
        .first()
    )
    if not last_employee:
        return None, None

    last_config = (
        MonthConfig.query
        .filter_by(user_id=last_employee.id)
        .order_by(MonthConfig.billing_year.desc(), MonthConfig.billing_month.desc())
        .first()
    )
    last_balance = (
        VacationBalance.query
        .filter_by(user_id=last_employee.id)
        .order_by(VacationBalance.year.desc())
        .first()
    )
    return last_config, last_balance


@dashboard_bp.route('/')
@login_required
def index():
    if current_user.is_company:
        target = get_effective_user()
        if target is None:
            employees = get_company_employees(current_user.id)
            return render_template('dashboard/employees.html', employees=employees)
    else:
        target = current_user

    months_data, current_key = build_months_data(target.id)

    today = date.today()
    current_year = today.year
    balance = get_or_create_vacation_balance(target.id, db.session)
    used    = calculate_vacation_used(target.id, current_year, db.session)

    vacation_info = {
        'total':               balance.vacation_total,
        'on_demand_total':     balance.on_demand_total,
        'remote_total':        balance.remote_total,
        'used_vacation':       used['used_vacation'],
        'used_on_demand':      used['used_on_demand'],
        'used_remote':         used['used_remote'],
        'remaining_vacation':  balance.vacation_total - used['used_vacation'],
        'remaining_on_demand': balance.on_demand_total - used['used_on_demand'],
        'remaining_remote':    balance.remote_total - used['used_remote'],
        'care_leave_total':       balance.care_leave_total,
        'force_majeure_total':    balance.force_majeure_total,
        'child_care_total':       balance.child_care_total,
        'used_care_leave':        used['used_care_leave'],
        'used_force_majeure':     used['used_force_majeure'],
        'used_child_care':        used['used_child_care'],
        'remaining_care_leave':    balance.care_leave_total - used['used_care_leave'],
        'remaining_force_majeure': balance.force_majeure_total - used['used_force_majeure'],
        'remaining_child_care':    balance.child_care_total - used['used_child_care'],
    }

    return render_template(
        'dashboard/index.html',
        months_data=months_data,
        current_key=current_key,
        vacation_info=vacation_info,
        balance=balance,
        format_hours=format_hours,
        format_currency=format_currency,
        MONTH_NAMES=MONTH_NAMES,
        viewing_employee=(target if current_user.is_company else None),
    )


@dashboard_bp.route('/employees/new', methods=['GET', 'POST'])
@login_required
def employee_new():
    if not current_user.is_company:
        abort(403)

    last_config, last_balance = get_last_employee_defaults(current_user.id)

    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        login = request.form.get('login', '').strip().lower()
        password  = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not name or not login or not password:
            flash('Imię i nazwisko, login i hasło są wymagane.', 'error')
            return redirect(url_for('dashboard.employee_new'))
        if password != password2:
            flash('Hasła nie są identyczne.', 'error')
            return redirect(url_for('dashboard.employee_new'))
        if len(password) < 6:
            flash('Hasło musi mieć minimum 6 znaków.', 'error')
            return redirect(url_for('dashboard.employee_new'))
        if User.query.filter_by(login=login).first():
            flash('Ten login jest już zajęty.', 'error')
            return redirect(url_for('dashboard.employee_new'))

        try:
            employee = User(
                name=name,
                login=login,
                account_type='employee',
                company_id=current_user.id,
            )
            employee.set_password(password)
            employee.generate_pin()
            db.session.add(employee)
            db.session.flush()  # żeby mieć employee.id

            today = date.today()
            billing_year, billing_month = get_billing_period(today)

            hourly_rate = Decimal(request.form.get('hourly_rate', '0').replace(',', '.'))
            work_days_selected = request.form.getlist('work_days')
            work_days = ','.join(sorted(work_days_selected)) if work_days_selected else '0,1,2,3,4'
            hours_per_day = Decimal(request.form.get('hours_per_day', '8').replace(',', '.'))
            config = MonthConfig(
                user_id=employee.id,
                billing_year=billing_year,
                billing_month=billing_month,
                hourly_rate=hourly_rate,
                bonus=Decimal('0'),
                billing_start_day=int(request.form.get('billing_start_day', 23)),
                billing_end_day=int(request.form.get('billing_end_day', 22)),
                round_minutes=int(request.form.get('round_minutes', 15)),
                overtime_rate=int(request.form.get('overtime_rate', 100)),
                work_days=work_days,
                offday_rate=int(request.form.get('offday_rate', 100)),
                hours_per_day=hours_per_day,
                paid_break_minutes=int(request.form.get('paid_break_minutes', 15)),
            )
            working_days = get_working_days_in_billing_period(
                billing_year, billing_month,
                start_day=config.billing_start_day, end_day=config.billing_end_day,
                work_days=[int(d) for d in work_days.split(',')],
            )
            config.expected_hours = Decimal(str(float(hours_per_day) * working_days))
            db.session.add(config)

            balance = VacationBalance(
                user_id=employee.id,
                year=today.year,
                vacation_total=int(request.form.get('vacation_total', 26)),
                on_demand_total=int(request.form.get('on_demand_total', 4)),
                remote_total=int(request.form.get('remote_total', 0)),
                care_leave_total=int(request.form.get('care_leave_total', 5)),
                force_majeure_total=int(request.form.get('force_majeure_total', 2)),
                child_care_total=int(request.form.get('child_care_total', 2)),
            )
            db.session.add(balance)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Błąd: {e}', 'error')
            return redirect(url_for('dashboard.employee_new'))

        set_viewing_employee(employee.id)
        flash(f'Dodano pracownika: {employee.name}.', 'success')
        return redirect(url_for('dashboard.index'))

    work_days_set = set(str(d) for d in last_config.work_days_list()) if last_config else {'0', '1', '2', '3', '4'}

    return render_template(
        'dashboard/employee_form.html',
        last_config=last_config,
        last_balance=last_balance,
        work_days_set=work_days_set,
    )


@dashboard_bp.route('/employees/<int:employee_id>/select', methods=['POST'])
@login_required
def employee_select(employee_id):
    if not current_user.is_company:
        abort(403)
    employee = User.query.filter_by(
        id=employee_id, company_id=current_user.id, account_type='employee'
    ).first_or_404()
    set_viewing_employee(employee.id)
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/employees/exit', methods=['POST'])
@login_required
def employee_exit():
    if not current_user.is_company:
        abort(403)
    clear_viewing_employee()
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/employees/<int:employee_id>/delete', methods=['POST'])
@login_required
def employee_delete(employee_id):
    if not current_user.is_company:
        abort(403)
    employee = User.query.filter_by(
        id=employee_id, company_id=current_user.id, account_type='employee'
    ).first_or_404()

    name = employee.name
    db.session.delete(employee)
    db.session.commit()
    clear_viewing_employee()

    flash(f'Usunięto pracownika: {name}.', 'success')
    return redirect(url_for('dashboard.index'))

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from collections import defaultdict
from datetime import date
from decimal import Decimal

from wlogio_app import db
from wlogio_app.models import WorkEntry, MonthConfig, VacationBalance
from wlogio_app.calculator import (
    calculate_month_summary,
    calculate_vacation_used,
    get_billing_period,
    get_working_days_in_billing_period,
    get_or_create_vacation_balance,
    format_hours,
    format_currency,
)

dashboard_bp = Blueprint('dashboard', __name__)

MONTH_NAMES = {
    1: 'Styczeń', 2: 'Luty', 3: 'Marzec', 4: 'Kwiecień',
    5: 'Maj', 6: 'Czerwiec', 7: 'Lipiec', 8: 'Sierpień',
    9: 'Wrzesień', 10: 'Październik', 11: 'Listopad', 12: 'Grudzień'
}


def calculate_forecast(expected_hours, overtime_hours, hourly_rate, bonus):
    """
    Prognoza wynagrodzenia za miesiąc:
    (dni robocze × 8h × stawka) + (nadgodziny × stawka) + premia
    = (expected_hours + overtime_hours) × stawka + premia

    Jeśli nadgodziny ujemne — odejmowane od prognozy.
    """
    rate = Decimal(str(hourly_rate))
    exp  = Decimal(str(expected_hours))
    ot   = Decimal(str(overtime_hours))
    bon  = Decimal(str(bonus or 0))
    return float((exp + ot) * rate + bon)


@dashboard_bp.route('/')
@login_required
def index():
    today = date.today()
    current_billing_year, current_billing_month = get_billing_period(today)

    all_entries = (
        WorkEntry.query
        .filter_by(user_id=current_user.id)
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
        for c in MonthConfig.query.filter_by(user_id=current_user.id).all()
    }

    sorted_keys = sorted(periods.keys(), key=lambda x: (x[0], x[1]), reverse=True)

    current_key = (current_billing_year, current_billing_month)
    if current_key not in periods:
        periods[current_key] = []
        if current_key not in sorted_keys:
            sorted_keys.insert(0, current_key)

    months_data = []
    for key in sorted_keys:
        year, month = key
        entries = periods[key]
        config = configs.get(key)

        hourly_rate  = float(config.hourly_rate) if config else 0.0
        working_days = get_working_days_in_billing_period(year, month)
        expected_hours = working_days * 8
        bonus = float(config.bonus) if config and config.bonus else 0.0

        summary = calculate_month_summary(entries, hourly_rate, expected_hours, bonus)

        forecast = calculate_forecast(
            expected_hours,
            summary['overtime_hours'],
            hourly_rate,
            bonus,
        )

        months_data.append({
            'year': year,
            'month': month,
            'month_name': MONTH_NAMES.get(month, str(month)),
            'is_current': key == current_key,
            'entries': entries,
            'config': config,
            'summary': summary,
            'hourly_rate': hourly_rate,
            'working_days': working_days,
            'forecast': forecast,
        })

    # Bilans urlopowy
    current_year = today.year
    balance = get_or_create_vacation_balance(current_user.id, db.session)
    used = calculate_vacation_used(current_user.id, current_year, db.session)

    vacation_info = {
        'total': balance.vacation_total,
        'on_demand_total': balance.on_demand_total,
        'remote_total': balance.remote_total,
        'used_vacation': used['used_vacation'],
        'used_on_demand': used['used_on_demand'],
        'used_remote': used['used_remote'],
        'remaining_vacation': balance.vacation_total - used['used_vacation'],
        'remaining_on_demand': balance.on_demand_total - used['used_on_demand'],
        'remaining_remote': balance.remote_total - used['used_remote'],
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
    )

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from collections import defaultdict
from datetime import date

from app import db
from app.models import WorkEntry, MonthConfig, VacationBalance
from app.calculator import (
    calculate_month_summary,
    calculate_vacation_used,
    get_billing_period,
    format_hours,
    format_currency,
)

dashboard_bp = Blueprint('dashboard', __name__)

MONTH_NAMES = {
    1: 'Styczeń', 2: 'Luty', 3: 'Marzec', 4: 'Kwiecień',
    5: 'Maj', 6: 'Czerwiec', 7: 'Lipiec', 8: 'Sierpień',
    9: 'Wrzesień', 10: 'Październik', 11: 'Listopad', 12: 'Grudzień'
}


@dashboard_bp.route('/')
@login_required
def index():
    # Aktualny okres rozliczeniowy
    today = date.today()
    current_billing_year, current_billing_month = get_billing_period(today)

    # Wszystkie wpisy użytkownika posortowane od najnowszych
    all_entries = (
        WorkEntry.query
        .filter_by(user_id=current_user.id)
        .order_by(WorkEntry.billing_year.desc(),
                  WorkEntry.billing_month.desc(),
                  WorkEntry.date.asc())
        .all()
    )

    # Grupuj wpisy wg (billing_year, billing_month)
    periods = defaultdict(list)
    for entry in all_entries:
        key = (entry.billing_year, entry.billing_month)
        periods[key].append(entry)

    # Pobierz konfiguracje miesięcy
    configs = {
        (c.billing_year, c.billing_month): c
        for c in MonthConfig.query.filter_by(user_id=current_user.id).all()
    }

    # Zbuduj listę miesięcy posortowaną od najnowszego
    sorted_keys = sorted(periods.keys(), key=lambda x: (x[0], x[1]), reverse=True)

    # Jeśli nie ma żadnych wpisów — dodaj pusty aktualny miesiąc
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

        hourly_rate = float(config.hourly_rate) if config else 0
        expected_hours = float(config.expected_hours) if config and config.expected_hours else 0
        bonus = float(config.bonus) if config and config.bonus else 0

        summary = calculate_month_summary(entries, hourly_rate, expected_hours, bonus)

        months_data.append({
            'year': year,
            'month': month,
            'month_name': MONTH_NAMES.get(month, str(month)),
            'is_current': key == current_key,
            'entries': entries,
            'config': config,
            'summary': summary,
            'hourly_rate': hourly_rate,
        })

    # Bilans urlopowy na bieżący rok
    current_year = today.year
    vacation_balance = VacationBalance.query.filter_by(
        user_id=current_user.id,
        year=current_year
    ).first()

    used = calculate_vacation_used(current_user.id, current_year, db.session)

    vacation_info = {
        'total': vacation_balance.vacation_total if vacation_balance else 26,
        'on_demand_total': vacation_balance.on_demand_total if vacation_balance else 4,
        'remote_total': vacation_balance.remote_total if vacation_balance else 0,
        'used_vacation': used['used_vacation'],
        'used_on_demand': used['used_on_demand'],
        'used_remote': used['used_remote'],
        'remaining_vacation': (vacation_balance.vacation_total if vacation_balance else 26) - used['used_vacation'],
        'remaining_on_demand': (vacation_balance.on_demand_total if vacation_balance else 4) - used['used_on_demand'],
        'remaining_remote': (vacation_balance.remote_total if vacation_balance else 0) - used['used_remote'],
    }

    return render_template(
        'dashboard/index.html',
        months_data=months_data,
        current_key=current_key,
        vacation_info=vacation_info,
        format_hours=format_hours,
        format_currency=format_currency,
        MONTH_NAMES=MONTH_NAMES,
    )

"""
analysis.py - Analiza: wykresy miesięczne (wynagrodzenie, godziny, nieobecności)
dla całego okresu wprowadzania danych.

Dostępna dla kont 'individual' (własne dane) i 'company' (dane zbiorcze wszystkich
pracowników firmy). Konta 'employee' nie mają dostępu. Liczby pochodzą z tej samej
funkcji build_months_data() co panel pracy i eksport — bez duplikowania logiki.
"""
from collections import OrderedDict

from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from wlogio_app.routes.dashboard import build_months_data, get_company_employees

analysis_bp = Blueprint('analysis', __name__)

MONTH_SHORT = {
    1: 'sty', 2: 'lut', 3: 'mar', 4: 'kwi', 5: 'maj', 6: 'cze',
    7: 'lip', 8: 'sie', 9: 'wrz', 10: 'paź', 11: 'lis', 12: 'gru',
}


def _collect(user_ids):
    """Sumuje miesiące rozliczeniowe wskazanych kont: {(rok, miesiąc): dict sum}."""
    totals = {}
    for uid in user_ids:
        months, _ = build_months_data(uid, include_empty_current=False)
        for m in months:
            if not m['entries']:
                continue
            s = m['summary']
            t = totals.setdefault((m['year'], m['month']),
                                  {'salary': 0.0, 'hours': 0.0, 'vacation': 0, 'sick': 0})
            t['salary'] += s['total_with_bonus']
            t['hours'] += s['total_hours']
            t['vacation'] += s['vacation_days'] + s['on_demand_days']
            t['sick'] += s['sick_days']
    return totals


def _series(totals):
    """Ciągła oś miesięcy od pierwszego do ostatniego z danymi (luki = 0)."""
    if not totals:
        return []
    (y0, m0), (y1, m1) = min(totals), max(totals)
    rows = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        t = totals.get((y, m), {'salary': 0.0, 'hours': 0.0, 'vacation': 0, 'sick': 0})
        rows.append({
            'label': f'{MONTH_SHORT[m]} {y}',
            'salary': round(t['salary'], 2),
            'hours': round(t['hours'], 2),
            'vacation': t['vacation'],
            'sick': t['sick'],
        })
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return rows


@analysis_bp.route('/', methods=['GET'])
@login_required
def index():
    if current_user.account_type not in ('individual', 'company'):
        abort(403)

    is_company = current_user.is_company
    if is_company:
        employees = get_company_employees(current_user.id)
        user_ids = [e.id for e in employees]
        employees_count = len(employees)
    else:
        user_ids = [current_user.id]
        employees_count = None

    rows = _series(_collect(user_ids))
    return render_template('analysis/index.html', rows=rows,
                           is_company=is_company, employees_count=employees_count)

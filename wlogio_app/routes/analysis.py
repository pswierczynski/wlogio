"""
analysis.py - Analiza: wykresy miesięczne (wynagrodzenie, godziny, nieobecności)
dla całego okresu wprowadzania danych.

Dostępna dla kont 'individual' (własne dane) i 'company' (dane zbiorcze wszystkich
pracowników firmy). Konta 'employee' nie mają dostępu. Liczby pochodzą z tej samej
funkcji build_months_data() co panel pracy i eksport — bez duplikowania logiki.
"""
from datetime import timedelta

from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from wlogio_app.calculator import get_billing_period_dates, _parse_work_days
from wlogio_app.holidays import polish_holidays
from wlogio_app.routes.dashboard import build_months_data, get_company_employees

analysis_bp = Blueprint('analysis', __name__)

MONTH_SHORT = {
    1: 'sty', 2: 'lut', 3: 'mar', 4: 'kwi', 5: 'maj', 6: 'cze',
    7: 'lip', 8: 'sie', 9: 'wrz', 10: 'paź', 11: 'lis', 12: 'gru',
}


def _current_month_complete(month):
    """
    Bieżący miesiąc rozliczeniowy jest „pełny” dopiero, gdy wpisano czas pracy
    za jego ostatni dzień roboczy (ostatni dzień okresu, który jest dniem pracy
    wg konfiguracji miesiąca i nie jest świętem). Wcześniej dane są niepełne.
    """
    cfg = month['config']
    start = cfg.billing_start_day if cfg and cfg.billing_start_day else None
    end = cfg.billing_end_day if cfg and cfg.billing_end_day else None
    d_from, d_to = get_billing_period_dates(month['year'], month['month'], start, end)
    work_days = _parse_work_days(cfg.work_days) if cfg and cfg.work_days else [0, 1, 2, 3, 4]
    holidays = set(polish_holidays(d_from.year)) | set(polish_holidays(d_to.year))

    last = d_to
    while last >= d_from and (last.weekday() not in work_days or last in holidays):
        last -= timedelta(days=1)
    for e in month['entries']:
        if e.date == last and (e.entry_type != 'work' or float(e.hours_worked or 0) > 0):
            return True
    return False


def _collect(user_ids):
    """
    Sumuje miesiące rozliczeniowe wskazanych kont: {(rok, miesiąc): dict sum}.
    Bieżący miesiąc trafia do wyniku dopiero po jego zakończeniu (patrz
    _current_month_complete); dla konta firmowego — gdy zakończyli go wszyscy
    pracownicy mający w nim wpisy.
    """
    totals = {}
    pending = {}          # bieżący miesiąc: {klucz: [lista sum per konto]}
    incomplete = set()
    for uid in user_ids:
        months, current_key = build_months_data(uid, include_empty_current=False)
        for m in months:
            if not m['entries'] or (m['year'], m['month']) > current_key:
                continue   # puste i przyszłe (planowane) miesiące nie wchodzą do analizy
            s = m['summary']
            row = {'salary': s['total_with_bonus'], 'hours': s['total_hours'],
                   'vacation': s['vacation_days'] + s['on_demand_days'], 'sick': s['sick_days']}
            key = (m['year'], m['month'])
            if m['is_current']:
                if not _current_month_complete(m):
                    incomplete.add(key)
                pending.setdefault(key, []).append(row)
                continue
            t = totals.setdefault(key, {'salary': 0.0, 'hours': 0.0, 'vacation': 0, 'sick': 0})
            for k, v in row.items():
                t[k] += v
    for key, rows in pending.items():
        if key in incomplete:
            continue
        t = totals.setdefault(key, {'salary': 0.0, 'hours': 0.0, 'vacation': 0, 'sick': 0})
        for row in rows:
            for k, v in row.items():
                t[k] += v
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

"""
analysis.py - Analiza: wykresy miesięczne (wynagrodzenie, godziny, nieobecności)
dla całego okresu wprowadzania danych.

Dostępna dla kont 'individual' (własne dane) i 'company' (dane zbiorcze wszystkich
pracowników firmy). Konta 'employee' nie mają dostępu. Liczby pochodzą z tej samej
funkcji build_months_data() co panel pracy i eksport — bez duplikowania logiki.
"""
from datetime import date, timedelta

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


VACATION_TYPES = ('vacation', 'on_demand')
SICK_TYPES = ('sick_leave',)


def _longest_run(months, types):
    """
    Najdłuższa nieprzerwana seria dni nieobecności danego rodzaju. Weekendy i święta
    pomiędzy dniami nieobecności nie przerywają serii (urlop od piątku do poniedziałku
    to jedna seria). Zwraca {'days': liczba dni, 'from': data, 'to': data} lub None.
    """
    dates = sorted({e.date for m in months for e in m['entries'] if e.entry_type in types})
    if not dates:
        return None
    holidays = set()
    for y in {d.year for d in dates} | {d.year + 1 for d in dates}:
        holidays |= set(polish_holidays(y))

    def bridged(a, b):
        d = a + timedelta(days=1)
        while d < b:
            if d.weekday() < 5 and d not in holidays:
                return False
            d += timedelta(days=1)
        return True

    best = None
    start = prev = dates[0]
    count = 1
    for d in dates[1:] + [None]:
        if d is not None and bridged(prev, d):
            count += 1
            prev = d
            continue
        if best is None or count > best['days']:
            best = {'days': count, 'from': start, 'to': prev}
        if d is not None:
            start = prev = d
            count = 1
    return best


def _ytd_sum(user_ids, year, upto):
    """Suma zarobiona od 1 stycznia roku `year` do daty `upto` (włącznie)."""
    total = 0.0
    for uid in user_ids:
        months, _ = build_months_data(uid, date_from=date(year, 1, 1), date_to=upto,
                                      include_empty_current=False)
        for m in months:
            if m['year'] != year:
                continue
            s = m['summary']
            # miesiąc, w którym wypada `upto`, jest jeszcze niepełny — bez jednorazowej premii
            total += s['actual_salary'] if m['month'] == upto.month else s['total_with_bonus']
    return total


def _fmt_range(r):
    if not r:
        return None
    a, b = r['from'], r['to']
    text = a.strftime('%d.%m.%Y') if a == b else f"{a.strftime('%d.%m.%Y')} – {b.strftime('%d.%m.%Y')}"
    return {'days': r['days'], 'range': text}


def _label(key):
    return f'{MONTH_SHORT[key[1]]} {key[0]}'


def _stats(user_ids, totals, extras, leaves):
    """Zestaw wartości do bloku podsumowania nad wykresem (None = brak danych)."""
    if not totals:
        return None
    today = date.today()
    this_year, prev_year = today.year, today.year - 1

    def avg(vals):
        return sum(vals) / len(vals) if vals else None

    salaries = {k: v['salary'] for k, v in totals.items()}
    hi = max(salaries, key=salaries.get)
    lo = min(salaries, key=salaries.get)

    rates = [e['rate'] for e in extras if e['rate'] and e['rate'] > 0]
    bonus = max(extras, key=lambda e: e['bonus'], default=None)
    ot = max(extras, key=lambda e: e['overtime'], default=None)

    try:
        same_day_prev = today.replace(year=prev_year)
    except ValueError:      # 29 lutego
        same_day_prev = today.replace(year=prev_year, day=28)
    ytd = _ytd_sum(user_ids, this_year, today)
    ytd_prev = _ytd_sum(user_ids, prev_year, same_day_prev)
    diff = ytd - ytd_prev
    pct = (diff / ytd_prev * 100) if ytd_prev else None

    def best_leave(kind):
        runs = [r for r in leaves[kind] if r]
        return _fmt_range(max(runs, key=lambda r: r['days'])) if runs else None

    return {
        'avg_this_year': avg([v for k, v in salaries.items() if k[0] == this_year]),
        'avg_prev_year': avg([v for k, v in salaries.items() if k[0] == prev_year]),
        'avg_all': avg(list(salaries.values())),
        'avg_rate': avg(rates),
        'sum_all': sum(salaries.values()),
        'ytd': ytd, 'ytd_prev': ytd_prev, 'ytd_diff': diff, 'ytd_pct': pct,
        'ytd_prev_label': same_day_prev.strftime('%d.%m.%Y'),
        'max_salary': {'value': salaries[hi], 'label': _label(hi)},
        'min_salary': {'value': salaries[lo], 'label': _label(lo)},
        'max_bonus': {'value': bonus['bonus'], 'label': _label(bonus['key'])} if bonus and bonus['bonus'] > 0 else None,
        'max_overtime': {'value': ot['overtime'], 'label': _label(ot['key'])} if ot and ot['overtime'] > 0 else None,
        'longest_vacation': best_leave('vacation'),
        'longest_sick': best_leave('sick'),
    }


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
    extras = []           # rekordy per konto i miesiąc (premia, nadgodziny, stawka)
    leaves = {'vacation': [], 'sick': []}   # najdłuższe serie nieobecności per konto
    for uid in user_ids:
        months, current_key = build_months_data(uid, include_empty_current=False)
        leaves['vacation'].append(_longest_run(months, VACATION_TYPES))
        leaves['sick'].append(_longest_run(months, SICK_TYPES))
        for m in months:
            if not m['entries'] or (m['year'], m['month']) > current_key:
                continue   # puste i przyszłe (planowane) miesiące nie wchodzą do analizy
            s = m['summary']
            row = {'salary': s['total_with_bonus'], 'hours': s['total_hours'],
                   'vacation': s['vacation_days'] + s['on_demand_days'], 'sick': s['sick_days']}
            key = (m['year'], m['month'])
            extras.append({'key': key, 'bonus': s['bonus'], 'overtime': s['overtime_hours'],
                           'rate': m['hourly_rate']})
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
    extras = [e for e in extras if e['key'] in totals]
    return totals, extras, leaves


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

    totals, extras, leaves = _collect(user_ids)
    rows = _series(totals)
    stats = _stats(user_ids, totals, extras, leaves)
    return render_template('analysis/index.html', rows=rows, stats=stats,
                           is_company=is_company, employees_count=employees_count)

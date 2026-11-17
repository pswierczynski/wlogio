"""
calendar.py - Kalendarz: bieżący miesiąc i dwa kolejne, z zaznaczonymi urlopami,
zwolnieniami lekarskimi i świętami.

Dostępny dla kont 'individual' (własne dni) i 'company' (wszyscy pracownicy:
na dzień pokazujemy liczbę osób na urlopie / zwolnieniu). Konto 'employee' nie ma dostępu.
Święta państwowe są liczone algorytmicznie (stałe + zależne od Wielkanocy),
dodatkowo uwzględniamy wpisy typu 'holiday' z rejestru.
"""
import calendar as pycal
from datetime import date, timedelta

from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from wlogio_app.models import WorkEntry, User
from wlogio_app.routes.dashboard import get_company_employees
from wlogio_app.scope import local_today

calendar_bp = Blueprint('calendar', __name__)

MONTH_NAMES = ['', 'Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec',
               'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień']

VACATION_TYPES = ('vacation', 'on_demand', 'unpaid')


def easter(year):
    """Niedziela Wielkanocna (algorytm Gaussa/Meeusa)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def polish_holidays(year):
    """{data: nazwa} świąt ustawowo wolnych od pracy w Polsce."""
    e = easter(year)
    h = {
        date(year, 1, 1): 'Nowy Rok',
        date(year, 1, 6): 'Trzech Króli',
        e: 'Wielkanoc',
        e + timedelta(days=1): 'Poniedziałek Wielkanocny',
        date(year, 5, 1): 'Święto Pracy',
        date(year, 5, 3): 'Święto Konstytucji 3 Maja',
        e + timedelta(days=49): 'Zielone Świątki',
        e + timedelta(days=60): 'Boże Ciało',
        date(year, 8, 15): 'Wniebowzięcie NMP',
        date(year, 11, 1): 'Wszystkich Świętych',
        date(year, 11, 11): 'Narodowe Święto Niepodległości',
        date(year, 12, 24): 'Wigilia',
        date(year, 12, 25): 'Boże Narodzenie',
        date(year, 12, 26): 'Drugi dzień Świąt',
    }
    if year < 2025:  # Wigilia jest dniem wolnym dopiero od 2025 r.
        h.pop(date(year, 12, 24), None)
    return h


def _months_ahead(today, count=3):
    y, m = today.year, today.month
    out = []
    for _ in range(count):
        out.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


@calendar_bp.route('/', methods=['GET'])
@login_required
def index():
    if current_user.account_type not in ('individual', 'company'):
        abort(403)

    today = local_today()
    months = _months_ahead(today)
    first = date(months[0][0], months[0][1], 1)
    ly, lm = months[-1]
    last = date(ly, lm, pycal.monthrange(ly, lm)[1])

    is_company = current_user.is_company
    if is_company:
        people = get_company_employees(current_user.id)
    else:
        people = [current_user]
    names = {p.id: p.name for p in people}

    entries = []
    if names:
        entries = (WorkEntry.query
                   .filter(WorkEntry.user_id.in_(list(names)),
                           WorkEntry.date >= first, WorkEntry.date <= last,
                           WorkEntry.entry_type.in_(VACATION_TYPES + ('sick_leave', 'holiday')))
                   .all())

    # {iso: {'holiday': nazwa|None, 'vacation': [imiona], 'sick': [imiona]}}
    days = {}

    def slot(d):
        return days.setdefault(d.isoformat(), {'holiday': None, 'vacation': [], 'sick': []})

    for y, _ in {(y, m) for y, m in months}:
        for d, name in polish_holidays(y).items():
            if first <= d <= last:
                slot(d)['holiday'] = name
    for en in entries:
        s = slot(en.date)
        if en.entry_type == 'holiday':
            s['holiday'] = s['holiday'] or 'Święto'
        elif en.entry_type == 'sick_leave':
            s['sick'].append(names[en.user_id])
        else:
            s['vacation'].append(names[en.user_id])

    blocks = []
    for y, m in months:
        weeks = pycal.Calendar(firstweekday=0).monthdatescalendar(y, m)
        blocks.append({
            'title': f'{MONTH_NAMES[m]} {y}',
            'weeks': [[{'date': d, 'iso': d.isoformat(), 'in_month': d.month == m,
                        'today': d == today, 'weekend': d.weekday() >= 5}
                       for d in w] for w in weeks],
        })

    return render_template('calendar/index.html', blocks=blocks, days=days,
                           is_company=is_company, total=len(people))

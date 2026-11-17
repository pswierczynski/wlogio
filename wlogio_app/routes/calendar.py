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
from wlogio_app.holidays import polish_holidays

calendar_bp = Blueprint('calendar', __name__)

MONTH_NAMES = ['', 'Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec',
               'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień']

VACATION_TYPES = ('vacation', 'on_demand', 'unpaid')


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

"""
holidays.py - polskie święta ustawowo wolne od pracy oraz automatyczne dodawanie ich
do miesiąca rozliczeniowego (przy pierwszym wpisie w nowym miesiącu).
"""
from datetime import date, timedelta
from decimal import Decimal

from wlogio_app import db


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


def seed_month_holidays(user_id, billing_year, billing_month, config):
    """
    Dodaje wpisy 'holiday' (8 h płatne) dla świąt wypadających w dniach roboczych
    miesiąca rozliczeniowego (wg dni pracy z konfiguracji miesiąca).
    Dni, które już mają jakikolwiek wpis (np. praca w święto), pozostają bez zmian.
    Nie robi commita — robi to wywołujący.
    """
    from wlogio_app.models import WorkEntry
    from wlogio_app.calculator import get_billing_period_dates

    d_from, d_to = get_billing_period_dates(
        billing_year, billing_month, config.billing_start_day, config.billing_end_day)
    work_days = config.work_days_list()
    taken = {e.date for e in WorkEntry.query.filter(
        WorkEntry.user_id == user_id, WorkEntry.date >= d_from, WorkEntry.date <= d_to)}

    added = 0
    for year in {d_from.year, d_to.year}:
        for day, _name in sorted(polish_holidays(year).items()):
            if not (d_from <= day <= d_to) or day in taken or day.weekday() not in work_days:
                continue
            db.session.add(WorkEntry(
                user_id=user_id, date=day,
                billing_year=billing_year, billing_month=billing_month,
                entry_type='holiday',
                hours_worked=Decimal('8'), hours_billed=Decimal('8'),
            ))
            added += 1
    return added


def month_is_empty(user_id, billing_year, billing_month):
    """True, jeśli konto nie ma jeszcze żadnego wpisu w tym miesiącu rozliczeniowym."""
    from wlogio_app.models import WorkEntry
    return WorkEntry.query.filter_by(
        user_id=user_id, billing_year=billing_year, billing_month=billing_month).first() is None

"""
calculator.py
=============
Logika obliczeń czasu pracy i wynagrodzenia.

Zasady z wlogio.txt / examples.md:
- Programowa przerwa: 15 min (odliczana zawsze)
- Nadprogramowa przerwa: czas ponad 15 min (odliczany od przepracowanych)
- Zaokrąglenie do 0.25h (15 min)
- Miesiąc rozliczeniowy: 23 bieżącego → 22 następnego
"""

from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import math


BREAK_MINUTES = 15          # programowa przerwa (zawsze odliczana)
ROUND_TO = Decimal('0.25')  # zaokrąglenie godzin


def calculate_hours(time_start, time_end, break_start=None, break_end=None):
    """
    Oblicza przepracowane godziny dla jednego dnia.

    Parametry:
        time_start  - godzina przyjścia (datetime.time)
        time_end    - godzina wyjścia (datetime.time)
        break_start - początek przerwy (datetime.time lub None)
        break_end   - koniec przerwy (datetime.time lub None)

    Zwraca słownik:
        raw_minutes         - całkowite minuty od start do end
        break_minutes       - faktyczna przerwa (minuty)
        extra_break_minutes - nadprogramowa przerwa ponad 15 min
        net_minutes         - minuty po odjęciu nadprogramowej przerwy
        hours_worked        - net_minutes / 60 (float, przed zaokrągleniem)
        hours_billed        - zaokrąglone do 0.25
    """
    # Zamień time na minuty od północy
    start_min = time_start.hour * 60 + time_start.minute
    end_min = time_end.hour * 60 + time_end.minute

    # Obsługa pracy przez północ (mało prawdopodobne ale bezpieczne)
    if end_min < start_min:
        end_min += 24 * 60

    raw_minutes = end_min - start_min

    # Oblicz faktyczną przerwę
    if break_start and break_end:
        bs_min = break_start.hour * 60 + break_start.minute
        be_min = break_end.hour * 60 + break_end.minute
        break_minutes = max(0, be_min - bs_min)
    else:
        break_minutes = 0

    # Nadprogramowa przerwa = czas ponad 15 min
    extra_break_minutes = max(0, break_minutes - BREAK_MINUTES)

    # Netto = całość - nadprogramowa przerwa
    net_minutes = raw_minutes - extra_break_minutes

    hours_worked = net_minutes / 60.0

    # Zaokrąglenie do 0.25
    hours_billed = float(
        Decimal(str(hours_worked)).quantize(ROUND_TO, rounding=ROUND_HALF_UP)
    )

    return {
        'raw_minutes': raw_minutes,
        'break_minutes': break_minutes,
        'extra_break_minutes': extra_break_minutes,
        'net_minutes': net_minutes,
        'hours_worked': round(hours_worked, 4),
        'hours_billed': hours_billed,
    }


def get_billing_period(entry_date):
    """
    Zwraca (billing_year, billing_month) dla podanej daty.

    Logika:
    - Dzień 23+ bieżącego miesiąca → należy do kolejnego miesiąca rozliczeniowego
    - Dzień 1-22 bieżącego miesiąca → należy do bieżącego miesiąca rozliczeniowego

    Przykłady:
    - 24.03 → billing_month=4 (kwiecień), billing_year=rok
    - 15.04 → billing_month=4 (kwiecień), billing_year=rok
    - 22.04 → billing_month=4 (kwiecień), billing_year=rok
    - 23.04 → billing_month=5 (maj), billing_year=rok
    """
    if entry_date.day >= 23:
        # Kolejny miesiąc rozliczeniowy
        if entry_date.month == 12:
            return entry_date.year + 1, 1
        else:
            return entry_date.year, entry_date.month + 1
    else:
        return entry_date.year, entry_date.month


def calculate_month_summary(entries, hourly_rate, expected_hours, bonus=0):
    """
    Oblicza podsumowanie miesiąca na podstawie listy wpisów.

    Parametry:
        entries        - lista obiektów WorkEntry
        hourly_rate    - stawka godzinowa (Decimal lub float)
        expected_hours - oczekiwana liczba godzin (dni_robocze * 8)
        bonus          - premia (domyślnie 0)

    Zwraca słownik z podsumowaniem.
    """
    rate = Decimal(str(hourly_rate))
    expected = Decimal(str(expected_hours)) if expected_hours else Decimal('0')

    total_billed = Decimal('0')
    work_days = 0
    vacation_days = 0
    on_demand_days = 0
    holiday_days = 0
    sick_days = 0
    remote_days = 0

    for entry in entries:
        billed = Decimal(str(entry.hours_billed))
        total_billed += billed

        if entry.entry_type == 'work':
            work_days += 1
            if entry.is_remote:
                remote_days += 1
        elif entry.entry_type == 'vacation':
            vacation_days += 1
        elif entry.entry_type == 'on_demand':
            on_demand_days += 1
        elif entry.entry_type == 'holiday':
            holiday_days += 1
        elif entry.entry_type == 'sick_leave':
            sick_days += 1

    actual_salary = total_billed * rate
    expected_salary = expected * rate
    overtime_hours = total_billed - expected
    total_with_bonus = actual_salary + Decimal(str(bonus or 0))

    return {
        'total_hours': float(total_billed),
        'expected_hours': float(expected),
        'overtime_hours': float(overtime_hours),
        'actual_salary': float(actual_salary),
        'expected_salary': float(expected_salary),
        'bonus': float(bonus or 0),
        'total_with_bonus': float(total_with_bonus),
        'work_days': work_days,
        'vacation_days': vacation_days,
        'on_demand_days': on_demand_days,
        'holiday_days': holiday_days,
        'sick_days': sick_days,
        'remote_days': remote_days,
    }


def calculate_vacation_used(user_id, year, db_session):
    """
    Oblicza wykorzystane urlopy z wpisów WorkEntry dla danego roku kalendarzowego.
    Reset następuje z dniem 1 stycznia (nowy rok = nowe liczniki).

    Zwraca słownik:
        used_vacation   - dni urlopu zwykłego
        used_on_demand  - dni urlopu na żądanie
        used_remote     - dni pracy zdalnej
    """
    from app.models import WorkEntry
    from sqlalchemy import extract

    entries = db_session.query(WorkEntry).filter(
        WorkEntry.user_id == user_id,
        extract('year', WorkEntry.date) == year,
        WorkEntry.entry_type.in_(['vacation', 'on_demand', 'work'])
    ).all()

    used_vacation = sum(1 for e in entries if e.entry_type == 'vacation')
    used_on_demand = sum(1 for e in entries if e.entry_type == 'on_demand')
    used_remote = sum(1 for e in entries if e.entry_type == 'work' and e.is_remote)

    return {
        'used_vacation': used_vacation,
        'used_on_demand': used_on_demand,
        'used_remote': used_remote,
    }


def format_hours(hours):
    """
    Formatuje godziny jako 'Xh Ymin'.
    Np. 8.25 → '8h 15min', 9.5 → '9h 30min'
    """
    h = int(hours)
    m = round((hours - h) * 60)
    if m == 0:
        return f'{h}h 00min'
    return f'{h}h {m:02d}min'


def format_currency(amount):
    """
    Formatuje kwotę jako '1 234,56 zł'.
    """
    return f'{amount:,.2f} zł'.replace(',', ' ').replace('.', ',')

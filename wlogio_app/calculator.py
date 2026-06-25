"""
calculator.py - logika obliczeń czasu pracy i wynagrodzenia
"""

from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP


BREAK_MINUTES = 15
ROUND_TO = Decimal('0.25')


def get_working_days_in_billing_period(billing_year, billing_month):
    if billing_month == 1:
        start_month, start_year = 12, billing_year - 1
    else:
        start_month, start_year = billing_month - 1, billing_year

    start_date = date(start_year, start_month, 23)
    end_date = date(billing_year, billing_month, 22)

    working_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            working_days += 1
        current += timedelta(days=1)
    return working_days


def parse_breaks(breaks_str):
    """
    Parsuje string przerw "HH:MM-HH:MM;HH:MM-HH:MM" na listę tupli (time, time).
    Zwraca [] jeśli breaks_str jest pusty/None.
    Ignoruje segmenty które nie da się sparsować (odporność na błędne dane).
    """
    if not breaks_str or not breaks_str.strip():
        return []

    result = []
    for segment in breaks_str.split(';'):
        segment = segment.strip()
        if not segment or '-' not in segment:
            continue
        try:
            start_str, end_str = segment.split('-', 1)
            start_t = datetime.strptime(start_str.strip(), '%H:%M').time()
            end_t = datetime.strptime(end_str.strip(), '%H:%M').time()
            result.append((start_t, end_t))
        except ValueError:
            continue
    return result


def format_breaks(breaks_list):
    """
    Formatuje listę tupli (time, time) na string "HH:MM-HH:MM;HH:MM-HH:MM".
    Zwraca None jeśli lista jest pusta.
    """
    if not breaks_list:
        return None
    segments = []
    for start_t, end_t in breaks_list:
        segments.append(f'{start_t.strftime("%H:%M")}-{end_t.strftime("%H:%M")}')
    return ';'.join(segments)


def _to_min(t):
    if t is None:
        return None
    return t.hour * 60 + t.minute


def calculate_hours(time_start, time_end, breaks=None):
    """
    Oblicza godziny pracy na podstawie time_start, time_end i listy przerw.

    breaks: lista tupli (time, time) — wynik parse_breaks().
            Każda przerwa powinna być już znormalizowana względem przejścia
            przez północ przez wywołującego (patrz entries.py walidacja).

    Suma czasu wszystkich przerw - 15 min = nadprogramowa przerwa (jeśli > 0).
    """
    start_min = _to_min(time_start)
    end_min = _to_min(time_end)
    if end_min < start_min:
        end_min += 24 * 60
    raw_minutes = end_min - start_min

    breaks = breaks or []
    total_break_minutes = 0
    for bs, be in breaks:
        bs_min = _to_min(bs)
        be_min = _to_min(be)
        if be_min < bs_min:
            be_min += 24 * 60
        total_break_minutes += max(0, be_min - bs_min)

    extra_break_minutes = max(0, total_break_minutes - BREAK_MINUTES)
    net_minutes = raw_minutes - extra_break_minutes
    hours_worked = net_minutes / 60.0
    hours_billed = round(hours_worked * 4) / 4

    return {
        'raw_minutes': raw_minutes,
        'break_minutes': total_break_minutes,
        'extra_break_minutes': extra_break_minutes,
        'net_minutes': net_minutes,
        'hours_worked': round(hours_worked, 4),
        'hours_billed': hours_billed,
    }


def get_billing_period(entry_date):
    if entry_date.day >= 23:
        if entry_date.month == 12:
            return entry_date.year + 1, 1
        return entry_date.year, entry_date.month + 1
    return entry_date.year, entry_date.month


def calculate_month_summary(entries, hourly_rate, expected_hours, bonus=0):
    """
    Nadgodziny = suma odchyleń każdego dnia pracy od 8h.
    Urlop bezpłatny: 0h, nie odlicza od bilansu urlopów.
    """
    rate = Decimal(str(hourly_rate))
    expected = Decimal(str(expected_hours)) if expected_hours else Decimal('0')

    total_billed = Decimal('0')
    overtime = Decimal('0')
    work_days = 0
    vacation_days = 0
    on_demand_days = 0
    unpaid_days = 0
    holiday_days = 0
    sick_days = 0
    remote_days = 0

    for entry in entries:
        billed = Decimal(str(entry.hours_billed))

        if entry.entry_type == 'unpaid':
            unpaid_days += 1
            work_days += 1
            vacation_days += 1
            continue

        total_billed += billed

        if entry.entry_type == 'work':
            work_days += 1
            overtime += billed - Decimal('8')
            if entry.is_remote:
                remote_days += 1
        elif entry.entry_type == 'vacation':
            vacation_days += 1
            work_days += 1
        elif entry.entry_type == 'on_demand':
            on_demand_days += 1
            vacation_days += 1
            work_days += 1
        elif entry.entry_type == 'holiday':
            holiday_days += 1
            work_days += 1
        elif entry.entry_type == 'sick_leave':
            sick_days += 1
            work_days += 1

    actual_salary = total_billed * rate
    total_with_bonus = actual_salary + Decimal(str(bonus or 0))

    return {
        'total_hours': float(total_billed),
        'expected_hours': float(expected),
        'overtime_hours': float(overtime),
        'actual_salary': float(actual_salary),
        'bonus': float(bonus or 0),
        'total_with_bonus': float(total_with_bonus),
        'work_days': work_days,
        'vacation_days': vacation_days,
        'on_demand_days': on_demand_days,
        'unpaid_days': unpaid_days,
        'holiday_days': holiday_days,
        'sick_days': sick_days,
        'remote_days': remote_days,
    }


def calculate_vacation_used(user_id, year, db_session):
    """
    Urlop na żądanie pomniejsza OBIE pule: on_demand i vacation.
    """
    from wlogio_app.models import WorkEntry
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
        'used_vacation': used_vacation + used_on_demand,
        'used_on_demand': used_on_demand,
        'used_remote': used_remote,
    }


def get_next_vacation_number(user_id, year, db_session):
    """Numer kolejnego dnia urlopowego w roku."""
    from wlogio_app.models import WorkEntry
    from sqlalchemy import extract

    count = db_session.query(WorkEntry).filter(
        WorkEntry.user_id == user_id,
        extract('year', WorkEntry.date) == year,
        WorkEntry.entry_type.in_(['vacation', 'on_demand'])
    ).count()
    return count + 1


def get_next_remote_number(user_id, year, db_session):
    """Numer kolejnego dnia pracy zdalnej w roku."""
    from wlogio_app.models import WorkEntry
    from sqlalchemy import extract

    count = db_session.query(WorkEntry).filter(
        WorkEntry.user_id == user_id,
        extract('year', WorkEntry.date) == year,
        WorkEntry.entry_type == 'work',
        WorkEntry.is_remote == True
    ).count()
    return count + 1


def get_or_create_vacation_balance(user_id, db_session):
    """
    Pobiera lub tworzy bilans urlopowy na bieżący rok.
    Automatycznie przenosi niewykorzystane urlopy z poprzedniego roku.
    """
    from wlogio_app.models import VacationBalance

    current_year = date.today().year
    balance = db_session.query(VacationBalance).filter_by(
        user_id=user_id, year=current_year
    ).first()

    if not balance:
        prev = db_session.query(VacationBalance).filter_by(
            user_id=user_id, year=current_year - 1
        ).first()

        carry_over = 0
        if prev:
            prev_used = calculate_vacation_used(user_id, current_year - 1, db_session)
            prev_remaining = prev.vacation_total - prev_used['used_vacation']
            carry_over = max(0, prev_remaining)

        balance = VacationBalance(
            user_id=user_id,
            year=current_year,
            vacation_total=26 + carry_over,
            on_demand_total=4,
            remote_total=24,
        )
        db_session.add(balance)
        db_session.commit()

    return balance


def format_hours(hours):
    h = int(hours)
    m = round((float(hours) - h) * 60)
    return f'{h}h {m:02d}min'


def format_currency(amount):
    try:
        formatted = f'{float(amount):,.2f}'
        parts = formatted.split('.')
        integer_part = parts[0].replace(',', '\u00a0')
        return f'{integer_part},{parts[1]} zł'
    except Exception:
        return '0,00 zł'

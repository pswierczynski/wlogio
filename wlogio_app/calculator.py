"""
calculator.py - logika obliczeń czasu pracy i wynagrodzenia

Parametry konfiguracji miesiąca (MonthConfig) wpływające na obliczenia:
- billing_start_day / billing_end_day : zakres okresu rozliczeniowego (default 23/22)
- round_minutes     : zaokrąglenie godzin (1, 5, 10, 15, 30 — default 15)
- paid_break_minutes: płatna przerwa odliczana od sumy przerw (default 15)
- overtime_rate     : % stawki godzinowej za nadgodziny (default 100)
- work_days         : CSV dni tygodnia traktowanych jako robocze (default '0,1,2,3,4')
- offday_rate       : % stawki za pracę w dni poza roboczymi (default 100)
- hours_per_day     : norma godzinowa dnia roboczego (default 8)
"""

from datetime import datetime, date, timedelta
from decimal import Decimal

BREAK_MINUTES = 15
ROUND_TO = Decimal('0.25')

DEFAULT_BILLING_START_DAY  = 23
DEFAULT_BILLING_END_DAY    = 22
DEFAULT_ROUND_MINUTES      = 15
DEFAULT_PAID_BREAK_MINUTES = 15
DEFAULT_OVERTIME_RATE      = 100
DEFAULT_WORK_DAYS          = [0, 1, 2, 3, 4]
DEFAULT_OFFDAY_RATE        = 100
DEFAULT_HOURS_PER_DAY      = 8.0


def _round_to_minutes(hours_worked, round_minutes):
    if round_minutes <= 0:
        round_minutes = 15
    factor = 60 / round_minutes
    return round(hours_worked * factor) / factor


def _parse_work_days(work_days_val):
    if isinstance(work_days_val, list):
        return work_days_val
    if not work_days_val:
        return DEFAULT_WORK_DAYS[:]
    try:
        return [int(d.strip()) for d in str(work_days_val).split(',') if d.strip()]
    except ValueError:
        return DEFAULT_WORK_DAYS[:]


def _get_config_value(config, attr, default):
    if config is None:
        return default
    val = getattr(config, attr, None)
    if val is None:
        return default
    return val


def get_billing_period(entry_date, start_day=None):
    if start_day is None:
        start_day = DEFAULT_BILLING_START_DAY
    if entry_date.day >= start_day:
        if entry_date.month == 12:
            return entry_date.year + 1, 1
        return entry_date.year, entry_date.month + 1
    return entry_date.year, entry_date.month


def get_billing_period_dates(billing_year, billing_month, start_day=None, end_day=None):
    if start_day is None:
        start_day = DEFAULT_BILLING_START_DAY
    if end_day is None:
        end_day = DEFAULT_BILLING_END_DAY
    if billing_month == 1:
        prev_month, prev_year = 12, billing_year - 1
    else:
        prev_month, prev_year = billing_month - 1, billing_year
    date_from = date(prev_year, prev_month, start_day)
    date_to   = date(billing_year, billing_month, end_day)
    return date_from, date_to


def get_working_days_in_billing_period(billing_year, billing_month,
                                        start_day=None, end_day=None,
                                        work_days=None):
    if start_day is None:
        start_day = DEFAULT_BILLING_START_DAY
    if end_day is None:
        end_day = DEFAULT_BILLING_END_DAY
    work_days_list = _parse_work_days(work_days) if work_days is not None \
                     else DEFAULT_WORK_DAYS[:]
    date_from, date_to = get_billing_period_dates(
        billing_year, billing_month, start_day, end_day
    )
    working_days = 0
    current = date_from
    while current <= date_to:
        if current.weekday() in work_days_list:
            working_days += 1
        current += timedelta(days=1)
    return working_days


def get_working_days_in_billing_period_from_config(billing_year, billing_month, config=None):
    start_day = _get_config_value(config, 'billing_start_day', DEFAULT_BILLING_START_DAY)
    end_day   = _get_config_value(config, 'billing_end_day',   DEFAULT_BILLING_END_DAY)
    work_days = _get_config_value(config, 'work_days',         None)
    return get_working_days_in_billing_period(
        billing_year, billing_month, start_day, end_day, work_days
    )


def parse_breaks(breaks_str):
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
            end_t   = datetime.strptime(end_str.strip(),   '%H:%M').time()
            result.append((start_t, end_t))
        except ValueError:
            continue
    return result


def format_breaks(breaks_list):
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


def calculate_hours(time_start, time_end, breaks=None,
                    round_minutes=None, paid_break_minutes=None):
    if round_minutes is None:
        round_minutes = DEFAULT_ROUND_MINUTES
    if paid_break_minutes is None:
        paid_break_minutes = DEFAULT_PAID_BREAK_MINUTES

    start_min = _to_min(time_start)
    end_min   = _to_min(time_end)
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

    extra_break_minutes = max(0, total_break_minutes - paid_break_minutes)
    net_minutes  = raw_minutes - extra_break_minutes
    hours_worked = net_minutes / 60.0
    hours_billed = _round_to_minutes(hours_worked, round_minutes)

    return {
        'raw_minutes':         raw_minutes,
        'break_minutes':       total_break_minutes,
        'extra_break_minutes': extra_break_minutes,
        'net_minutes':         net_minutes,
        'hours_worked':        round(hours_worked, 4),
        'hours_billed':        hours_billed,
    }


def calculate_month_summary(entries, hourly_rate, expected_hours, bonus=0,
                             hours_per_day=None, overtime_rate=None,
                             work_days=None, offday_rate=None):
    if hours_per_day is None:
        hours_per_day = DEFAULT_HOURS_PER_DAY
    if overtime_rate is None:
        overtime_rate = DEFAULT_OVERTIME_RATE
    if offday_rate is None:
        offday_rate = DEFAULT_OFFDAY_RATE

    work_days_list = _parse_work_days(work_days) if work_days is not None \
                     else DEFAULT_WORK_DAYS[:]

    rate     = Decimal(str(hourly_rate))
    expected = Decimal(str(expected_hours)) if expected_hours else Decimal('0')
    hpd      = Decimal(str(hours_per_day))
    ot_rate  = Decimal(str(overtime_rate)) / Decimal('100')
    od_rate  = Decimal(str(offday_rate))   / Decimal('100')

    total_billed    = Decimal('0')
    overtime        = Decimal('0')
    actual_salary   = Decimal('0')
    work_days_count = 0
    vacation_days   = 0
    on_demand_days  = 0
    unpaid_days     = 0
    holiday_days    = 0
    sick_days       = 0
    remote_days     = 0

    for entry in entries:
        billed = Decimal(str(entry.hours_billed))

        if entry.entry_type == 'unpaid':
            unpaid_days     += 1
            work_days_count += 1
            vacation_days   += 1
            continue

        total_billed += billed

        if entry.entry_type == 'work':
            work_days_count += 1
            is_offday = entry.date.weekday() not in work_days_list
            if is_offday:
                actual_salary += billed * rate * od_rate
            else:
                normal_h   = min(billed, hpd)
                overtime_h = max(Decimal('0'), billed - hpd)
                overtime  += (billed - hpd)
                actual_salary += normal_h * rate + overtime_h * rate * ot_rate
            if entry.is_remote:
                remote_days += 1
        elif entry.entry_type == 'vacation':
            vacation_days   += 1
            work_days_count += 1
            actual_salary   += billed * rate
        elif entry.entry_type == 'on_demand':
            on_demand_days  += 1
            vacation_days   += 1
            work_days_count += 1
            actual_salary   += billed * rate
        elif entry.entry_type == 'holiday':
            holiday_days    += 1
            work_days_count += 1
            actual_salary   += billed * rate
        elif entry.entry_type == 'sick_leave':
            sick_days       += 1
            work_days_count += 1
            actual_salary   += billed * rate

    total_with_bonus = actual_salary + Decimal(str(bonus or 0))

    return {
        'total_hours':      float(total_billed),
        'expected_hours':   float(expected),
        'overtime_hours':   float(overtime),
        'actual_salary':    float(actual_salary),
        'bonus':            float(bonus or 0),
        'total_with_bonus': float(total_with_bonus),
        'work_days':        work_days_count,
        'vacation_days':    vacation_days,
        'on_demand_days':   on_demand_days,
        'unpaid_days':      unpaid_days,
        'holiday_days':     holiday_days,
        'sick_days':        sick_days,
        'remote_days':      remote_days,
    }


def calculate_vacation_used(user_id, year, db_session):
    from wlogio_app.models import WorkEntry
    from sqlalchemy import extract

    entries = db_session.query(WorkEntry).filter(
        WorkEntry.user_id == user_id,
        extract('year', WorkEntry.date) == year,
        WorkEntry.entry_type.in_(['vacation', 'on_demand', 'work'])
    ).all()

    used_vacation  = sum(1 for e in entries if e.entry_type == 'vacation')
    used_on_demand = sum(1 for e in entries if e.entry_type == 'on_demand')
    used_remote    = sum(1 for e in entries if e.entry_type == 'work' and e.is_remote)

    return {
        'used_vacation':  used_vacation + used_on_demand,
        'used_on_demand': used_on_demand,
        'used_remote':    used_remote,
    }


def get_next_vacation_number(user_id, year, db_session):
    from wlogio_app.models import WorkEntry
    from sqlalchemy import extract

    count = db_session.query(WorkEntry).filter(
        WorkEntry.user_id == user_id,
        extract('year', WorkEntry.date) == year,
        WorkEntry.entry_type.in_(['vacation', 'on_demand'])
    ).count()
    return count + 1


def get_next_remote_number(user_id, year, db_session):
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
            prev_used      = calculate_vacation_used(user_id, current_year - 1, db_session)
            prev_remaining = prev.vacation_total - prev_used['used_vacation']
            carry_over     = max(0, prev_remaining)

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

"""
importer.py
===========
Parser i importer danych z pliku wlogio.txt do bazy danych.

Format wejściowy opisany w examples.md:
  - Dzień pracy:     01) 24.03: 09:50 - 17:50 (14:12-14:22) / 08h 00min - (15)+00min przerwy = 08h 00min = 8
  - Brak przerwy:    01) 24.03: 09:50 - 17:50 (xx:xx-xx:xx) / ...
  - Urlop:           01) 23.03: urlop (4) = 8
  - Urlop na żądanie:01) 30.09: urlop na żądanie (19) = 8
  - Święto:          01) 06.04: święto (8)
  - Zwolnienie:      01) 30.01: zwolnienie lekarskie (8)

Uruchomienie:
    python importer.py --file wlogio.txt --email user@example.com
"""

import re
import sys
import argparse
from datetime import datetime, date
from decimal import Decimal

# Mapowanie nazw miesięcy na numery (dla nagłówków sekcji)
MONTH_NAMES_PL = {
    'STYCZEŃ': 1, 'LUTY': 2, 'MARZEC': 3, 'KWIECIEŃ': 4,
    'MAJ': 5, 'CZERWIEC': 6, 'LIPIEC': 7, 'SIERPIEŃ': 8,
    'WRZESIEŃ': 9, 'PAŹDZIERNIK': 10, 'LISTOPAD': 11, 'GRUDZIEŃ': 12,
}

# Regex dla różnych typów wpisów
RE_HEADER = re.compile(
    r'^([A-ZĄĆĘŁŃÓŚŹŻ]+)_(\d{4})$'
)

RE_WORK = re.compile(
    r'^\d+\)\s+(\d{2}\.\d{2}):\s+'          # numer i data
    r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s+' # godzina start - end
    r'\((\d{2}:\d{2}|\d{2}:\d{2})-(\d{2}:\d{2}|\d{2}:\d{2}|xx:xx)\)'  # przerwa
    r'.*?=\s*([\d,\.]+)$'                    # wynik końcowy
)

RE_WORK_NO_BREAK = re.compile(
    r'^\d+\)\s+(\d{2}\.\d{2}):\s+'
    r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s+'
    r'\(xx:xx-xx:xx\)'
    r'.*?=\s*([\d,\.]+)$'
)

RE_VACATION = re.compile(
    r'^\d+\)\s+(\d{2}\.\d{2}):\s+urlop\s+\((\d+)\)\s*=\s*8'
)

RE_ON_DEMAND = re.compile(
    r'^\d+\)\s+(\d{2}\.\d{2}):\s+urlop na żądanie\s+\((\d+)\)\s*=\s*8'
)

RE_HOLIDAY = re.compile(
    r'^\d+\)\s+(\d{2}\.\d{2}):\s+święto'
)

RE_SICK = re.compile(
    r'^\d+\)\s+(\d{2}\.\d{2}):\s+zwolnienie lekarskie'
)

RE_REMOTE = re.compile(
    r'\(PZ-KRK\)\s*\((\d+)\)'
)

RE_SUMMARY_IS = re.compile(
    r'^Jest:\s+([\d,\.]+)\s+\([+-][\d,\.]+\)'
)

RE_SUMMARY_SHOULD = re.compile(
    r'^Powinno być:\s+([\d]+)\s*=\s*([\d\s,\.]+)\s*zł'
)

RE_BONUS = re.compile(
    r'Jest:.*?=\s*[\d\s,\.]+\s*\+\s*([\d\s,\.]+)\s*='
)


def parse_date(day_month_str, year):
    """Parsuje datę w formacie DD.MM dla danego roku."""
    try:
        day, month = map(int, day_month_str.split('.'))
        return date(year, month, day)
    except Exception:
        return None


def get_billing_period(entry_date):
    """Oblicza okres rozliczeniowy (23→22)."""
    if entry_date.day >= 23:
        if entry_date.month == 12:
            return entry_date.year + 1, 1
        return entry_date.year, entry_date.month + 1
    return entry_date.year, entry_date.month


def parse_hours(val_str):
    """Parsuje string godzin: '8,25' lub '8.25' → Decimal."""
    return Decimal(val_str.replace(',', '.').strip())


def parse_time(time_str):
    """Parsuje czas 'HH:MM' → datetime.time lub None."""
    if not time_str or 'xx' in time_str:
        return None
    try:
        return datetime.strptime(time_str.strip(), '%H:%M').time()
    except ValueError:
        return None


def parse_wlogio(filepath):
    """
    Parsuje plik wlogio.txt i zwraca listę słowników z danymi wpisów.

    Zwraca:
        entries  - lista wpisów
        summaries - słownik {(year, month): {expected_hours, expected_salary, bonus}}
    """
    entries = []
    summaries = {}

    current_section_year = None
    current_section_month = None

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line:
            continue

        # --- Nagłówek sekcji np. MAJ_2026 ---
        m = RE_HEADER.match(line)
        if m:
            month_name = m.group(1)
            year = int(m.group(2))
            month_num = MONTH_NAMES_PL.get(month_name)
            if month_num:
                current_section_year = year
                current_section_month = month_num
            continue

        # --- Podsumowanie "Powinno być" ---
        m = RE_SUMMARY_SHOULD.match(line)
        if m and current_section_year and current_section_month:
            expected_h = int(m.group(1))
            salary_str = m.group(2).replace(' ', '').replace(',', '.')
            try:
                expected_salary = float(salary_str)
            except ValueError:
                expected_salary = 0

            key = (current_section_year, current_section_month)
            if key not in summaries:
                summaries[key] = {}
            summaries[key]['expected_hours'] = expected_h
            summaries[key]['expected_salary'] = expected_salary
            continue

        # --- Podsumowanie "Jest" (szukaj premii) ---
        m = RE_SUMMARY_IS.match(line)
        if m and current_section_year and current_section_month:
            key = (current_section_year, current_section_month)
            if key not in summaries:
                summaries[key] = {}
            # Szukaj premii w tym samym wierszu (np. "= 7308,25 + 2186,91 = ...")
            bonus_match = re.search(r'=\s*[\d\s,\.]+\s*\+\s*([\d\s,\.]+)\s*=', line)
            if bonus_match:
                bonus_str = bonus_match.group(1).replace(' ', '').replace(',', '.')
                try:
                    summaries[key]['bonus'] = float(bonus_str)
                except ValueError:
                    pass
            continue

        # Pomiń linie które nie są wpisami dni
        if not re.match(r'^\d+\)', line):
            continue

        if current_section_year is None:
            continue

        # Pomiń puste wpisy (np. "11) 07.05:" bez danych)
        # Wpis jest pusty jeśli po dacie nie ma żadnych danych
        if re.match(r'^\d+\)\s+\d{2}\.\d{2}:\s*$', line):
            continue

        year = current_section_year

        # --- Urlop na żądanie (sprawdź przed zwykłym urlopem) ---
        m = RE_ON_DEMAND.match(line)
        if m:
            d = parse_date(m.group(1), year)
            if d:
                billing_year, billing_month = get_billing_period(d)
                entries.append({
                    'date': d,
                    'billing_year': billing_year,
                    'billing_month': billing_month,
                    'entry_type': 'on_demand',
                    'vacation_day_number': int(m.group(2)),
                    'hours_worked': Decimal('8'),
                    'hours_billed': Decimal('8'),
                    'is_remote': False,
                })
            continue

        # --- Urlop zwykły ---
        m = RE_VACATION.match(line)
        if m:
            d = parse_date(m.group(1), year)
            if d:
                billing_year, billing_month = get_billing_period(d)
                entries.append({
                    'date': d,
                    'billing_year': billing_year,
                    'billing_month': billing_month,
                    'entry_type': 'vacation',
                    'vacation_day_number': int(m.group(2)),
                    'hours_worked': Decimal('8'),
                    'hours_billed': Decimal('8'),
                    'is_remote': False,
                })
            continue

        # --- Święto ---
        m = RE_HOLIDAY.match(line)
        if m:
            d = parse_date(m.group(1), year)
            if d:
                billing_year, billing_month = get_billing_period(d)
                entries.append({
                    'date': d,
                    'billing_year': billing_year,
                    'billing_month': billing_month,
                    'entry_type': 'holiday',
                    'hours_worked': Decimal('8'),
                    'hours_billed': Decimal('8'),
                    'is_remote': False,
                })
            continue

        # --- Zwolnienie lekarskie ---
        m = RE_SICK.match(line)
        if m:
            d = parse_date(m.group(1), year)
            if d:
                billing_year, billing_month = get_billing_period(d)
                entries.append({
                    'date': d,
                    'billing_year': billing_year,
                    'billing_month': billing_month,
                    'entry_type': 'sick_leave',
                    'hours_worked': Decimal('8'),
                    'hours_billed': Decimal('8'),
                    'is_remote': False,
                })
            continue

        # --- Dzień pracy (bez przerwy) ---
        m = RE_WORK_NO_BREAK.match(line)
        if m:
            d = parse_date(m.group(1), year)
            if d:
                billing_year, billing_month = get_billing_period(d)
                is_remote = bool(RE_REMOTE.search(line))
                remote_trip = None
                rt = RE_REMOTE.search(line)
                if rt:
                    remote_trip = int(rt.group(1))

                hours_billed = parse_hours(m.group(4))
                entry = {
                    'date': d,
                    'billing_year': billing_year,
                    'billing_month': billing_month,
                    'entry_type': 'work',
                    'time_start': parse_time(m.group(2)),
                    'time_end': parse_time(m.group(3)),
                    'break_start': None,
                    'break_end': None,
                    'extra_break_minutes': 0,
                    'hours_worked': hours_billed,
                    'hours_billed': hours_billed,
                    'is_remote': is_remote,
                    'remote_trip_number': remote_trip,
                }
                entries.append(entry)
            continue

        # --- Dzień pracy (z przerwą) ---
        m = RE_WORK.match(line)
        if m:
            d = parse_date(m.group(1), year)
            if d:
                billing_year, billing_month = get_billing_period(d)
                is_remote = bool(RE_REMOTE.search(line))
                remote_trip = None
                rt = RE_REMOTE.search(line)
                if rt:
                    remote_trip = int(rt.group(1))

                # Wyciągnij godziny przerwy
                break_start = parse_time(m.group(4))
                break_end_str = m.group(5)
                break_end = parse_time(break_end_str)

                hours_billed = parse_hours(m.group(6))
                entry = {
                    'date': d,
                    'billing_year': billing_year,
                    'billing_month': billing_month,
                    'entry_type': 'work',
                    'time_start': parse_time(m.group(2)),
                    'time_end': parse_time(m.group(3)),
                    'break_start': break_start,
                    'break_end': break_end,
                    'extra_break_minutes': 0,
                    'hours_worked': hours_billed,
                    'hours_billed': hours_billed,
                    'is_remote': is_remote,
                    'remote_trip_number': remote_trip,
                }
                entries.append(entry)
            continue

    return entries, summaries


def clear_user_data(user_email):
    """Czyści wszystkie wpisy i konfiguracje dla użytkownika przed re-importem."""
    from app import create_app, db
    from app.models import User, WorkEntry, MonthConfig, VacationBalance

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=user_email).first()
        if not user:
            print(f'[BŁĄD] Użytkownik {user_email} nie istnieje.')
            return False

        deleted_entries = WorkEntry.query.filter_by(user_id=user.id).delete()
        deleted_configs = MonthConfig.query.filter_by(user_id=user.id).delete()
        deleted_balances = VacationBalance.query.filter_by(user_id=user.id).delete()
        db.session.commit()

        print(f'[INFO] Usunięto: {deleted_entries} wpisów, '
              f'{deleted_configs} konfiguracji, '
              f'{deleted_balances} bilansów urlopowych.')
        return True


def import_to_db(filepath, user_email):
    """
    Główna funkcja importu — parsuje plik i zapisuje do bazy.
    """
    from app import create_app, db
    from app.models import User, WorkEntry, MonthConfig

    app = create_app()

    with app.app_context():
        user = User.query.filter_by(email=user_email).first()
        if not user:
            print(f'[BŁĄD] Użytkownik {user_email} nie istnieje w bazie.')
            sys.exit(1)

        print(f'[INFO] Importuję dane dla: {user.email}')
        entries, summaries = parse_wlogio(filepath)
        print(f'[INFO] Znaleziono {len(entries)} wpisów.')

        imported = 0
        skipped = 0

        for data in entries:
            # Sprawdź czy wpis już istnieje
            existing = WorkEntry.query.filter_by(
                user_id=user.id,
                date=data['date']
            ).first()

            if existing:
                skipped += 1
                continue

            entry = WorkEntry(
                user_id=user.id,
                date=data['date'],
                billing_year=data['billing_year'],
                billing_month=data['billing_month'],
                entry_type=data['entry_type'],
                time_start=data.get('time_start'),
                time_end=data.get('time_end'),
                break_start=data.get('break_start'),
                break_end=data.get('break_end'),
                extra_break_minutes=data.get('extra_break_minutes', 0),
                hours_worked=data['hours_worked'],
                hours_billed=data['hours_billed'],
                vacation_day_number=data.get('vacation_day_number'),
                is_remote=data.get('is_remote', False),
                remote_trip_number=data.get('remote_trip_number'),
            )
            db.session.add(entry)
            imported += 1

        db.session.commit()
        print(f'[INFO] Zaimportowano: {imported}, pominięto (duplikaty): {skipped}')

        # Importuj konfiguracje miesięcy z podsumowań
        print(f'[INFO] Importuję konfiguracje {len(summaries)} miesięcy...')

        # Importuj też miesiące które mają wpisy ale nie mają podsumowań
        all_billing_periods = set()
        for data in entries:
            all_billing_periods.add((data['billing_year'], data['billing_month']))

        for year, month in all_billing_periods:
            if (year, month) not in summaries:
                summaries[(year, month)] = {}

        for (year, month), summary_data in summaries.items():
            config = MonthConfig.query.filter_by(
                user_id=user.id,
                billing_year=year,
                billing_month=month
            ).first()

            if not config:
                prev_m = month - 1
                prev_y = year
                if prev_m == 0:
                    prev_m = 12
                    prev_y -= 1

                prev_config = MonthConfig.query.filter_by(
                    user_id=user.id,
                    billing_year=prev_y,
                    billing_month=prev_m
                ).first()

                # Oblicz stawkę z podsumowania
                rate = Decimal('0')
                if 'expected_hours' in summary_data and 'expected_salary' in summary_data:
                    eh = summary_data['expected_hours']
                    es = summary_data['expected_salary']
                    if eh > 0:
                        rate = Decimal(str(round(es / eh, 2)))

                if rate == 0 and prev_config:
                    rate = prev_config.hourly_rate

                # Expected hours zawsze z kalendarza
                from app.calculator import get_working_days_in_billing_period
                working_days = get_working_days_in_billing_period(year, month)
                expected_h = working_days * 8

                config = MonthConfig(
                    user_id=user.id,
                    billing_year=year,
                    billing_month=month,
                    hourly_rate=rate,
                    expected_hours=Decimal(str(expected_h)),
                    bonus=Decimal(str(summary_data.get('bonus', 0))),
                )
                db.session.add(config)

        db.session.commit()
        print('[INFO] Import zakończony pomyślnie.')


def create_default_user():
    """
    Tworzy domyślnego użytkownika z pliku core.md:
    przemyslaw.swierczynski@apaka.com.pl / Przemek121!
    """
    from app import create_app, db
    from app.models import User

    app = create_app()
    with app.app_context():
        email = 'przemyslaw.swierczynski@apaka.com.pl'
        existing = User.query.filter_by(email=email).first()
        if existing:
            print(f'[INFO] Użytkownik {email} już istnieje.')
            return

        user = User(
            email=email,
            name='Przemysław Świerczyński',
        )
        user.set_password('Przemek121!')
        db.session.add(user)
        db.session.commit()
        print(f'[INFO] Utworzono użytkownika: {email}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Importer danych wlogio.txt')
    parser.add_argument('--file', default='wlogio.txt', help='Ścieżka do pliku wlogio.txt')
    parser.add_argument('--email', default='przemyslaw.swierczynski@apaka.com.pl',
                        help='Email użytkownika w bazie')
    parser.add_argument('--create-user', action='store_true',
                        help='Utwórz domyślnego użytkownika przed importem')
    parser.add_argument('--clear-first', action='store_true',
                        help='Usuń istniejące dane użytkownika przed importem')
    args = parser.parse_args()

    if args.create_user:
        create_default_user()

    if args.clear_first:
        clear_user_data(args.email)

    import_to_db(args.file, args.email)

"""
reimport.py
===========
Jednorazowy skrypt do wyczyszczenia i reimportu danych z wlogio.txt.
Uruchom: python3 reimport.py

Usuwa WSZYSTKIE wpisy, konfiguracje i bilanse użytkownika,
następnie importuje dane z wlogio.txt od nowa.
"""

import sys
import os

# Upewnij się że jesteśmy w katalogu projektu
os.chdir(os.path.dirname(os.path.abspath(__file__)))

EMAIL = 'przemyslaw.swierczynski@apaka.com.pl'
WLOGIO_FILE = 'wlogio.txt'


def main():
    from app import create_app, db
    from app.models import User, WorkEntry, MonthConfig, VacationBalance, HourlyRate
    from app.calculator import get_working_days_in_billing_period
    from importer import parse_wlogio
    from decimal import Decimal

    app = create_app()

    with app.app_context():

        # --- Krok 1: Znajdź użytkownika ---
        user = User.query.filter_by(email=EMAIL).first()
        if not user:
            print(f'[BŁĄD] Użytkownik {EMAIL} nie istnieje. Uruchom najpierw:')
            print('  python3 importer.py --create-user')
            sys.exit(1)

        print(f'[INFO] Użytkownik: {user.email} (id={user.id})')

        # --- Krok 2: Wyczyść dane ---
        we = WorkEntry.query.filter_by(user_id=user.id).delete()
        mc = MonthConfig.query.filter_by(user_id=user.id).delete()
        vb = VacationBalance.query.filter_by(user_id=user.id).delete()
        hr = HourlyRate.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        print(f'[INFO] Usunięto: {we} wpisów, {mc} konfiguracji miesięcy, '
              f'{vb} bilansów, {hr} stawek')

        # --- Krok 3: Parsuj plik ---
        if not os.path.exists(WLOGIO_FILE):
            print(f'[BŁĄD] Nie znaleziono pliku {WLOGIO_FILE}')
            sys.exit(1)

        entries, summaries = parse_wlogio(WLOGIO_FILE)

        # Filtruj puste wpisy (bez godzin / bez sensu)
        valid_entries = []
        skipped = 0
        for e in entries:
            # Pomiń wpisy z datą która generuje billing_year > aktualny rok + 1
            import datetime
            if e['billing_year'] > datetime.date.today().year + 1:
                print(f'[WARN] Pomijam wpis z nieprawidłowym rokiem: '
                      f'{e["date"]} → billing {e["billing_year"]}-{e["billing_month"]}')
                skipped += 1
                continue
            valid_entries.append(e)

        print(f'[INFO] Znaleziono {len(valid_entries)} wpisów '
              f'(pominięto {skipped} nieprawidłowych)')

        # --- Krok 4: Importuj wpisy ---
        imported = 0
        duplicates = 0
        for data in valid_entries:
            existing = WorkEntry.query.filter_by(
                user_id=user.id,
                date=data['date']
            ).first()
            if existing:
                duplicates += 1
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

        db.session.flush()
        print(f'[INFO] Zaimportowano: {imported} wpisów, duplikaty: {duplicates}')

        # --- Krok 5: Zbierz wszystkie okresy z wpisów ---
        all_periods = set()
        for data in valid_entries:
            all_periods.add((data['billing_year'], data['billing_month']))

        # Dodaj okresy z podsumowań
        for (y, m) in summaries:
            all_periods.add((y, m))

        print(f'[INFO] Tworzę konfiguracje dla {len(all_periods)} okresów...')

        # Posortuj chronologicznie żeby stawka dziedziczyła poprawnie
        sorted_periods = sorted(all_periods)

        prev_rate = Decimal('0')

        for (year, month) in sorted_periods:
            summary_data = summaries.get((year, month), {})

            # Oblicz stawkę z podsumowania "Powinno być"
            rate = Decimal('0')
            if 'expected_hours' in summary_data and 'expected_salary' in summary_data:
                eh = summary_data['expected_hours']
                es = summary_data['expected_salary']
                if eh > 0:
                    computed = round(es / eh, 2)
                    rate = Decimal(str(computed))

            # Jeśli nie udało się wyliczyć — dziedzicz poprzednią
            if rate == 0 and prev_rate > 0:
                rate = prev_rate

            prev_rate = rate if rate > 0 else prev_rate

            # Expected hours z kalendarza (dni robocze pon-pt, 23→22)
            working_days = get_working_days_in_billing_period(year, month)
            expected_hours = working_days * 8

            bonus = Decimal(str(summary_data.get('bonus', 0)))

            config = MonthConfig(
                user_id=user.id,
                billing_year=year,
                billing_month=month,
                hourly_rate=rate,
                expected_hours=Decimal(str(expected_hours)),
                bonus=bonus,
            )
            db.session.add(config)

        # --- Krok 6: Bilans urlopowy z nagłówka pliku ---
        # Dane z wlogio.txt: "Dni urlopowych zostało: 18 (wykorzystane 8 z 26)"
        import datetime
        current_year = datetime.date.today().year

        balance_2026 = VacationBalance(
            user_id=user.id,
            year=2026,
            vacation_total=26,
            on_demand_total=4,
            remote_total=24,
        )
        db.session.add(balance_2026)

        db.session.commit()
        print('[INFO] Import zakończony pomyślnie.')
        print()
        print('Podsumowanie:')
        print(f'  Wpisy:              {imported}')
        print(f'  Okresy rozlicz.:    {len(sorted_periods)}')
        print(f'  Bilans urlopowy:    2026 (26 dni / 4 na żądanie / 24 zdalna)')


if __name__ == '__main__':
    main()

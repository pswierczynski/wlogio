# Wlogio — Dokumentacja projektu (stan na 15.05.2026, etap multi-break zakończony)

## Stack technologiczny

* **Backend:** Python 3.11+ / Flask
* **Baza danych:** PostgreSQL na Supabase (darmowy tier, połączenie przez Transaction Pooler port 6543)
* **ORM:** SQLAlchemy + Flask-SQLAlchemy
* **Hosting:** Render.com (darmowy tier, Python 3.14, gunicorn)
* **Frontend:** Tailwind CSS + DaisyUI + Alpine.js
* **Storage avatarów:** Supabase Storage (bucket: `avatars`, publiczny)
* **Autoryzacja:** Flask-Login, hasła hashowane przez pbkdf2:sha256
* **Repozytorium:** https://github.com/pswierczynski/wlogio
* **Aplikacja:** https://wlogio.onrender.com

## Modele bazy danych

### User
- `id`, `email` (unique), `password_hash`, `name`, `is_active`
- `pin` (VARCHAR 4) — 4-cyfrowy PIN do ekranu powitalnego
- `avatar` (TEXT) — publiczny URL do Supabase Storage

### WorkEntry
- `id`, `user_id`, `date`, `billing_year`, `billing_month`, `entry_type`
- `time_start`, `time_end` — godziny pracy
- `breaks` (TEXT) — **wiele przerw** w formacie `"HH:MM-HH:MM;HH:MM-HH:MM;HH:MM-HH:MM"`
- `extra_break_minutes`, `hours_worked`, `hours_billed`
- `vacation_day_number`, `is_remote`, `remote_trip_number`, `notes`

**WAŻNE:** Kolumny `break_start` i `break_end` zostały usunięte (etap cleanup). Cała logika przerw przechodzi przez kolumnę `breaks` i funkcje `parse_breaks()` / `format_breaks()` w `calculator.py`.

### MonthConfig
- `user_id`, `billing_year`, `billing_month`
- `hourly_rate`, `expected_hours` (z kalendarza), `bonus`, `notes`

### VacationBalance
- `user_id`, `year`, `vacation_total` (26), `on_demand_total` (4), `remote_total` (24)

## Logika wielu przerw (calculator.py)

### Format przechowywania
`breaks` to string: `"15:10-15:20;16:30-16:45;17:50-17:55"` — segmenty oddzielone `;`, każdy segment to `HH:MM-HH:MM`.

### Funkcje
- `parse_breaks(breaks_str)` → lista tupli `(time, time)`. Ignoruje błędne segmenty.
- `format_breaks(breaks_list)` → string z listy tupli, lub `None` jeśli lista pusta.
- `calculate_hours(time_start, time_end, breaks)` → suma czasu wszystkich przerw, odlicza 15 min programowych, liczy nadprogramową przerwę i godziny.

### Walidacja (backend `entries.py` + frontend `form.html`)
- Każda przerwa musi mieścić się w przedziale `time_start..time_end`
- Przerwy NIE mogą się nakładać (sprawdzane po sortowaniu chronologicznym)
- Obsługa przejścia przez północ: jeśli `break_start < time_start` w wartości minut, przerwa jest traktowana jako następny dzień (+24h)
- Niekompletny wiersz przerwy (tylko start albo tylko end) blokuje zapis z komunikatem błędu

### Formularz dodawania/edycji dnia (`entries/form.html`)
- Dynamiczna lista wierszy przerw zarządzana przez Alpine.js (`breakRows`)
- Przyciski "Dodaj przerwę" / usuń wiersz (ikona kosza)
- Pola formularza: `break_start_0`, `break_end_0`, `break_start_1`, `break_end_1`, ... (indeksowane sekwencyjnie)
- Backend (`_fill_work_entry` w `entries.py`) czyta pola po indeksie aż nie znajdzie kolejnego

### Ekran powitalny (`welcome.py` + `welcome/index.html`)
- Przerwy zapisywane jako otwarte segmenty: `"13:00-"` (bez końca) podczas trwania przerwy
- Kliknięcie "Przerwa" dodaje nowy segment do `breaks` (o ile poprzedni jest zamknięty)
- Kliknięcie "Koniec przerwy" domyka ostatni otwarty segment
- Przycisk "Przerwa" jest aktywny zawsze gdy status = `working` — można rozpoczynać wiele przerw w ciągu dnia
- **Frontend wyświetla tylko OSTATNIĄ przerwę** pod przyciskami (`get_last_break()` w `welcome.py`), plus opcjonalny licznik `(przerw dzisiaj: N)` gdy więcej niż 1
- `auto_close_stale_entries()` (po 24h bez `time_end`) domyka też ostatnią otwartą przerwę

### Dashboard (`dashboard/index.html`)
- Kolumna "Przerwy" (zmieniona z "Przerwa") wyświetla każdy segment `breaks` w osobnej linii
- `entry.breaks.split(';')` w Jinja2, myślnik zamieniony na en-dash (`–`) dla lepszej czytelności

## Logika biznesowa (bez zmian)

### Okres rozliczeniowy
- Miesiąc liczony od **23 dnia poprzedniego** do **22 dnia bieżącego**

### Typy wpisów (entry_type)
- `work`, `vacation`, `on_demand`, `unpaid`, `holiday`, `sick_leave`

### Obliczanie godzin
- Przerwa programowa: 15 min (suma wszystkich przerw - 15 min = nadprogramowa, jeśli > 0)
- Zaokrąglenie: `round(hours * 4) / 4`
- Obsługa pracy przez północ: `end_min < start_min → end_min += 24*60`

### Nadgodziny, bilans urlopowy, renumeracja urlopów — bez zmian względem poprzedniej wersji.

## Ekran powitalny (/welcome/) — status

Status (`compute_status()` w `welcome.py`):
- `'working'` — `time_start` ustawiony ORAZ (brak `time_end` LUB `now < time_end`) ORAZ nie jesteśmy w ostatniej przerwie
- `'break'` — warunek working spełniony ORAZ ostatnia przerwa ma `start` ORAZ (brak `end` LUB `now < end`)
- `'idle'` — wszystkie pozostałe przypadki

Status sprawdza wyłącznie OSTATNI segment przerwy z `breaks` — wcześniejsze (zamknięte) przerwy nie wpływają na status.

## Migracje SQL — historia (Supabase)

```sql
-- Dodanie PIN i avatara do users
ALTER TABLE users ADD COLUMN IF NOT EXISTS pin VARCHAR(4);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT;

-- Usunięcie duplikatów kolumn zegarowych (clock_* vs time_*)
ALTER TABLE work_entries DROP COLUMN IF EXISTS clock_in;
ALTER TABLE work_entries DROP COLUMN IF EXISTS clock_out;
ALTER TABLE work_entries DROP COLUMN IF EXISTS break_clock_start;
ALTER TABLE work_entries DROP COLUMN IF EXISTS break_clock_end;

-- Usunięcie nieużywanej tabeli historii stawek
DROP TABLE IF EXISTS hourly_rates;

-- Dodanie kolumny breaks (wiele przerw) + migracja istniejących danych
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS breaks TEXT;
UPDATE work_entries
SET breaks = CONCAT(TO_CHAR(break_start, 'HH24:MI'), '-', TO_CHAR(break_end, 'HH24:MI'))
WHERE break_start IS NOT NULL AND break_end IS NOT NULL AND breaks IS NULL;

-- Cleanup: usunięcie przejściowych kolumn break_start/break_end
ALTER TABLE work_entries DROP COLUMN IF EXISTS break_start;
ALTER TABLE work_entries DROP COLUMN IF EXISTS break_end;
```

## Znane rozwiązania technicznie ważne

1. **psycopg3** zamiast psycopg2 — Render używa Python 3.14.
2. **config.py** — automatycznie zamienia `postgres://`/`postgresql://` na `postgresql+psycopg://`.
3. **Hashowanie haseł** — `pbkdf2:sha256` (nie scrypt).
4. **Strefa czasowa** — `datetime.now(ZoneInfo('Europe/Warsaw'))`.
5. **Supabase pooler** — Transaction Pooler (port 6543).
6. **Zaokrąglenie godzin** — `round(hours * 4) / 4`.
7. **Folder wlogio_app** — NIE `app/`.
8. **Alpine.js i onclick** — nigdy `onclick="func('{{ var }}')"` z Jinja2 — użyj `data-*` + JS listenery.
9. **Status bez godziny zakończenia** — brak `time_end` = working do odwołania; brak końca ostatniej przerwy = break do odwołania.
10. **Template literals w atrybutach HTML** — unikać backtick + `${}` wewnątrz `x-data="..."` — ryzyko błędu renderowania w niektórych przeglądarkach/parserach. Używać konkatenacji stringów `'a' + b + 'c'`.

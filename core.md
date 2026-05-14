# Wlogio — Dokumentacja projektu (stan na 14.05.2026)

## Stack technologiczny

* **Backend:** Python 3.11+ / Flask
* **Baza danych:** PostgreSQL na Supabase (darmowy tier, połączenie przez Transaction Pooler port 6543)
* **ORM:** SQLAlchemy + Flask-SQLAlchemy
* **Hosting:** Render.com (darmowy tier, Python 3.14, gunicorn)
* **Frontend:** Tailwind CSS + DaisyUI + Alpine.js
* **Storage avatarów:** Supabase Storage (bucket: `avatars`, publiczny)
* **Autoryzacja:** Flask-Login, hasła hashowane przez pbkdf2:sha256 (nie scrypt - niekompatybilny z Python 3.9 na macOS)
* **Repozytorium:** https://github.com/pswierczynski/wlogio
* **Aplikacja:** https://wlogio.onrender.com

## Struktura projektu

```
wlogio/
├── run.py                          # punkt startowy, sys.path.insert dla Render
├── config.py                       # konfiguracja z .env, postgres:// → postgresql+psycopg://
├── requirements.txt                # psycopg[binary]==3.2.10 (nie psycopg2 - Python 3.14)
├── render.yaml
├── reimport_xlsx.py                # importer danych z pliku xlsx
├── wlogio_app/                     # główny moduł (NIE app/ - konflikt z paczką na Render)
│   ├── __init__.py                 # create_app(), explicite template_folder i static_folder
│   ├── models.py
│   ├── calculator.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── entries.py
│   │   ├── settings.py
│   │   └── welcome.py
│   └── templates/
│       ├── base.html
│       ├── auth/
│       ├── dashboard/
│       ├── entries/
│       ├── settings/
│       └── welcome/
```

**Ważne:** Folder główny nazywa się `wlogio_app/` (nie `app/`) — Render ma zainstalowaną paczkę o nazwie `app` która koliduje z lokalnym folderem. `run.py` używa `sys.path.insert(0, ...)`.

## Zmienne środowiskowe

```env
SECRET_KEY=...                      # losowy string min 32 znaki
DATABASE_URL=postgresql://postgres.[ref]:[HASLO]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
FLASK_ENV=production
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_SERVICE_KEY=...            # service_role key z Supabase → Project Settings → API
```

Upload avatarów przez REST API (`requests` biblioteka), nie przez supabase-py SDK.

## Modele bazy danych

### User
- `id`, `email` (unique), `password_hash`, `name`, `is_active`
- `pin` (VARCHAR 4) — 4-cyfrowy PIN do ekranu powitalnego, generowany losowo przy rejestracji
- `avatar` (TEXT) — publiczny URL do Supabase Storage

### WorkEntry
- `id`, `user_id`, `date`, `billing_year`, `billing_month`, `entry_type`
- `time_start`, `time_end`, `break_start`, `break_end` — godziny z formularza dashboard
- `clock_in`, `clock_out`, `break_clock_start`, `break_clock_end` — godziny z ekranu powitalnego
- `extra_break_minutes`, `hours_worked`, `hours_billed` (zaokrąglone do 0.25)
- `vacation_day_number`, `is_remote`, `remote_trip_number`, `notes`

**Migracja SQL (Supabase):**
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS pin VARCHAR(4);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT;
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS clock_in TIME;
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS clock_out TIME;
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS break_clock_start TIME;
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS break_clock_end TIME;
```

### MonthConfig
- `user_id`, `billing_year`, `billing_month`
- `hourly_rate`, `expected_hours` (tylko do odczytu — z kalendarza), `bonus`, `notes`

### VacationBalance
- `user_id`, `year`, `vacation_total` (26), `on_demand_total` (4), `remote_total` (24)

### HourlyRate
- Historia zmian stawek (do audytu)

## Logika biznesowa

### Okres rozliczeniowy
- Miesiąc liczony od **23 dnia poprzedniego** do **22 dnia bieżącego**
- Wpis z 24.03 → `billing_month=4` (kwiecień)
- Wpis z 22.04 → `billing_month=4` (kwiecień)
- Wpis z 23.04 → `billing_month=5` (maj)

### Typy wpisów (entry_type)
- `work` — normalny dzień pracy
- `vacation` — urlop (odlicza od puli urlopów)
- `on_demand` — urlop na żądanie (odlicza od puli on_demand ORAZ puli urlopów)
- `unpaid` — urlop bezpłatny (0h, nie odlicza od puli urlopów)
- `holiday` — święto ustawowe
- `sick_leave` — zwolnienie lekarskie

### Obliczanie godzin (calculator.py)
- Przerwa programowa: 15 min (odliczana gdy jest przerwa > 15 min)
- Nadprogramowa przerwa = czas przerwy - 15 min
- Zaokrąglenie: `round(hours * 4) / 4` (do wielokrotności 0.25) — NIE quantize Decimal
- Obsługa pracy przez północ: `end_min < start_min → end_min += 24*60`
- Strefa czasowa: `Europe/Warsaw` przez `zoneinfo.ZoneInfo`

### Nadgodziny
- Suma odchyleń każdego dnia od 8h (nie od sumy miesięcznej)
- Przykład: 6.5h → -1.5, 8.25h → +0.25, suma = -1.25

### Wymagane godziny (expected_hours)
- Obliczane z kalendarza: dni robocze (pon-pt) w okresie 23→22 × 8
- Użytkownik nie może zmieniać tej wartości

### Bilans urlopowy
- Jeden globalny bilans (bez podziału na lata w UI)
- Reset 1 stycznia: on_demand i remote zerują się, urlopy przenoszą nadwyżkę
- Przykład: zostało 5 urlopów z 2026 → pula 2027 = 26 + 5 = 31

### Walidacja przerwy
- Przerwa musi mieścić się w przedziale godzin pracy
- Bez ustawionej godziny pracy nie można ustawić przerwy
- Walidacja w backend (entries.py) i frontend (Alpine.js w form.html)

## Ekran powitalny (/welcome/)

### Dostęp
- Przycisk "Ekran powitalny" na ekranie logowania → modal z hasłem `Przemek121!`
- Weryfikacja przez `/welcome/verify-password` (POST JSON)

### Siatka avatarów
- Wyświetla WSZYSTKICH aktywnych użytkowników (z i bez avatara)
- Bez avatara: szare kółko (`bg-neutral`) z białymi inicjałami (imię + nazwisko)
- Siatka: 2 kolumny mobile, 3 tablet (640px+), 4 desktop (900px+)
- Dla 1-3 użytkowników: wyśrodkowana z ograniczoną szerokością

### Statusy użytkowników (polling co 10s)
Endpoint `/welcome/statuses` zwraca `{user_id: status}` gdzie status to:
- `'working'` — `now >= time_start AND now < time_end` (obie muszą być ustawione)
- `'break'` — warunek working spełniony AND `now >= break_start AND now < break_end`
- `'idle'` — wszystkie pozostałe

Priorytet: `clock_*` (ekran powitalny) > `time_*` (dashboard)

### Obramowania i przeźroczystość
- `working` → zielone obramowanie (`box-shadow: 0 0 0 4px #22c55e`), pełna widoczność
- `break` → pomarańczowe obramowanie (`box-shadow: 0 0 0 4px #f59e0b`), pełna widoczność
- `idle` → szare obramowanie, 50% przeźroczystości (`opacity: 0.5`)
- Klasy CSS: `ring-status-working/break/idle` + `avatar-working/break/idle`
- Obramowania aktualizowane w czasie rzeczywistym bez odświeżania (DOM manipulation w fetchStatuses())

### Przepływ użytkownika
1. Kliknięcie avatara → animacja → ekran PIN
2. PIN (4 cyfry, klawiatura numeryczna) → weryfikacja `/welcome/verify-pin`
3. Poprawny PIN → ekran z przyciskami zegarowymi + status użytkownika

### Przyciski zegarowe
- Przyjście → clock_in, time_start (tylko raz dziennie)
- Wyjście → clock_out, time_end (aktywny dopiero po Przyjście)
- Przy Wyjściu: jeśli przerwa aktywna → automatycznie ją kończy
- Przerwa → aktywna gdy `clockStatus === 'working'`
- Koniec przerwy → aktywna gdy `clockStatus === 'break'`
- Po Wyjściu: przycisk Przerwa wyłącza się

### Obsługa pracy przez północ
- `clock_in` zawsze tworzy wpis na dzień ROZPOCZĘCIA
- `clock_out` i przerwy szukają aktywnego wpisu (clock_in bez clock_out) z dziś lub wczoraj
- Przyciski nie restartują o północy gdy praca trwa

### Ważna uwaga techniczna (Alpine.js)
Przyciski avatarów używają `data-uid`, `data-name`, `data-avatar` zamiast `onclick` — unika problemów z escapowaniem cudzysłowów w Jinja2. Event listenery w `DOMContentLoaded`. Dostęp do Alpine przez `window._welcomeSelectUser` zarejestrowany w `init()`.

## Ustawienia konta (/settings/profile)

- Wgrywanie avatara → Supabase Storage przez REST API (PUT + fallback POST)
- Usuwanie avatara (usuwa wszystkie rozszerzenia: jpg/jpeg/png/gif/webp)
- Wyświetlanie PIN (4 cyfry)
- Zmiana imienia i nazwiska
- Zmiana hasła

## Dashboard

### Navbar
- Desktop: pełne imię i nazwisko (`max-w-[180px] truncate`)
- Mobile: tylko ikona profilu bez tekstu
- Dropdown: Moje konto (ikona person) + Ustawienia (ikona gear) + Wyloguj

### Harmonijka miesięcy
- Aktualny miesiąc zawsze rozwinięty, minione zwinięte
- Tylko jeden miesiąc rozwinięty naraz (Alpine.js `openMonth`)
- Separator roku między miesiącami różnych lat
- Podsumowanie widoczne bez rozwijania

### Tabela wpisów
- Stałe szerokości kolumn (col-date, col-type, col-time, col-break, col-hours, col-salary, col-actions)
- Badge dla typów: Praca/Urlop/Na żąd./Bezpłatny/Święto/Zwolnienie
- Numer urlopu w badge (np. "Urlop (5)")
- Oznaczenie PZ dla pracy zdalnej

### Podsumowanie miesiąca
- Przepracowane, Wymagane (z kalendarza), Nadgodziny, Wynagrodzenie + premia
- Stawka, liczba dni, urlop, zdalna

## Import danych (reimport_xlsx.py)

- Parsuje plik xlsx z ewidencją pracy
- Dedukuje rok wpisu z miesiąca sekcji (np. STYCZEŃ_2026 + wpis 23.12 → rok 2025)
- Czyści dane użytkownika przed importem (`--clear-first`)
- Expected_hours z kalendarza (nie z pliku)
- Stawka dziedziczona z poprzedniego miesiąca jeśli nie można wyliczyć

## Znane rozwiązania technicznie ważne

1. **psycopg3** zamiast psycopg2 — Render używa Python 3.14 gdzie psycopg2 nie działa. Używamy `psycopg[binary]==3.2.10`. Connection string musi zaczynać się od `postgresql+psycopg://`.

2. **config.py** — automatycznie zamienia `postgres://` i `postgresql://` na `postgresql+psycopg://`.

3. **Hashowanie haseł** — `method='pbkdf2:sha256'` zamiast domyślnego scrypt (niekompatybilny z macOS Python 3.9).

4. **Strefa czasowa** — wszystkie operacje czasowe przez `datetime.now(ZoneInfo('Europe/Warsaw'))`.

5. **Supabase pooler** — używaj Transaction Pooler (port 6543), nie Direct Connection (port 5432 — zablokowany na darmowym tierze).

6. **Zaokrąglenie godzin** — `round(hours * 4) / 4`, nie `Decimal.quantize('0.25')` (to zaokrągla do 2 miejsc po przecinku, nie do wielokrotności 0.25).

7. **Folder wlogio_app** — NIE app/ (konflikt z zainstalowaną paczką na Render).

8. **Alpine.js i onclick** — nigdy nie używaj `onclick="func('{{ var }}')"` z Jinja2 — problem z cudzysłowami. Używaj `data-*` atrybutów i event listenerów w JS.

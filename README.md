# Wlogio — Rejestr Czasu Pracy

Aplikacja webowa do prowadzenia rejestru godzin pracy z automatycznym obliczaniem wynagrodzenia.

## Stack technologiczny

- **Backend:** Python 3.11+ / Flask
- **Baza danych:** MySQL
- **Frontend:** Tailwind CSS + DaisyUI
- **Hosting:** Render.com (darmowy tier)

## Wymagania

- Python 3.11+
- Dostęp do bazy MySQL
- Konto na Render.com (do deployu)

## Instalacja lokalna

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/twoj-user/wlogio.git
cd wlogio

# 2. Utwórz wirtualne środowisko
python -m venv venv
source venv/bin/activate        # macOS/Linux
# lub: venv\Scripts\activate    # Windows

# 3. Zainstaluj zależności
pip install -r requirements.txt

# 4. Skopiuj i uzupełnij .env
cp .env.example .env
# Edytuj .env — podaj dane MySQL i SECRET_KEY

# 5. Utwórz tabele w bazie
python run.py

# 6. (Opcjonalnie) Utwórz domyślnego użytkownika i zaimportuj dane
python importer.py --create-user --file wlogio.txt

# 7. Uruchom aplikację
python run.py
```

Aplikacja dostępna pod: http://localhost:5000

## Import danych z wlogio.txt

```bash
# Utwórz użytkownika i zaimportuj całą historię
python importer.py --create-user --file wlogio.txt

# Import dla innego użytkownika
python importer.py --file wlogio.txt --email inny@email.com
```

## Struktura miesiąca rozliczeniowego

Miesiąc liczony od **23 dnia bieżącego** do **22 dnia następnego**.
Przykład: wpis z 24.03 należy do okresu rozliczeniowego KWIECIEŃ.

## Zasady obliczania godzin

- Programowa przerwa: **15 min** (odliczana zawsze)
- Nadprogramowa przerwa: czas ponad 15 min (odliczany od przepracowanych)
- Zaokrąglenie do **0.25h** (15 min)

## Deploy na Render.com

1. Wgraj projekt na GitHub
2. Utwórz nowy **Web Service** na Render.com
3. Ustaw zmienne środowiskowe (DATABASE_URL, SECRET_KEY)
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn run:app`

Dodaj `gunicorn` do `requirements.txt` przed deployem.

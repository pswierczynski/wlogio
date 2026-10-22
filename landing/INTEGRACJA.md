# Wlogio — strona główna (wersja finalna: „Kontrast — Zaokrąglone, Inter Bold”)

To jest wybrana przez Ciebie wersja bazowa strony marketingowej Wlogio —
ultraminimalistyczny styl „Porcelain”, ciemna, zaokrąglona (12px) sekcja
subskrypcji z czterema planami w jednym rzędzie, i pogrubione nagłówki
w kroju `Inter` (700). Względem poprzedniej odsłony dodałem kilka sekcji
i usprawnień, które realnie podnoszą jakość strony jako całości —
nie tylko wygląd, ale też strukturę treści, SEO i kompletność.

Integracja z repozytorium `pswierczynski/wlogio` i Render pozostaje
identyczna jak w poprzednich wersjach — patrz `INTEGRACJA.md` z wersji 1
(konfiguracja `render.yaml`, drugi serwis statyczny, domena, alternatywa
z blueprintem Flask).

## Co nowego w tej wersji

### 1. Sekcja „Jak to działa” (zaraz po hero)
Cztery ponumerowane kroki — od założenia konta, przez konfigurację
zespołu i uruchomienie terminalu, po samo rejestrowanie czasu pracy.
Pomaga nowemu odwiedzającemu od razu zrozumieć, jak wygląda wdrożenie,
zanim jeszcze dojdzie do cennika.

### 2. Tabela „Indywidualne czy firmowe?” (przed cennikiem)
Prosta tabela porównawcza dwóch typów kont — dla kogo, panel pracy,
zarządzanie pracownikami, terminal/kiosk, subkonta, cena. Odpowiada
wprost na najczęstszą wątpliwość przy wyborze planu, zanim odwiedzający
zobaczy konkretne ceny. Na wąskich ekranach tabela przewija się poziomo
zamiast się rozpadać na nieczytelne wiersze.

### 3. Sekcja FAQ (przed sekcją zaufania/statystyk)
Sześć pytań i odpowiedzi w natywnym akordeonie (`<details>/<summary>` —
zero dodatkowego JS, w pełni dostępne z klawiatury i dla czytników
ekranu). Treść pytań wynika wprost z zasad działania systemu, które
wcześniej opisałeś (różnica kont, zmiana planu firmowego, terminal
kontra tablet, limity pracowników, osobne hasła do terminala i panelu,
rozliczenie roczne) — nic nie jest zmyślone, to tylko uporządkowanie
informacji, które już ustaliliśmy.

### 4. Strony prawne zamiast martwych linków
Dodałem `regulamin.html` i `polityka-prywatnosci.html` — nie są to gotowe
dokumenty prawne (oznaczone wyraźnie jako szablon do uzupełnienia przez
prawnika), ale realne, działające strony zamiast linków prowadzących do
`#`. To ważne z dwóch powodów: (1) usługa płatna z subskrypcją
faktycznie potrzebuje takich dokumentów, (2) martwe linki w stopce
obniżają wiarygodność strony.

### 5. SEO i udostępnianie w social media
- `<link rel="canonical">`, `<meta name="robots">`.
- Open Graph (`og:title`, `og:description`, `og:image`, `og:url`) i karta
  Twittera — dzięki temu link do strony ładnie się wyświetli udostępniony
  na LinkedInie, Facebooku czy w komunikatorach. **Podmień `og:url` i
  `og:image` na docelowy adres domeny i realny obrazek** (na razie
  wskazują na `https://wlogio.pl/...` jako placeholder).
- Dane strukturalne JSON-LD (`SoftwareApplication`) z listą planów i cen —
  pomaga wyszukiwarkom prawidłowo zrozumieć, czym jest Wlogio.

### 6. Nawigacja
Dodałem link „FAQ” w głównym menu (zamiast „Integracje”, które teraz
prowadzi tam z linku w stopce — funkcja integracji nadal ma swój akapit
na stronie, po prostu nie zajmuje już miejsca w głównym menu, żeby nie
było za tłoczno).

## Jedna rzecz do ustawienia

W pliku `assets/js/main.js`, na samej górze, wpisz adres swojej aplikacji:

```js
window.WLOGIO_APP_URL = window.WLOGIO_APP_URL || "https://app.wlogio.pl";
```

## Co jeszcze warto dograć przed publikacją

- **Zdjęcie `assets/img/hero.png`** — nadal nie było częścią przesłanych
  mi plików. Planujesz tam zdjęcie terminala i panelu pracy na MacBooku —
  hero jest już przygotowane pod dowolne proporcje takiego zdjęcia
  (wyśrodkowane w pionie względem tekstu).
- **Treść `regulamin.html` i `polityka-prywatnosci.html`** — to szkielety
  z wyraźnie oznaczonymi miejscami do uzupełnienia, nie gotowe dokumenty.
- **`og:image`** — warto przygotować dedykowany obrazek 1200×630px do
  udostępniania w social media (na razie placeholder).
- **Prawdziwy formularz rejestracji** — `rejestracja.html` to nadal wybór
  planu, nie właściwe zakładanie konta; to obsługuje aplikacja Flask pod
  `{WLOGIO_APP_URL}/register?plan=...&billing=...`.


## Hero ze zdjęciem na całą szerokość

Zdjęcie tła hero: `assets/img/hero-bg.jpg` (nazwa musi być dokładnie taka, małymi literami).
Zalecane: JPG, ok. 2400 × 1000 px (proporcje ~2,3:1), do ok. 400 KB. Motyw (laptop + terminal) ma być w środkowo-prawej części, lewa strona zostaje spokojna — pod tekstem.
Menu leży na zdjęciu (przezroczyste), po przewinięciu strony robi się białe. Boczne marginesy (`.wrap`) bez zmian.

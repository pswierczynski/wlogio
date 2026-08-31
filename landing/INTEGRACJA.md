# Wlogio — wariant „Zaokrąglone — Pogrubione (Inter 700)" — integracja

To rozwinięcie polubionego wariantu „Kontrast — Zaokrąglone": ta sama
struktura (cennik z 4 planami w jednym rzędzie, umiarkowane zaokrąglenie
12px, przełącznik miesięcznie/rocznie), ale z dwiema zmianami:

1. **Nagłówki są wyraźnie pogrubione** (patrz sekcja poniżej — różny
   stopień/krój w zależności od wariantu).
2. **Hero na górze strony wyrównano w pionie do środka** — tekst po lewej
   i zdjęcie po prawej mają teraz wspólną oś środkową
   (`align-items:center` zamiast `align-items:end`), więc niezależnie od
   proporcji zdjęcia, które wstawisz, obie kolumny będą wizualnie
   wyśrodkowane względem siebie.

Integracja z repozytorium `pswierczynski/wlogio` i Render jest identyczna
jak w poprzednich wersjach — patrz `INTEGRACJA.md` z wersji 1.

## Charakterystyka pogrubienia

Nagłówki zostają w tym samym kroju co reszta strony (`Inter`), ale na
wadze 700 (zamiast 400) — najbezpieczniejsza, najbardziej spójna zmiana:
wygląda jak naturalne domknięcie hierarchii typograficznej, bez
wprowadzania drugiego kroju pisma.

## Ważne: brakujące zdjęcie

Strona odwołuje się do `assets/img/hero.png`. Wspomniałeś, że planujesz
tam zdjęcie terminala i panelu pracy uruchomionego na MacBooku — to dobrze
komponuje się z tym układem: zdjęcie nie ma wymuszonych proporcji
(`.hero-image` nie ustawia `aspect-ratio`), więc dopasuje się do
naturalnego kształtu Twojego zdjęcia, a dzięki wyśrodkowaniu w pionie
będzie ładnie zbalansowane względem tekstu niezależnie od tego, czy
zdjęcie wyjdzie szersze, czy bardziej kwadratowe.

## Jedna rzecz do ustawienia

W pliku `assets/js/main.js`, na samej górze, wpisz adres swojej aplikacji:

```js
window.WLOGIO_APP_URL = window.WLOGIO_APP_URL || "https://app.wlogio.pl";
```

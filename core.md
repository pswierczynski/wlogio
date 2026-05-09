Logika i wyświetlanie:

* Ładny, nowoczesny i przejrzysty wygląd aplikacji z nie za dużą ilością różnych kolorów.
* Rejestrowanie nowych użytkowników i logowanie przez adres email i hasło.
* Miesiąc pracy liczony od 23 dnia miesiąca do 22 dnia kolejnego miesiąca.
* Użytkownik dodając nowy dzień uzupełnia godzinę przyjścia i wyjścia oraz godziny ewentualnej przerwy.
* Grupuj dodawane dni w miesiące. Dodawać nowy dzień użytkownik może we wszystkich minionych miesiącach do 22 dnia aktualnego miesiąca.
* Oddzielaj zakładki miesięcy informacją z jakiego są roku.
* Możliwość ustawienia, że dany dzień jest dniem urlopowym, urlopem na żądanie, urlopem bezpłatnym, świątecznym lub na dany dzień ma się zwolnienie lekarskie lub pracuje się zdalnie.
* Wyświetlanie miesięcy od najnowszego do najstarszego w tabelach sortowanych od góry do dołu, gdzie aktualny miesiąc jest zawsze na samej górze.
* Dni miesiąca sortowane od góry do dołu gdzie na samej dole jest najbardziej aktualny dzień.
* Struktura harmonijki gdzie aktualny miesiąc jest rozwinięty, a minione zwinięte z możliwością rozwinięcia.
* Możliwy tylko jeden rozwinięty miesiąc w tym samym czasie.
* Widoczne podsumowanie każdego minionego miesiąca bez konieczności rozwijania.
* Każdy miesiąc aby miał widoczne i wyróżnione nagłówki dla kolumn.
* Dni robocze miesięcy jako kolejne wiersze w tabeli.
* Możliwość edycji każdego dnia i jego danych w dowolnym miesiącu.
* Podsumowanie dla każdego miesiąca aktualizowane po zmianie danych.
* Stawka godzinowa możliwa do modyfikacji dla każdego miesiąca. Nowy miesiąc niech przyjmuje automatycznie wysokość stawki z poprzedniego miesiąca.
* Możliwość ustawienia dodatkowej premii dla każdego miesiąca. Jeżeli brak premii ustaw 0.
* Parametry suma dni urlopowych, urlopów na żądanie i pracy zdalnej do ręcznego ustawiania w bilansie miesiąca. Urlopy i prace zdalne wykorzystane i pozostałe niech obliczają się automatycznie z wpisywanych dni ale jedynie dla aktualnego roku. Czyli z dniem 1 stycznia kolejnego roku liczba odejmowanych dni od tych sum resetuje się.
* Dodaj możliwość dodawania i wyświetlania dnia jako Urlop bezpłatny. Urlopy bezpłatne nie odliczają się od bilansu urlopów i dają 0 przepracowanych godzin.
* Dodawać nowe dni można we wszystkich minionych miesiącach do 22 dnia aktualnego miesiąca. Możliwość edytowania dodanych dni zostaje bez zmian.
* Zaokrąglenia godzin pracy są o wielokrotność liczby 0,25 czyli np. 7, 7,25, 7,5, 7,75, 8, 8,25, 8,5, 8,75, 9, 9,25 itp.
* W podsumowaniu dla każdego miesiąca ustaw wartości: Przepracowane (suma przepracowanych zaokrąglonych godzin obliczana z dni dodanych przez użytkownika), Wymagane (ilość dni od 23 dnia miesiąca do 22 dnia kolejnego miesiąca z pominięciem sobót i niedziel), Nadgodziny (suma odchyleń do liczby 8 z zaokrąglonych przepracowanych godzin z dni dodanych przez użytkownika. Np. jeden dzień ma 6,5 godzin, drugi ma 8,25 to suma Nadgodzin wynosi -1,25), Stawka (podawaj ją z ustawień miesiąca), Wynagrodzenie (Wylicz przez pomnożenie Stawki przez zaokrągloną liczbę przepracowanych godzin), Dni pracy (ilość wszystkich dni dodanych w miesiącu przez użytkownika uwzględniająca również Urlopy, Urlopy na żądanie, Urlopy bezpłatne, Zwolnienia i Pracę zdalną), Urlop (ilość dni urlopowych wykorzystanych w danym miesiącu w tym również Urlopów na żądanie i Urlopy bezpłatne).
* Bilas urlopowy niech będzie tylko jeden, bez dodawania kolejnych i bez wyświetlania roku ale z możliwością edycji. Standardowo pule niech posiadają 26 dni Urlopu, 4 dni Urlopu na żądanie i 24 dni pracy zdalnej. Wraz z 1 stycznia kolejnego roku wykorzystane Urlopy na żądanie i wykorzystane Dni pracy zdalnej resetują się do 0 i odejmowane są od pul na nowo. Same urlopy natomiast również się restartują ale jeżeli pozostała jakaś liczba niewykorzystanych urlopów z poprzedniego roku dodają się one do nowej puli Urlopów. (np. zostało 5 urlopów z roku 2026, to 1 stycznia 2027 pula Urlopów zostanie zresetowana do liczby 31).
* Suma nadgodzin dla każdego miesiąca niech zlicza się jedynie z dodanych przez użytkownika dni w miesiącu i niech będzie wyliczana jedynie z odchyleń dla każdego dnia od 8 godzin.
* Nie można dodać konfiguracji miesiąca jeżeli nie poda się ilości godzin roboczych w miesiącu oraz wartości premii. Liczba godzin roboczych w miesiącu powinna być obliczana automatycznie na podstawie dni od 23 dnia miesiąca do 22 dnia kolejnego miesiąca z pominięciem sobót i niedziel pomnożona przez 8 godzin. Użytkownik nie może tego zmieniać. Natomiast wartość premii jeżeli nie zostanie ustawiona, ustawiaj ją na 0.
* Na telefonie niektóre teksty wychodzą poza ramkę min. tekst "na żądanie" na liście dni, Imię i nazwisko użytkownika na górnym pasku, słowo wykorz. u góry aplikacji. Popraw wyświetlanie na telefonie.
* Aplikacja na telefonie czasem wyświetla się niepoprawnie min. zakładka ustawienia wychodzi poza szerokość ekranu telefonu.
* Ekran logowania wyśrodkuj w pionie na ekranie telefonu.
* Zakładka ustawienia wyświetla się niepoprawnie również na desktop, kolumny są za wąskie i dane nie mieszczą się na szerokość. Poszerz je odpowiednio.
* Bilans urlopowy niech będzie ustawiony z możliwością edycji. Dla nowych użytkowników niech będzie ustawiony ze standardowymi wartościami (Urlopy: 26, Na żądanie 4, Praca zdalna 24).
* Wykorzystanie urlopu na żądanie pomniejsza swoją pulę ale również pomniejsza pulę Urlopów.
* Podczas ustawiania Urlopów i Urlopów na żądanie użytkownik nie ustawia numeru dnia urlopowego w roku. Liczba ta wyświetla się przy dodawaniu urlopu ale nie można jej edytować i obliczana jest automatycznie na podstawie wykorzystanych już urlopów z danego rocznego bilansu.
* Przy przycisku pracy zdalnej usuń napis (PZ-KRK) oraz możliwość wpisania nr. wyjazdu. Nie jest to potrzebne, niech to się wyświetla i wylicza na podstawie wykorzystanych już dni pracy zdalnej z danego rocznego bilansu.
* Kolumny list miesięcy i dni wyświetlają się nierówno kiedy jakieś dane są dłuższe od innych lub ich brakuje. Popraw to proszę.


Dodatkowe funkcje:

* W oknie do logowania możliwość wyboru zalogowania się do "Ekranu powitalnego" hasłem Przemek121!. To będzie prosty panel z wgranymi zdjęciami użytkowników i ładnymi animacjami przejść w JavaScript. Ekran składać będzie się tylko z okrągłych klikanych zdjęć pracowników ułożonych w siatce zależnej od ilości wgranych użytkowników. 1 użytkownik to siatka z 1 kolumny z jednym wierszem, 2 użytkowników to 2 kolumny z jednym wierszem, 3 użytkowników to 3 kolumny z jednym wierszem i 4 użytkowników to 4 kolumny z jednym wierszem. Powyżej 4 użytkowników zdjęcia układają się w siatce 4 kolumn z wieloma wierszami z możliwością pionowego przewijania.
* Jeżeli użytkownik nie ma wgranego swojego zdjęcia nie wyświetlaj go na Ekranie powitalnym.
* Po kliknięciu w obrazek pracownika pojawia się poprzez animacje ekran wpisania kodu PIN z 4 liczb, a następnie po wpisaniu poprawnego PIN dwa okrągłe przyciski: Rozpoczęcie pracy i Rozpoczęcie przerwy. Po kliknięciu przycisku Rozpoczęcie pracy, przycisk podmienia się na przycisk Zakończenie pracy. Po kliknięciu przycisku Rozpoczęcie przerwy, przycisk podmienia się na przycisk Zakończenie przerwy. kliknięcie przycisków nadpisuje dane w bazie danych aktualną godziną.
* Kazdy przycisk można przycisnąć tylko raz w ciągu dnia. Przyciski Zakończenia aktywują się z dopiero po kliknięciu przycisków Rozpoczęcia.
* Użytkownik w ustawieniach swojego konta ma możliwość wgrania swojego zdjęcia z ograniczeniami jak przy tego typu panelach.
* Użytkownik w ustawieniach swojego konta może wyświetlić swój numer PIN, który potrzebny mu będzie w Ekranie powitalnym. Numer PIN składa się z 4 liczb i generowany jest losowo podczas rejestracji użytkownika.
* Ekran powitalny to uproszczony system wlogio do obsługi na wspólnym ekranie dotykowym przez pracowników przy wejściu do biura. Korzysta z tej samej bazy danych co aplikacja wlogio i nadpisuje te same dane u wybranego użytkownika.
# HALibrus

Integracja **Home Assistant** umożliwiająca pobieranie planu lekcji ucznia z systemu **Librus** i prezentowanie go w Home Assistant.

Pomysł na integrację powstał z praktycznej potrzeby — potrzebne było miejsce, do którego można zajrzeć w dowolnej chwili i szybko sprawdzić aktualny oraz nadchodzący plan lekcji.

## Funkcje

* pobieranie planu lekcji z konta ucznia w Librusie,
* pobieranie planu na najbliższe **5 dni roboczych**,
* w weekend pobieranie planu na **kolejny tydzień**,
* możliwość ustawienia częstotliwości odświeżania danych,
* zwracanie wpisów planu lekcji z tagami HTML,
* możliwość wykorzystania danych z kartami Home Assistant,
* dostosowanie do współpracy z **Week Planner Card** dostępnej w HACS.

## Wymagania

Do działania integracji potrzebne są:

* Home Assistant,
* konto ucznia w Librusie,
* biblioteka `librus-apix`.

Integracja wykorzystuje bibliotekę:

[librus-apix](https://github.com/RustySnek/librus-apix)

## Instalacja

### Instalacja ręczna

Skopiuj katalog `halibrus` do:

```text
/config/custom_components/halibrus/
```

Struktura katalogów powinna wyglądać podobnie do:

```text
/config/
└── custom_components/
    └── halibrus/
        ├── __init__.py
        ├── manifest.json
        └── ...
```

Po skopiowaniu plików uruchom ponownie Home Assistant.

## Konfiguracja

Po ponownym uruchomieniu Home Assistant przejdź do:

**Ustawienia → Urządzenia i usługi → Dodaj integrację**

Wyszukaj:

**HALibrus**

Podczas konfiguracji należy podać:

| Parametr                     | Opis                                           |
| ---------------------------- | ---------------------------------------------- |
| Nazwa połączenia             | Nazwa pozwalająca rozpoznać dane połączenie    |
| Nazwa użytkownika do Librusa | Nazwa użytkownika konta ucznia w Librusie      |
| Hasło do konta w Librusie    | Hasło do konta ucznia w Librusie               |
| Interwał                     | Co jaki czas odpytywać Librusa o aktualne dane |

Interwał odświeżania można ustawić w zakresie **15–720 minut**.

## Plan lekcji

Integracja pobiera plan lekcji na najbliższe **5 dni roboczych**.

W weekend plan pobierany jest na **kolejny tydzień**.

Dzięki temu plan lekcji na nadchodzące dni może być dostępny w Home Assistant jeszcze przed rozpoczęciem kolejnego tygodnia nauki.

## Week Planner Card

HALibrus zwraca wpisy planu lekcji zawierające tagi HTML i jest dostosowany do współpracy z **Week Planner Card** dostępnej w HACS.

Przykładowe wykorzystanie może wyglądać następująco:

```text
Poniedziałek

08:00  Matematyka
09:00  Język polski
10:00  Fizyka
11:00  Informatyka
```

Rekomendowane jest dodanie tutaj zrzutu ekranu przedstawiającego plan lekcji w Home Assistant z wykorzystaniem Week Planner Card.

## Dane logowania

HALibrus wymaga danych logowania do **konta ucznia w Librusie**.

Dane te należy wprowadzać wyłącznie podczas konfiguracji integracji w Home Assistant.

**Nie umieszczaj loginu ani hasła do Librusa w publicznym repozytorium GitHub ani w plikach konfiguracyjnych udostępnianych publicznie.**

## Odświeżanie danych

Integracja odpytuje Librusa zgodnie z ustawionym interwałem.

Dostępny zakres:

```text
15–720 minut
```

Ustawienie krótkiego interwału powoduje częstsze odpytywanie Librusa. W przypadku braku potrzeby częstych aktualizacji zalecane jest ustawienie dłuższego interwału.

## Rozwiązywanie problemów

Jeżeli plan lekcji nie jest aktualizowany:

1. Sprawdź logi Home Assistant.
2. Sprawdź poprawność nazwy użytkownika i hasła do Librusa.
3. Sprawdź, czy konto ucznia w Librusie działa poprawnie.
4. Sprawdź dostępność serwisu Librus.
5. Sprawdź, czy używana wersja HALibrus jest aktualna.
6. Sprawdź, czy biblioteka `librus-apix` jest aktualna.
7. Po ręcznej aktualizacji plików integracji uruchom ponownie Home Assistant.

## Ograniczenia

HALibrus jest zależny od biblioteki `librus-apix` oraz działania serwisu Librus.

Zmiany w sposobie logowania lub strukturze serwisu Librus mogą spowodować konieczność aktualizacji integracji lub biblioteki `librus-apix`.

## Zależności

HALibrus korzysta z:

* [librus-apix](https://github.com/RustySnek/librus-apix)

Podziękowania dla autora biblioteki `librus-apix` za udostępnienie rozwiązania umożliwiającego komunikację z Librusem.

## Licencja

Informacje dotyczące licencji znajdują się w pliku `LICENSE`.

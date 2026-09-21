"""Koordynator danych integracji Librus Synergia (wersja 2).

Moduł definiuje klasę :class:`LibrusCoordinator`, która cyklicznie pobiera
plan lekcji z serwisu Librus Synergia.

* W dni robocze (poniedziałek-piątek) plan odczytywany jest dla pięciu dni
  roboczych licząc od dnia bieżącego.
* W weekend (sobota, niedziela) plan odczytywany jest dla **całego kolejnego
  tygodnia** (poniedziałek-piątek następnego tygodnia). Dzięki temu w weekend
  dostępny jest pełny, spójny plan na nadchodzący tydzień.
"""

import logging

from collections import defaultdict
from datetime import timedelta, datetime, date

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import CONF_LOGIN, CONF_PASSWORD, CONF_INTERVAL

from librus_apix.client import Client, Token, new_client
from librus_apix.schedule import get_schedule, schedule_detail
from librus_apix.timetable import get_timetable
from librus_apix.exceptions import TokenError

_LOGGER: logging.Logger = logging.getLogger(__package__)


class LibrusCoordinator(DataUpdateCoordinator):
    """Koordynator pobierający plan lekcji z Librus Synergia.

    W dni robocze plan odczytywany jest dla pięciu dni roboczych licząc od
    dnia bieżącego. W weekend plan odczytywany jest dla całego następnego
    tygodnia (poniedziałek-piątek).

    Attributes:
        hass: Instancja Home Assistant.
        entry: Wpis konfiguracyjny integracji.
        login: Login użytkownika Librus.
        password: Hasło użytkownika Librus.
        update_interval: Odstęp czasu między odświeżeniami danych.
        conf_interval: Skonfigurowany odstęp odświeżania w minutach.
        client: Klient API Librus.
        token: Aktywny token autoryzacyjny Librus (lub ``None``).
    """

    #: Liczba dni roboczych, dla których zawsze odczytywany jest plan lekcji.
    working_days_count: int = 5

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Inicjalizuje koordynatora danych.

        Args:
            hass: Instancja Home Assistant.
            entry: Wpis konfiguracyjny integracji.
        """
        #: Instancja Home Assistant.
        self.hass = hass

        #: Wpis konfiguracyjny integracji.
        self.entry = entry

        #: Login użytkownika Librus.
        self.login = entry.data[CONF_LOGIN]

        #: Hasło użytkownika Librus.
        self.password = entry.data[CONF_PASSWORD]

        #: Odstęp czasu między odświeżeniami danych.
        self.update_interval = timedelta(minutes=entry.data[CONF_INTERVAL])

        #: Skonfigurowany odstęp odświeżania w minutach.
        self.conf_interval = entry.data[CONF_INTERVAL]

        #: Klient API Librus.
        self.client: Client = new_client()

        #: Aktywny token autoryzacyjny Librus (lub ``None``).
        self.token = None

        super().__init__(
            hass,
            _LOGGER,
            name="Librus Coordinator",
            update_interval=self.update_interval,
            always_update=True,
        )

    @staticmethod
    def _is_weekend(reference: date) -> bool:
        """Sprawdza, czy podana data wypada w weekend (sobota lub niedziela).

        Args:
            reference: Data do sprawdzenia.

        Returns:
            ``True`` jeżeli data wypada w sobotę lub niedzielę.
        """
        return reference.weekday() >= 5

    @staticmethod
    def _working_days(reference: date, count: int = 5):
        """Zwraca listę kolejnych dni roboczych zaczynając od daty odniesienia.

        Dni weekendowe (sobota, niedziela) są pomijane.

        Args:
            reference: Data, od której rozpoczyna się wyznaczanie dni.
            count: Liczba dni roboczych do zwrócenia.

        Returns:
            Posortowana rosnąco lista kolejnych dni roboczych.
        """
        days = []
        cursor = reference
        while len(days) < count:
            if cursor.weekday() < 5:
                days.append(cursor)
            cursor += timedelta(days=1)
        return days

    @staticmethod
    def _next_week_working_days(reference: date):
        """Zwraca poniedziałek-piątek następnego tygodnia względem daty odniesienia.

        Args:
            reference: Data odniesienia (typowo sobota lub niedziela).

        Returns:
            Lista pięciu dni roboczych następnego tygodnia (pon-pt).
        """
        current_monday = reference - timedelta(days=reference.weekday())
        next_monday = current_monday + timedelta(days=7)
        return [next_monday + timedelta(days=offset) for offset in range(5)]

    def _target_days(self):
        """Zwraca listę docelowych dni, dla których należy odczytać plan.

        W dni robocze zwracane jest ``working_days_count`` kolejnych dni
        roboczych licząc od dnia bieżącego. W weekend zwracany jest cały
        następny tydzień (poniedziałek-piątek).

        Returns:
            Lista obiektów :class:`datetime.date`.
        """
        today = datetime.now().date()
        if self._is_weekend(today):
            return self._next_week_working_days(today)
        return self._working_days(today, self.working_days_count)

    def _target_dates(self):
        """Zwraca zbiór docelowych dni w formacie ISO.

        Returns:
            Zbiór łańcuchów dat (``RRRR-MM-DD``).
        """
        return {d.isoformat() for d in self._target_days()}

    def _get_week_mondays(self):
        """Zwraca posortowane poniedziałki obejmujące docelowe dni.

        Returns:
            Lista obiektów :class:`datetime.date` reprezentujących poniedziałki
            tygodni, do których należą docelowe dni.
        """
        days = self._target_days()
        return sorted({d - timedelta(days=d.weekday()) for d in days})

    def _get_months(self):
        """Zwraca listę lat i miesięcy obejmujących docelowe dni.

        Returns:
            Lista słowników z kluczami ``year`` oraz ``month``.
        """
        days = self._target_days()
        months = {(d.year, d.month) for d in days}
        return [
            {"year": str(year), "month": f"{month:02d}"}
            for (year, month) in sorted(months)
        ]

    def _filter_events_month(self, events_dict=None, year="2026", month="01"):
        """Filtruje zdarzenia miesiąca do docelowych dni.

        Args:
            events_dict: Słownik zdarzeń kluczowany numerem dnia miesiąca.
            year: Rok w formacie tekstowym.
            month: Miesiąc w formacie tekstowym (``MM``).

        Returns:
            Słownik mapujący datę ISO na listę zdarzeń tego dnia.
        """
        target_dates = self._target_dates()
        result = defaultdict(list)

        if not events_dict:
            return result

        for day in events_dict:
            try:
                day_iso = date(int(year), int(month), int(day)).isoformat()
            except (ValueError, TypeError):
                continue
            if day_iso in target_dates:
                result[day_iso] = events_dict[day]

        return result

    async def _login_to_librus(self):
        """Loguje się do Librusa i zapisuje aktywny token.

        Raises:
            UpdateFailed: Gdy logowanie się nie powiedzie.
        """
        try:
            self.client = new_client()
            self.token = await self.hass.async_add_executor_job(
                self.client.get_token, self.login, self.password
            )
        except Exception as refresh_err:
            self.token = None
            _LOGGER.error(f"Nie udało się odświeżyć tokenu: {refresh_err}")
            raise UpdateFailed(
                "Token wygasł i nie udało się odświeżyć — ponawianie przy następnym cyklu"
            )

    async def _download_schedule(self):
        """Pobiera szczegóły zdarzeń dla docelowych dni.

        Returns:
            Słownik mapujący datę ISO na listę słowników ze szczegółami.
        """
        main_details = defaultdict(list)
        detail_cache = {}

        for item in self._get_months():
            try:
                schedule = await self.hass.async_add_executor_job(
                    get_schedule, self.client, item["month"], item["year"]
                )
            except TokenError:
                _LOGGER.warning("Token wygasł — próba odświeżenia [_download_schedule]...")
                try:
                    await self._login_to_librus()

                    schedule = await self.hass.async_add_executor_job(
                        get_schedule, self.client, item["month"], item["year"]
                    )
                except Exception as err:
                    self.token = None
                    _LOGGER.error(f"Nie mogłem pobrać schedule: {err}")
                    raise

            filtered = self._filter_events_month(
                schedule, item["year"], item["month"]
            )
            for day_iso in filtered:
                for event in filtered[day_iso]:
                    if not event.href:
                        continue
                    if event.href not in detail_cache:
                        prefix, href = event.href.split("/")
                        detail_cache[event.href] = await self.hass.async_add_executor_job(
                            schedule_detail, self.client, prefix, href
                        )
                    details = detail_cache[event.href]
                    if details.keys() >= {"Data", "Nr lekcji", "Rodzaj", "Przedmiot", "Opis"}:
                        main_details[details["Data"]].append(details)

        return main_details

    async def _download_timetable(self):
        """Pobiera plan lekcji (timetable) dla docelowych dni.

        Returns:
            Słownik mapujący datę ISO na listę obiektów ``Period``.
        """
        timetable = defaultdict(list)
        target_dates = self._target_dates()

        for monday in self._get_week_mondays():
            monday_datetime = datetime(monday.year, monday.month, monday.day)
            try:
                week_timetable = await self.hass.async_add_executor_job(
                    get_timetable, self.client, monday_datetime
                )
            except TokenError:
                _LOGGER.warning("Token wygasł — próba odświeżenia [_download_timetable]...")
                try:
                    await self._login_to_librus()

                    week_timetable = await self.hass.async_add_executor_job(
                        get_timetable, self.client, monday_datetime
                    )
                except Exception as err:
                    self.token = None
                    _LOGGER.error(f"Nie mogłem pobrać timetable: {err}")
                    raise

            for day_periods in week_timetable:
                for period in day_periods:
                    if period.date in target_dates:
                        timetable[period.date].append(period)

        return timetable

    async def _async_update_data(self):
        """Pobiera aktualne dane z Librusa i zwraca je koordynatorowi.

        Returns:
            Słownik z kluczami ``timetable`` oraz ``schedule``.

        Raises:
            UpdateFailed: Gdy aktualizacja danych się nie powiedzie.
        """
        schedule = defaultdict(list)

        try:
            if self.token is None:
                await self._login_to_librus()

            timetable = await self._download_timetable()
            if timetable:
                schedule = await self._download_schedule()

            _LOGGER.debug(
                "LibrusCoordinator._async_update_data - aktualizacja z Librus "
                "| entry.data: %s, update_interval: %s",
                self.conf_interval,
                self.update_interval,
            )

            return {
                "timetable": timetable,
                "schedule": schedule,
            }

        except Exception as err:
            raise UpdateFailed(f"Librus update failed: {err}") from err

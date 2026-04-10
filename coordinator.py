import logging

from collections import defaultdict

from datetime import timedelta, datetime
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import CONF_LOGIN, CONF_PASSWORD, CONF_INTERVAL

from librus_apix.client import Client, Token, new_client
from librus_apix.schedule import get_schedule, schedule_detail
from librus_apix.grades import get_grades
from librus_apix.timetable import get_timetable
from librus_apix.exceptions import TokenError

_LOGGER: logging.Logger = logging.getLogger(__package__)

class LibrusCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):

        self.hass = hass
        self.entry = entry

        self.login = entry.data[CONF_LOGIN]
        self.password = entry.data[CONF_PASSWORD]
        self.update_interval = timedelta(minutes=entry.data[CONF_INTERVAL])
        #self.update_interval = timedelta(seconds=entry.data[CONF_INTERVAL])
        self.conf_interval = entry.data[CONF_INTERVAL]

        self.client: Client = new_client()
        self.token = None

        self._last_grades = []

        super().__init__(
            hass,
            _LOGGER,
            name="Librus Coordinator",
            update_interval=self.update_interval,
            always_update=True,
        )


    def _get_week_months(self):
        today = datetime.now()

        # początek tygodnia (poniedziałek)
        start_of_week = today - timedelta(days=today.weekday())

        # koniec tygodnia (niedziela)
        end_of_week = start_of_week + timedelta(days=6)

        # zbieramy unikalne (rok, miesiąc)
        months = set()

        current_day = start_of_week
        while current_day <= end_of_week:
            month = current_day.strftime("%m")
            year = current_day.strftime("%Y")
            months.add((year, month))
            current_day += timedelta(days=1)

        # wynik
        return {
            "current": [
                {"year": y, "month": m}
                for (y, m) in sorted(months)
            ]
        }

    def _filter_events_week(self, events_dict = None, month = 1):
        result = defaultdict(list)

        today = datetime.now()
        weekday = today.weekday()  # 0=pon, 6=niedz

        # Oblicz poniedziałek aktualnego tygodnia
        start_of_week = today - timedelta(days=weekday)

        # Weekend → bierz następny tydzień
        if weekday >= 5:  # sobota(5), niedziela(6)
            start_of_week += timedelta(days=7)

        # Zakres dni (pon-pt)
        days_range = [
            (start_of_week + timedelta(days=i)).day
            for i in range(5)
            if (start_of_week + timedelta(days=i)).month == month
        ]

        for day in days_range:
            if day in events_dict:
                result[day] = events_dict[day]

        return result

    async def _download_schedule(self, client):
        main_details = defaultdict(list)
        dates = self._get_week_months()

        for item in dates["current"]:
            schedule = await self.hass.async_add_executor_job(get_schedule, client, item["month"], item["year"])
            #schedule = get_schedule(client, item["month"], item["year"])
            filtered = self._filter_events_week (schedule, int(item["month"]))
            for day in filtered:
                for event in filtered[day]:
                     if event.href:
                        prefix, href = event.href.split('/')
                        details = await self.hass.async_add_executor_job(schedule_detail,client, prefix, href)
                        #details = schedule_detail(client, prefix, href)
                        if details.keys() >= {'Data', 'Nr lekcji', 'Rodzaj', 'Przedmiot', 'Opis'}:
                            main_details[details['Data']].append(details)


        return main_details


    async def _download_timetable(self, client):
        
        today = datetime.now()
        weekday = today.weekday()  # 0=pon, 6=niedz

        # Oblicz poniedziałek aktualnego tygodnia
        start_of_week = today - timedelta(days=weekday)

        # Weekend → bierz następny tydzień
        if weekday >= 5:  # sobota(5), niedziela(6)
            start_of_week += timedelta(days=7)



        monday_date = start_of_week.strftime("%Y-%m-%d")
        monday_datetime = datetime.strptime(monday_date, "%Y-%m-%d")

        try:
            timetable = await self.hass.async_add_executor_job(get_timetable, self.client, monday_datetime)

            return timetable
        except TokenError:
            _LOGGER.warning("Token wygasł — próba odświeżenia...")
            try:
                self.client = new_client()
                self.token = await self.hass.async_add_executor_job(self.client.get_token, self.login, self.password)
                timetable = await self.hass.async_add_executor_job( get_timetable, self.client, monday_datetime )
                return timetable
            except Exception as refresh_err:
                self.token = None
                _LOGGER.error(f"Nie udało się odświeżyć tokenu: {refresh_err}")
                raise


    async def _async_update_data(self):
        schedule = defaultdict(list)

        try:
            if self.token is None:
                self.client = new_client()
                self.token = await self.hass.async_add_executor_job(self.client.get_token, self.login, self.password)
            
            timetable = await self._download_timetable( self.client )
            if timetable:
                schedule = await self._download_schedule( self.client )
            
            _LOGGER.debug(f"LibrusCoordinator_async_update_data - Update from librus | entry.data: {self.conf_interval}, update_interval: {self.update_interval}")

            return {
                "timetable": timetable,
                "schedule" : schedule,
            }
        except TokenError:
            # Token całkowicie nieważny — wymuś ponowne logowanie
            _LOGGER.warning("Wymuszam ponowne pobranie tokenu przy następnym odświeżeniu")
            self.token = None
            raise UpdateFailed("Token wygasł i nie udało się odświeżyć — ponawianie przy następnym cyklu")

        except Exception as err:
            raise UpdateFailed(f"Librus update failed: {err}") from err

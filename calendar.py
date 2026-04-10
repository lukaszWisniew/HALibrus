from __future__ import annotations
from datetime import datetime, timedelta
from collections import defaultdict
import logging


from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

#from librus_apix.get_timetable import get_timetable, Period
from librus_apix.timetable import get_timetable, Period

from .const import DOMAIN, CONF_NAME, CONF_LOGIN


_LOGGER: logging.Logger = logging.getLogger(__package__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Konfiguracja platformy kalendarza Librus."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
            LibrusCalendar(coordinator, entry)
    ]

    async_add_entities(entities)

class LibrusCalendar(CoordinatorEntity, CalendarEntity):
    """Encja kalendarza wyświetlająca plan lekcji z Librusa."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        if entry.data[CONF_NAME]:
            self._attr_name = f"Librus Plan Lekcji - {entry.data[CONF_NAME]}"
        else:
            self._attr_name = f"Librus Plan Lekcji - {entry.data[CONF_LOGIN]}"
        #self._attr_name = "Librus Plan Lekcji"
        self._attr_unique_id = f"{entry.entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Zwraca aktualnie trwające zdarzenie (lekcję)."""
        events = self._get_events_from_coordinator()
        now = dt_util.now()
        for event in events:
            if event.start <= now <= event.end:
                return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Zwraca listę zdarzeń w podanym zakresie dat dla interfejsu HA."""
        all_events = self._get_events_from_coordinator()
        return [
            event
            for event in all_events
            if start_date <= event.start <= end_date
        ]

    def _get_events_from_coordinator(self) -> list[CalendarEvent]:
        
        if not self.coordinator.data:
            return []

        """Konwertuje list[list[Period]] na spłaszczoną listę CalendarEvent."""
        timetable: list[list[Period]] = self.coordinator.data["timetable"]
        schedule: defaultdict(list) = self.coordinator.data["schedule"]

        events = []

        # Librus-apix zwraca listę list (dni tygodnia), gdzie indeks 0 to poniedziałek.
        # Musimy wyliczyć datę poniedziałku bieżącego tygodnia, aby dopasować dni.
        today = datetime.now()
        weekday = today.weekday()  # 0=pon, 6=niedz

        # Oblicz poniedziałek aktualnego tygodnia
        monday = today - timedelta(days=weekday)

        # Weekend → bierz następny tydzień
        if weekday >= 5:  # sobota(5), niedziela(6)
            monday += timedelta(days=7)

        for day_index, day_periods in enumerate(timetable):
            # Obliczamy konkretną datę dla danego dnia tygodnia (np. poniedziałek + 2 dni = środa)
            current_day = (monday + timedelta(days=day_index)).date()
            prev_summary = '---'
            #_LOGGER.debug(f"get_events_from_coordinator - current_day: {current_day}")
            for period in day_periods:
                try:
                    #_LOGGER.debug(f"get_events_from_coordinator - period {period}")
                    start_time = datetime.strptime(period.date_from, "%H:%M").time()
                    end_time = datetime.strptime(period.date_to, "%H:%M").time()

                    tz = dt_util.get_default_time_zone()

                    start_dt = datetime.combine(current_day, start_time, tzinfo=tz)
                    end_dt = datetime.combine(current_day, end_time, tzinfo=tz)

                    # Przygotowanie opisu lekcji
                    summary = period.subject if period.subject else "---"
                    description = f"Nauczyciel: {period.teacher_and_classroom}"
                    #location = f"Sala: {period.classroom}" if period.classroom else ""
            

                    if not(summary == '---'):
                        detail = next(
                            (item for item in schedule.get(period.date, [])
                            if int(item.get('Nr lekcji'),0) == period.number),
                            None
                        )
                        if detail:
                            summary = f"{period.subject} [{detail["Rodzaj"]}]"
                            description = f"<b>Rodzaj:</b> {detail["Rodzaj"]}<br><b>Opis:</b> {detail["Opis"]}<br><b>Nauczyciel:</b> {detail["Nauczyciel"]}<br><b>Data dodania:</b> {detail["Data dodania"]}"

                    if period.info:
                        if 'zastępstwo' in period.info:
                            summary = f"{period.subject} [ZASTĘPSTWO]"
                            description = f"<b>Lekcja:</b> {period.info["zastępstwo"]["subject_swap"]}<br><b>Nauczyciel:</b> {period.info["zastępstwo"]["teacher_swap"]}<br><b>Data dodania:</b> {period.info["zastępstwo"]["date_added"]}"
                        else:
                            detail = next(
                                (item for item in schedule.get(period.date, [])
                                if int(item.get('Nr lekcji'),0) == period.number),
                                None
                            )
                            if detail:
                                description = f"<b>Rodzaj:</b> {detail["Rodzaj"]}<br><b>Opis:</b> {detail["Opis"]}<br><b>Nauczyciel:</b> {detail["Nauczyciel"]}<br><b>Data dodania:</b> {detail["Data dodania"]}"
                            else:
                                #description = f"[0] {period.info}"
                                         description = f"<h3>{list(period.info.keys())[0]}</h3>"

                            summary = f"{period.subject} [{list(period.info.keys())[0]}]"

                   # _LOGGER.debug(f"get_events_from_coordinator - start_dt: {start_dt}, end_dt: {end_dt}, summary:{summary}, desc:{description}")
                    if not( summary == '---' and prev_summary != '---') :
                        events.append(
                            CalendarEvent(
                                summary=summary,
                                start=start_dt,
                                end=end_dt,
                                description=description,
                            )
                        )
                        prev_summary = summary

                except (ValueError, IndexError, AttributeError) as e:
                    # Pominięcie wpisów z błędnym formatem godziny
                    _LOGGER.warning(f"Błąd parsowania lekcji: {period} | {e}")
                    continue
        
        return events

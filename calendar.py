"""Platforma kalendarza integracji Librus Synergia."""

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

from librus_apix.timetable import get_timetable, Period

from .const import DOMAIN, CONF_NAME, CONF_LOGIN


_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Konfiguracja platformy kalendarza Librus.

    Args:
        hass: Instancja Home Assistant.
        entry: Wpis konfiguracyjny integracji.
        async_add_entities: Funkcja rejestrująca encje w Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
            LibrusCalendar(coordinator, entry)
    ]

    async_add_entities(entities)


class LibrusCalendar(CoordinatorEntity, CalendarEntity):
    """Encja kalendarza wyświetlająca plan lekcji z Librusa.

    Encja korzysta z danych koordynatora obejmujących pięć dni roboczych
    licząc od dnia bieżącego.

    Attributes:
        coordinator: Koordynator danych integracji Librus.
        _attr_name: Nazwa encji kalendarza.
        _attr_unique_id: Unikalny identyfikator encji.
    """

    def __init__(self, coordinator, entry):
        """Inicjalizuje encję kalendarza.

        Args:
            coordinator: Koordynator danych integracji Librus.
            entry: Wpis konfiguracyjny integracji.
        """
        super().__init__(coordinator)
        if entry.data[CONF_NAME]:
            self._attr_name = f"Librus Plan Lekcji - {entry.data[CONF_NAME]}"
        else:
            self._attr_name = f"Librus Plan Lekcji - {entry.data[CONF_LOGIN]}"

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
        """Zwraca listę zdarzeń w podanym zakresie dat dla interfejsu HA.

        Args:
            hass: Instancja Home Assistant.
            start_date: Początek zakresu dat.
            end_date: Koniec zakresu dat.

        Returns:
            Lista zdarzeń kalendarza mieszczących się w zakresie dat.
        """
        all_events = self._get_events_from_coordinator()
        return [
            event
            for event in all_events
            if start_date <= event.start <= end_date
        ]

    def _get_events_from_coordinator(self) -> list[CalendarEvent]:
        """Konwertuje dane koordynatora na listę zdarzeń kalendarza.

        Returns:
            Lista obiektów :class:`CalendarEvent` reprezentujących lekcje.
        """
        if not self.coordinator.data:
            return []

        timetable: defaultdict = self.coordinator.data["timetable"]
        schedule: defaultdict = self.coordinator.data["schedule"]

        events = []
        tz = dt_util.get_default_time_zone()

        for date_iso, day_periods in sorted(timetable.items()):
            try:
                current_day = datetime.strptime(date_iso, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                _LOGGER.warning(f"Pomijam dzień o błędnym formacie daty: {date_iso}")
                continue

            prev_summary = '---'
            for period in day_periods:
                try:
                    start_time = datetime.strptime(period.date_from, "%H:%M").time()
                    end_time = datetime.strptime(period.date_to, "%H:%M").time()

                    start_dt = datetime.combine(current_day, start_time, tzinfo=tz)
                    end_dt = datetime.combine(current_day, end_time, tzinfo=tz)

                    # Przygotowanie opisu lekcji
                    summary = period.subject if period.subject else "---"
                    description = f"Nauczyciel: {period.teacher_and_classroom}"

                    if not (summary == '---'):
                        detail = next(
                            (item for item in schedule.get(period.date, [])
                             if int(item.get('Nr lekcji', 0)) == period.number),
                            None
                        )
                        if detail:
                            summary = f"{period.subject} [{detail['Rodzaj']}]"
                            description = (f"<b>Rodzaj:</b> {detail['Rodzaj']}<br>"
                                           f"<b>Opis:</b> {detail['Opis']}<br>"
                                           f"<b>Nauczyciel:</b> {detail['Nauczyciel']}<br>"
                                           f"<b>Data dodania:</b> {detail['Data dodania']}")

                    if period.info:
                        if 'zastępstwo' in period.info:
                            summary = f"{period.subject} [ZASTĘPSTWO]"
                            description = (f"<b>Lekcja:</b> {period.info['zastępstwo']['subject_swap']}<br>"
                                           f"<b>Nauczyciel:</b> {period.info['zastępstwo']['teacher_swap']}<br>"
                                           f"<b>Data dodania:</b> {period.info['zastępstwo']['date_added']}")
                        else:
                            detail = next(
                                (item for item in schedule.get(period.date, [])
                                 if int(item.get('Nr lekcji', 0)) == period.number),
                                None
                            )
                            if detail:
                                description = (f"<b>Rodzaj:</b> {detail['Rodzaj']}<br>"
                                               f"<b>Opis:</b> {detail['Opis']}<br>"
                                               f"<b>Nauczyciel:</b> {detail['Nauczyciel']}<br>"
                                               f"<b>Data dodania:</b> {detail['Data dodania']}")
                            else:
                                description = f"<h3>{list(period.info.keys())[0]}</h3>"

                            summary = f"{period.subject} [{list(period.info.keys())[0]}]"

                    if summary == '---':
                        continue

                    if not (summary == '---' and prev_summary != '---'):
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

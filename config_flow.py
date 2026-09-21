"""Przepływ konfiguracji integracji Librus Synergia."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_LOGIN, CONF_PASSWORD, CONF_INTERVAL, CONF_NAME

from librus_apix.client import Client

_LOGGER = logging.getLogger(__name__)


class LibrusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Przepływ konfiguracji zbierający dane dostępowe do Librus."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Obsługuje krok konfiguracji inicjowany przez użytkownika.

        Args:
            user_input: Dane wprowadzone przez użytkownika lub ``None``.

        Returns:
            Wynik utworzenia wpisu albo formularz konfiguracji.
        """
        errors = {}

        if user_input is not None:

            try:
                if user_input[CONF_NAME] != "" :
                    title=f"Librus {user_input[CONF_NAME]}"
                else:
                    title=f"Librus {user_input[CONF_LOGIN]}"

                return self.async_create_entry(
                    title=title,
                    data=user_input,
                )

            except Exception as err:

                _LOGGER.error("Librus login error: %s", err)

                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME): str,
                    vol.Required(CONF_LOGIN): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_INTERVAL, default=120): selector.NumberSelector(
                         selector.NumberSelectorConfig(
                           min=15,
                           max=720,
                           step=1,
                           unit_of_measurement="minutes",
                           mode="box",
                        )
                   ),
                }
            ),
            errors=errors,
        )

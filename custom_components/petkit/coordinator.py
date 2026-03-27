"""DataUpdateCoordinator for the PetKit integration."""
from __future__ import annotations

from datetime import timedelta
import json
import logging

from petkitaio import PetKitClient
from petkitaio.exceptions import AuthError, PetKitError, RegionError, ServerError
from petkitaio.model import PetKitData


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LOGGER,
    POLLING_INTERVAL,
    REGION,
    TIMEOUT,
    TIMEZONE,
    USE_BLE_RELAY,
)


class PetKitDataUpdateCoordinator(DataUpdateCoordinator):
    """PetKit Data Update Coordinator."""

    data: PetKitData

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the PetKit coordinator."""

        if entry.options[TIMEZONE] == "Set Automatically":
            tz = None
        else:
            tz = entry.options[TIMEZONE]
        self.fast_poll_expiration = None
        try:
            self.client = PetKitClient(
                entry.data[CONF_EMAIL],
                entry.data[CONF_PASSWORD],
                session=async_get_clientsession(hass),
                region=entry.options[REGION],
                timezone=tz,
                timeout=TIMEOUT,
            )
            self.client.use_ble_relay = entry.options[USE_BLE_RELAY]
            super().__init__(
                hass,
                LOGGER,
                name=DOMAIN,
                update_interval=timedelta(seconds=entry.options[POLLING_INTERVAL]),
            )
        except RegionError as error:
            raise ConfigEntryAuthFailed(error) from error

    async def _async_update_data(self) -> PetKitData:
        """Fetch data from PetKit."""

        try:
            data = await self.client.get_petkit_data()
        except (AuthError, RegionError) as error:
            raise ConfigEntryAuthFailed(error) from error
        except (ServerError, PetKitError) as error:
            raise UpdateFailed(error) from error

        if LOGGER.isEnabledFor(logging.DEBUG):
            try:
                LOGGER.debug(
                    "Found the following PetKit devices/pets:\n%s",
                    json.dumps(data, default=vars, indent=4),
                )
            except TypeError:
                LOGGER.debug("Could not format PetKit device data for logging")

        return data

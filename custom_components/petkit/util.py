"""Utilities for PetKit Integration"""
from __future__ import annotations

from asyncio import timeout

from petkitaio import PetKitClient
from petkitaio.exceptions import AuthError, PetKitError, RegionError, ServerError, TimezoneError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOGGER, PETKIT_ERRORS, TIMEOUT


async def async_validate_api(
    hass: HomeAssistant,
    email: str,
    password: str,
    region: str,
    timezone: str,
    use_ble_relay: bool
) -> bool:
    """Get data from API."""

    if timezone == "Set Automatically":
        tz = None
    else:
        tz = timezone
    client = PetKitClient(
        email,
        password,
        session=async_get_clientsession(hass),
        region=region,
        timezone=tz,
        timeout=TIMEOUT,
    )
    client.use_ble_relay = use_ble_relay
    try:
        async with timeout(TIMEOUT):
            devices_query = await client.get_device_rosters()
    except AuthError as err:
        LOGGER.error('Could not authenticate on PetKit servers: %s', err)
        raise AuthError(err) from err
    except TimezoneError as err:
        error = (
            'A timezone could not be found. If you are running Home Assistant '
            'as a standalone Docker container, you must define the TZ '
            'environmental variable. If the TZ variable is defined or you are '
            'running Home Assistant OS, your timezone was not found in the '
            'tzlocal library - Please manually select a timezone during setup.'
        )
        LOGGER.error(error)
        raise TimezoneError(error) from err
    except ServerError as err:
        LOGGER.error('PetKit servers are busy. Please try again later.')
        raise ServerError(err) from err
    except RegionError as err:
        LOGGER.error('Region error: %s', err)
        raise RegionError(err) from err
    except PetKitError as err:
        LOGGER.error('Unknown PetKit Error: %s', err)
        raise PetKitError(err) from err
    except PETKIT_ERRORS as err:
        LOGGER.error('Failed to get information from PetKit servers: %s', err)
        raise ConnectionError from err

    devices = sum(len(value['result']['devices']) for value in devices_query.values())


    if devices == 0:
        LOGGER.error("Could not retrieve any devices from PetKit servers")
        raise NoDevicesError
    return True


class NoDevicesError(Exception):
    """ No Devices from PetKit API. """

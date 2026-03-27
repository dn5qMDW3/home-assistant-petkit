"""Text platform for PetKit integration."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PetKitDataUpdateCoordinator
from .entity import PetKitFeederEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set Up PetKit Text Entities."""

    coordinator: PetKitDataUpdateCoordinator = entry.runtime_data

    text_entities = []

    for feeder_id, feeder_data in coordinator.data.feeders.items():

        # D4s Feeder
        if feeder_data.type == 'd4s':
            text_entities.append(
                ManualFeed(coordinator, feeder_id)
            )
    async_add_entities(text_entities)

class ManualFeed(PetKitFeederEntity, TextEntity):
    """Representation of manual feeding amount selector."""

    _attr_icon = 'mdi:bowl-mix'
    _attr_native_max = 5
    _attr_native_min = 3

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "manual_feed")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    @property
    def pattern(self) -> str:
        """Check validity with regex pattern."""
        return "^([0-9]|10),([0-9]|10)$"

    @property
    def native_value(self) -> str:
        """Always reset to 0,0"""
        return "0,0"

    async def async_set_value(self, value: str) -> None:
        """Set manual feeding amount."""

        portions = value.split(',')
        await self.coordinator.client.dual_hopper_manual_feeding(self.feeder_data, int(portions[0]), int(portions[1]))
        await self.coordinator.async_request_refresh()

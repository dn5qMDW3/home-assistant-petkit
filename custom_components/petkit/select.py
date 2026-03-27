"""Select platform for PetKit integration."""
from __future__ import annotations

import asyncio

from petkitaio.constants import FeederSetting, LitterBoxSetting
from petkitaio.exceptions import BluetoothError

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CLEANING_INTERVAL_NAMED,
    FEEDER_MANUAL_FEED_OPTIONS,
    LIGHT_BRIGHTNESS_COMMAND,
    LIGHT_BRIGHTNESS_NAMED,
    LIGHT_BRIGHTNESS_OPTIONS,
    LITTER_TYPE_NAMED,
    MANUAL_FEED_NAMED,
    MINI_FEEDER_MANUAL_FEED_OPTIONS,
    WF_MODE_COMMAND,
    WF_MODE_NAMED,
    WF_MODE_OPTIONS,
)
from .coordinator import PetKitDataUpdateCoordinator
from .entity import PetKitFeederEntity, PetKitLitterBoxEntity, PetKitWaterFountainEntity
from .exceptions import PetKitBluetoothError

LIGHT_BRIGHTNESS_TO_PETKIT = {v: k for (k, v) in LIGHT_BRIGHTNESS_COMMAND.items()}
LIGHT_BRIGHTNESS_TO_PETKIT_NUMBERED = {v: k for (k, v) in LIGHT_BRIGHTNESS_NAMED.items()}
WF_MODE_TO_PETKIT = {v: k for (k, v) in WF_MODE_COMMAND.items()}
WF_MODE_TO_PETKIT_NUMBERED = {v: k for (k, v) in WF_MODE_NAMED.items()}
MANUAL_FEED_TO_PETKIT = {v: k for (k, v) in MANUAL_FEED_NAMED.items()}
CLEANING_INTERVAL_TO_PETKIT = {v: k for (k, v) in CLEANING_INTERVAL_NAMED.items()}
LITTER_TYPE_TO_PETKIT = {v: k for (k, v) in LITTER_TYPE_NAMED.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set Up PetKit Select Entities."""

    coordinator: PetKitDataUpdateCoordinator = entry.runtime_data

    selects = []

    for wf_id, wf_data in coordinator.data.water_fountains.items():
        # Water Fountains (W5)
        selects.extend((
            WFLightBrightness(coordinator, wf_id),
            WFMode(coordinator, wf_id),
        ))
    for feeder_id, feeder_data in coordinator.data.feeders.items():
        # D4 and Mini Feeders
        if feeder_data.type in ['d4', 'feedermini']:
            selects.append(
                ManualFeed(coordinator, feeder_id)
            )
        # D3 Feeder
        if feeder_data.type == 'd3':
            selects.append(
                Sound(coordinator, feeder_id)
            )

    # Litter boxes
    for lb_id, lb_data in coordinator.data.litter_boxes.items():
        # Pura X & Pura MAX
        selects.extend((
            LBCleaningInterval(coordinator, lb_id),
            LBLitterType(coordinator, lb_id),
        ))

    async_add_entities(selects)

class WFLightBrightness(PetKitWaterFountainEntity, SelectEntity):
    """Representation of Water Fountain Light Brightness level."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "light_brightness")

    @property
    def icon(self) -> str:
        """Set icon."""

        brightness = self.wf_data.data['settings']['lampRingBrightness']

        if brightness == 1:
            return 'mdi:lightbulb-on-30'
        if brightness == 2:
            return 'mdi:lightbulb-on-50'
        return 'mdi:lightbulb-on'

    @property
    def available(self) -> bool:
        """Determine if device is available.

        Return true if light is on
        """

        return self.wf_data.data['settings']['lampRingSwitch'] == 1

    @property
    def current_option(self) -> str:
        """Returns currently active brightness setting."""

        current_brightness = self.wf_data.data['settings']['lampRingBrightness']
        return LIGHT_BRIGHTNESS_NAMED[current_brightness]

    @property
    def options(self) -> list[str]:
        """Return list of all available brightness levels."""

        return LIGHT_BRIGHTNESS_OPTIONS

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        if not self.coordinator.client.use_ble_relay:
            raise HomeAssistantError(f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}')
        if not self.wf_data.group_relay:
            raise HomeAssistantError(
                f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}. '
                f'PetKit did not return a valid relay device. If you do have a relay device, '
                f'it may temporarily be offline.'
            )

        ha_to_petkit = LIGHT_BRIGHTNESS_TO_PETKIT.get(option)
        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, ha_to_petkit)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try setting light brightness again.')
        else:
            self.wf_data.data['settings']['lampRingBrightness'] = LIGHT_BRIGHTNESS_TO_PETKIT_NUMBERED.get(option)
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

class WFMode(PetKitWaterFountainEntity, SelectEntity):
    """Representation of Water Fountain mode."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "mode")

    @property
    def icon(self) -> str:
        """Set icon."""

        mode = self.wf_data.data['mode']

        if mode == 1:
            return 'mdi:waves'
        if mode == 2:
            return 'mdi:brain'

    @property
    def available(self) -> bool:
        """Determine if device is available."""

        return True

    @property
    def current_option(self) -> str:
        """Returns currently active mode."""

        mode = self.wf_data.data['mode']
        return WF_MODE_NAMED[mode]

    @property
    def options(self) -> list[str]:
        """Return list of all available modes."""

        return WF_MODE_OPTIONS

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        if not self.coordinator.client.use_ble_relay:
            raise HomeAssistantError(f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}')
        if not self.wf_data.group_relay:
            raise HomeAssistantError(
                f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}. '
                f'PetKit did not return a valid relay device. If you do have a relay device, '
                f'it may temporarily be offline.'
            )

        ha_to_petkit = WF_MODE_TO_PETKIT.get(option)
        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, ha_to_petkit)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try setting mode again.')
        else:
            self.wf_data.data['mode'] = WF_MODE_TO_PETKIT_NUMBERED.get(option)
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

class ManualFeed(PetKitFeederEntity, SelectEntity):
    """Representation of manual feeding amount selector."""

    _attr_icon = 'mdi:bowl-mix'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "manual_feed")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    @property
    def current_option(self) -> str:
        """Returns blank option by default."""

        return MANUAL_FEED_NAMED[0]

    @property
    def options(self) -> list[str]:
        """Return list of all available manual feed amounts."""

        if self.feeder_data.type == 'feedermini':
            return MINI_FEEDER_MANUAL_FEED_OPTIONS
        else:
            return FEEDER_MANUAL_FEED_OPTIONS

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        ha_to_petkit = MANUAL_FEED_TO_PETKIT.get(option)

        await self.coordinator.client.manual_feeding(self.feeder_data, ha_to_petkit)
        await self.coordinator.async_request_refresh()


class Sound(PetKitFeederEntity, SelectEntity):
    """Representation of D3 Sound selection."""

    _attr_icon = 'mdi:surround-sound'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "sound")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    @property
    def current_option(self) -> str:
        """Return currently selected sound."""

        available_sounds = self.feeder_data.sound_list
        current_sound_id = self.feeder_data.data['settings']['selectedSound']
        return available_sounds[current_sound_id]

    @property
    def options(self) -> list[str]:
        """Return list of all available sound names."""

        available_sounds = self.feeder_data.sound_list
        sound_names = list(available_sounds.values())
        return sound_names

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        available_sounds = self.feeder_data.sound_list
        NAME_TO_SOUND_ID = {v: k for (k, v) in available_sounds.items()}
        ha_to_petkit = NAME_TO_SOUND_ID.get(option)

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SELECTED_SOUND, ha_to_petkit)
        self.feeder_data.data['settings']['selectedSound'] = ha_to_petkit
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBCleaningInterval(PetKitLitterBoxEntity, SelectEntity):
    """Representation of litter box cleaning interval."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "cleaning_interval")

    @property
    def icon(self) -> str:
        """Set icon."""

        if self.lb_data.device_detail['settings']['autoIntervalMin'] == 0:
            return 'mdi:timer-off'
        else:
            return 'mdi:timer'

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        kitten_mode_off = self.lb_data.device_detail['settings']['kitten'] == 0
        auto_clean = self.lb_data.device_detail['settings']['autoWork'] == 1
        avoid_repeat = self.lb_data.device_detail['settings']['avoidRepeat'] == 1

        if self.lb_data.device_detail['state']['pim'] != 0:
            return kitten_mode_off and auto_clean and avoid_repeat
        return False

    @property
    def current_option(self) -> str:
        """Return currently selected interval."""

        return CLEANING_INTERVAL_NAMED[self.lb_data.device_detail['settings']['autoIntervalMin']]

    @property
    def options(self) -> list[str]:
        """Return list of all available intervals."""

        intervals = list(CLEANING_INTERVAL_NAMED.values())
        return intervals

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        ha_to_petkit = CLEANING_INTERVAL_TO_PETKIT.get(option)

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.CLEAN_INTERVAL, ha_to_petkit)
        self.lb_data.device_detail['settings']['autoIntervalMin'] = ha_to_petkit
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBLitterType(PetKitLitterBoxEntity, SelectEntity):
    """Representation of litter box litter type."""

    _attr_icon = 'mdi:grain'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "litter_type")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.lb_data.device_detail['state']['pim'] != 0

    @property
    def current_option(self) -> str:
        """Return currently selected type."""

        return LITTER_TYPE_NAMED[self.lb_data.device_detail['settings']['sandType']]

    @property
    def options(self) -> list[str]:
        """Return list of all available litter types."""

        litter_types = list(LITTER_TYPE_NAMED.values())
        return litter_types

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        ha_to_petkit = LITTER_TYPE_TO_PETKIT.get(option)

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.SAND_TYPE, ha_to_petkit)
        self.lb_data.device_detail['settings']['sandType'] = ha_to_petkit
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

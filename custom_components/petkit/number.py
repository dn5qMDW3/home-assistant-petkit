"""Number platform for PetKit integration."""
from __future__ import annotations

from petkitaio.constants import FeederSetting, LitterBoxSetting, PetSetting
from petkitaio.exceptions import PetKitError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_system import METRIC_SYSTEM

from .coordinator import PetKitDataUpdateCoordinator
from .entity import PetKitFeederEntity, PetKitLitterBoxEntity, PetKitPetEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set Up PetKit Number Entities."""

    coordinator: PetKitDataUpdateCoordinator = entry.runtime_data

    numbers = []

    # Pets
    for pet_id, pet_data in coordinator.data.pets.items():
        numbers.append(
            PetWeight(coordinator, pet_id)
        )

    for feeder_id, feeder_data in coordinator.data.feeders.items():
        # Only D3 Feeder
        if feeder_data.type == 'd3':
            numbers.extend((
                Surplus(coordinator, feeder_id),
                Volume(coordinator, feeder_id),
                ManualFeed(coordinator, feeder_id),
            ))

        # Only D4s Feeder
        if feeder_data.type == 'd4s':
            numbers.append(
                MinEatingDuration(coordinator, feeder_id)
            )

        # Fresh Element Feeder
        if feeder_data.type == 'feeder':
            numbers.append(
                FreshElementManualFeed(coordinator, feeder_id)
            )

    for lb_id, lb_data in coordinator.data.litter_boxes.items():
        # Pura X & Pura MAX
        numbers.append(
            LBCleaningDelay(coordinator, lb_id)
        )
        # Pura MAX
        if lb_data.type == 't4':
            numbers.append(
                LBStopTime(coordinator, lb_id)
            )

    async_add_entities(numbers)


class PetWeight(PetKitPetEntity, NumberEntity):
    """Representation of Pet Weight."""

    _attr_device_class = NumberDeviceClass.WEIGHT
    _attr_mode = NumberMode.BOX
    _attr_native_step = 0.1

    def __init__(self, coordinator, pet_id):
        super().__init__(coordinator, pet_id, "set_weight")

    @property
    def entity_picture(self) -> str:
        """Grab associated pet picture."""

        if 'avatar' in self.pet_data.data:
            return self.pet_data.data['avatar']
        return None

    @property
    def icon(self) -> str:
        """Set icon if the pet doesn't have an avatar."""

        if 'avatar' in self.pet_data.data:
            return None
        return 'mdi:weight'

    @property
    def native_value(self) -> float:
        """Returns current weight."""

        pet_weight = self.pet_data.data['weight']
        if self.hass.config.units is METRIC_SYSTEM:
            return pet_weight
        return round((pet_weight * 2.2046226), 1)

    @property
    def native_unit_of_measurement(self) -> UnitOfMass:
        """Return kilograms or pounds."""

        if self.hass.config.units is METRIC_SYSTEM:
            return UnitOfMass.KILOGRAMS
        return UnitOfMass.POUNDS

    @property
    def native_min_value(self) -> float:
        """Return minimum allowed value."""

        if self.hass.config.units is METRIC_SYSTEM:
            return 1.0
        return 2.2

    @property
    def native_max_value(self) -> float:
        """Return max value allowed."""

        if self.hass.config.units is METRIC_SYSTEM:
            return 150.0
        return 330.0

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""

        if self.hass.config.units is METRIC_SYSTEM:
            # Always send value with one decimal point in case user sends more decimal points or none
            converted_value = round(value, 1)
        else:
            converted_value = round((value * 0.4535924), 1)
        await self.coordinator.client.update_pet_settings(self.pet_data, PetSetting.WEIGHT, converted_value)
        await self.coordinator.async_request_refresh()


class Surplus(PetKitFeederEntity, NumberEntity):
    """Representation of D3 Feeder surplus amount."""

    _attr_icon = 'mdi:food-drumstick'
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_device_class = NumberDeviceClass.WEIGHT
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 20
    _attr_native_max_value = 100
    _attr_native_step = 10

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "surplus")

    @property
    def native_value(self) -> int:
        """Returns current surplus setting."""

        return self.feeder_data.data['settings']['surplus']

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SURPLUS, int(value))
        self.feeder_data.data['settings']['surplus'] = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class Volume(PetKitFeederEntity, NumberEntity):
    """Representation of D3 Feeder speaker volume."""

    _attr_icon = 'mdi:volume-high'
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 1
    _attr_native_max_value = 9
    _attr_native_step = 1

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "volume")

    @property
    def native_value(self) -> int:
        """Returns current volume setting."""

        return self.feeder_data.data['settings']['volume']

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.VOLUME, int(value))
        self.feeder_data.data['settings']['volume'] = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class ManualFeed(PetKitFeederEntity, NumberEntity):
    """Representation of D3 Feeder manual feeding."""

    _attr_icon = 'mdi:bowl-mix'
    _attr_native_value = 4
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_device_class = NumberDeviceClass.WEIGHT
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 4
    _attr_native_max_value = 200
    _attr_native_step = 1

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "manual_feed")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""

        if (value < 5) or (value > 200):
            raise PetKitError(f'{self.feeder_data.data["name"]} can only accept manual feeding amounts between 5 to 200 grams')
        else:
            await self.coordinator.client.manual_feeding(self.feeder_data, int(value))
            await self.coordinator.async_request_refresh()


class LBCleaningDelay(PetKitLitterBoxEntity, NumberEntity):
    """Representation of litter box cleaning delay."""

    _attr_icon = 'mdi:motion-pause'
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = 60
    _attr_native_step = 1

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "cleaning_delay")

    @property
    def native_value(self) -> int:
        """Returns currently set delay in minutes."""

        return (self.lb_data.device_detail['settings']['stillTime'] / 60)

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        kitten_mode_off = self.lb_data.device_detail['settings']['kitten'] == 0
        auto_clean = self.lb_data.device_detail['settings']['autoWork'] == 1

        if self.lb_data.device_detail['state']['pim'] != 0:
            return kitten_mode_off and auto_clean
        return False

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""

        seconds = int(value * 60)
        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DELAY_CLEAN_TIME, seconds)
        self.lb_data.device_detail['settings']['stillTime'] = seconds
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class MinEatingDuration(PetKitFeederEntity, NumberEntity):
    """Representation of D4s shortest eating duration."""

    _attr_icon = 'mdi:clock-digital'
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 3
    _attr_native_max_value = 60
    _attr_native_step = 1

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "min_eating_duration")

    @property
    def native_value(self) -> int:
        """Returns current timer setting."""

        return self.feeder_data.data['settings']['shortest']

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.MIN_EAT_DURATION, int(value))
        self.feeder_data.data['settings']['shortest'] = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class FreshElementManualFeed(PetKitFeederEntity, NumberEntity):
    """Representation of Fresh Element feeder manual feeding."""

    _attr_icon = 'mdi:bowl-mix'
    _attr_native_value = 0
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_device_class = NumberDeviceClass.WEIGHT
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = 400
    _attr_native_step = 20

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "manual_feed")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""

        if (value < 20) or (value > 400):
            raise PetKitError(f'{self.feeder_data.data["name"]} can only accept manual feeding amounts between 20 to 400 grams')
        else:
            await self.coordinator.client.manual_feeding(self.feeder_data, int(value))
            await self.coordinator.async_request_refresh()


class LBStopTime(PetKitLitterBoxEntity, NumberEntity):
    """Representation of litter box emergency stop timeout."""

    _attr_native_min_value = 60
    _attr_native_max_value = 900
    _attr_native_step = 60
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = 'mdi:timer-stop'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "stop_time")

    @property
    def native_value(self) -> int:
        """Return current stop time."""
        return self.lb_data.device_detail['settings'].get('stopTime', 600)

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_set_native_value(self, value: int) -> None:
        """Update the current value."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.STOP_TIME, int(value))
        self.lb_data.device_detail['settings']['stopTime'] = int(value)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

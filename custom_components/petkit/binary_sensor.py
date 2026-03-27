"""Binary Sensor platform for PetKit integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PetKitDataUpdateCoordinator
from .entity import PetKitFeederEntity, PetKitLitterBoxEntity, PetKitWaterFountainEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set Up PetKit Binary Sensor Entities."""

    coordinator: PetKitDataUpdateCoordinator = entry.runtime_data

    binary_sensors = []

    for wf_id, wf_data in coordinator.data.water_fountains.items():
        # Water Fountains (W5)
        binary_sensors.append(
            WFWater(coordinator, wf_id)
        )

    for feeder_id, feeder_data in coordinator.data.feeders.items():

        #All feeders except D4s
        if feeder_data.type != 'd4s':
            binary_sensors.append(
                FoodLevel(coordinator, feeder_id)
            )

        # D4 and D4s feeders
        if feeder_data.type in ['d4', 'd4s']:
            binary_sensors.append(
                BatteryInstalled(coordinator, feeder_id)
            )

        # D4s Feeder
        if feeder_data.type == 'd4s':
            binary_sensors.extend((
                FoodLevelHopper1(coordinator, feeder_id),
                FoodLevelHopper2(coordinator, feeder_id)
                ))

        # D3 Feeder
        if feeder_data.type == 'd3':
            binary_sensors.append(
                BatteryCharging(coordinator, feeder_id)
            )

    # Litter boxes
    for lb_id, lb_data in coordinator.data.litter_boxes.items():
        # Pura X & Pura MAX
        if lb_data.type in ['t3', 't4']:
            binary_sensors.extend((
                LBBinFull(coordinator, lb_id),
                LBLitterLack(coordinator, lb_id),
            ))
        # Pura X & Pura MAX with Pura Air
        if (lb_data.type == 't3') or ('k3Device' in lb_data.device_detail):
            binary_sensors.append(
                LBDeodorizerLack(coordinator, lb_id)
            )
        # Pura X
        if lb_data.type == 't3':
            binary_sensors.append(
                LBManuallyPaused(coordinator, lb_id)
            )

    async_add_entities(binary_sensors)


class WFWater(PetKitWaterFountainEntity, BinarySensorEntity):
    """Representation of Water Fountain lack of water warning."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "water_level")

    @property
    def is_on(self) -> bool:
        """Return True if water needs to be added."""
        return self.wf_data.data['lackWarning'] == 1

    @property
    def icon(self) -> str:
        """Set icon."""
        if self.wf_data.data['lackWarning'] == 1:
            return 'mdi:water-alert'
        else:
            return 'mdi:water'


class FoodLevel(PetKitFeederEntity, BinarySensorEntity):
    """Representation of Feeder lack of food warning."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "food_level")

    @property
    def is_on(self) -> bool:
        """Return True if food needs to be added."""
        if self.feeder_data.type == 'd3':
            return self.feeder_data.data['state']['food'] < 2
        # The food key for the Fresh Element represents grams left
        return self.feeder_data.data['state']['food'] == 0

    @property
    def icon(self) -> str:
        """Set icon."""
        if self.feeder_data.type == 'd3':
            if self.feeder_data.data['state']['food'] < 2:
                return 'mdi:food-drumstick-off'
            else:
                return 'mdi:food-drumstick'
        if self.feeder_data.data['state']['food'] == 0:
            return 'mdi:food-drumstick-off'
        else:
            return 'mdi:food-drumstick'


class BatteryInstalled(PetKitFeederEntity, BinarySensorEntity):
    """Representation of if Feeder has batteries installed."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:battery'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "battery_installed")

    @property
    def is_on(self) -> bool:
        """Return True if battery installed."""
        return self.feeder_data.data['state']['batteryPower'] == 1


class BatteryCharging(PetKitFeederEntity, BinarySensorEntity):
    """Representation of if Feeder battery is charging."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_icon = 'mdi:battery'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "battery_charging")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "battery"

    @property
    def is_on(self) -> bool:
        """Return True if battery is charging."""
        return self.feeder_data.data['state']['charge'] > 1


class LBBinFull(PetKitLitterBoxEntity, BinarySensorEntity):
    """Representation of litter box wastebin full or not."""

    _attr_icon = 'mdi:delete'
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "wastebin")

    @property
    def is_on(self) -> bool:
        """Return True if wastebin is full."""
        return self.lb_data.device_detail['state']['boxFull']


class LBLitterLack(PetKitLitterBoxEntity, BinarySensorEntity):
    """Representation of litter box lacking sand."""

    _attr_icon = 'mdi:landslide'
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "litter_lack")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "litter"

    @property
    def is_on(self) -> bool:
        """Return True if litter is empty."""
        return self.lb_data.device_detail['state']['sandLack']


class LBDeodorizerLack(PetKitLitterBoxEntity, BinarySensorEntity):
    """Representation of litter box lacking deodorizer."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "deodorizer_lack")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        #Pura Air
        if 'k3Device' in self.lb_data.device_detail:
            return "pura_air_liquid"
        #Pura X
        else:
            return "deodorizer"

    @property
    def icon(self) -> str:
        """Set icon."""
        #Pura Air
        if 'k3Device' in self.lb_data.device_detail:
            return 'mdi:cup'
        #Pura X
        else:
            return 'mdi:spray'

    @property
    def is_on(self) -> bool:
        """Return True if deodorizer is empty."""
        return self.lb_data.device_detail['state']['liquidLack']

    @property
    def available(self) -> bool:
        """Determine if entity is available.

        Return true if there is a Pura Air
        device associated or this is a Pura X.
        """
        if self.lb_data.type == 't4':
            return 'k3Device' in self.lb_data.device_detail
        else:
            return True


class LBManuallyPaused(PetKitLitterBoxEntity, BinarySensorEntity):
    """Representation of if litter box is manually paused by user."""

    _attr_icon = 'mdi:pause'
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "manually_paused")

    @property
    def is_on(self) -> bool:
        """Return True if manually paused."""
        return self.lb_data.manually_paused


class FoodLevelHopper1(PetKitFeederEntity, BinarySensorEntity):
    """Representation of Feeder lack of food warning for Hopper 1."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "food_level_hopper_1")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "food_level_hopper_one"

    @property
    def is_on(self) -> bool:
        """Return True if food needs to be added."""
        return self.feeder_data.data['state']['food1'] < 1

    @property
    def icon(self) -> str:
        """Set icon."""
        if self.feeder_data.data['state']['food1'] == 0:
            return 'mdi:food-drumstick-off'
        else:
            return 'mdi:food-drumstick'


class FoodLevelHopper2(PetKitFeederEntity, BinarySensorEntity):
    """Representation of Feeder lack of food warning for Hopper 2."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "food_level_hopper_2")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "food_level_hopper_two"

    @property
    def is_on(self) -> bool:
        """Return True if food needs to be added."""
        return self.feeder_data.data['state']['food2'] < 1

    @property
    def icon(self) -> str:
        """Set icon."""
        if self.feeder_data.data['state']['food2'] == 0:
            return 'mdi:food-drumstick-off'
        else:
            return 'mdi:food-drumstick'

"""Sensor platform for PetKit integration."""
from __future__ import annotations

from datetime import datetime
from math import floor
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import(
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PetKitDataUpdateCoordinator
from .entity import (
    PetKitFeederEntity,
    PetKitLitterBoxEntity,
    PetKitPetEntity,
    PetKitPurifierEntity,
    PetKitWaterFountainEntity,
)
from .litter_events import (
    EVENT_DESCRIPTION,
    EVENT_TYPE_NAMED,
    MAX_EVENT_DESCRIPTION,
    MAX_EVENT_TYPES,
    MAX_EVENT_TYPE_NAMED,
    VALID_EVENT_TYPES
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set Up PetKit Sensor Entities."""

    coordinator: PetKitDataUpdateCoordinator = entry.runtime_data

    sensors = []

    for wf_id, wf_data in coordinator.data.water_fountains.items():
        # Water Fountains (W5)
        sensors.extend((
            WFEnergyUse(coordinator, wf_id),
            WFLastUpdate(coordinator, wf_id),
            WFFilter(coordinator, wf_id),
            WFPurifiedWater(coordinator, wf_id),
        ))

    for feeder_id, feeder_data in coordinator.data.feeders.items():
        # All Feeders
        sensors.extend((
            FeederStatus(coordinator, feeder_id),
            FeederDesiccant(coordinator, feeder_id),
            FeederBattStatus(coordinator, feeder_id),
            FeederRSSI(coordinator, feeder_id),
            FeederError(coordinator, feeder_id),
        ))

        # D3 & D4
        if feeder_data.type in ['d3', 'd4']:
            sensors.extend((
                TimesDispensed(coordinator, feeder_id),
                TotalPlanned(coordinator, feeder_id),
                PlannedDispensed(coordinator, feeder_id),
                TotalDispensed(coordinator, feeder_id),
            ))

        # D4 Feeder
        if feeder_data.type == 'd4':
            sensors.append(
                ManualDispensed(coordinator, feeder_id)
            )

        #D3 Feeder
        if feeder_data.type == 'd3':
            sensors.extend((
                AmountEaten(coordinator, feeder_id),
                TimesEaten(coordinator, feeder_id),
                FoodInBowl(coordinator, feeder_id),
            ))

        # D4s Feeder
        if feeder_data.type == 'd4s':
            sensors.extend((
                TimesEaten(coordinator, feeder_id),
                TimesDispensed(coordinator, feeder_id),
                AvgEatingTime(coordinator, feeder_id),
                ManualDispensedHopper1(coordinator, feeder_id),
                ManualDispensedHopper2(coordinator, feeder_id),
                TotalPlannedHopper1(coordinator, feeder_id),
                TotalPlannedHopper2(coordinator, feeder_id),
                PlannedDispensedHopper1(coordinator, feeder_id),
                PlannedDispensedHopper2(coordinator, feeder_id),
                TotalDispensedHopper1(coordinator, feeder_id),
                TotalDispensedHopper2(coordinator, feeder_id)
            ))

        # Fresh Element Feeder
        if feeder_data.type == 'feeder':
            sensors.append(
                FoodLeft(coordinator, feeder_id)
            )

    # Litter boxes
    for lb_id, lb_data in coordinator.data.litter_boxes.items():
        #Pura Air device for MAX litter box
        if (lb_data.type == 't4') and ('k3Device' in lb_data.device_detail):
            sensors.extend((
                PuraAirBattery(coordinator, lb_id),
                PuraAirLiquid(coordinator, lb_id)
            ))
        # Pura X & MAX
        if lb_data.type in ['t3', 't4']:
            sensors.extend((
                LBDeodorizerLevel(coordinator, lb_id),
                LBLitterLevel(coordinator, lb_id),
                LBLitterWeight(coordinator, lb_id),
                LBRSSI(coordinator, lb_id),
                LBError(coordinator, lb_id),
                LBTimesUsed(coordinator, lb_id),
                LBAverageUse(coordinator, lb_id),
                LBTotalUse(coordinator, lb_id),
                LBLastUsedBy(coordinator, lb_id)
            ))
        # Pura X
        if lb_data.type == 't3':
            sensors.append(
                LBLastEvent(coordinator, lb_id)
            )
        # Pura MAX
        if lb_data.type == 't4':
            sensors.extend((
                MAXLastEvent(coordinator, lb_id),
                MAXWorkState(coordinator, lb_id)
            ))

    # Pets
    for pet_id, pet_data in coordinator.data.pets.items():
        # Only add sensor for cats that have litter box(s)
        if (pet_data.type == 'Cat') and coordinator.data.litter_boxes:
            sensors.extend((
                PetRecentWeight(coordinator, pet_id),
                PetLastUseDuration(coordinator, pet_id),
            ))

    #Purifiers
    for purifier_id, purifier_data in coordinator.data.purifiers.items():
        sensors.extend((
            PurifierError(coordinator, purifier_id),
            PurifierHumidity(coordinator, purifier_id),
            PurifierTemperature(coordinator, purifier_id),
            AirPurified(coordinator, purifier_id),
            PurifierRSSI(coordinator, purifier_id),
            PurifierLiquid(coordinator, purifier_id)
        ))
    async_add_entities(sensors)


class WFEnergyUse(PetKitWaterFountainEntity, SensorEntity):
    """Representation of energy used by water fountain today."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "energy_usage")

    @property
    def native_value(self) -> float:
        """Return total energy usage in kWh."""

        todayPumpRunTime = self.wf_data.data['todayPumpRunTime']
        energy_usage = round(((0.75 * todayPumpRunTime) / 3600000), 4)
        return energy_usage


class WFLastUpdate(PetKitWaterFountainEntity, SensorEntity):
    """Representation of time water fountain data was last updated."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "last_update")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "last_data_update"

    @property
    def native_value(self) -> datetime:
        """Return date/time of last water fountain data update.

        This is only expected to change if the user has a valid relay.
        Those without a relay will need to connect to the water fountain
        via bluetooth to get the data to update.
        """

        last_update = self.wf_data.data['updateAt']
        return datetime.fromisoformat(last_update.replace('.000Z', '+00:00'))

    @property
    def available(self) -> bool:
        """Determine if device is available.

        Return true if a date/time is specified
        in the updateAt key.
        """

        return bool(self.wf_data.data['updateAt'])


class WFFilter(PetKitWaterFountainEntity, SensorEntity):
    """Representation of water fountain filter percentage left."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "filter_percent")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "filter"

    @property
    def native_value(self) -> int:
        """Return current filter percent left."""

        return self.wf_data.data['filterPercent']

    @property
    def icon(self) -> str:
        """Set filter icon."""

        if self.wf_data.data['filterPercent'] == 0:
            return 'mdi:filter-off'
        else:
            return 'mdi:filter'


class WFPurifiedWater(PetKitWaterFountainEntity, SensorEntity):
    """Representation of amount of times water has been purified today"""

    _attr_icon = 'mdi:water-pump'
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "purified_water")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "purified_water_today"

    @property
    def native_value(self) -> int:
        """Return number of times water was purified today."""

        f = ((1.5 * self.wf_data.data['todayPumpRunTime'])/60)
        f2 = 2.0
        purified_today =  int((f/f2))
        return purified_today


class FeederStatus(PetKitFeederEntity, SensorEntity):
    """Representation of feeder status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "status")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "feeder_status"

    @property
    def native_value(self) -> str | None:
        """Return status of the feeder."""

        pim = self.feeder_data.data['state']['pim']
        if pim == 0:
            return 'offline'
        elif pim == 1:
            return 'normal'
        elif pim == 2:
            return 'on_batteries'
        else:
            return None

    @property
    def icon(self) -> str | None:
        """Set status icon."""

        pim = self.feeder_data.data['state']['pim']
        if pim == 0:
            return 'mdi:cloud-off'
        elif pim == 1:
            return 'mdi:cloud'
        elif pim == 2:
            return 'mdi:battery'
        else:
            return None


class FeederDesiccant(PetKitFeederEntity, SensorEntity):
    """Representation of feeder desiccant days remaining."""

    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = 'mdi:air-filter'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "desiccant_days")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "desiccant_days_remaining"

    @property
    def native_value(self) -> int:
        """Return days remaining."""

        return self.feeder_data.data['state']['desiccantLeftDays']


class FeederBattStatus(PetKitFeederEntity, SensorEntity):
    """Representation of feeder battery status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "battery_status")

    @property
    def native_value(self) -> str:
        """Return status of the feeder battery."""

        battery_level = self.feeder_data.data['state']['batteryStatus']
        if battery_level == 1:
            return "normal"
        else:
            return "low"

    @property
    def icon(self) -> str:
        """Set battery status icon."""

        battery_level = self.feeder_data.data['state']['batteryStatus']
        if battery_level == 1:
            return "mdi:battery"
        else:
            return "mdi:battery-alert-variant"

    @property
    def available(self) -> bool:
        """Set to True only if battery is being used.

        When Battery isn't being used the level is always 0
        """

        return self.feeder_data.data['state']['pim'] == 2


class TotalDispensed(PetKitFeederEntity, SensorEntity):
    """Representation of feeder total food dispensed."""

    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "total_dispensed")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "dispensed"

    @property
    def native_value(self) -> int:
        """Return total dispensed."""

        return self.feeder_data.data['state']['feedState']['realAmountTotal']


class TotalPlanned(PetKitFeederEntity, SensorEntity):
    """Representation of feeder total planned to be dispensed."""

    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "total_planned")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "planned"

    @property
    def native_value(self) -> int:
        """Return total planned."""

        return self.feeder_data.data['state']['feedState']['planAmountTotal']


class PlannedDispensed(PetKitFeederEntity, SensorEntity):
    """Representation of feeder planned that has been dispensed."""

    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "planned_dispensed")

    @property
    def native_value(self) -> int:
        """Return total planned dispensed."""

        return self.feeder_data.data['state']['feedState']['planRealAmountTotal']


class ManualDispensed(PetKitFeederEntity, SensorEntity):
    """Representation of feeder amount that has been manually dispensed."""

    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "manual_dispensed")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "manually_dispensed"

    @property
    def native_value(self) -> int:
        """Return total manually dispensed."""

        return self.feeder_data.data['state']['feedState']['addAmountTotal']


class TimesDispensed(PetKitFeederEntity, SensorEntity):
    """Representation of feeder amount of times food has been dispensed."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "times_dispensed")

    @property
    def native_value(self) -> int:
        """Return total times dispensed."""

        if self.feeder_data.type == 'd3':
            return len(self.feeder_data.data['state']['feedState']['feedTimes'])
        else:
            return self.feeder_data.data['state']['feedState']['times']


class FeederRSSI(PetKitFeederEntity, SensorEntity):
    """Representation of feeder WiFi connection strength."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_icon = 'mdi:wifi'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "feeder_rssi")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "rssi"

    @property
    def native_value(self) -> int:
        """Return RSSI measurement."""

        return self.feeder_data.data['state']['wifi']['rsq']


class AmountEaten(PetKitFeederEntity, SensorEntity):
    """Representation of amount eaten by pet today."""

    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "amount_eaten")

    @property
    def native_value(self) -> int:
        """Return total amount eaten."""

        return self.feeder_data.data['state']['feedState']['eatAmountTotal']


class TimesEaten(PetKitFeederEntity, SensorEntity):
    """Representation of amount of times pet ate today."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "times_eaten")

    @property
    def native_value(self) -> int:
        """Return total times eaten."""

        if self.feeder_data.type == 'd4s':
            return self.feeder_data.data['state']['feedState']['eatCount']
        else:
            return len(self.feeder_data.data['state']['feedState']['eatTimes'])


class FoodInBowl(PetKitFeederEntity, SensorEntity):
    """Representation of amount of food in D3 feeder bowl."""

    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "food_in_bowl")

    @property
    def native_value(self) -> int:
        """Return current amount of food in bowl."""

        return self.feeder_data.data['state']['weight']


class FeederError(PetKitFeederEntity, SensorEntity):
    """Representation of D3 feeder error."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:alert-circle'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "feeder_error")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "error"

    @property
    def native_value(self) -> str:
        """Return current error if there is one."""

        if 'errorMsg' in self.feeder_data.data['state']:
            return self.feeder_data.data['state']['errorMsg']
        else:
            return 'no_error'


class LBDeodorizerLevel(PetKitLitterBoxEntity, SensorEntity):
    """Representation of litter box deodorizer left."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "deodorizer_level")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""

        #Pura MAX uses N50 deodorizer and not liquid
        if self.lb_data.type == 't4':
            return "n50_odor_eliminator"
        else:
            return "deodorizer_level"

    @property
    def icon(self) -> str:
        """Set icon."""

        if self.lb_data.type == 't4':
            return 'mdi:air-filter'
        else:
            return 'mdi:spray-bottle'

    @property
    def native_value(self) -> int:
        """Return current percentage or days left."""

        #Pura MAX
        if self.lb_data.type == 't4':
            deodorant_days = self.lb_data.device_detail['state']['deodorantLeftDays']
            if deodorant_days < 1:
                return 0
            else:
                return deodorant_days
        #Pura X
        else:
            return self.lb_data.device_detail['state']['liquid']

    @property
    def native_unit_of_measurement(self) -> str | UnitOfTime:
        """Return percent or days as the native unit."""

        #Pura MAX
        if self.lb_data.type == 't4':
            return UnitOfTime.DAYS
        #Pura X
        else:
            return PERCENTAGE


class LBLitterLevel(PetKitLitterBoxEntity, SensorEntity):
    """Representation of litter box litter percentage left."""

    _attr_icon = 'mdi:landslide'
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "litter_level")

    @property
    def native_value(self) -> int:
        """Return current percentage."""

        return self.lb_data.device_detail['state']['sandPercent']


class LBLitterWeight(PetKitLitterBoxEntity, SensorEntity):
    """Representation of litter box litter weight."""

    _attr_icon = 'mdi:landslide'
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "litter_weight")

    @property
    def native_value(self) -> float:
        """Return current weight in Kg."""

        return round((self.lb_data.device_detail['state']['sandWeight'] / 1000), 1)


class LBRSSI(PetKitLitterBoxEntity, SensorEntity):
    """Representation of litter box wifi strength."""

    _attr_icon = 'mdi:wifi'
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "rssi")

    @property
    def native_value(self) -> int:
        """Return current signal strength."""

        return self.lb_data.device_detail['state']['wifi']['rsq']


class LBError(PetKitLitterBoxEntity, SensorEntity):
    """Representation of litter box error."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:alert-circle'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "error")

    @property
    def native_value(self) -> str:
        """Return current error if there is one."""

        if 'errorMsg' in self.lb_data.device_detail['state']:
            return self.lb_data.device_detail['state']['errorMsg']
        else:
            return 'no_error'


class LBTimesUsed(PetKitLitterBoxEntity, SensorEntity):
    """Representation of litter box usage count."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = 'mdi:counter'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "times_used")

    @property
    def native_value(self) -> int:
        """Return current usage count."""

        return self.lb_data.statistics['times']


class LBAverageUse(PetKitLitterBoxEntity, SensorEntity):
    """Representation of litter box average usage."""

    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = 'mdi:clock'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "average_use")

    @property
    def native_value(self) -> int:
        """Return current usage time average in seconds."""

        return self.lb_data.statistics['avgTime']


class LBTotalUse(PetKitLitterBoxEntity, SensorEntity):
    """Representation of litter box total usage."""

    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = 'mdi:clock'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "total_use")

    @property
    def native_value(self) -> int:
        """Return current usage time average in seconds."""

        return self.lb_data.statistics['totalTime']


class LBLastUsedBy(PetKitLitterBoxEntity, SensorEntity):
    """Representation of last pet to use the litter box."""

    _attr_icon = 'mdi:cat'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "last_used_by")

    @property
    def native_value(self) -> str:
        """Return last pet to use the litter box."""

        if self.lb_data.statistics['statisticInfo']:
            last_record = self.lb_data.statistics['statisticInfo'][-1]
            if last_record['petId'] == '0':
                return 'unknown_pet'
            else:
                return last_record['petName']
        else:
            return 'no_record_yet'


class LBLastEvent(PetKitLitterBoxEntity, SensorEntity):
    """Representation of Pura X last litter box event."""

    _attr_icon = 'mdi:calendar'
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "last_event")
        self.sub_events = None

    @property
    def native_value(self) -> str:
        """Return last litter box event from device record."""

        if self.lb_data.device_record:
            last_record = self.lb_data.device_record[-1]
            if last_record['subContent']:
                self.sub_events = self.sub_events_to_description(last_record['subContent'])
            else:
                self.sub_events = 'no_sub_events'
            event = self.result_to_description(last_record['eventType'], last_record)
            return event
        else:
            return 'no_events_yet'

    @property
    def extra_state_attributes(self):
        """Return sub events associated with the main event."""

        return {
            'sub_events': self.sub_events
        }

    def result_to_description(self, event_type: int, record: dict[str, Any]) -> str:
        """Return a description of the last event"""

        # Make sure event_type is valid
        if event_type not in VALID_EVENT_TYPES:
            return 'event_type_unknown'

        # Pet out events don't have result or reason
        if event_type != 10:
            result = record['content']['result']
            if 'startReason' in record['content']:
                reason = record['content']['startReason']

            if event_type == 5:
                if result == 2:
                    if 'error' in record['content']:
                        error = record['content']['error']
                    else:
                        return EVENT_TYPE_NAMED[event_type]

                    try:
                        description = EVENT_DESCRIPTION[event_type][result][reason][error]
                    except KeyError:
                        return EVENT_TYPE_NAMED[event_type]
                    return description

                else:
                    try:
                        description = EVENT_DESCRIPTION[event_type][result][reason]
                    except KeyError:
                        return EVENT_TYPE_NAMED[event_type]
                    return description

            if event_type in [6, 7]:
                if result == 2:
                    if 'error' in record['content']:
                        error = record['content']['error']
                    else:
                        return EVENT_TYPE_NAMED[event_type]

                    try:
                        description = EVENT_DESCRIPTION[event_type][result][error]
                    except KeyError:
                        return EVENT_TYPE_NAMED[event_type]
                    return description

                else:
                    try:
                        description = EVENT_DESCRIPTION[event_type][result]
                    except KeyError:
                        return EVENT_TYPE_NAMED[event_type]
                    return description

            if event_type == 8:
                try:
                    description = EVENT_DESCRIPTION[event_type][result][reason]
                except KeyError:
                    return EVENT_TYPE_NAMED[event_type]
                return description

        if event_type == 10:
            if (record['petId'] == '-2') or (record['petId'] == '-1'):
                name = 'Unknown'
            else:
                name = record['petName']
            return f'{name} used the litter box'

    def sub_events_to_description(self, sub_events: list[dict[str, Any]]) -> list[str]:
        """Create a list containing all of the sub events associated with an event to be used as attribute"""

        event_list: list[str] = []
        for event in sub_events:
            description = self.result_to_description(event['eventType'], event)
            event_list.append(description)
        return event_list


class PetRecentWeight(PetKitPetEntity, RestoreSensor):
    """Representation of most recent weight measured by litter box."""

    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, pet_id):
        super().__init__(coordinator, pet_id, "recent_weight")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "latest_weight"

    @property
    def litter_boxes(self) -> dict:
        """Handle coordinator Litter Boxes data."""

        return self.coordinator.data.litter_boxes

    @property
    def entity_picture(self) -> str | None:
        """Grab associated pet picture."""

        if 'avatar' in self.pet_data.data:
            return self.pet_data.data['avatar']
        else:
            return None

    @property
    def icon(self) -> str | None:
        """Set icon if the pet doesn't have an avatar."""

        if 'avatar' in self.pet_data.data:
            return None
        else:
            return 'mdi:weight'

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle entity update."""

        sorted_dict = self.grab_recent_weight()
        if sorted_dict:
            last_key = list(sorted_dict)[-1]
            latest_weight = sorted_dict[last_key]
            weight_calculation = round((latest_weight / 1000), 1)
            self._attr_native_value = weight_calculation
            self.async_write_ha_state()
        else:
            return

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        await super().async_added_to_hass()

        if last_state := await self.async_get_last_sensor_data():
            self._attr_native_value = last_state.native_value
        else:
            # If user is setting up the integration when there is no weight yet
            # for the current day, return 0.0
            self._attr_native_value = 0.0

    def grab_recent_weight(self) -> float:
        """Grab the most recent weight."""

        weight_dict: dict[int, int] = {}

        for lb_id, lb_data in self.litter_boxes.items():
            if lb_data.statistics['statisticInfo']:
                try:
                    final_idx = max(index for index, stat in enumerate(lb_data.statistics['statisticInfo']) if stat['petId'] == self.pet_data.id)
                except ValueError:
                    continue
                else:
                    last_stat = lb_data.statistics['statisticInfo'][final_idx]
                    weight = last_stat['petWeight']
                    time = last_stat['xTime']
                    weight_dict[time] = weight
        sorted_dict = dict(sorted(weight_dict.items()))
        return sorted_dict


class PetLastUseDuration(PetKitPetEntity, RestoreSensor):
    """Representation of most recent litter box use duration."""

    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, pet_id):
        super().__init__(coordinator, pet_id, "last_use_duration")

    @property
    def litter_boxes(self) -> dict:
        """Handle coordinator Litter Boxes data."""

        return self.coordinator.data.litter_boxes

    @property
    def entity_picture(self) -> str | None:
        """Grab associated pet picture."""

        if 'avatar' in self.pet_data.data:
            return self.pet_data.data['avatar']
        else:
            return None

    @property
    def icon(self) -> str | None:
        """Set icon if the pet doesn't have an avatar."""

        if 'avatar' in self.pet_data.data:
            return None
        else:
            return 'mdi:clock'

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle entity update."""

        sorted_dict = self.grab_recent_duration()
        if sorted_dict:
            last_key = list(sorted_dict)[-1]
            latest_duration = sorted_dict[last_key]
            self._attr_native_value = latest_duration
            self.async_write_ha_state()
        else:
            return

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        await super().async_added_to_hass()

        if last_state := await self.async_get_last_sensor_data():
            self._attr_native_value = last_state.native_value
        else:
            # If user is setting up the integration when there is no duration yet
            # for the current day, return 0
            self._attr_native_value = 0

    def grab_recent_duration(self) -> float:
        """Grab the most recent duration."""

        duration_dict: dict[int, int] = {}

        for lb_id, lb_data in self.litter_boxes.items():
            if lb_data.statistics['statisticInfo']:
                try:
                    final_idx = max(index for index, stat in enumerate(lb_data.statistics['statisticInfo']) if stat['petId'] == self.pet_data.id)
                # Handle if the pet didn't use the litter box
                except ValueError:
                    continue
                else:
                    last_stat = lb_data.statistics['statisticInfo'][final_idx]
                    duration = last_stat['petTotalTime']
                    time = last_stat['xTime']
                    duration_dict[time] = duration
        sorted_dict = dict(sorted(duration_dict.items()))
        return sorted_dict


class PuraAirBattery(PetKitLitterBoxEntity, SensorEntity):
    """Representation of Pura Air battery level."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "pura_air_battery")

    @property
    def native_value(self) -> int:
        """Return current battery percentage."""

        return self.lb_data.device_detail['k3Device']['battery']

    @property
    def available(self) -> bool:
        """Determine if device is available.

        Return true if there is a pura air
        device associated.
        """

        return 'k3Device' in self.lb_data.device_detail


class PuraAirLiquid(PetKitLitterBoxEntity, SensorEntity):
    """Representation of Pura Air liquid level."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = 'mdi:cup'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "pura_air_liquid")

    @property
    def native_value(self) -> int:
        """Return current liquid left."""

        return self.lb_data.device_detail['k3Device']['liquid']

    @property
    def available(self) -> bool:
        """Determine if device is available.

        Return true if there is a pura air
        device associated.
        """

        return 'k3Device' in self.lb_data.device_detail


class MAXLastEvent(PetKitLitterBoxEntity, SensorEntity):
    """Representation of last Pura MAX litter box event."""

    _attr_icon = 'mdi:calendar'
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "max_last_event")
        self.sub_events = None

    @property
    def native_value(self) -> str:
        """Return last litter box event from device record."""

        if self.lb_data.device_record:
            last_record = self.lb_data.device_record[-1]
            if last_record['subContent']:
                self.sub_events = self.sub_events_to_description(last_record['subContent'])
            else:
                self.sub_events = 'no_sub_events'
            event = self.result_to_description(last_record['eventType'], last_record)
            return event
        else:
            return 'no_events_yet'

    @property
    def extra_state_attributes(self):
        """Return sub events associated with the main event."""

        return {
            'sub_events': self.sub_events
        }

    def result_to_description(self, event_type: int, record: dict[str, Any]) -> str:
        """Return a description of the last event"""

        # Make sure event_type is valid
        if event_type not in MAX_EVENT_TYPES:
            return 'event_type_unknown'

        # Pet out events don't have result or reason
        if event_type != 10:
            result = record['content']['result']
            if 'startReason' in record['content']:
                reason = record['content']['startReason']

            if event_type == 5:
                if result == 2:
                    if 'error' in record['content']:
                        error = record['content']['error']
                    else:
                        return MAX_EVENT_TYPE_NAMED[event_type]

                    try:
                        description = MAX_EVENT_DESCRIPTION[event_type][result][reason][error]
                    except KeyError:
                        if reason == 0:
                            return 'auto_cleaning_failed_other'
                        elif reason == 1:
                            return 'scheduled_cleaning_failed_other'
                        else:
                            return 'manual_cleaning_failed_other'
                    return description

                else:
                    try:
                        description = MAX_EVENT_DESCRIPTION[event_type][result][reason]
                    except KeyError:
                        return MAX_EVENT_TYPE_NAMED[event_type]
                    return description

            if event_type in [6, 7]:
                if result == 2:
                    if 'error' in record['content']:
                        error = record['content']['error']
                    else:
                        return MAX_EVENT_TYPE_NAMED[event_type]

                    try:
                        description = MAX_EVENT_DESCRIPTION[event_type][result][error]
                    except KeyError:
                        if event_type == 6:
                            return 'litter_empty_failed_other'
                        else:
                            return 'reset_failed_other'
                    return description

                else:
                    try:
                        description = MAX_EVENT_DESCRIPTION[event_type][result]
                    except KeyError:
                        return MAX_EVENT_TYPE_NAMED[event_type]
                    return description

            if event_type == 8:
                try:
                    if result == 9:
                        return 'cat_stopped_odor'
                    else:
                        description = MAX_EVENT_DESCRIPTION[event_type][result][reason]
                except KeyError:
                    return MAX_EVENT_TYPE_NAMED[event_type]
                return description

            if event_type == 17:
                try:
                    description = MAX_EVENT_DESCRIPTION[event_type][result]
                except KeyError:
                    return MAX_EVENT_TYPE_NAMED[event_type]
                return description

        if event_type == 10:
            if (record['petId'] == '-2') or (record['petId'] == '-1'):
                name = 'Unknown'
            else:
                name = record['petName']
            return f'{name} used the litter box'

    def sub_events_to_description(self, sub_events: list[dict[str, Any]]) -> list[str]:
        """Create a list containing all the sub-events associated with an event to be used as attribute"""

        event_list: list[str] = []
        for event in sub_events:
            description = self.result_to_description(event['eventType'], event)
            event_list.append(description)
        return event_list


class MAXWorkState(PetKitLitterBoxEntity, SensorEntity):
    """Representation of current Pura MAX litter box state."""

    _attr_icon = 'mdi:account-hard-hat'
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "max_work_state")

    @property
    def native_value(self) -> str:
        """Return current litter box work state from device_detail."""

        if 'workState' in self.lb_data.device_detail['state']:
            work_state = self.lb_data.device_detail['state']['workState']

            if work_state['workMode'] == 0:
                work_process = work_state['workProcess']
                if work_process / 10 == 1:
                    return 'cleaning_litter_box'
                elif int(floor((work_process / 10))) == 2:
                    if work_process % 10 == 2:
                        if 'safeWarn' in work_state:
                            if work_state['safeWarn'] != 0:
                                if work_state['safeWarn'] == 1:
                                    return 'cleaning_paused_pet_entered'
                                else:
                                    return 'cleaning_paused_system_error'
                            if work_state['safeWarn'] == 0:
                                ### petInTime could be referring to key in state and not workState
                                if (pet_time := work_state.get('petInTime')) == 0:
                                    return 'cleaning_paused_pet_approach'
                                else:
                                    if pet_time:
                                        return 'cleaning_paused_pet_using'
                                    else:
                                        return 'unknown_safe_warn_state'
                    else:
                        return 'cleaning_litter_box_paused'
                elif work_process / 10 == 3:
                    return 'resetting_device'
                elif int(floor((work_process / 10))) == 4:
                    if work_process % 10 == 2:
                        if 'safeWarn' in work_state:
                            if work_state['safeWarn'] != 0:
                                if work_state['safeWarn'] == 1:
                                    return 'paused_pet_entered'
                                else:
                                    return 'paused_system_error'
                            if work_state['safeWarn'] == 0:
                                ### petInTime could be referring to key in state and not workState
                                if work_state['petInTime'] == 0:
                                    return 'paused_pet_approach'
                                else:
                                    return 'paused_pet_using'
                    else:
                        return 'litter_box_paused'
                else:
                    return 'cleaning_litter_box'
            if work_state['workMode'] == 1:
                work_process = work_state['workProcess']
                if work_process / 10 == 1:
                    return 'dumping_litter'
                if int(floor((work_process / 10))) == 2:
                    if work_process % 10 == 2:
                        if 'safeWarn' in work_state:
                            if work_state['safeWarn'] != 0:
                                if work_state['safeWarn'] == 1:
                                    return 'dumping_paused_pet_entered'
                                else:
                                    return 'dumping_paused_system_error'
                            if work_state['safeWarn'] == 0:
                                ### petInTime could be referring to key in state and not workState
                                if work_state['petInTime'] == 0:
                                    return 'dumping_paused_pet_approach'
                                else:
                                    return 'dumping_paused_pet_using'
                    else:
                        return 'dumping_litter_paused'
                if work_process / 10 == 3:
                    return 'resetting_device'
                if int(floor((work_process / 10))) == 4:
                    if work_process % 10 == 2:
                        if 'safeWarn' in work_state:
                            if work_state['safeWarn'] != 0:
                                if work_state['safeWarn'] == 1:
                                    return 'paused_pet_entered'
                                else:
                                    return 'paused_system_error'
                            if work_state['safeWarn'] == 0:
                                ### petInTime could be referring to key in state and not workState
                                if work_state['petInTime'] == 0:
                                    return 'paused_pet_approach'
                                else:
                                    return 'paused_pet_using'
                    else:
                        return 'litter_box_paused'
            if work_state['workMode'] == 3:
                return 'resetting'
            if work_state['workMode'] == 4:
                return 'leveling'
            if work_state['workMode'] == 5:
                return 'calibrating'
            if work_state['workMode'] == 9:
                work_process = work_state['workProcess']
                if work_process / 10 == 1:
                    return 'maintenance_mode'
                if int(floor((work_process / 10))) == 2:
                    if work_process % 10 == 2:
                        if 'safeWarn' in work_state:
                            if work_state['safeWarn'] != 0:
                                if work_state['safeWarn'] == 1:
                                    return 'maintenance_paused_pet_entered'
                                elif work_state['safeWarn'] == 3:
                                    return 'maintenance_paused_cover'
                                else:
                                    return 'maintenance_paused_system_error'
                            if work_state['safeWarn'] == 0:
                                ### petInTime could be referring to key in state and not workState
                                if work_state['petInTime'] == 0:
                                    return 'maintenance_paused_pet_approach'
                                else:
                                    return 'maintenance_paused_pet_using'
                    else:
                        return 'maintenance_paused'
                if work_process / 10 == 3:
                    return 'exit_maintenance'
                if int(floor((work_process / 10))) == 4:
                    if work_process % 10 == 2:
                        if 'safeWarn' in work_state:
                            if work_state['safeWarn'] != 0:
                                if work_state['safeWarn'] == 1:
                                    return 'maintenance_exit_paused_pet_entered'
                                elif work_state['safeWarn'] == 3:
                                    return 'maintenance_exit_paused_cover'
                                else:
                                    return 'maintenance_exit_paused_system_error'
                            if work_state['safeWarn'] == 0:
                                ### petInTime could be referring to key in state and not workState
                                if work_state['petInTime'] == 0:
                                    return 'maintenance_exit_paused_pet_approach'
                                else:
                                    return 'maintenance_exit_paused_pet_using'
                    else:
                        return 'maintenance_exit_paused'
        else:
            return 'idle'


class AvgEatingTime(PetKitFeederEntity, SensorEntity):
    """Representation of average time pet spent eating."""

    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:clock-digital'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "avg_eating_time")

    @property
    def native_value(self) -> int:
        """Return average eating time."""

        return self.feeder_data.data['state']['feedState']['eatAvg']


class ManualDispensedHopper1(PetKitFeederEntity, SensorEntity):
    """Representation of feeder amount that has been manually dispensed from hopper 1."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "manual_dispensed_hopp_1")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "manually_dispensed_hopp_one"

    @property
    def native_value(self) -> int:
        """Return total manually dispensed."""

        return self.feeder_data.data['state']['feedState']['addAmountTotal1']


class ManualDispensedHopper2(PetKitFeederEntity, SensorEntity):
    """Representation of feeder amount that has been manually dispensed from hopper 2."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "manual_dispensed_hopp_2")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "manually_dispensed_hopp_two"

    @property
    def native_value(self) -> int:
        """Return total manually dispensed."""

        return self.feeder_data.data['state']['feedState']['addAmountTotal2']


class TotalPlannedHopper1(PetKitFeederEntity, SensorEntity):
    """Representation of feeder total planned to be dispensed from hopper 1."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "total_planned_hopp_1")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "planned_hopp_one"

    @property
    def native_value(self) -> int:
        """Return total planned."""

        return self.feeder_data.data['state']['feedState']['planAmountTotal1']


class TotalPlannedHopper2(PetKitFeederEntity, SensorEntity):
    """Representation of feeder total planned to be dispensed from hopper 2."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "total_planned_hopp_2")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "planned_hopp_two"

    @property
    def native_value(self) -> int:
        """Return total planned."""

        return self.feeder_data.data['state']['feedState']['planAmountTotal2']


class PlannedDispensedHopper1(PetKitFeederEntity, SensorEntity):
    """Representation of feeder planned that has been dispensed from hopper 1."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "planned_dispensed_hopp_1")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "planned_dispensed_hopp_one"

    @property
    def native_value(self) -> int:
        """Return total planned dispensed."""

        return self.feeder_data.data['state']['feedState']['planRealAmountTotal1']


class PlannedDispensedHopper2(PetKitFeederEntity, SensorEntity):
    """Representation of feeder planned that has been dispensed from hopper 2."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "planned_dispensed_hopp_2")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "planned_dispensed_hopp_two"

    @property
    def native_value(self) -> int:
        """Return total planned dispensed."""

        return self.feeder_data.data['state']['feedState']['planRealAmountTotal2']


class TotalDispensedHopper1(PetKitFeederEntity, SensorEntity):
    """Representation of feeder total food dispensed from hopper 1."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "total_dispensed_hopp_1")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "dispensed_hopp_one"

    @property
    def native_value(self) -> int:
        """Return total dispensed."""

        return self.feeder_data.data['state']['feedState']['realAmountTotal1']


class TotalDispensedHopper2(PetKitFeederEntity, SensorEntity):
    """Representation of feeder total food dispensed from hopper 2."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:food-drumstick'

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "total_dispensed_hopp_2")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "dispensed_hopp_two"

    @property
    def native_value(self) -> int:
        """Return total dispensed."""

        return self.feeder_data.data['state']['feedState']['realAmountTotal2']


class PurifierError(PetKitPurifierEntity, SensorEntity):
    """Representation of Purifier error."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:alert-circle'

    def __init__(self, coordinator, purifier_id):
        super().__init__(coordinator, purifier_id, "purifier_error")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "error"

    @property
    def native_value(self) -> str:
        """Return current error if there is one."""

        if 'errorMsg' in self.purifier_data.device_detail['state']:
            return self.purifier_data.device_detail['state']['errorMsg']
        else:
            return 'no_error'


class PurifierHumidity(PetKitPurifierEntity, SensorEntity):
    """ Representation of Purifier Humidity """

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, purifier_id):
        super().__init__(coordinator, purifier_id, "purifier_humidity")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "humidity"

    @property
    def native_value(self) -> int:
        """ Return current humidity """

        return round((self.purifier_data.device_detail['state']['humidity'] / 10))


class PurifierTemperature(PetKitPurifierEntity, SensorEntity):
    """ Representation of Purifier Temperature """

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, purifier_id):
        super().__init__(coordinator, purifier_id, "purifier_temperature")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "temperature"

    @property
    def native_value(self) -> int:
        """ Return current temperature in Celsius """

        return round((self.purifier_data.device_detail['state']['temp'] / 10))


class AirPurified(PetKitPurifierEntity, SensorEntity):
    """ Representation of amount of air purified."""

    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator, purifier_id):
        super().__init__(coordinator, purifier_id, "air_purified")

    @property
    def native_value(self) -> int:
        """Return amount of air purified in cubic meters."""

        return round(self.purifier_data.device_detail['state']['refresh'])


class PurifierRSSI(PetKitPurifierEntity, SensorEntity):
    """Representation of purifier WiFi connection strength."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_icon = 'mdi:wifi'

    def __init__(self, coordinator, purifier_id):
        super().__init__(coordinator, purifier_id, "rssi")

    @property
    def native_value(self) -> int:
        """Return RSSI measurement."""

        return self.purifier_data.device_detail['state']['wifi']['rsq']


class PurifierLiquid(PetKitPurifierEntity, SensorEntity):
    """Representation of purifier liquid left."""

    _attr_icon = 'mdi:cup-water'
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, purifier_id):
        super().__init__(coordinator, purifier_id, "liquid")

    @property
    def native_value(self) -> int:
        """Return current percentage left"""

        return self.purifier_data.device_detail['state']['liquid']


class FoodLeft(PetKitFeederEntity, SensorEntity):
    """Representation of percent food left."""

    _attr_icon = 'mdi:food-drumstick'
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "food_left")

    @property
    def native_value(self) -> int:
        """Return current percentage left"""

        return self.feeder_data.data['state']['percent']

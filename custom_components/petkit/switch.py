"""Switch platform for PetKit integration."""
from __future__ import annotations

from typing import Any
import asyncio

from petkitaio.constants import FeederSetting, LitterBoxCommand, LitterBoxSetting, PurifierSetting, W5Command
from petkitaio.exceptions import BluetoothError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PetKitDataUpdateCoordinator
from .entity import PetKitFeederEntity, PetKitLitterBoxEntity, PetKitPurifierEntity, PetKitWaterFountainEntity
from .exceptions import PetKitBluetoothError


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set Up PetKit Switch Entities."""

    coordinator: PetKitDataUpdateCoordinator = entry.runtime_data

    switches = []

    for wf_id, wf_data in coordinator.data.water_fountains.items():
        # Water Fountains (W5)
        switches.extend((
            WFLight(coordinator, wf_id),
            WFPower(coordinator, wf_id),
            WFDisturb(coordinator, wf_id),
        ))

    for feeder_id, feeder_data in coordinator.data.feeders.items():
        # All Feeders
        switches.extend((
            IndicatorLight(coordinator, feeder_id),
            ChildLock(coordinator, feeder_id),
        ))

        # D4 and D4s Feeder
        if feeder_data.type in ['d4', 'd4s']:
            switches.extend((
                ShortageAlarm(coordinator, feeder_id),
                DispenseTone(coordinator, feeder_id),
            ))

        # D3 Feeder
        if feeder_data.type == 'd3':
            switches.extend((
                VoiceDispense(coordinator, feeder_id),
                DoNotDisturb(coordinator, feeder_id),
                SurplusControl(coordinator, feeder_id),
                SystemNotification(coordinator, feeder_id),
            ))

    # Litter boxes
    for lb_id, lb_data in coordinator.data.litter_boxes.items():
        # Pura X & Pura MAX
        switches.extend((
            LBAutoClean(coordinator, lb_id),
            LBAvoidRepeat(coordinator, lb_id),
            LBDoNotDisturb(coordinator, lb_id),
            LBPeriodicCleaning(coordinator, lb_id),
            LBKittenMode(coordinator, lb_id),
            LBDisplay(coordinator, lb_id),
            LBChildLock(coordinator, lb_id),
            LBLightWeight(coordinator, lb_id),
            LBPower(coordinator, lb_id)
        ))
        # Pura X & Pura MAX with Pura Air
        if (lb_data.type == 't3') or ('k3Device' in lb_data.device_detail):
            switches.extend((
                LBAutoOdor(coordinator, lb_id),
                LBPeriodicOdor(coordinator, lb_id)
            ))
        # Pura MAX
        if lb_data.type == 't4':
            switches.extend((
                LBContRotation(coordinator, lb_id),
                LBDeepCleaning(coordinator, lb_id),
                LBEnhancedAdsorption(coordinator, lb_id)
            ))
            # Pura MAX with Pura Air
            if 'k3Device' in lb_data.device_detail:
                switches.append(
                    LBDeepDeodor(coordinator, lb_id)
                )

    # Purifiers
    for purifier_id, purifier_data in coordinator.data.purifiers.items():
        switches.extend((
            PurifierLight(coordinator, purifier_id),
            PurifierTone(coordinator, purifier_id)
        ))

    async_add_entities(switches)


class WFLight(PetKitWaterFountainEntity, SwitchEntity):
    """Representation of Water Fountain light switch."""

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "light")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:lightbulb' if self.is_on else 'mdi:lightbulb-off'

    @property
    def is_on(self) -> bool:
        """Determine if light is on."""
        return self.wf_data.data['settings']['lampRingSwitch'] == 1

    @property
    def available(self) -> bool:
        """Determine if device is available."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Turn light on."""

        if not self.coordinator.client.use_ble_relay:
            raise HomeAssistantError(f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}')
        if not self.wf_data.group_relay:
            raise HomeAssistantError(
                f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}. '
                f'PetKit did not return a valid relay device. If you do have a relay device, '
                f'it may temporarily be offline.'
            )

        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, W5Command.LIGHT_ON)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try turning on the light again.')
        else:
            self.wf_data.data['settings']['lampRingSwitch'] = 1
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn light off."""

        if not self.coordinator.client.use_ble_relay:
            raise HomeAssistantError(f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}')
        if not self.wf_data.group_relay:
            raise HomeAssistantError(
                f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}. '
                f'PetKit did not return a valid relay device. If you do have a relay device, '
                f'it may temporarily be offline.'
            )

        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, W5Command.LIGHT_OFF)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try turning off the light again.')
        else:
            self.wf_data.data['settings']['lampRingSwitch'] = 0
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

class WFPower(PetKitWaterFountainEntity, SwitchEntity):
    """Representation of Water Fountain power switch."""

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "power")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:power-plug' if self.is_on else 'mdi:power-plug-off'

    @property
    def is_on(self) -> bool:
        """Determine if water fountain is running."""
        return self.wf_data.data['powerStatus'] == 1

    @property
    def available(self) -> bool:
        """Determine if device is available."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Turn power on.

        Turning power on, puts the device back to the
        mode (normal, smart) it was in before it was paused.
        """

        if not self.coordinator.client.use_ble_relay:
            raise HomeAssistantError(f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}')
        if not self.wf_data.group_relay:
            raise HomeAssistantError(
                f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}. '
                f'PetKit did not return a valid relay device. If you do have a relay device, '
                f'it may temporarily be offline.'
            )

        if self.wf_data.data['mode'] == 1:
            command = W5Command.NORMAL
        else:
            command = W5Command.SMART

        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, command)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try turning on the water fountain again.')
        else:
            self.wf_data.data['powerStatus'] = 1
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn power off.

        This is equivalent to pausing the water fountain
        from the app.
        """

        if not self.coordinator.client.use_ble_relay:
            raise HomeAssistantError(f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}')
        if not self.wf_data.group_relay:
            raise HomeAssistantError(
                f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}. '
                f'PetKit did not return a valid relay device. If you do have a relay device, '
                f'it may temporarily be offline.'
            )

        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, W5Command.PAUSE)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try turning off the water fountain again.')
        else:
            self.wf_data.data['powerStatus'] = 0
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

class WFDisturb(PetKitWaterFountainEntity, SwitchEntity):
    """Representation of Water Fountain do not disturb switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "disturb")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "do_not_disturb"

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:sleep' if self.is_on else 'mdi:sleep-off'

    @property
    def is_on(self) -> bool:
        """Determine if DND is on."""
        return self.wf_data.data['settings']['noDisturbingSwitch'] == 1

    @property
    def available(self) -> bool:
        """Determine if device is available."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Turn DND on."""

        if not self.coordinator.client.use_ble_relay:
            raise HomeAssistantError(f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}')
        if not self.wf_data.group_relay:
            raise HomeAssistantError(
                f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}. '
                f'PetKit did not return a valid relay device. If you do have a relay device, '
                f'it may temporarily be offline.'
            )

        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, W5Command.DO_NOT_DISTURB)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try turning on Do Not Disturb again.')
        else:
            self.wf_data.data['settings']['noDisturbingSwitch'] = 1
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn DND off."""

        if not self.coordinator.client.use_ble_relay:
            raise HomeAssistantError(f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}')
        if not self.wf_data.group_relay:
            raise HomeAssistantError(
                f'A PetKit BLE relay is required to control {self.wf_data.data["name"]}. '
                f'PetKit did not return a valid relay device. If you do have a relay device, '
                f'it may temporarily be offline.'
            )

        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, W5Command.DO_NOT_DISTURB_OFF)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try turning off Do Not Disturb again.')
        else:
            self.wf_data.data['settings']['noDisturbingSwitch'] = 0
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

class IndicatorLight(PetKitFeederEntity, SwitchEntity):
    """Representation of Feeder indicator light switch."""

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "indicator_light")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:lightbulb' if self.is_on else 'mdi:lightbulb-off'

    @property
    def is_on(self) -> bool:
        """Determine if indicator light is on."""
        return self.feeder_data.data['settings']['lightMode'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn indicator light on."""

        if self.feeder_data.type == 'feedermini':
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.MINI_INDICATOR_LIGHT, 1)
        elif self.feeder_data.type == 'feeder':
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.FRESH_ELEMENT_INDICATOR_LIGHT, 1)
        else:
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.INDICATOR_LIGHT, 1)

        self.feeder_data.data['settings']['lightMode'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn indicator light off."""

        if self.feeder_data.type == 'feedermini':
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.MINI_INDICATOR_LIGHT, 0)
        elif self.feeder_data.type == 'feeder':
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.FRESH_ELEMENT_INDICATOR_LIGHT, 0)
        else:
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.INDICATOR_LIGHT, 0)

        self.feeder_data.data['settings']['lightMode'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

class ChildLock(PetKitFeederEntity, SwitchEntity):
    """Representation of Feeder child lock switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "child_lock")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:lock' if self.is_on else 'mdi:lock-open'

    @property
    def is_on(self) -> bool:
        """Determine if child lock is on."""
        return self.feeder_data.data['settings']['manualLock'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn child lock on."""

        if self.feeder_data.type == 'feedermini':
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.MINI_CHILD_LOCK, 1)
        elif self.feeder_data.type == 'feeder':
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.FRESH_ELEMENT_CHILD_LOCK, 1)
        else:
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.CHILD_LOCK, 1)

        self.feeder_data.data['settings']['manualLock'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn child lock off."""

        if self.feeder_data.type == 'feedermini':
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.MINI_CHILD_LOCK, 0)
        elif self.feeder_data.type == 'feeder':
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.FRESH_ELEMENT_CHILD_LOCK, 0)
        else:
            await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.CHILD_LOCK, 0)

        self.feeder_data.data['settings']['manualLock'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

class ShortageAlarm(PetKitFeederEntity, SwitchEntity):
    """Representation of Feeder shortage alarm."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "food_shortage_alarm")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:alarm' if self.is_on else 'mdi:alarm-off'

    @property
    def is_on(self) -> bool:
        """Determine if food shortage alarm is on."""
        return self.feeder_data.data['settings']['foodWarn'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn food shortage alarm on."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SHORTAGE_ALARM, 1)
        self.feeder_data.data['settings']['foodWarn'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn food shortage alarm off."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SHORTAGE_ALARM, 0)
        self.feeder_data.data['settings']['foodWarn'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

class DispenseTone(PetKitFeederEntity, SwitchEntity):
    """Representation of dispense tone switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "dispense_tone")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:ear-hearing' if self.is_on else 'mdi:ear-hearing-off'

    @property
    def is_on(self) -> bool:
        """Determine if food dispense tone is on."""
        if self.feeder_data.type == 'd4s':
            return self.feeder_data.data['settings']['feedTone'] == 1
        else:
            return self.feeder_data.data['settings']['feedSound'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn dispense tone on."""

        if self.feeder_data.type == 'd4s':
            setting = FeederSetting.FEED_TONE
        else:
            setting = FeederSetting.DISPENSE_TONE
        await self.coordinator.client.update_feeder_settings(self.feeder_data, setting, 1)

        if self.feeder_data.type == 'd4s':
            self.feeder_data.data['settings']['feedTone'] = 1
        else:
            self.feeder_data.data['settings']['feedSound'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn dispense tone off."""

        if self.feeder_data.type == 'd4s':
            setting = FeederSetting.FEED_TONE
        else:
            setting = FeederSetting.DISPENSE_TONE
        await self.coordinator.client.update_feeder_settings(self.feeder_data, setting, 0)

        if self.feeder_data.type == 'd4s':
            self.feeder_data.data['settings']['feedTone'] = 0
        else:
            self.feeder_data.data['settings']['feedSound'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class VoiceDispense(PetKitFeederEntity, SwitchEntity):
    """Representation of D3 Feeder Voice with dispense."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "voice_dispense")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "voice_with_dispense"

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:account-voice' if self.is_on else 'mdi:account-voice-off'

    @property
    def is_on(self) -> bool:
        """Determine if voice with dispense is on."""
        return self.feeder_data.data['settings']['soundEnable'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn voice with dispense on."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SOUND_ENABLE, 1)

        self.feeder_data.data['settings']['soundEnable'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn voice with dispense off."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SOUND_ENABLE, 0)

        self.feeder_data.data['settings']['soundEnable'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class DoNotDisturb(PetKitFeederEntity, SwitchEntity):
    """Representation of D3 Feeder DND."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "do_not_disturb")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:sleep' if self.is_on else 'mdi:sleep-off'

    @property
    def is_on(self) -> bool:
        """Determine if DND is on."""
        return self.feeder_data.data['settings']['disturbMode'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn DND on."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.DO_NOT_DISTURB, 1)

        self.feeder_data.data['settings']['disturbMode'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn DND off."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.DO_NOT_DISTURB, 0)

        self.feeder_data.data['settings']['disturbMode'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class SurplusControl(PetKitFeederEntity, SwitchEntity):
    """Representation of D3 Feeder Surplus Control."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "surplus_control")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:food-drumstick' if self.is_on else 'mdi:food-drumstick-off'

    @property
    def is_on(self) -> bool:
        """Determine if surplus control is on."""
        return self.feeder_data.data['settings']['surplusControl'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn surplus control on."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SURPLUS_CONTROL, 1)

        self.feeder_data.data['settings']['surplusControl'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn surplus control off."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SURPLUS_CONTROL, 0)

        self.feeder_data.data['settings']['surplusControl'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class SystemNotification(PetKitFeederEntity, SwitchEntity):
    """Representation of D3 Feeder System Notification sound."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "system_notification")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "system_notification_sound"

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:bell-ring' if self.is_on else 'mdi:bell-off'

    @property
    def is_on(self) -> bool:
        """Determine if system notification is on."""
        return self.feeder_data.data['settings']['systemSoundEnable'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.feeder_data.data['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn system notification on."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SYSTEM_SOUND, 1)

        self.feeder_data.data['settings']['systemSoundEnable'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn system notification off."""

        await self.coordinator.client.update_feeder_settings(self.feeder_data, FeederSetting.SYSTEM_SOUND, 0)

        self.feeder_data.data['settings']['systemSoundEnable'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBAutoOdor(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box auto odor removal."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "auto_odor")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "auto_odor_removal"

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:scent' if self.is_on else 'mdi:scent-off'

    @property
    def is_on(self) -> bool:
        """Determine if auto odor removal is on."""
        return self.lb_data.device_detail['settings']['autoRefresh'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        if self.lb_data.device_detail['state']['pim'] != 0:
            # Make Sure Pura MAX has Pura Air associated with it
            if self.lb_data.type == 't4':
                return 'k3Device' in self.lb_data.device_detail
            else:
                return True
        else:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn auto odor removal on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.AUTO_ODOR, 1)

        self.lb_data.device_detail['settings']['autoRefresh'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn auto odor removal off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.AUTO_ODOR, 0)

        self.lb_data.device_detail['settings']['autoRefresh'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBAutoClean(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box auto cleaning switch."""

    _attr_icon = 'mdi:vacuum'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "auto_clean")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "auto_cleaning"

    @property
    def is_on(self) -> bool:
        """Determine if auto cleaning is on."""
        return self.lb_data.device_detail['settings']['autoWork'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return (self.lb_data.device_detail['state']['pim'] != 0) and (self.lb_data.device_detail['settings']['kitten'] != 1)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn auto cleaning on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.AUTO_CLEAN, 1)

        self.lb_data.device_detail['settings']['autoWork'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn auto cleaning off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.AUTO_CLEAN, 0)

        self.lb_data.device_detail['settings']['autoWork'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBAvoidRepeat(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box avoid repeat cleaning switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "avoid_repeat")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "avoid_repeat_cleaning"

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:repeat' if self.is_on else 'mdi:repeat-off'

    @property
    def is_on(self) -> bool:
        """Determine if avoid repeat is on."""
        return self.lb_data.device_detail['settings']['avoidRepeat'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        if (self.lb_data.device_detail['state']['pim'] != 0) and (self.lb_data.device_detail['settings']['kitten'] != 1):
            # Only available if automatic cleaning is turned on
            return self.lb_data.device_detail['settings']['autoWork'] != 0
        else:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn avoid repeat cleaning on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.AVOID_REPEAT_CLEAN, 1)

        self.lb_data.device_detail['settings']['avoidRepeat'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn avoid repeat cleaning off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.AVOID_REPEAT_CLEAN, 0)

        self.lb_data.device_detail['settings']['avoidRepeat'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBDoNotDisturb(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box dnd switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "dnd")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "do_not_disturb"

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:sleep' if self.is_on else 'mdi:sleep-off'

    @property
    def is_on(self) -> bool:
        """Determine if dnd is on."""
        return self.lb_data.device_detail['settings']['disturbMode'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn dnd on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DO_NOT_DISTURB, 1)

        self.lb_data.device_detail['settings']['disturbMode'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn dnd off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DO_NOT_DISTURB, 0)

        self.lb_data.device_detail['settings']['disturbMode'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBPeriodicCleaning(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box periodic cleaning switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "periodic_cleaning")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:timer' if self.is_on else 'mdi:timer-off'

    @property
    def is_on(self) -> bool:
        """Determine if periodic cleaning is on."""
        return self.lb_data.device_detail['settings']['fixedTimeClear'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return (self.lb_data.device_detail['state']['pim'] != 0) and (self.lb_data.device_detail['settings']['kitten'] != 1)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn periodic cleaning on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.PERIODIC_CLEAN, 1)

        self.lb_data.device_detail['settings']['fixedTimeClear'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn periodic cleaning off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.PERIODIC_CLEAN, 0)

        self.lb_data.device_detail['settings']['fixedTimeClear'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBPeriodicOdor(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box periodic odor removal."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "periodic_odor")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "periodic_odor_removal"

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:scent' if self.is_on else 'mdi:scent-off'

    @property
    def is_on(self) -> bool:
        """Determine if periodic odor removal is on."""
        return self.lb_data.device_detail['settings']['fixedTimeRefresh'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        if self.lb_data.device_detail['state']['pim'] != 0:
            # Make sure Pura MAX has associated Pura Air
            if self.lb_data.type == 't4':
                return 'k3Device' in self.lb_data.device_detail
            else:
                return True
        else:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn periodic odor removal on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.PERIODIC_ODOR, 1)

        self.lb_data.device_detail['settings']['fixedTimeRefresh'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn periodic odor removal off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.PERIODIC_ODOR, 0)

        self.lb_data.device_detail['settings']['fixedTimeRefresh'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBKittenMode(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box kitten mode."""

    _attr_icon = 'mdi:cat'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "kitten_mode")

    @property
    def is_on(self) -> bool:
        """Determine if kitten mode is on."""
        return self.lb_data.device_detail['settings']['kitten'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn kitten mode on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.KITTEN_MODE, 1)

        self.lb_data.device_detail['settings']['kitten'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn kitten mode off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.KITTEN_MODE, 0)

        self.lb_data.device_detail['settings']['kitten'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBDisplay(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box display power."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "display")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:monitor' if self.is_on else 'mdi:monitor-off'

    @property
    def is_on(self) -> bool:
        """Determine if display is on."""
        return self.lb_data.device_detail['settings']['lightMode'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn display on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DISPLAY, 1)

        self.lb_data.device_detail['settings']['lightMode'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn display off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DISPLAY, 0)

        self.lb_data.device_detail['settings']['lightMode'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBChildLock(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box child lock."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "child_lock")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:lock' if self.is_on else 'mdi:lock-off'

    @property
    def is_on(self) -> bool:
        """Determine if child lock is on."""
        return self.lb_data.device_detail['settings']['manualLock'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn child lock on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.CHILD_LOCK, 1)

        self.lb_data.device_detail['settings']['manualLock'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn child lock off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.CHILD_LOCK, 0)

        self.lb_data.device_detail['settings']['manualLock'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBLightWeight(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box light weight cleaning disabler."""

    _attr_icon = 'mdi:feather'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "light_weight")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "light_weight_cleaning_disabled"

    @property
    def is_on(self) -> bool:
        """Determine if light weight disabler is on."""
        return self.lb_data.device_detail['settings']['underweight'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        kitten_mode_off = self.lb_data.device_detail['settings']['kitten'] == 0
        auto_clean = self.lb_data.device_detail['settings']['autoWork'] == 1
        avoid_repeat = self.lb_data.device_detail['settings']['avoidRepeat'] == 1

        if self.lb_data.device_detail['state']['pim'] != 0:
            # Kitten mode must be off and auto cleaning and avoid repeat must be on
            return kitten_mode_off and auto_clean and avoid_repeat
        else:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn light weight disabler on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DISABLE_LIGHT_WEIGHT, 1)

        self.lb_data.device_detail['settings']['underweight'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn light weight disabler off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DISABLE_LIGHT_WEIGHT, 0)

        self.lb_data.device_detail['settings']['underweight'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBPower(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box power switch."""

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "power")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:power' if self.is_on else 'mdi:power-off'

    @property
    def is_on(self) -> bool:
        """Determine if litter box is powered on."""
        return self.lb_data.device_detail['state']['power'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn power on."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.POWER)

        self.lb_data.device_detail['state']['power'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn power off."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.POWER)

        self.lb_data.device_detail['state']['power'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBContRotation(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box continuous rotation setting."""

    _attr_icon = 'mdi:rotate-3d-variant'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "cont_rotation")

    @property
    def is_on(self) -> bool:
        """Determine if continuous rotation is on."""
        return self.lb_data.device_detail['settings']['downpos'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn continuous rotation on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.CONT_ROTATION, 1)

        self.lb_data.device_detail['settings']['downpos'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn continuous rotation off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.CONT_ROTATION, 0)

        self.lb_data.device_detail['settings']['downpos'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBDeepCleaning(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box deep cleaning setting."""

    _attr_icon = 'mdi:vacuum'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "deep_cleaning")

    @property
    def is_on(self) -> bool:
        """Determine if deep cleaning is on."""
        return self.lb_data.device_detail['settings']['deepClean'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn deep cleaning on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DEEP_CLEAN, 1)

        self.lb_data.device_detail['settings']['deepClean'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn deep cleaning off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DEEP_CLEAN, 0)

        self.lb_data.device_detail['settings']['deepClean'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBDeepDeodor(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box deep deodorization setting."""

    _attr_icon = 'mdi:spray-bottle'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "deep_deodor")

    @property
    def is_on(self) -> bool:
        """Determine if deep deodorization is on."""
        return self.lb_data.device_detail['settings']['deepRefresh'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        if self.lb_data.device_detail['state']['pim'] != 0:
            # Make sure Pura Air is still associated with litter box
            return 'k3Device' in self.lb_data.device_detail
        else:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn deep deodorization on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DEEP_REFRESH, 1)

        self.lb_data.device_detail['settings']['deepRefresh'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn deep deodorization off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.DEEP_REFRESH, 0)

        self.lb_data.device_detail['settings']['deepRefresh'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class PurifierLight(PetKitPurifierEntity, SwitchEntity):
    """Representation of Purifier indicator light switch."""

    def __init__(self, coordinator, purifier_id):
        super().__init__(coordinator, purifier_id, "indicator_light")

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:lightbulb' if self.is_on else 'mdi:lightbulb-off'

    @property
    def is_on(self) -> bool:
        """Determine if indicator light is on."""
        return self.purifier_data.device_detail['settings']['lightMode'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.purifier_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn indicator light on."""

        await self.coordinator.client.update_purifier_settings(self.purifier_data, PurifierSetting.LIGHT, 1)

        self.purifier_data.device_detail['settings']['lightMode'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn indicator light off."""

        await self.coordinator.client.update_purifier_settings(self.purifier_data, PurifierSetting.LIGHT, 0)

        self.purifier_data.device_detail['settings']['lightMode'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class PurifierTone(PetKitPurifierEntity, SwitchEntity):
    """Representation of purifier tone switch."""

    def __init__(self, coordinator, purifier_id):
        super().__init__(coordinator, purifier_id, "tone")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return "prompt_tone"

    @property
    def icon(self) -> str:
        """Set icon."""
        return 'mdi:ear-hearing' if self.is_on else 'mdi:ear-hearing-off'

    @property
    def is_on(self) -> bool:
        """Determine if prompt tone is on."""
        return self.purifier_data.device_detail['settings']['sound'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.purifier_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn prompt tone on."""

        await self.coordinator.client.update_purifier_settings(self.purifier_data, PurifierSetting.SOUND, 1)

        self.purifier_data.device_detail['settings']['sound'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn prompt tone off."""

        await self.coordinator.client.update_purifier_settings(self.purifier_data, PurifierSetting.SOUND, 0)

        self.purifier_data.device_detail['settings']['sound'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LBEnhancedAdsorption(PetKitLitterBoxEntity, SwitchEntity):
    """Representation of litter box enhanced adsorption setting."""

    _attr_icon = 'mdi:water-circle'
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "enhanced_adsorption")

    @property
    def is_on(self) -> bool:
        """Determine if enhanced adsorption is on."""
        return self.lb_data.device_detail['settings']['bury'] == 1

    @property
    def available(self) -> bool:
        """Only make available if device is online."""
        return self.lb_data.device_detail['state']['pim'] != 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn enhanced adsorption on."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.ENHANCED_ADSORPTION, 1)

        self.lb_data.device_detail['settings']['bury'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn enhanced adsorption off."""

        await self.coordinator.client.update_litter_box_settings(self.lb_data, LitterBoxSetting.ENHANCED_ADSORPTION, 0)

        self.lb_data.device_detail['settings']['bury'] = 0
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

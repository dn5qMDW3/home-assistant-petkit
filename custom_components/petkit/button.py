"""Button platform for PetKit integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from petkitaio.constants import FeederCommand, LitterBoxCommand, W5Command
from petkitaio.exceptions import BluetoothError

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    FAST_INTERVAL,
    MAX_CLEANING_STATE,
    MAX_PAUSED_STATE,
    POLLING_INTERVAL,
)
from .coordinator import PetKitDataUpdateCoordinator
from .entity import PetKitFeederEntity, PetKitLitterBoxEntity, PetKitWaterFountainEntity
from .exceptions import PetKitBluetoothError


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set Up PetKit Button Entities."""

    coordinator: PetKitDataUpdateCoordinator = entry.runtime_data

    buttons = []

    for wf_id, wf_data in coordinator.data.water_fountains.items():
        # Water Fountains (W5)
        if wf_data.group_relay and coordinator.client.use_ble_relay:
            buttons.append(
                WFResetFilter(coordinator, wf_id)
            )

    for feeder_id, feeder_data in coordinator.data.feeders.items():
        # All Feeders
        buttons.append(
            ResetDesiccant(coordinator, feeder_id)
        )

        # D3, D4, and D4s
        if feeder_data.type in ['d3', 'd4', 'd4s', 'feeder']:
            buttons.append(
                CancelManualFeed(coordinator, feeder_id)
            )

        # D3
        if feeder_data.type == 'd3':
            buttons.append(
                CallPet(coordinator, feeder_id)
            )

        # D4s
        if feeder_data.type == 'd4s':
            buttons.append(
                FoodReplenished(coordinator, feeder_id)
            )

        # Fresh Element
        if feeder_data.type == 'feeder':
            buttons.extend((
                StartFeederCal(coordinator, feeder_id),
                StopFeederCal(coordinator, feeder_id)
            ))

    # Litter boxes
    for lb_id, lb_data in coordinator.data.litter_boxes.items():
        # Pura X & Pura MAX
        if lb_data.type in ['t3', 't4']:
            buttons.extend((
                LBStartCleaning(coordinator, lb_id),
                LBPauseCleaning(coordinator, lb_id)
            ))
        # Pura X & Pura MAX with Pura Air
        if (lb_data.type == 't3') or ('k3Device' in lb_data.device_detail):
            buttons.extend((
                LBOdorRemoval(coordinator, lb_id),
                LBResetDeodorizer(coordinator, lb_id)
            ))
        # Pura MAX
        if lb_data.type == 't4':
            buttons.extend((
                N50Reset(coordinator, lb_id),
                MAXStartMaint(coordinator, lb_id),
                MAXExitMaint(coordinator, lb_id),
                MAXPauseExitMaint(coordinator, lb_id),
                MAXResumeExitMaint(coordinator, lb_id),
                MAXDumpLitter(coordinator, lb_id),
                MAXPauseDumping(coordinator, lb_id),
                MAXResumeDumping(coordinator, lb_id)
            ))
            # Pura MAX with Pura Air
            if 'k3Device' in lb_data.device_detail:
                buttons.append(
                    MAXLightOn(coordinator, lb_id)
                )

    async_add_entities(buttons)


class WFResetFilter(PetKitWaterFountainEntity, ButtonEntity):
    """Representation of Water Fountain filter reset button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, wf_id):
        super().__init__(coordinator, wf_id, "reset_filter")

    @property
    def available(self) -> bool:
        """Determine if device is available.

        Return true if there is a valid relay
        and the main relay device is online.
        """

        return bool(self.wf_data.group_relay)

    async def async_press(self) -> None:
        """Handle the button press."""

        try:
            await self.coordinator.client.control_water_fountain(self.wf_data, W5Command.RESET_FILTER)
        except BluetoothError:
            raise PetKitBluetoothError(f'Bluetooth connection to {self.wf_data.data["name"]} failed. Please try resetting filter again.')
        else:
            self.wf_data.data['filterPercent'] = 100
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()


class ResetDesiccant(PetKitFeederEntity, ButtonEntity):
    """Representation of feeder desiccant reset button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "reset_desiccant")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.reset_feeder_desiccant(self.feeder_data)

        self.feeder_data.data['state']['desiccantLeftDays'] = 30
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class CancelManualFeed(PetKitFeederEntity, ButtonEntity):
    """Representation of manual feed cancelation button."""

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "cancel_manual_feed")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.cancel_manual_feed(self.feeder_data)
        await self.coordinator.async_request_refresh()


class CallPet(PetKitFeederEntity, ButtonEntity):
    """Representation of calling pet button for d3 feeder."""

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "call_pet")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.call_pet(self.feeder_data)
        await self.coordinator.async_request_refresh()


class LBStartCleaning(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of litter box start/resume cleaning."""

    _attr_icon = 'mdi:vacuum'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "start_cleaning")
        self.original_poll_interval = True

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        # Check the poll interval prior to checking availability
        # Pura MAX and MAX 2
        if self.lb_data.type == 't4':
            self.original_poll_interval = self.check_poll_interval()
        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        # Pura MAX and MAX 2
        if self.lb_data.type == 't4':
            if 'workState' in self.lb_data.device_detail['state']:
                if self.lb_data.device_detail['state']['workState'] == MAX_PAUSED_STATE:
                    ## Button is also used for resuming cleaning so we need to be able to execute the command
                    ## when a paused workState is encountered.
                    await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.START_CLEAN)
                    await asyncio.sleep(4)
                    # Stop fast polling after 5 minutes max since litter box
                    # has likely finished cleaning at that point.
                    self.coordinator.fast_poll_expiration = datetime.now() + timedelta(seconds=300)
                    self.coordinator.update_interval = FAST_INTERVAL
                    await self.coordinator.async_request_refresh()
                else:
                    raise HomeAssistantError(
                        f'Unable to start cleaning: litter box not ready. Starting a cleaning is only available '
                        f'when the litter box reports a state of "idle" or current cleaning is paused'
                    )
            else:
                await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.START_CLEAN)
                await asyncio.sleep(4)
                # Stop fast polling after 5 minutes max since litter box
                # has likely finished cleaning at that point.
                self.coordinator.fast_poll_expiration = datetime.now() + timedelta(seconds=300)
                self.coordinator.update_interval = FAST_INTERVAL
                await self.coordinator.async_request_refresh()
        # Handle Pura X litter box
        else:
            await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.START_CLEAN)
            await asyncio.sleep(2)
            await self.coordinator.async_request_refresh()

    def check_poll_interval(self) -> bool:
        """Determines if poll interval needs to be changed back.
        Changes the coordinator update interval back
        to the user-defined interval once the litter box is idle
        or if a set amount of time has elapsed since the coordinator
        update interval was changed.
        """

        current_dt = datetime.now()
        lb_state = self.lb_data.device_detail['state']

        ## If workState is not in lb_state, the litter box is considered
        ## to be "idle".
        original_poll_interval = timedelta(seconds=self.coordinator.config_entry.options[POLLING_INTERVAL])
        if self.coordinator.update_interval == original_poll_interval:
            return True
        if not self.coordinator.fast_poll_expiration:
            # If there isn't a fast poll expiration, but the
            # litter box is idle, return poll interval back to
            # original interval.
            if ('workState' not in lb_state):
                self.coordinator.update_interval = original_poll_interval
                return True
        else:
            if ('workState' not in lb_state) or ((self.coordinator.fast_poll_expiration - current_dt).total_seconds() <= 0):
                self.coordinator.update_interval = original_poll_interval
                self.coordinator.fast_poll_expiration = None
                return True
            else:
                return False

class LBPauseCleaning(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of litter box pause cleaning."""

    _attr_icon = 'mdi:pause'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "pause_cleaning")
        self.original_poll_interval = True

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        # Check the poll interval prior to checking availability
        # Pura MAX and MAX 2
        if self.lb_data.type == 't4':
            self.original_poll_interval = self.check_poll_interval()
        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        # Pura MAX and MAX 2
        if self.lb_data.type == 't4':
            if 'workState' in self.lb_data.device_detail['state']:
                if self.lb_data.device_detail['state']['workState'] != MAX_CLEANING_STATE:
                    raise HomeAssistantError(
                        'Unable to pause cleaning: Pausing is only available when a manual cleaning is in progress.'
                    )
                else:
                    await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.PAUSE_CLEAN)
                    await asyncio.sleep(4)
                    # Pause expires in 10 minutes
                    self.coordinator.fast_poll_expiration = datetime.now() + timedelta(seconds=600)
                    self.coordinator.update_interval = FAST_INTERVAL
                    await self.coordinator.async_request_refresh()
            else:
                raise HomeAssistantError(
                    'Unable to pause cleaning: Pausing is only available when a manual cleaning is in progress.'
                )
        else:
            await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.PAUSE_CLEAN)
            await asyncio.sleep(2)
            await self.coordinator.async_request_refresh()

    def check_poll_interval(self) -> bool:
        """Determines if poll interval needs to be changed back.
        Changes the coordinator update interval back
        to the user-defined interval once the litter box is idle
        or if a set amount of time has elapsed since the coordinator
        update interval was changed.
        """

        current_dt = datetime.now()
        lb_state = self.lb_data.device_detail['state']

        ## If workState is not in lb_state, the litter box is considered
        ## to be "idle".
        original_poll_interval = timedelta(seconds=self.coordinator.config_entry.options[POLLING_INTERVAL])
        if self.coordinator.update_interval == original_poll_interval:
            return True
        if not self.coordinator.fast_poll_expiration:
            # If there isn't a fast poll expiration, but the
            # litter box is idle, return poll interval back to
            # original interval.
            if ('workState' not in lb_state):
                self.coordinator.update_interval = original_poll_interval
                return True
        else:
            if ('workState' not in lb_state) or ((self.coordinator.fast_poll_expiration - current_dt).total_seconds() <= 0):
                self.coordinator.update_interval = original_poll_interval
                self.coordinator.fast_poll_expiration = None
                return True
            else:
                return False

class LBOdorRemoval(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of litter box odor removal."""

    _attr_icon = 'mdi:scent'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "odor_removal")

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        # Pura Air deodorizer
        if self.lb_data.type == 't4':
            if 'k3Device' in self.lb_data.device_detail:
                return lb_online and lb_power_on
            else:
                return False
        # Pura X
        else:
            return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.ODOR_REMOVAL)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()


class LBResetDeodorizer(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of litter box deodorizer reset."""

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "reset_deodorizer")

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""

        # Pura MAX
        if self.lb_data.type == 't4':
            return "reset_pura_air_liquid"
        # Pura X
        else:
            return "reset_deodorizer"

    @property
    def icon(self) -> str:
        """Set icon."""

        # Pura MAX
        if self.lb_data.type == 't4':
            return 'mdi:cup'
        # Pura X
        else:
            return 'mdi:scent'

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        # Pura Air deodorizer
        if self.lb_data.type == 't4':
            if 'k3Device' in self.lb_data.device_detail:
                return lb_online and lb_power_on
            else:
                return False
        # Pura X
        else:
            return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        # Pura MAX
        if self.lb_data.type == 't4':
            await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.RESET_MAX_DEODOR)
        # Pura X:
        else:
            await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.RESET_DEODOR)
        await self.coordinator.async_request_refresh()


class N50Reset(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of Pura MAX N50 deodorant reset."""

    _attr_icon = 'mdi:air-filter'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "n50_reset")

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.reset_pura_max_deodorizer(self.lb_data)
        await self.coordinator.async_request_refresh()


class MAXLightOn(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of Pura MAX light button."""

    _attr_icon = 'mdi:lightbulb-on'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "light_on")

    @property
    def unique_id(self) -> str:
        """Sets unique ID for this entity."""

        return str(self.lb_data.id) + '_max_light'

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        if lb_online and lb_power_on:
            # Make sure Pura Air is connected
            return 'k3Device' in self.lb_data.device_detail
        else:
            return False

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.LIGHT_ON)
        await asyncio.sleep(1.5)
        await self.coordinator.async_request_refresh()


class MAXStartMaint(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of starting Pura MAX maintenance mode."""

    _attr_icon = 'mdi:tools'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "start_maintenance")
        self.original_poll_interval = True

    @property
    def unique_id(self) -> str:
        """Sets unique ID for this entity."""

        return str(self.lb_data.id) + '_start_max_maint'

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        # Check the poll interval prior to checking availability
        self.original_poll_interval = self.check_poll_interval()
        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.START_MAINTENANCE)
        await asyncio.sleep(2)
        # Stop fast polling after 10 minutes since litter box
        # automatically exits maintenance mode in 10 minutes if
        # user doesn't initiate the exit manually
        self.coordinator.fast_poll_expiration = datetime.now() + timedelta(seconds=600)
        self.coordinator.update_interval = FAST_INTERVAL
        await self.coordinator.async_request_refresh()

    def check_poll_interval(self) -> bool:
        """Determines if poll interval needs to be changed back.
        Changes the coordinator update interval back
        to the user-defined interval once the litter box is idle
        or if a set amount of time has elapsed since the coordinator
        update interval was changed.
        """

        current_dt = datetime.now()
        lb_state = self.lb_data.device_detail['state']

        ## If workState is not in lb_state, the litter box is considered
        ## to be "idle".
        original_poll_interval = timedelta(seconds=self.coordinator.config_entry.options[POLLING_INTERVAL])
        if self.coordinator.update_interval == original_poll_interval:
            return True
        if not self.coordinator.fast_poll_expiration:
            # If there isn't a fast poll expiration, but the
            # litter box is idle, return poll interval back to
            # original interval.
            if ('workState' not in lb_state):
                self.coordinator.update_interval = original_poll_interval
                return True
        else:
            if ('workState' not in lb_state) or ((self.coordinator.fast_poll_expiration - current_dt).total_seconds() <= 0):
                self.coordinator.update_interval = original_poll_interval
                self.coordinator.fast_poll_expiration = None
                return True
            else:
                return False


class MAXExitMaint(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of exiting Pura MAX maintenance mode."""

    _attr_icon = 'mdi:tools'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "exit_maintenance")
        self.original_poll_interval = True

    @property
    def unique_id(self) -> str:
        """Sets unique ID for this entity."""

        return str(self.lb_data.id) + '_exit_max_maint'

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        #Check the poll interval prior to checking availability
        self.original_poll_interval = self.check_poll_interval()
        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.EXIT_MAINTENANCE)
        await asyncio.sleep(2)
        # Stop fast polling after 3 minutes
        self.coordinator.fast_poll_expiration = datetime.now() + timedelta(seconds=180)
        self.coordinator.update_interval = FAST_INTERVAL
        await self.coordinator.async_request_refresh()

    def check_poll_interval(self) -> bool:
        """Determines if poll interval needs to be changed back.
        Changes the coordinator update interval back
        to the user-defined interval once the litter box is idle
        or if a set amount of time has elapsed since the coordinator
        update interval was changed.
        """

        current_dt = datetime.now()
        lb_state = self.lb_data.device_detail['state']

        ## If workState is not in lb_state, the litter box is considered
        ## to be "idle".
        original_poll_interval = timedelta(seconds=self.coordinator.config_entry.options[POLLING_INTERVAL])
        if self.coordinator.update_interval == original_poll_interval:
            return True
        if not self.coordinator.fast_poll_expiration:
            # If there isn't a fast poll expiration, but the
            # litter box is idle, return poll interval back to
            # original interval.
            if ('workState' not in lb_state):
                self.coordinator.update_interval = original_poll_interval
                return True
        else:
            if ('workState' not in lb_state) or ((self.coordinator.fast_poll_expiration - current_dt).total_seconds() <= 0):
                self.coordinator.update_interval = original_poll_interval
                self.coordinator.fast_poll_expiration = None
                return True
            else:
                return False


class MAXPauseExitMaint(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of pausing exiting Pura MAX maintenance mode."""

    _attr_icon = 'mdi:tools'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "pause_exit_maintenance")
        self.original_poll_interval = True

    @property
    def unique_id(self) -> str:
        """Sets unique ID for this entity."""

        return str(self.lb_data.id) + '_pause_exit_max_maint'

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        #Check the poll interval prior to checking availability
        self.original_poll_interval = self.check_poll_interval()
        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.PAUSE_MAINTENANCE_EXIT)
        await asyncio.sleep(2)
        self.coordinator.fast_poll_expiration = datetime.now() + timedelta(seconds=600)
        self.coordinator.update_interval = FAST_INTERVAL
        await self.coordinator.async_request_refresh()

    def check_poll_interval(self) -> bool:
        """Determines if poll interval needs to be changed back.
        Changes the coordinator update interval back
        to the user-defined interval once the litter box is idle
        or if a set amount of time has elapsed since the coordinator
        update interval was changed.
        """

        current_dt = datetime.now()
        lb_state = self.lb_data.device_detail['state']

        ## If workState is not in lb_state, the litter box is considered
        ## to be "idle".
        original_poll_interval = timedelta(seconds=self.coordinator.config_entry.options[POLLING_INTERVAL])
        if self.coordinator.update_interval == original_poll_interval:
            return True
        if not self.coordinator.fast_poll_expiration:
            # If there isn't a fast poll expiration, but the
            # litter box is idle, return poll interval back to
            # original interval.
            if ('workState' not in lb_state):
                self.coordinator.update_interval = original_poll_interval
                return True
        else:
            if ('workState' not in lb_state) or ((self.coordinator.fast_poll_expiration - current_dt).total_seconds() <= 0):
                self.coordinator.update_interval = original_poll_interval
                self.coordinator.fast_poll_expiration = None
                return True
            else:
                return False


class MAXResumeExitMaint(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of continuing exiting Pura MAX maintenance mode."""

    _attr_icon = 'mdi:tools'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "resume_exit_maintenance")
        self.original_poll_interval = True

    @property
    def unique_id(self) -> str:
        """Sets unique ID for this entity."""

        return str(self.lb_data.id) + '_resume_exit_max_maint'

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        #Check the poll interval prior to checking availability
        self.original_poll_interval = self.check_poll_interval()
        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.RESUME_MAINTENANCE_EXIT)
        await asyncio.sleep(2)
        self.coordinator.fast_poll_expiration = datetime.now() + timedelta(seconds=180)
        self.coordinator.update_interval = FAST_INTERVAL
        await self.coordinator.async_request_refresh()

    def check_poll_interval(self) -> bool:
        """Determines if poll interval needs to be changed back.
        Changes the coordinator update interval back
        to the user-defined interval once the litter box is idle
        or if a set amount of time has elapsed since the coordinator
        update interval was changed.
        """

        current_dt = datetime.now()
        lb_state = self.lb_data.device_detail['state']

        ## If workState is not in lb_state, the litter box is considered
        ## to be "idle".
        original_poll_interval = timedelta(seconds=self.coordinator.config_entry.options[POLLING_INTERVAL])
        if self.coordinator.update_interval == original_poll_interval:
            return True
        if not self.coordinator.fast_poll_expiration:
            # If there isn't a fast poll expiration, but the
            # litter box is idle, return poll interval back to
            # original interval.
            if ('workState' not in lb_state):
                self.coordinator.update_interval = original_poll_interval
                return True
        else:
            if ('workState' not in lb_state) or ((self.coordinator.fast_poll_expiration - current_dt).total_seconds() <= 0):
                self.coordinator.update_interval = original_poll_interval
                self.coordinator.fast_poll_expiration = None
                return True
            else:
                return False

class MAXDumpLitter(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of dumping cat litter."""

    _attr_icon = 'mdi:landslide'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "dump_litter")

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.DUMP_LITTER)
        await asyncio.sleep(1.5)
        await self.coordinator.async_request_refresh()


class MAXPauseDumping(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of pausing dumping cat litter."""

    _attr_icon = 'mdi:landslide'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "pause_dump_litter")

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.PAUSE_LITTER_DUMP)
        await asyncio.sleep(1.5)
        await self.coordinator.async_request_refresh()


class MAXResumeDumping(PetKitLitterBoxEntity, ButtonEntity):
    """Representation of resuming dumping cat litter."""

    _attr_icon = 'mdi:landslide'

    def __init__(self, coordinator, lb_id):
        super().__init__(coordinator, lb_id, "resume_dump_litter")

    @property
    def available(self) -> bool:
        """Only make available if device is online and on."""

        lb_online = self.lb_data.device_detail['state']['pim'] == 1
        lb_power_on = self.lb_data.device_detail['state']['power'] == 1

        return lb_online and lb_power_on

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.control_litter_box(self.lb_data, LitterBoxCommand.RESUME_LITTER_DUMP)
        await asyncio.sleep(1.5)
        await self.coordinator.async_request_refresh()


class FoodReplenished(PetKitFeederEntity, ButtonEntity):
    """Representation of food replenished command button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "food_replenished")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.food_replenished(self.feeder_data)

        self.feeder_data.data['state']['food1'] = 1
        self.feeder_data.data['state']['food2'] = 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class StartFeederCal(PetKitFeederEntity, ButtonEntity):
    """Representation of fresh element feeder start calibration button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "start_cal")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.fresh_element_calibration(self.feeder_data, FeederCommand.START_CALIBRATION)
        await self.coordinator.async_request_refresh()


class StopFeederCal(PetKitFeederEntity, ButtonEntity):
    """Representation of fresh element feeder stop calibration button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, feeder_id):
        super().__init__(coordinator, feeder_id, "stop_cal")

    @property
    def available(self) -> bool:
        """Only make available if device is online."""

        return self.feeder_data.data['state']['pim'] != 0

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.client.fresh_element_calibration(self.feeder_data, FeederCommand.STOP_CALIBRATION)
        await self.coordinator.async_request_refresh()

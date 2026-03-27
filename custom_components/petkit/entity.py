"""Base entity classes for PetKit integration."""
from __future__ import annotations

from typing import Any

from petkitaio.model import Feeder, LitterBox, Pet, Purifier, W5Fountain

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FEEDERS, LITTER_BOXES, PURIFIERS, WATER_FOUNTAINS
from .coordinator import PetKitDataUpdateCoordinator


class PetKitEntity(CoordinatorEntity[PetKitDataUpdateCoordinator]):
    """Base class for all PetKit entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PetKitDataUpdateCoordinator,
        entity_key: str,
    ) -> None:
        """Initialize a PetKit entity."""
        super().__init__(coordinator)
        self._entity_key = entity_key

    @property
    def translation_key(self) -> str:
        """Translation key for this entity."""
        return self._entity_key


class PetKitWaterFountainEntity(PetKitEntity):
    """Base class for Water Fountain entities."""

    def __init__(
        self, coordinator: PetKitDataUpdateCoordinator, wf_id: int, entity_key: str
    ) -> None:
        """Initialize a Water Fountain entity."""
        super().__init__(coordinator, entity_key)
        self.wf_id = wf_id

    @property
    def wf_data(self) -> W5Fountain:
        """Handle coordinator Water Fountain data."""
        return self.coordinator.data.water_fountains[self.wf_id]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.wf_data.id)},
            "name": self.wf_data.data['name'],
            "manufacturer": "PetKit",
            "model": WATER_FOUNTAINS.get(self.wf_data.data["typeCode"], "Unidentified Water Fountain") if "typeCode" in self.wf_data.data else "Unidentified Water Fountain",
            "sw_version": f'{self.wf_data.data["hardware"]}.{self.wf_data.data["firmware"]}',
        }

    @property
    def unique_id(self) -> str:
        """Set unique ID for this entity."""
        return str(self.wf_data.id) + '_' + self._entity_key


class PetKitFeederEntity(PetKitEntity):
    """Base class for Feeder entities."""

    def __init__(
        self, coordinator: PetKitDataUpdateCoordinator, feeder_id: int, entity_key: str
    ) -> None:
        """Initialize a Feeder entity."""
        super().__init__(coordinator, entity_key)
        self.feeder_id = feeder_id

    @property
    def feeder_data(self) -> Feeder:
        """Handle coordinator Feeder data."""
        return self.coordinator.data.feeders[self.feeder_id]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.feeder_data.id)},
            "name": self.feeder_data.data['name'],
            "manufacturer": "PetKit",
            "model": FEEDERS[self.feeder_data.type],
            "sw_version": f'{self.feeder_data.data["firmware"]}',
        }

    @property
    def unique_id(self) -> str:
        """Set unique ID for this entity."""
        return str(self.feeder_data.id) + '_' + self._entity_key


class PetKitLitterBoxEntity(PetKitEntity):
    """Base class for Litter Box entities."""

    def __init__(
        self, coordinator: PetKitDataUpdateCoordinator, lb_id: int, entity_key: str
    ) -> None:
        """Initialize a Litter Box entity."""
        super().__init__(coordinator, entity_key)
        self.lb_id = lb_id

    @property
    def lb_data(self) -> LitterBox:
        """Handle coordinator Litter Box data."""
        return self.coordinator.data.litter_boxes[self.lb_id]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.lb_data.id)},
            "name": self.lb_data.device_detail['name'],
            "manufacturer": "PetKit",
            "model": LITTER_BOXES[self.lb_data.type],
            "sw_version": f'{self.lb_data.device_detail["firmware"]}',
        }

    @property
    def unique_id(self) -> str:
        """Set unique ID for this entity."""
        return str(self.lb_data.id) + '_' + self._entity_key


class PetKitPurifierEntity(PetKitEntity):
    """Base class for Purifier entities."""

    def __init__(
        self, coordinator: PetKitDataUpdateCoordinator, purifier_id: int, entity_key: str
    ) -> None:
        """Initialize a Purifier entity."""
        super().__init__(coordinator, entity_key)
        self.purifier_id = purifier_id

    @property
    def purifier_data(self) -> Purifier:
        """Handle coordinator Purifier data."""
        return self.coordinator.data.purifiers[self.purifier_id]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.purifier_data.id)},
            "name": self.purifier_data.device_detail['name'],
            "manufacturer": "PetKit",
            "model": PURIFIERS[self.purifier_data.type],
            "sw_version": f'{self.purifier_data.device_detail["firmware"]}',
        }

    @property
    def unique_id(self) -> str:
        """Set unique ID for this entity."""
        return str(self.purifier_data.id) + '_' + self._entity_key


class PetKitPetEntity(PetKitEntity):
    """Base class for Pet entities."""

    def __init__(
        self, coordinator: PetKitDataUpdateCoordinator, pet_id: int, entity_key: str
    ) -> None:
        """Initialize a Pet entity."""
        super().__init__(coordinator, entity_key)
        self.pet_id = pet_id

    @property
    def pet_data(self) -> Pet:
        """Handle coordinator Pet data."""
        return self.coordinator.data.pets[self.pet_id]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.pet_data.id)},
            "name": self.pet_data.data['name'],
            "manufacturer": "PetKit",
            "model": self.pet_data.type,
        }

    @property
    def unique_id(self) -> str:
        """Set unique ID for this entity."""
        return self.pet_data.id + '_' + self._entity_key

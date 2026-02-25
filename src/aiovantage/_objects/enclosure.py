"""Enclosure object."""

from dataclasses import dataclass

from .location_object import LocationObject
from .types import Parent


@dataclass(kw_only=True)
class Enclosure(LocationObject):
    """Enclosure object — a physical rack cabinet containing dimmer/relay modules."""

    parent: Parent

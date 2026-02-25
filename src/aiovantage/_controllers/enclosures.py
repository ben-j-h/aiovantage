"""Enclosures controller."""

from aiovantage.objects import Enclosure

from .base import Controller


class EnclosuresController(Controller[Enclosure]):
    """Enclosures controller.

    Enclosures are physical rack cabinets that house dimmer and relay modules.
    They are useful for building a proper device hierarchy in which modules
    appear as children of their physical enclosure.
    """

    vantage_types = ("Enclosure",)

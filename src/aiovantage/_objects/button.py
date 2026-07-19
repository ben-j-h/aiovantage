"""Button object."""

from dataclasses import dataclass, field

from aiovantage.object_interfaces import ButtonInterface

from .system_object import SystemObject
from .types import Parent


@dataclass(kw_only=True)
class Button(SystemObject, ButtonInterface):
    """Button object."""

    parent: Parent
    down: int = 0
    up: int = 0
    hold: int = 0
    # Design Center's backup XML export omits <Text1>/<Text2> entirely (not
    # even as an empty tag) for buttons with no text on that line, so these
    # need defaults -- without one, parsing a button missing either element
    # raises instead of defaulting to "", silently dropping the button.
    text1: str = ""
    text2: str = ""
    placement_table: list[int] = field(
        default_factory=list[int],
        metadata={
            "name": "Place",
            "wrapper": "PlacementTable",
        },
    )
    button_style: int
    led_style: int = field(
        metadata={
            "name": "LEDStyle",
        },
    )

    @property
    def text(self) -> str:
        """Return the button text."""
        return f"{self.text1}\n{self.text2}" if self.text2 else self.text1

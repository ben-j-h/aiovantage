from aiovantage.objects import Button

from .base import Controller, StatusType


class ButtonsController(Controller[Button]):
    """Buttons controller."""

    vantage_types = ("Button",)

    async def enable_state_monitoring(self) -> None:
        """Subscribe to button press and LED state changes."""
        await super().enable_state_monitoring()

        # S:LED events are category-based and are NOT included in the Enhanced Log.
        # When the base class chose Enhanced Log for button state (new firmware),
        # we also need an explicit STATUS LED subscription to receive pushed LED updates.
        if self._status_type == StatusType.OBJECT:
            led_unsub = self._vantage.event_stream.subscribe_status(
                self._handle_status_event, "LED"
            )
            self._status_unsubs.append(led_unsub)

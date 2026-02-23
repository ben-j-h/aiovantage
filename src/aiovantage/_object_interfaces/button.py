from decimal import Decimal
from enum import IntEnum, StrEnum

from typing_extensions import override

from aiovantage import logger
from aiovantage.command_client import Converter
from aiovantage.errors import CommandError, ConversionError

from .base import Interface, method


class ButtonInterface(Interface):
    """Button object interface."""

    interface_name = "Button"

    class State(IntEnum):
        """Button state."""

        Up = 0
        Down = 1

    class SndType(IntEnum):
        """Button sound type."""

        Continuous = 0
        Pulsed = 1
        Off = 2

    class Polarity(IntEnum):
        """Button polarity."""

        NormallyOpen = 0
        NormallyClosed = 1

    class BlinkRate(StrEnum):
        """LED blink rate (firmware 3.9.x terminal command)."""

        Fast = "FAST"
        Medium = "MEDIUM"
        Slow = "SLOW"
        VerySlow = "VERYSLOW"
        Off = "OFF"

    # Properties
    state: State | None = State.Up
    led_active_color: tuple[int, int, int] | None = None
    led_inactive_color: tuple[int, int, int] | None = None
    led_blink_rate: "ButtonInterface.BlinkRate | None" = None

    # Methods
    @method("GetState", "GetStateHW", property="state")
    async def get_state(self, *, hw: bool = False) -> State:
        """Get the state of a button.

        Args:
            hw: Fetch the value from hardware instead of cache.

        Returns:
            The pressed state of the button.
        """
        # INVOKE <id> Button.GetState
        # -> R:INVOKE <id> <state (Up/Down)> Button.GetState
        return await self.invoke("Button.GetStateHW" if hw else "Button.GetState")

    @method("SetState", "SetStateSW")
    async def set_state(self, state: State, *, sw: bool = False) -> None:
        """Set the state of a button.

        Args:
            state: The state to set the button to, either a State.UP or State.DOWN.
            sw: Set the cached value instead of the hardware value.
        """
        # INVOKE <id> Button.SetState <state (0/1/Up/Down)>
        # -> R:INVOKE <id> <rcode> Button.SetState <state (Up/Down)>
        await self.invoke("Button.SetStateSW" if sw else "Button.SetState", state)

    @method("GetHoldOn", "GetHoldOnHW")
    async def get_hold_on(self, *, hw: bool = False) -> Decimal:
        """Get the hold on time of a button.

        Args:
            hw: Fetch the value from hardware instead of cache.

        Returns:
            The hold on time of the button, in seconds.
        """
        # INVOKE <id> Button.GetHoldOn
        # -> R:INVOKE <id> <seconds> Button.GetHoldOn
        return await self.invoke("Button.GetHoldOnHW" if hw else "Button.GetHoldOn")

    @method("SetHoldOn", "SetHoldOnSW")
    async def set_hold_on(self, seconds: Decimal, *, sw: bool = False) -> None:
        """Set the hold on time of a button.

        Args:
            seconds: The hold on time to set, in seconds.
            sw: Set the cached value instead of the hardware value.
        """
        # INVOKE <id> Button.SetHoldOn <seconds>
        # -> R:INVOKE <id> <rcode> Button.SetHoldOn <seconds>
        await self.invoke("Button.SetHoldOnSW" if sw else "Button.SetHoldOn", seconds)

    @method("GetPolarity", "GetPolarityHW")
    async def get_polarity(self, *, hw: bool = False) -> Polarity:
        """Get the polarity of a button.

        Args:
            hw: Fetch the value from hardware instead of cache.

        Returns:
            The polarity of the button.
        """
        # INVOKE <id> Button.GetPolarity
        # -> R:INVOKE <id> <polarity> Button.GetPolarity
        return await self.invoke("Button.GetPolarityHW" if hw else "Button.GetPolarity")

    @method("SetPolarity", "SetPolaritySW")
    async def set_polarity(self, polarity: Polarity, *, sw: bool = False) -> None:
        """Set the polarity of a button.

        Args:
            polarity: The polarity to set the button to.
            sw: Set the cached value instead of the hardware value.
        """
        # INVOKE <id> Button.SetPolarity <polarity (0/1/NormallyOpen/NormallyClosed)>
        # -> R:INVOKE <id> <rcode> Button.SetPolarity <polarity (NormallyOpen/NormallyClosed)>
        await self.invoke(
            "Button.SetPolaritySW" if sw else "Button.SetPolarity", polarity
        )

    @method("GetSndType", "GetSndTypeHW")
    async def get_snd_type(self, *, hw: bool = False) -> SndType:
        """Get the sound type of a button.

        Args:
            hw: Fetch the value from hardware instead of cache.

        Returns:
            The sound type of the button.
        """
        # INVOKE <id> Button.GetSndType
        # -> R:INVOKE <id> <snd_type> Button.GetSndType
        return await self.invoke("Button.GetSndTypeHW" if hw else "Button.GetSndType")

    @method("SetSndType", "SetSndTypeSW")
    async def set_snd_type(self, snd_type: SndType, *, sw: bool = False) -> None:
        """Set the sound type of a button.

        Args:
            snd_type: The sound type to set the button to.
            sw: Set the cached value instead of the hardware value.
        """
        # INVOKE <id> Button.SetSndType <snd_type (0/1/2/Continuous/Pulsed/Off)>
        # -> R:INVOKE <id> <rcode> Button.SetSndType <snd_type (Continuous/Pulsed/Off)>
        await self.invoke(
            "Button.SetSndTypeSW" if sw else "Button.SetSndType", snd_type
        )

    @method("GetPlacement", "GetPlacementHW")
    async def get_placement(self, *, hw: bool = False) -> int:
        """Get the placement of a button.

        Args:
            hw: Fetch the value from hardware instead of cache.

        Returns:
            The placement of the button on the keypad.
        """
        # INVOKE <id> Button.GetPlacement
        # -> R:INVOKE <id> <placement> Button.GetPlacement
        return await self.invoke(
            "Button.GetPlacementHW" if hw else "Button.GetPlacement"
        )

    @method("SetPlacement", "SetPlacementSW")
    async def set_placement(self, placement: int, *, sw: bool = False) -> None:
        """Set the placement of a button.

        Args:
            placement: The placement of the button on the keypad.
            sw: Set the cached value instead of the hardware value.
        """
        # INVOKE <id> Button.SetPlacement <placement>
        # -> R:INVOKE <id> <rcode> Button.SetPlacement <placement>
        await self.invoke(
            "Button.SetPlacementSW" if sw else "Button.SetPlacement", placement
        )

    # LED control (firmware 3.9.x terminal command, not an INVOKE method)
    async def set_led(
        self,
        active: tuple[int, int, int],
        inactive: tuple[int, int, int] = (0, 0, 0),
        blink_rate: "ButtonInterface.BlinkRate" = BlinkRate.Off,
    ) -> None:
        """Set the button LED colors and blink rate.

        Uses the firmware 3.9.x terminal command:
            LED <vid> <R1> <G1> <B1> <R2> <G2> <B2> <BlinkRate>

        Args:
            active: RGB tuple for the active (On) state.
            inactive: RGB tuple for the inactive (Off) state.
            blink_rate: Blink rate (FAST/MEDIUM/SLOW/VERYSLOW/OFF).
        """
        # LED <vid> <R1> <G1> <B1> <R2> <G2> <B2> <BlinkRate>
        if not self.command_client:
            raise ValueError("The object has no command client to send requests with.")
        r1, g1, b1 = active
        r2, g2, b2 = inactive
        await self.command_client.raw_request(
            f"LED {self.vid} {r1} {g1} {b1} {r2} {g2} {b2} {blink_rate}"
        )
        self.update_properties(
            {
                "led_active_color": active,
                "led_inactive_color": inactive,
                "led_blink_rate": blink_rate,
            }
        )

    async def clear_led(self) -> None:
        """Reset the button LED to off (master clear).

        Sends all-zero colors with blink OFF, which clears any logical fault
        or task conflict indicated by red flashing.
        """
        await self.set_led((0, 0, 0), (0, 0, 0), self.BlinkRate.Off)

    # Convenience functions, not part of the interface
    async def press(self) -> None:
        """Press a button."""
        await self.set_state(self.State.Down)

    async def release(self) -> None:
        """Release a button."""
        await self.set_state(self.State.Up)

    async def press_and_release(self) -> None:
        """Press and release a button."""
        await self.press()
        await self.release()

    @property
    def is_down(self) -> bool | None:
        """Return True if the button is down."""
        return self.state == self.State.Down

    @override
    async def fetch_state(self) -> list[str]:
        # Fetch button state via standard property getters (e.g. GetState)
        changed = await super().fetch_state()

        # Fetch LED state via the GETLED raw command
        # GETLED <vid>
        # -> R:GETLED <vid> <state(0/1)> <R1> <G1> <B1> <R2> <G2> <B2> <BlinkRate>
        if not self.command_client:
            return changed

        try:
            response = await self.command_client.raw_request(f"GETLED {self.vid}")
            _, _vid, _state, r1, g1, b1, r2, g2, b2, blink_str = Converter.tokenize(
                response[-1]
            )
            led_changed = self.update_properties(
                {
                    "led_active_color": (int(r1), int(g1), int(b1)),
                    "led_inactive_color": (int(r2), int(g2), int(b2)),
                    "led_blink_rate": ButtonInterface.BlinkRate(blink_str),
                }
            )
            changed.extend(led_changed)
        except (CommandError, ConversionError, ValueError) as ex:
            logger.warning("Failed to fetch LED state for vid %d: %s", self.vid, ex)

        return changed

    @override
    def handle_category_status(self, category: str, *args: str) -> list[str]:
        if category == "BTN":
            # STATUS BTN
            # -> S:BTN <id> <state (PRESS/RELEASE)>
            btn_map = {
                "PRESS": ButtonInterface.State.Down,
                "RELEASE": ButtonInterface.State.Up,
            }

            return self.update_properties({"state": btn_map[args[0]]})

        if category == "LED":
            # STATUS LED
            # -> S:LED <id> <state(0=inactive/1=active)> <R1> <G1> <B1> <R2> <G2> <B2> <BlinkRate>
            _state, r1, g1, b1, r2, g2, b2, blink_str = args[:8]
            return self.update_properties(
                {
                    "led_active_color": (int(r1), int(g1), int(b1)),
                    "led_inactive_color": (int(r2), int(g2), int(b2)),
                    "led_blink_rate": ButtonInterface.BlinkRate(blink_str),
                }
            )

        return super().handle_category_status(category, *args)

"""TouchPoint touchscreen station."""

from dataclasses import dataclass, field

from xsdata.formats.dataclass.models.generics import AnyElement

from .keypad import Keypad


def _local_name(qname: str | None) -> str:
    """Strip any XML namespace from a qualified name."""
    if qname is None:
        return ""
    return qname.rsplit("}", 1)[-1]


def _widget_vid_and_text(node: AnyElement) -> tuple[int | None, str | None]:
    """Extract a widget's target Button VID and visible label from its children."""
    vid: int | None = None
    text: str | None = None
    for child in node.children:
        if not isinstance(child, AnyElement):
            continue
        name = _local_name(child.qname)
        if name == "WidgetVid" and child.text:
            try:
                vid = int(child.text)
            except ValueError:
                pass
        elif name == "Text" and child.text and child.text.strip():
            text = child.text.strip()
    return vid, text


@dataclass(kw_only=True)
class TPT(Keypad):
    """TouchPoint touchscreen station, treated as a large keypad.

    A TPT's Buttons behave exactly like a physical keypad's buttons (Parent /
    Position, Down/Up/Hold actions, LEDs) — but the physical Button objects
    are usually blank, because the visible label is drawn on-screen as part
    of the LCD page design (``LcdScreen``) instead.

    We don't model the full LCD design — it's large and UI-only — but we
    capture whatever elements aren't otherwise mapped (LcdScreen, Resolution,
    FaceplateColor, ...) as a generic tree, so ``button_labels()`` can recover
    a human-readable label for each button from the page design.
    """

    extra: list[object] = field(
        default_factory=list,
        metadata={"type": "Wildcard"},
    )

    def button_labels(self) -> dict[int, str]:
        """Return a best-effort map of Button VID -> on-screen label.

        LCD page designs are built from widget ``<Button>`` nodes carrying a
        ``<WidgetVid>`` (the VID of the top-level Button object it triggers)
        and a ``<Text>`` (the visible label). Not every button has a widget,
        and not every widget has text, so coverage is partial.

        The result is computed once and cached on this instance -- not as a
        dataclass field (xsdata would try to bind it to XML), just a plain
        attribute set on first access.
        """
        cached: dict[int, str] | None = getattr(self, "_button_labels_cache", None)
        if cached is not None:
            return cached

        labels: dict[int, str] = {}

        def walk(node: object) -> None:
            if not isinstance(node, AnyElement):
                return
            if _local_name(node.qname) == "Button":
                vid, text = _widget_vid_and_text(node)
                if vid is not None and text:
                    labels.setdefault(vid, text)
            for child in node.children:
                walk(child)

        for node in self.extra:
            walk(node)

        self._button_labels_cache = labels  # type: ignore[attr-defined]
        return labels

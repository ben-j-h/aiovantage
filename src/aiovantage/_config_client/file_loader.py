"""Parse a Vantage Design Center backup XML file for local object caching.

The Design Center backup XML format has this structure:

    <Project FileVersion="..." DesignCenterVersion="...">
      <Objects>
        <Object>
          <Load VID="447" Master="1">
            <Name>Fan (Ceiling)</Name>
            ...
          </Load>
        </Object>
        <Object>
          <Area VID="125" Master="1">
            ...
          </Area>
        </Object>
      </Objects>
    </Project>

The inner <TypeName ...> element is structurally identical to what
IConfiguration.GetFilterResults returns.  We parse it with the same xsdata
machinery used by the config client, so every object type is handled
automatically — including Load, Area, Button, Task, GMem, Master, etc.

Unrecognised or unparseable elements are silently skipped so that future
Design Center versions with new object types don't break parsing.
"""

import warnings
from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree

import aiovantage.objects as _obj_module
from aiovantage.objects import SystemObject
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.parsers.config import ParserConfig
from xsdata.formats.dataclass.parsers.handlers import XmlEventHandler
from xsdata.utils.text import pascal_case


def _pascal_case_preserve(name: str) -> str:
    """Convert to PascalCase, preserving names that are already PascalCase."""
    if "_" in name or name.islower():
        return pascal_case(name)
    return name


def _build_type_map() -> dict[str, type[SystemObject]]:
    """Build a mapping from Vantage XML type names to Python dataclass classes.

    Uses vantage_type() on every exported class in aiovantage.objects so that
    unusual names like "Vantage.DGColorLoad" are handled correctly.
    """
    type_map: dict[str, type[SystemObject]] = {}
    for cls_name in _obj_module.__all__:
        cls = getattr(_obj_module, cls_name, None)
        if cls is None or not isinstance(cls, type):
            continue
        if not issubclass(cls, SystemObject):
            continue
        type_map[cls.vantage_type()] = cls
    return type_map


# Module-level cache so the map is built only once.
_TYPE_MAP: dict[str, type[SystemObject]] | None = None


def _get_type_map() -> dict[str, type[SystemObject]]:
    global _TYPE_MAP
    if _TYPE_MAP is None:
        _TYPE_MAP = _build_type_map()
    return _TYPE_MAP


def _make_parser() -> XmlParser:
    """Create an xsdata parser configured for aiovantage._objects."""
    xml_context = XmlContext(
        element_name_generator=_pascal_case_preserve,
        attribute_name_generator=_pascal_case_preserve,
        models_package="aiovantage._objects",
    )
    return XmlParser(
        config=ParserConfig(fail_on_unknown_properties=False),
        context=xml_context,
        handler=XmlEventHandler,
    )


def iter_controller_ips(
    path: str | Path,
) -> Iterator[tuple[int, str | None, str | None, str | None]]:
    """Yield (vid, ip_address, mac_address, firmware_version) tuples from ProjectInfo.

    The ProjectInfo section of a Design Center backup XML contains
    ``<Controller{VID}Info>`` elements that record per-controller network
    information.  This data is not available in the main ``<Objects>`` section.

    Args:
        path: Path to the Design Center backup XML file.

    Yields:
        ``(vid, ip_address, mac_address, firmware_version)`` tuples.
        Any field that is absent in the XML is yielded as ``None``.
    """
    tree = ElementTree.parse(path)
    root = tree.getroot()

    project_info = root.find("ProjectInfo")
    if project_info is None:
        return

    def _text(elem: ElementTree.Element, tag: str) -> str | None:
        child = elem.find(tag)
        return child.text.strip() if child is not None and child.text and child.text.strip() else None

    for elem in project_info:
        # Tags have the form Controller{VID}Info, e.g. Controller1Info, Controller2466Info
        if not (elem.tag.startswith("Controller") and elem.tag.endswith("Info")):
            continue
        vid_str = elem.tag[len("Controller") : -len("Info")]
        try:
            vid = int(vid_str)
        except ValueError:
            continue
        yield vid, _text(elem, "IPAddress"), _text(elem, "MACAddress"), _text(elem, "Firmware")


def iter_objects(path: str | Path) -> Iterator[SystemObject]:
    """Yield all parseable SystemObject instances from a Design Center backup XML file.

    Parses the file in a single pass and yields typed Vantage objects (Load, Area,
    Button, Task, GMem, …).  Unrecognised or unparseable elements are silently
    skipped so partial / future-format files remain usable.

    Args:
        path: Path to the Design Center backup XML file
              (e.g. ``192.168.0.200_config.txt``).

    Yields:
        Parsed :class:`~aiovantage.objects.SystemObject` instances.
    """
    type_map = _get_type_map()
    parser = _make_parser()

    tree = ElementTree.parse(path)
    root = tree.getroot()

    objects_elem = root.find("Objects")
    if objects_elem is None:
        return

    for object_elem in objects_elem.iter("Object"):
        children = list(object_elem)
        if not children:
            continue

        typed_elem = children[0]
        type_name = typed_elem.tag

        # Look up the Python class for this XML element name.
        cls = type_map.get(type_name)
        if cls is None:
            continue  # Skip WireLink, EthernetLink, and other infrastructure types.

        xml_str = ElementTree.tostring(typed_elem, encoding="unicode")
        try:
            # Suppress ConverterWarnings for empty/missing fields (e.g. blank m_time
            # strings) — these are normal in Design Center backup files and do not
            # affect object usability.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                obj = parser.from_string(xml_str, cls)
        except Exception:
            continue  # Skip objects that fail to parse (corrupt / truncated file).

        yield obj

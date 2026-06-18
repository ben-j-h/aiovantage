# aiovantage Architecture

## Overview

`aiovantage` is an async Python library for controlling Vantage InFusion home automation controllers. It communicates over two separate TCP services:

| Service | Default Port (SSL) | Default Port (plain) | Purpose |
|---|---|---|---|
| ACI (config) | 2010 | 2001 | Object discovery — XML-over-TCP |
| HCI (command) | 3010 | 3001 | Commands & real-time state — text protocol |

The `Vantage` class owns both connections and exposes typed **controllers** (one per object type) that manage collections of **objects** (dataclasses representing the hardware configuration).

---

## Layer Map

```
┌─────────────────────────────────────────────────────────┐
│                     Vantage (public API)                 │
│   .loads  .areas  .buttons  .tasks  .stations  …        │
├──────────────────────┬──────────────────────────────────┤
│   Controller[T]      │   (one per object type)          │
│   ├── QuerySet[T]    │   filter / get / iterate         │
│   └── EventDispatcher│   ObjectAdded/Updated/Deleted    │
├──────────────────────┴──────────────────────────────────┤
│  ConfigClient (ACI)  │  CommandClient + EventStream     │
│  XML-RPC over TCP    │  Line-protocol over TCP          │
│  port 2001/2010      │  port 3001/3010                  │
├──────────────────────┴──────────────────────────────────┤
│         ConfigConnection / CommandConnection             │
│         (asyncio TCP with auth probe, TLS, timeouts)    │
└─────────────────────────────────────────────────────────┘
```

---

## Core Components

### `Vantage` (`__init__.py`)

The top-level entry point. Instantiate it with a host and optional credentials:

```python
async with Vantage("192.168.0.200", ssl=False) as v:
    await v.initialize()
    for load in v.loads:
        print(load.name, load.level)
```

- Owns one `ConfigClient`, one `CommandClient`, one `EventStream`
- Creates all controllers at construction time
- `initialize()` populates all controllers in parallel via `asyncio.gather`
- **Local config file:** If `local_config_file=` is passed and the file exists, `_inject_from_file()` pre-populates controllers from a Design Center backup XML before any network calls. Controllers with pre-loaded objects skip the live IConfiguration fetch entirely.

### ConfigClient (`_config_client/`)

Talks to the ACI XML service on port 2001/2010.

- Uses **xsdata** for XML serialization/deserialization
- `XmlContext(models_package="aiovantage._objects")` — tells xsdata to look up dataclasses in `_objects/` by element name
- `_pascal_case_preserve()` — custom name generator that preserves existing PascalCase names (e.g., `IConfiguration`, `DName`) without mangling them
- `ConfigurationInterface.get_objects()` — the main fetch path: `OpenFilter` → loop `GetFilterResults` → `CloseFilter`

### CommandClient and EventStream (`_command_client/`)

Talk to the HCI text service on port 3001/3010.

- **CommandClient** — sends `INVOKE`, `GETLOAD`, `SET*` etc. and reads synchronous responses
- **EventStream** — maintains a persistent connection and routes async push messages:
  - `S:LOAD <vid> <level>` → category status (older firmware or fallback)
  - `EL: <vid> <method> <result>` → enhanced log (ELAGG) — preferred, richer
- **Auth probe:** Sends `ECHO`; if `R:ERROR` comes back, authentication is required. If `R:ECHO` comes back, no auth needed. This correctly handles controllers where login is disabled.
- **ELAGG probe:** Sends `ELAGG 1`; `R:ELAGG 1 ON` means enhanced log is supported and will be used for all status subscriptions.

### Controller Base (`_controllers/base.py`)

Manages a collection of typed Vantage objects.

```python
class LoadsController(Controller[Load]):
    vantage_types = ("Load",)        # which XML type names to fetch
```

Key behaviors:
- **`initialize()`** — fetches from IConfiguration (or skips if `_initialized` is already True from `inject()` calls), then calls `fetch_state()` and `enable_state_monitoring()`
- **`inject(obj)`** — add a pre-parsed object directly; sets `_initialized = True` to skip the live fetch
- **`enable_state_monitoring()`** — subscribes to ELAGG enhanced log events if supported, otherwise falls back to category STATUS events
- **Events emitted:** `ObjectAdded`, `ObjectUpdated(obj, attrs_changed)`, `ObjectDeleted`
- **`_lazy_initialize()`** — called by `QuerySet` on first access if controller not yet initialized

### Object Interfaces (`_object_interfaces/`)

Interfaces define *state* properties and *methods* for interacting with objects. Objects inherit from both their base class (`LocationObject`, etc.) and one or more interfaces.

The `@method` decorator links a Python async function to one or more Vantage RPC method names:

```python
class LoadInterface(Interface):
    level: Decimal | None = None          # state property

    @method("GetLevel", "GetLevelHW", property="level")
    async def get_level(self) -> Decimal: ...

    @method("SetLevel", "SetLevelSW")
    async def set_level(self, level: float) -> None: ...
```

- `property="level"` — when a status message reports `GetLevel`, update `self.level`
- `fetch=True` (default) — `fetch_state()` will call this getter to populate initial state
- `handle_object_status(method, result, *args)` — called by the controller for ELAGG/STATUS messages; routes to the right property via `_method_properties`
- `handle_category_status(category, *args)` — called for `S:LOAD`, `S:BTN` etc.; subclasses override this

### Objects (`_objects/`)

Dataclasses representing Vantage hardware/software objects. Hierarchy:

```
SystemObject               — vid, master, name, d_name, m_time
└── LocationObject         — area (parent area VID)
    ├── Load               — load_type, power_profile; is_relay/is_motor/is_light props
    ├── StationObject      — serial_number, bus
    │   ├── Keypad
    │   ├── DualRelayStation
    │   └── …
    └── …
Button                     — parent (station VID), text1, text2, state
Area                       — area (parent area VID for tree walking)
GMem                       — tag, data_type, value; is_bool/is_int/is_fixed props
Task                       — running, state
DryContact                 — is_down
…
```

- `vantage_type()` — class method; returns `Meta.name` if defined, else the class name. Must match the XML element tag in ACI responses and Design Center backup files.
- `d_name` — preferred display name (firmware ≥ 3.x); use `obj.d_name or obj.name` everywhere

---

## Adding a New Object Type

1. **Create `_objects/my_type.py`** — dataclass inheriting from `SystemObject` or `LocationObject`, plus any interface mixins
2. **Export it from `objects.py`** — add to imports and `__all__`
3. **Create `_controllers/my_types.py`** — subclass `Controller[MyType]` with `vantage_types = ("MyType",)` and any convenience query properties
4. **Register in `_controllers/__init__.py`** — add the new controller class to exports
5. **Wire up in `Vantage.__init__`** — `add_controller(MyTypesController)`; add property accessor

---

## Local Config File (Design Center Backup XML)

The `_config_client/file_loader.py` module parses Design Center backup XML files (`{host}_config.txt`) without any network connection. The format is:

```xml
<Project>
  <Objects>
    <Object>
      <Load VID="447" Master="1">...</Load>
    </Object>
  </Objects>
</Project>
```

The inner `<TypeName ...>` XML is byte-for-byte identical to what `IConfiguration.GetFilterResults` returns — so the same xsdata parser works for both. `iter_objects(path)` yields parsed `SystemObject` instances; `Vantage._inject_from_file()` routes each to the matching controller.

**Use case:** Loads deleted from Design Center ("phantom loads") whose hardware is still present will not appear in a live IConfiguration fetch but will be in the backup file.

---

## Authentication Flow

Both clients probe for authentication requirements on connection open:

- **Config client:** Sends `GetSysInfo`; valid response → no auth needed
- **Command client:** Sends `ECHO`; `R:ECHO` → no auth; `R:ERROR` → auth required

This probe correctly handles controllers where the admin password has been disabled (login is not possible). No credentials are required and `Vantage(host, ssl=False)` works without username/password.

---

## Firmware Compatibility Notes

- **GETLOAD** — old command; returns `R:ERROR:8 "Not Implemented"` on IC-II firmware. Use `INVOKE <vid> Load.GetLevel` instead.
- **ELAGG** — enhanced log aggregation; available on IC-II. If not supported, fall back to `STATUS LOAD`, `STATUS BTN` category subscriptions.
- **d_name / m_time** — optional fields; absent in firmware 2.x. Always prefer `d_name or name`.
- **`area` field on LocationObject** — may be `None` on older firmware; guard with `if obj.area`.

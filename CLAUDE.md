# aiovantage — Notes for Claude

## Repository layout

```
src/aiovantage/
├── __init__.py                  # Vantage top-level class; local_config_file param here
├── objects.py                   # Public re-exports of all object dataclasses
├── controllers.py               # Public re-exports of all controller classes
├── _objects/                    # One file per Vantage object type (dataclasses)
├── _controllers/                # One file per controller; base.py has inject() + initialize()
├── _object_interfaces/          # Mixin interfaces (LoadInterface, ButtonInterface, …)
├── _config_client/              # ACI XML service: ConfigClient + file_loader.py
│   ├── client.py                # xsdata parser/serializer setup lives here
│   ├── file_loader.py           # Parses Design Center backup XML (local_config_file path)
│   └── interfaces/              # RPC method wrappers (IConfiguration, IIntrospection, …)
└── _command_client/             # HCI text service: CommandClient + EventStream
```

## Critical non-obvious rules

### XML parsing (xsdata)

- `XmlContext(models_package="aiovantage._objects")` tells xsdata to auto-discover dataclasses from the `_objects/` package by matching XML element names to class names.
- `_pascal_case_preserve()` is the name generator for both element and attribute names. It preserves already-PascalCase names (like `IConfiguration`, `DName`, `VID`) that the default `pascal_case()` function would mangle.
- **Both** the config client (`client.py`) and the file loader (`file_loader.py`) must use the same `XmlContext` configuration. If you add a new parser, copy that setup verbatim.
- `ParserConfig(fail_on_unknown_properties=False)` is required — Design Center files contain fields that don't map to any dataclass field, and crashing on those would break parsing.

### Object type names

- `cls.vantage_type()` returns the XML element tag for a class. It uses `cls.Meta.name` if defined, otherwise the Python class name. Special cases: `VantageDGColorLoad.vantage_type()` → `"Vantage.DGColorLoad"` (note the dot).
- The `vantage_types` tuple on each controller must exactly match the strings returned by `vantage_type()` for the objects it manages.
- When adding a new object type, add `Meta.name = "TypeName"` to the dataclass only if the XML tag differs from the Python class name.

### Controller injection vs. live fetch

- If `controller._initialized is True` when `initialize()` is called, the IConfiguration fetch is **skipped entirely**. This is how the local config file path works.
- `inject(obj)` sets `_initialized = True` on the first call. Controllers with zero injected objects still have `_initialized = False` and will do a normal live fetch — so controllers for object types not in the file (e.g., `BlindsController` on a system with no blinds) still work correctly.
- Do **not** emit `ObjectAdded` inside `inject()` — HA subscribers aren't registered yet when injection happens.

### Authentication

- The command client probe sends `ECHO`; `R:ECHO` = no auth; `R:ERROR` = auth required.
- The config client probe sends `GetSysInfo`; if the response is parseable = no auth.
- These probes correctly handle a controller where login is **disabled** (no password set). Pass `ssl=False` for plain TCP ports 2001/3001.
- Never assume authentication is required. Always let the probe decide.

### d_name vs. name

- Always use `obj.d_name or obj.name` when displaying or building entity names — `d_name` is the user-visible display name that may differ from the internal `name` field, and it's blank (not None) on firmware where it isn't set.

### Status event routing

- ELAGG enhanced log (`EL: <vid> <method> <result>`) → `handle_object_status(method, result, *args)`
- Category status (`S:LOAD <vid> <level>`, `S:BTN <vid> PRESS`) → `handle_category_status(category, *args)`
- Each interface subclass overrides `handle_category_status` for its own category. The base class raises `NotImplementedError` — call `super()` at the end of any override.

## Common tasks

### Add a new Vantage object type

1. `_objects/my_type.py` — dataclass inheriting `SystemObject` (or `LocationObject` if it lives in an area), plus relevant interface mixins
2. `objects.py` — import and add to `__all__`
3. `_controllers/my_types.py` — `class MyTypesController(Controller[MyType]): vantage_types = ("MyType",)`
4. `controllers.py` — import and add to `__all__`  *(also `_controllers/__init__.py` if that file isn't empty)*
5. `__init__.py` — add `self._my_types = add_controller(MyTypesController)` and a `@property` accessor

### Add a new object interface method

```python
@method("GetFoo", "GetFooHW", property="foo")
async def get_foo(self) -> SomeType: ...
```

- The first method name is the normal call; the second (optional) is the HW variant.
- `property="foo"` — when a status message names this method, `self.foo` is updated automatically.
- Return type annotation is used by `Converter` for deserialization; must be accurate.

### Parse a Design Center backup XML without a live connection

```python
from aiovantage._config_client.file_loader import iter_objects
for obj in iter_objects("192.168.0.200_config.txt"):
    print(obj.vantage_type(), obj.vid, obj.name)
```

## Testing tips

- The live controller at `192.168.0.200` is accessible without credentials on ports 2001 and 3001 (plain TCP, no SSL).
- `INVOKE <vid> Load.GetLevel` → `R:INVOKE <vid> <level> Load.GetLevel` — quick smoke test for any load.
- `ELAGG 1` → `R:ELAGG 1 ON` — confirms enhanced log is supported.
- Use `poetry run python3` inside the `new/aiovantage/` directory; `pip`/`pip3` are not installed globally.

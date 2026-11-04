# Run the IOC

There are two ways to start the CATio IOC: using a YAML configuration file, or
using the `ioc` command directly.

## YAML-driven mode

The YAML mode is recommended when you have multiple controllers or want to keep
your configuration in version control.

Create (or reuse) a `fastcs.yaml` file:

```yaml
# yaml-language-server: $schema=schema.json

controllers:
  - id: BL04I-EA-CATIO-01
    type: fastcs_catio.CATioServerController
    tcp_settings:
      target_ip: "172.23.242.42"
      target_port: 27905
    route:
      route_name: ""
      user_name: "Administrator"
      password: "1"
    scan_timings:
      poll_period: 1.0
      notification_period: 0.2
    name_mappings:
      device_prefix: "{id}:ETH{:02d}"
      node_prefix: "BL04I-EA-E1RIO-{:02d}"
      module_prefix: "{node_prefix}:MOD{:02d}"

transport:
  - epicsca: {}
    gui:
      output_dir: ./screens
```

Then run:

```
$ fastcs-catio run fastcs.yaml
```

## Direct `ioc` command

The `ioc` command is useful for quick tests or environments where configuration
files are inconvenient.  All settings that the YAML file exposes are available
as options:

```
$ fastcs-catio ioc BL04I-EA-CATIO-01 172.23.242.42 \
    --device-prefix "{id}:ETH{:02d}" \
    --node-prefix "BL04I-EA-E1RIO-{:02d}" \
    --module-prefix "{node_prefix}:MOD{:02d}"
```

Run `fastcs-catio ioc --help` for the full list of options.

## PV name templates

Both modes use the same three template strings to build the PV paths for the
EtherCAT hardware hierarchy:

| Template field | Controls |
|---|---|
| `device_prefix` | EtherCAT device |
| `node_prefix`   | Coupler or Box node |
| `module_prefix` | Individual I/O module (terminal) |

Templates are rendered with Python's `str.format()`.  The following
placeholders are available in each field:

| Placeholder | Available in | Description |
|---|---|---|
| `{}` / `{n}` / `{n:02d}` | all | Numeric index of the component (see note on `{group_alias}` below) |
| `{id}` | all | The IOC root prefix (e.g. `BL04I-EA-CATIO-01`) |
| `{device_prefix}` | `node_prefix`, `module_prefix` | Rendered name of the parent device |
| `{node_prefix}` | `module_prefix` | Rendered name of the parent node |
| `{group_alias}` | `module_prefix` | Short type alias for the terminal (e.g. `24VDO`, `10VAI`, `CPL`).  When this placeholder is present the numeric index counts per-coupler per alias (1-based), so all terminals of the same type on the same coupler are numbered in order: `24VDO01`, `24VDO02`, etc.  Falls back to `MOD` if the terminal type has no alias defined. |

:::{note}
The `ioc` command follows Unix CLI convention and spells option names with
hyphens (e.g. `--node-prefix`), while the template placeholder keys use
underscores (e.g. `{node_prefix}`).  This is intentional: hyphens are not
valid in Python identifier syntax and cannot be used as `str.format()` keys.
:::

:::{warning}
Underscores are **not** allowed in PV name components.  This applies to:

- Template literal text — e.g. `"ETH_{:02d}"` is invalid.
- The IOC root prefix (`id` in YAML / `pv_prefix` in the `ioc` command) —
  e.g. `BL04I-EA_CATIO-01` is invalid.

Use hyphens instead.  CATio validates both at startup and raises a
`ValueError` before any hardware connection is attempted.
:::

When a rendered template contains a colon (`:`) the result is split on `:`
into path segments, making the component a child of whatever comes before the
colon.  For example, `"{id}:ETH{:02d}"` rendered with id `BL04I-EA-CATIO-01`
and index 1 gives the path `["BL04I-EA-CATIO-01", "ETH01"]`.

---
name: ads-simulator-testing
description: Patterns for testing and debugging the ADS simulator in `tests/ads_sim/` — instantiation, loading EtherCAT chain configs, counting symbols, inspecting devices/slaves, debugging PDO-filtering issues on specific terminal types, and comparing simulator output against real hardware. Surface when working in `tests/ads_sim/`, editing `tests/test_system.py`, hitting `ModuleNotFoundError` for `ads_sim`, hitting `TypeError`/`AttributeError` on `EtherCATChain`, or debugging port-48898 binding problems.
---

# ads-simulator-testing

Testing and validating the ADS simulator in `tests/ads_sim/`.

## Never run the IOC yourself

**Do NOT run `fastcs-catio ioc` commands.** The IOC needs network
access to real hardware that may be unavailable or specially
configured. Ask the user to run it and report errors back.

## Import the simulator correctly

```python
import sys
sys.path.insert(0, 'tests')  # required for imports to resolve
from ads_sim.ethercat_chain import EtherCATChain
from pathlib import Path
```

Without the `sys.path.insert`, `from ads_sim...` raises
`ModuleNotFoundError`.

## Instantiate and load a config

```python
chain = EtherCATChain()  # create instance first
chain.load_config(Path('tests/ads_sim/server_config_CX7000_cs2.yaml'))
```

`load_config` is an **instance method**. There is no `from_config`
classmethod.

Common mistakes:

- `EtherCATChain.load_config(path)` → `TypeError`
- `EtherCATChain.from_config(path)` → `AttributeError`

## Count and inspect symbols

```python
print(f'Total symbols: {chain.total_symbol_count}')
print(f'Hardware count: 550')
print(f'Difference: {chain.total_symbol_count - 550}')

for dev_id, device in chain.devices.items():
    print(f'Device {dev_id}: {device.name}')
    for slave in device.slaves:
        print(f'  {slave.name} ({slave.type})')
        symbols = slave.get_symbols(dev_id, chain.runtime_symbols)
        print(f'    Symbols: {len(symbols)}')
```

## Debug PDO filtering on a specific terminal type

```python
for dev_id, device in chain.devices.items():
    for slave in device.slaves:
        if 'EL1502' in slave.type:  # swap in the terminal you're debugging
            symbols = slave.get_symbols(dev_id, chain.runtime_symbols)
            print(f'{slave.name} ({slave.type}): {len(symbols)} symbols')
            for sym in symbols:
                print(f'  - {sym["name"]}')
```

## Compare simulator output against hardware

```sh
# Simulator (localhost) → reference YAML
./tests/diagnose_hardware.py --ip 127.0.0.1 --dump-symbols --output /tmp/sim.yaml

# Real hardware vs reference YAML
./tests/diagnose_hardware.py --ip 172.23.242.42 --dump-symbols --compare /tmp/sim.yaml
```

## Port 48898 already in use

If `test_system.py` reports port 48898 is taken, VS Code's
auto-port-forwarding is likely holding it. Open the VS Code "Ports"
panel (View → Ports) and delete any forwarding for 48898 so the
simulator can bind.

## Related files

- `tests/ads_sim/ethercat_chain.py` — chain and device/slave models
- `tests/ads_sim/server.py` — ADS protocol server
- `tests/ads_sim/server_config_CX7000_cs2.yaml` — default simulator chain
- `tests/test_system.py` — integration tests against the simulator

## Related skill

- [[beckhoff-xml]] — symbol-count mismatches between simulator and
  hardware usually trace back to terminal YAML / XML-parsing bugs.

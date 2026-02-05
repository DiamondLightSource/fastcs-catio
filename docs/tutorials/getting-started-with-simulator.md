# Getting Started with the Simulator

This tutorial walks you through running fastcs-catio with the ADS simulator,
allowing you to explore the system without real Beckhoff hardware.

## Prerequisites

- fastcs-catio installed (see [Installation](installation.md))
- Podman or Docker installed (for running Phoebus)

## Overview

fastcs-catio uses two types of YAML configuration files:

1. **Terminal Type Definitions** (`terminal_types.yaml`) - Describes the
   capabilities of each Beckhoff terminal type (e.g., EL2024, EL3104). This
   includes:
   - Product identity (vendor ID, product code, revision)
   - Symbol definitions (inputs, outputs, their data types)
   - CoE (CANopen over EtherCAT) objects for configuration

2. **Server Configuration** (`server_config_*.yaml`) - Describes the physical
   EtherCAT chain topology:
   - Which terminals are connected
   - Their positions in the chain
   - Device groupings

In this tutorial, we copy these files to `/tmp` so you can experiment with
modifying them without affecting the source repository.

## Step 1: Copy Configuration Files

First, copy the configuration files to a working directory:

```bash
# Copy terminal type definitions
cp src/catio_terminals/terminals/terminal_types.yaml /tmp/

# Copy server configurations (we'll use the CX7000_cs2 config)
cp tests/ads_sim/server_config_*.yaml /tmp/
```

You now have editable copies of:

| File | Purpose |
|------|---------|
| `/tmp/terminal_types.yaml` | Defines all supported terminal types and their symbols |
| `/tmp/server_config_CX7000_cs2.yaml` | Simulates a CX7000 with 107 I/O terminals |
| `/tmp/server_config_CX7000_cs1.yaml` | Alternative smaller configuration |
| `/tmp/server_config_CX8290_cs1.yaml` | CX8290 configuration |

## Step 2: Start the ADS Simulator

Open a terminal and start the simulator:

```bash
python -m tests.ads_sim \
    --terminal-defs /tmp/terminal_types.yaml \
    --config /tmp/server_config_CX7000_cs2.yaml \
    --log-level INFO
```

You should see output indicating the server has started:

```
2026-02-05 14:30:00 - ads_sim.server - INFO - ADS Simulation Server starting...
2026-02-05 14:30:00 - ads_sim.server - INFO - Listening on 127.0.0.1:48898 (TCP)
2026-02-05 14:30:00 - ads_sim.server - INFO - Loaded 107 slaves with 461 symbols
```

:::{tip}
Add `--disable-notifications` to reduce log verbosity once you've confirmed
the server is working.
:::

Leave this terminal running and open a new terminal for the next step.

## Step 3: Start the fastcs-catio IOC

In a new terminal, start the IOC connecting to the simulator:

```bash
fastcs-catio ioc TUTORIAL \
    --terminal-defs /tmp/terminal_types.yaml \
    --screens-dir /tmp/screens
```

The command arguments:
- `TUTORIAL` - The PV prefix for all EPICS records (e.g., `TUTORIAL:ETH1:...`)
- `--terminal-defs` - Points to our editable terminal definitions
- `--screens-dir` - Where to write the generated Phoebus `.bob` screen files

You should see the IOC start and begin polling the simulator:

```
INFO - Connecting to ADS server at 127.0.0.1:48898
INFO - Connected to I/O Server (version 3.1, build 2103)
INFO - Discovered 1 device with 107 slaves
INFO - Created 461 EPICS PVs
```

The IOC is now running and exposing the simulated I/O as EPICS PVs.

## Step 4: Launch Phoebus

This step uses podman. Therefore you need to have podman installed and configured on your system. **IMPORTANT**: this means that you cannot launch from inside the devcontainer if that is where you are running the simulator and IOC. Use a native terminal on your host machine for this step.

With both the simulator and IOC running, launch Phoebus to view the GUI:

```bash
./opi/phoebus-launch.sh
```

This starts Phoebus in a container with access to the generated screens.

:::{note}
The first launch may take a moment as it pulls the container image.
:::

## Step 5: Exploring the GUI

Once Phoebus opens, you'll see the main CATio screen showing the EtherCAT
device tree.

### Main Screen

The main screen (`catio.bob`) displays:

- **Device overview** - Shows the connected EtherCAT master device
- **Slave tree** - Hierarchical view of all terminals in the chain

Click on "ETH1" to see the first EtherCAT device, then click through the
hierarchy to explore individual terminals.

### Terminal Screens

Each terminal type has its own screen showing relevant I/O:

**Digital Output (EL2024)**

Navigate to any EL2024 terminal (e.g., Term 4) to see:
- 4 output channels with toggle buttons
- Working counter status
- State indicators

Try clicking the output toggles - they will update in the simulator.

**Digital Input (EL1004/EL1014)**

Digital input terminals show:
- 4 input channel states
- Working counter indicator

**Analog Input (EL3104/EL3204)**

Analog input terminals display:
- Multiple input channels with current values
- Status and diagnostic information

**Counter Terminals (EL1502)**

Counter terminals show:
- Counter values
- Control bits for counter operation
- Status indicators


## Step 6: Experiment

Now that everything is running, try these experiments:

### View EPICS PVs

In another terminal, use `caget` or `camonitor` to see the PVs:

```bash
# List all PVs with the TUTORIAL prefix
caget TUTORIAL:ETH1:RIO1:MOD1:CH1:OUTPUT

# Monitor a digital output
camonitor TUTORIAL:ETH1:RIO1:MOD1:CH1:OUTPUT
```

### Modify the Chain Topology

Edit `/tmp/server_config_CX7000_cs2.yaml` to:
- Remove terminals from the chain
- Change terminal positions

Restart both the simulator and IOC to see the new topology.

## Cleanup

When finished, stop the processes with `Ctrl+C`:

1. Stop Phoebus (close the window or `Ctrl+C`)
2. Stop the IOC (`Ctrl+C` in its terminal)
3. Stop the simulator (`Ctrl+C` in its terminal)

## Next Steps

- Learn about [terminal YAML definitions](../explanations/terminal-yaml-definitions.md)
- Explore the [architecture overview](../explanations/architecture-overview.md)

## Troubleshooting

### Port already in use

If you see "Address already in use" when starting the simulator:

The first thing to try is deleting the port forwarding in VS Code, which is likely the cause. Then restart the simulator and IOC.

```bash
# Check what's using port 48898
lsof -i :48898

# Kill the process or use a different port
python -m tests.ads_sim --port 48899
```

### No PVs visible in Phoebus

Ensure the IOC is running and check the PV prefix matches. The default
configuration uses `TUTORIAL` as the prefix.

### Container permission errors

If Phoebus fails to start, ensure your user can run containers:

```bash
podman ps  # Should work without sudo
```

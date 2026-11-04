# Customizing Terminal Definitions

This tutorial shows how to customize which symbols and CoE objects are exposed
by the IOC using the `catio-terminals` GUI editor.

## Prerequisites

- Completed [Getting Started with the Simulator](getting-started-with-simulator.md)
- Configuration files copied to `/tmp`

## Overview

The terminal definitions YAML file controls which data points the IOC exposes
as EPICS Process Variables (PVs). Each Beckhoff terminal type has many
potential symbols and CoE (CANopen over EtherCAT) configuration objects, but
you typically only need a subset of them.

In this tutorial, you will:
1. View an EL1502 counter terminal's current PVs
2. Use the catio-terminals GUI to add more CoE objects
3. See the new PVs appear after restarting the IOC

## Step 1: Start the Simulator

If the simulator from the first tutorial is still running, you can skip this
step. Otherwise, start it:

```bash
python -m tests.ads_sim \
    --terminal-defs /tmp/terminal_types.yaml \
    --config /tmp/server_config_CX7000_cs2.yaml \
    --disable-notifications
```

## Step 2: Start the IOC and Observe Current State

In a new terminal, start the IOC:

```bash
fastcs-catio ioc IOC \
    --terminal-defs /tmp/terminal_types.yaml
```

Use Phoebus to navigate to **ETH1 > RIO2 > MOD13**. You'll see the current
symbols and CoE objects exposed for the EL1502 terminal:

You can identify the CoEs by the fact that they are grouped into their own group boxes, the symbols all appear in the first group box.

## Step 3: Fetch the Beckhoff Terminal Database

Before editing terminal definitions, you need to download Beckhoff's ESI
(EtherCAT Slave Information) database. This XML catalog describes all terminal
types and their available symbols.

Run the cache update command:

```bash
catio-terminals update-cache
```

This downloads XML files from Beckhoff's website to `~/.cache/catio_terminals/`.
You only need to do this once (or when new terminal types are released).

:::{note}
The download may take a minute. You'll see progress messages as it parses
each XML file.
:::

## Step 4: Launch the Terminal Editor

Now launch the catio-terminals GUI to edit the terminal definitions:

```bash
catio-terminals edit /tmp/terminal_types.yaml
```

A browser window will open with the terminal editor interface.

:::{tip}
If a browser doesn't open automatically, look in the terminal output for a
URL like `http://localhost:8080` and open it manually.
:::

## Step 5: Find the EL1502 Terminal

The editor shows a list of all terminal types defined in the YAML file.

1. **Use the filter** - Type `EL1502` in the filter/search box at the top
2. **Click on EL1502** - This opens the terminal details panel

You'll see two main sections:
- **Symbol Nodes (PDO)** - Process data (counter values, control bits)
- **CoE Objects** - Configuration parameters accessible via SDO

## Step 6: Add CoE Objects

The EL1502 has several CoE objects available for configuration. Let's add
some useful ones.

### Available CoE Objects

The EL1502 supports the following CoE configuration objects and by default these are already selected in the YAML file. The 0x8000 range of Coe addresses represents the operational configuration parameters for all terminals that have CoE.

There are many more CoE objects available for the EL1502. In this exercise you can add a few more to see the result in the IOC and Phoebus.

| Index | Name | Purpose |
|-------|------|---------|
| 0x8000 | CNT Settings Ch.1 | Channel 1 counter configuration |
| 0x8010 | CNT Settings Ch.2 | Channel 2 counter configuration |
| 0x8020 | CNT Settings | Combined counter settings |

### Select CoE Objects

1. Scroll down to the **CoE Objects** section
2. Click the checkbox next to these objects to select them:
   - **CNT Settings Ch.1** (index 0x8000)
   - **CNT Settings Ch.2** (index 0x8010)
   - **CNT Settings** (index 0x8020)

3. Expand a CoE object to see its sub-indices:
   - Each sub-index is a configurable parameter
   - For example, CNT Settings Ch.1 has:
     - Enable function to set output
     - Enable function to reset output
     - Enable reload
     - Count down
     - Switch on threshold value
     - Switch off threshold value
     - Counter reload value

4. Select individual sub-indices you want to expose as PVs

:::{tip}
The counter threshold values are particularly useful - they let you configure
at what count values the terminal sets or resets its digital output.
:::

## Step 7: Save the Configuration

Click the **Save** button in the editor toolbar.

The YAML file is updated with your selections. You can verify by examining
the file:

```bash
# Check the EL1502 section in the YAML
grep -A 100 "EL1502:" /tmp/terminal_types.yaml | head -120
```

Look for `selected: true` on the CoE object subindices you enabled.

## Step 8: Restart the IOC

The IOC reads terminal definitions at startup, so you need to restart it to
pick up the changes.

1. Stop the running IOC with `Ctrl+C`
2. Restart it:

```bash
fastcs-catio ioc IOC \
    --terminal-defs /tmp/terminal_types.yaml
```

:::{note}
The simulator can stay running - you only need to restart the IOC.
:::

## Step 9: View the New PVs

Navigate back to the EL1502 terminal in Phoebus (ETH1 > RIO2 > MOD13).

You should now see additional PVs for the CoE objects you selected:
- Counter configuration parameters
- Threshold values
- Enable flags

These parameters are now readable and writable through EPICS!

### Example: Configure Counter Threshold

Try setting a counter threshold:

```bash
# Set the "switch on" threshold for channel 1 to 100
caput IOC:ETH1:RIO2:MOD13:CNT_SETTINGS_CH_1:SWITCH_ON_THRESHOLD_VALUE 100

# Read it back
caget IOC:ETH1:RIO2:MOD13:CNT_SETTINGS_CH_1:SWITCH_ON_THRESHOLD_VALUE
```

## Understanding CoE vs PDO

| Type | What It Is | Access Speed | Use Case |
|------|------------|--------------|----------|
| **PDO (Symbol)** | Process data | Fast (cyclic) | Real-time I/O values |
| **CoE (SDO)** | Configuration | Slower (acyclic) | Setup parameters |

- **PDO symbols** (counter value, status bits) update every EtherCAT cycle
- **CoE objects** (thresholds, enable flags) are configuration parameters read/written on demand

Most applications need PDO symbols for monitoring. CoE objects are useful when
you need to configure terminal behavior at runtime.

## Experiment Further

### Add More Terminal Types

TODO: this experiment needs to be expanded into a separate tutorial in which we add terminals to the chain and then see that we need to update the terminal definitions to get those new terminals working.

Try adding CoE objects to other terminal types:
- **EL3104** - Analog input scaling and filter settings
- **EL2024** - Digital output diagnostics

### Remove Unused Symbols

If your IOC has too many PVs, use the editor to deselect symbols you don't
need. This reduces memory usage and simplifies the Phoebus screens.

### Create Custom YAML Files

For production deployments, you might maintain separate YAML files for
different beamlines or experiments:

```bash
# Copy the base definitions
cp /tmp/terminal_types.yaml /tmp/beamline_i22.yaml

# Edit for I22-specific terminals
catio-terminals edit /tmp/beamline_i22.yaml

# Start IOC with custom definitions
fastcs-catio ioc BL22I-EA-CATIO-01 \
    --terminal-defs /tmp/beamline_i22.yaml
```

## Next Steps

- Learn about [Terminal YAML Definitions](../explanations/terminal-yaml-definitions.md)
  in depth
- Explore [CoE Parameters](../explanations/coe-parameters.md) available for
  different terminal types
- See [Architecture Overview](../explanations/architecture-overview.md) for how
  the system works

## Troubleshooting

### CoE Objects Not Appearing

- Ensure you saved the YAML file in the editor
- Verify the IOC was restarted (not just the simulator)
- Check for YAML syntax errors: `python -c "import yaml; yaml.safe_load(open('/tmp/terminal_types.yaml'))"`

### Editor Won't Start

- Ensure the terminals optional dependency is installed: `uv pip install -e ".[terminals]"`
- Check no other process is using port 8080

### PV Names Changed

CoE object PV names are derived from their names in the Beckhoff XML. If names
look different after editing, the XML database may have been updated. This is
normal - the names are canonical from Beckhoff.

Because the screens are autogenerated, you need only refresh them with `right-click > Re-load display` to see the new PVs after editing terminal definitions and restarting the IOC.

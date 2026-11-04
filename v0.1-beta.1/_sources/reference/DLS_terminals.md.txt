# DLS Terminal Types

A full list of the EtherCAT terminal types found in Diamond Light Source production IOCs.

Extracted (by Claude) from `devices.list` on 2026-01-27, which was made using:

```bash
grep device /dls_sw/prod/R3.14.12.7/ioc/*/*/*/*App/data/expanded.xml > devices.list
```

## Summary

| Series | Count | Description |
|--------|-------|-------------|
| EK1xxx | 2 | EtherCAT Couplers |
| EL1xxx | 4 | Digital Inputs |
| EL2xxx | 7 | Digital Outputs |
| EL3xxx | 9 | Analog Inputs |
| EL4xxx | 2 | Analog Outputs |
| EL9xxx | 4 | System/Power |
| ELMxxxx | 1 | Measurement |
| EP2xxx | 2 | EtherCAT Box Digital I/O |
| EP3xxx | 4 | EtherCAT Box Analog Input |
| EP4xxx | 2 | EtherCAT Box Analog Output |
| **Total** | **35** | |

## Terminal List

### EtherCAT Couplers (EK1xxx)

| Terminal | Description |
|----------|-------------|
| EK1100 | EtherCAT Coupler |
| EK1122 | EtherCAT Junction |

### Digital Inputs (EL1xxx)

| Terminal | Description |
|----------|-------------|
| EL1014 | 4Ch Digital Input 24V DC |
| EL1084 | 4Ch Digital Input 24V DC, Negative Switching |
| EL1124 | 4Ch Digital Input 5V DC |
| EL1502 | 2Ch Up/Down Counter 24V DC |

### Digital Outputs (EL2xxx)

| Terminal | Description |
|----------|-------------|
| EL2024 | 4Ch Digital Output 24V DC, 2A |
| EL2024-0010 | 4Ch Digital Output 24V DC, 2A (TwinSAFE SC) |
| EL2124 | 4Ch Digital Output 5V DC |
| EL2502 | 2Ch PWM Output 24V DC |
| EL2595 | LED Dimmer Terminal |
| EL2612 | 2Ch Relay Output, NO |
| EL2624 | 4Ch Relay Output, NO |

### Analog Inputs (EL3xxx)

| Terminal | Description |
|----------|-------------|
| EL3104 | 4Ch Analog Input +/-10V, Differential |
| EL3124 | 4Ch Analog Input 4-20mA, Differential |
| EL3202 | 2Ch PT100 RTD Input |
| EL3202-0010 | 2Ch PT100 RTD Input (High Precision) |
| EL3314 | 4Ch Thermocouple Input |
| EL3356-0010 | 1Ch Precision Load Cell Input |
| EL3602 | 2Ch Analog Input +/-10V, Differential, 24-bit |
| EL3702 | 2Ch Analog Input +/-10V, Differential, Oversampling |
| ELM3704-0000 | 4Ch Multi-function Analog Input |

### Analog Outputs (EL4xxx)

| Terminal | Description |
|----------|-------------|
| EL4134 | 4Ch Analog Output +/-10V |
| EL4732 | 2Ch Analog Output +/-10V, 16-bit |

### System/Power (EL9xxx)

| Terminal | Description |
|----------|-------------|
| EL9410 | E-Bus Power Supply |
| EL9505 | Power Supply 5V DC |
| EL9510 | Power Supply 10V DC |
| EL9512 | Power Supply 12V DC |

### EtherCAT Box - Digital I/O (EP2xxx)

| Terminal | Description |
|----------|-------------|
| EP2338-0002 | 8Ch Digital Input + 8Ch Digital Output 24V DC |
| EP2624-0002 | 4Ch Relay Output |

### EtherCAT Box - Analog Input (EP3xxx)

| Terminal | Description |
|----------|-------------|
| EP3174-0002 | 4Ch Analog Input +/-10V |
| EP3204-0002 | 4Ch PT100 RTD Input |
| EP3314-0002 | 4Ch Thermocouple Input |

### EtherCAT Box - Analog Output (EP4xxx)

| Terminal | Description |
|----------|-------------|
| EP4174-0002 | 4Ch Analog Output +/-10V |
| EP4374-0002 | 2Ch Analog Input + 2Ch Analog Output +/-10V |

## Raw List

```
EK1100
EK1122
EL1014
EL1084
EL1124
EL1502
EL2024
EL2024-0010
EL2124
EL2502
EL2595
EL2612
EL2624
EL3104
EL3124
EL3202
EL3202-0010
EL3314
EL3356-0010
EL3602
EL3702
EL4134
EL4732
EL9410
EL9505
EL9510
EL9512
ELM3704-0000
EP2338-0002
EP2624-0002
EP3174-0002
EP3204-0002
EP3314-0002
EP4174-0002
EP4374-0002
```

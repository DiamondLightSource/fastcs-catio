[![CI](https://github.com/DiamondLightSource/fastcs-catio/actions/workflows/ci.yml/badge.svg)](https://github.com/DiamondLightSource/fastcs-catio/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/DiamondLightSource/fastcs-catio/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/fastcs-catio)
[![PyPI](https://img.shields.io/pypi/v/fastcs-catio.svg)](https://pypi.org/project/fastcs-catio)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# fastcs-catio

CATio provides control system integration for Beckhoff EtherCAT I/O devices running under TwinCAT. It uses the ADS protocol to communicate with TwinCAT PLCs and exposes device data as EPICS Process Variables through the FastCS framework.

Source          | <https://github.com/DiamondLightSource/fastcs-catio>
:---:           | :---:
PyPI            | `pip install fastcs-catio`
Docker          | `docker run ghcr.io/diamondlightsource/fastcs-catio:latest`
Documentation   | <https://diamondlightsource.github.io/fastcs-catio>
Releases        | <https://github.com/DiamondLightSource/fastcs-catio/releases>

## Quick Start

```bash
# Install
pip install fastcs-catio

# Run the IOC
fastcs-catio ioc --target-ip 192.168.1.100
```

<!-- README only content. Anything below this line won't be included in index.md -->

See https://diamondlightsource.github.io/fastcs-catio for more detailed documentation.

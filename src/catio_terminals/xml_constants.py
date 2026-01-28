"""Constants and patterns for Beckhoff XML parsing."""

import re

# Pre-compiled regex patterns
TERMINAL_ID_PATTERN = re.compile(r"([A-Z]{2,3}\d{4})", re.IGNORECASE)

# Captures: (prefix)(keyword)(channel_num)(suffix)
CHANNEL_KEYWORD_PATTERN = re.compile(
    r"(.*?)\s*(Channel|Ch\.?|Input|Output|AI|AO|DI|DO)\s+(\d+)(.*)",
    re.IGNORECASE,
)

CHANNEL_NUMBER_PATTERN = re.compile(r"(.+?)\s+(\d+)$")

# Match array element pattern: "BaseName__ARRAY [N]" or "BaseName ARRAY [N]"
# Captures: (base_name, array_index)
ARRAY_ELEMENT_PATTERN = re.compile(r"^(.+?)(?:__|[ ])ARRAY \[(\d+)\]$")

# ADS type mapping
ADS_TYPE_MAP: dict[str, int] = {
    "BOOL": 33,
    "BYTE": 16,
    "USINT": 16,
    "SINT": 17,
    "WORD": 18,
    "UINT": 18,
    "INT": 2,
    "DWORD": 19,
    "UDINT": 19,
    "DINT": 3,
    "REAL": 4,
    "LREAL": 5,
}

# URL category mapping for Beckhoff website
URL_CATEGORY_MAP: dict[str, str] = {
    "DigIn": "el-ed1xxx-digital-input",
    "DigOut": "el-ed2xxx-digital-output",
    "AnaIn": "el-ed3xxx-analog-input",
    "AnaOut": "el-ed4xxx-analog-output",
    "Measuring": "el5xxx-position-measurement",
    "Communication": "el6xxx-communication",
    "Motor": "el7xxx-servo-drive",
    "PowerSupply": "el9xxx-power-supply",
}


def parse_hex_value(value: str) -> int:
    """Parse Beckhoff hex string (#x prefix) or standard hex to integer.

    Args:
        value: Hex string with #x prefix or standard format

    Returns:
        Integer value
    """
    if value.startswith("#x"):
        return int(value[2:], 16)
    return int(value, 0)


def get_ads_type(data_type: str) -> int:
    """Map EtherCAT data type to ADS type code.

    Args:
        data_type: EtherCAT data type name (e.g., "BOOL", "UINT")

    Returns:
        ADS type code (65 = generic structure for unknown types)
    """
    return ADS_TYPE_MAP.get(data_type.upper(), 65)


def generate_terminal_url(terminal_id: str, group_type: str) -> str:
    """Generate Beckhoff website URL for a terminal.

    Args:
        terminal_id: Terminal ID (e.g., "EL3104")
        group_type: Group type from XML (e.g., "AnaIn")

    Returns:
        URL to Beckhoff product page
    """
    category = URL_CATEGORY_MAP.get(group_type, "ethercat-terminals")
    base = "https://www.beckhoff.com/en-gb/products/i-o/ethercat-terminals"
    return f"{base}/{category}/{terminal_id.lower()}.html"

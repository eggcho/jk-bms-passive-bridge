# JK BMS Passive Bridge

Passive multi-pack JK BMS RS485 bridge for Home Assistant.

This project listens to the JK UART2 / RS485 traffic without sending active
queries on the bus. It is meant for installations where a master device
already owns the bus, for example:

- JK master pack polling multiple slave packs
- Deye inverter connected to the battery bus
- Home Assistant consuming the same data passively through MQTT

## What it does

- Passively decodes JK `0x01` and `0x02` frames from the bus
- Identifies the source pack using the short Modbus delimiter after each JK frame
- Publishes MQTT discovery and state topics for Home Assistant
- Uses entity names compatible with [`jk-bms-card`](https://github.com/Pho3niX90/jk-bms-card)
- Includes forensic tools for live monitoring, passive capture, frame analysis, and MQTT cleanup

## Why this exists

Many JK BMS integrations assume they can poll the device directly. That is not
always safe on a shared bus where another master is already active. This bridge
focuses on the passive case: read what is already on the wire and do not inject
queries into the production bus.

## Current scope

Tested on a real setup with:

- JK BMS PB2A16S20P packs
- 2 packs in parallel
- UART2 / RS485 passive sniffing
- Home Assistant over MQTT
- entity naming aligned with `jk-bms-card`

The parser currently relies on full `300-byte` frames for stable state updates.
Shorter frames are tracked as partial frames and ignored for state publication.

## Repository layout

- `src/jk_bms_passive_bridge/`
  - application code
- `config/config.example.yaml`
  - example runtime configuration
- `docs/`
  - architecture and usage notes
- `tests/`
  - parser and mapping tests

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Create a local config file:

```bash
cp config/config.example.yaml config/config.yaml
```

Edit:

- serial port
- MQTT broker credentials
- pack names, addresses, prefixes

## Main commands

Run the Home Assistant poller:

```bash
jk-bms-ha-poller --config config/config.yaml
```

Run the live forensic monitor:

```bash
jk-bms-live-monitor --config config/config.yaml
```

Capture passive traffic for 60 seconds:

```bash
jk-bms-passive-capture captures/bus.bin --config config/config.yaml --seconds 60
```

Analyze a capture:

```bash
jk-bms-frame-analyzer captures/bus.bin
```

Clear retained MQTT topics from older runs:

```bash
jk-bms-mqtt-cleanup --config config/config.yaml
```

## Home Assistant

The poller publishes discovery entities with prefixes you define in
`config/config.yaml`.

Example prefix:

- `jk_bms_pack_1`

Example entities:

- `sensor.jk_bms_pack_1_total_voltage`
- `sensor.jk_bms_pack_1_current`
- `sensor.jk_bms_pack_1_cell_voltage_1`
- `sensor.jk_bms_pack_1_cell_resistance_1`
- `switch.jk_bms_pack_1_charging`
- `binary_sensor.jk_bms_pack_1_balancing`

See [docs/home-assistant.md](docs/home-assistant.md).

## Limitations

- Not all JK information appears passively on the bus
- Version / about blocks such as `0x1400` are not currently available in passive mode on the tested setup
- The project is intentionally conservative and avoids active reads on the production bus
- More JK hardware / firmware variants need field validation

## Development

Run tests:

```bash
pip install -e .[dev]
pytest
```

## License

MIT

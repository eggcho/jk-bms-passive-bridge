# JK BMS Passive Bridge

Passive multi-pack JK BMS RS485 bridge for Home Assistant.

## Problem solved

This project solves one very specific problem:

**reading multiple JK BMS packs from one RS485 bus without becoming another bus master.**

This matters in real installations where:

- one JK pack already acts as the master on UART2 / RS485
- one or more slave packs answer on the same bus
- a Deye inverter or another external device is already connected
- Home Assistant should receive the same data without sending active queries

Most JK integrations assume they can poll one BMS directly. That is often not
the right model for a shared bus with multiple packs. This bridge takes the
opposite approach:

- do not poll the production bus
- do not compete with the existing master
- only decode what is already present on the wire

This project listens to the JK UART2 / RS485 traffic without sending active
queries on the bus. It is meant for installations where a master device
already owns the bus, for example:

- JK master pack polling multiple slave packs
- Deye inverter connected to the battery bus
- Home Assistant consuming the same data passively through MQTT

In addition to passive realtime/config decoding, the bridge can optionally send
an infrequent active `0x1400` about/version query to enrich the data with:

- hardware version
- software version
- serial number
- bluetooth name
- first-on date

Sensitive values such as the Bluetooth PIN and password are published only in a
masked form. The raw values are available only through the dedicated probe
tool.

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

## What can be observed on the bus

On the tested setup, the useful passive traffic is made of two JK frame types:

- `0x01` = config / settings block
- `0x02` = realtime / status block

Each JK frame is followed by a short Modbus write-style delimiter. That
delimiter is the key to pack identification.

Example, master pack realtime frame:

```text
55 AA EB 90 02 00 ...
00 10 16 20 00 01 05 9A
```

Example, master pack config frame:

```text
55 AA EB 90 01 00 ...
00 10 16 1E 00 01 64 56
```

Example, slave pack realtime frame:

```text
55 AA EB 90 02 00 ...
02 10 16 20 00 01 04 78
```

What these examples show:

- `55 AA EB 90` is the JK frame header
- the JK frame byte after the header identifies the block type:
  - `01` = config
  - `02` = realtime
- the first byte of the short delimiter identifies the source pack:
  - `00` = master pack
  - `02` = slave pack with address `0x02`
- the delimiter register byte distinguishes the JK bulk block:
  - `1E` -> config block
  - `20` -> realtime block

On the tested installation, these frames repeat continuously for each pack.
In a clean 60 second capture, the bridge observed:

- 9 valid `0x01` frames for pack `0x00`
- 9 valid `0x02` frames for pack `0x00`
- 9 valid `0x01` frames for pack `0x02`
- 9 valid `0x02` frames for pack `0x02`

See [docs/protocol-notes.md](docs/protocol-notes.md) for a more detailed
explanation of what is visible in a passive dump and which fields are carried
by each frame type.

## Current scope

Tested on a real setup with:

- JK BMS PB2A16S20P packs
- 2 packs in parallel
- UART2 / RS485 passive sniffing
- Home Assistant over MQTT
- entity naming aligned with `jk-bms-card`

The parser currently relies on full `300-byte` frames for stable state updates.
Shorter frames are tracked as partial frames and ignored for state publication.

The optional active `about` query is intended for installations where this
serial adapter is connected to a JK RS485 port that is safe to query directly.

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

If you want a beginner-friendly guide with exact commands, start here:

- [docs/beginner-step-by-step.md](docs/beginner-step-by-step.md)

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

Actively probe the about/version block:

```bash
jk-bms-active-probe --pack 0x02 --query about --hex
```

## Home Assistant

The poller publishes Home Assistant MQTT discovery automatically.

High level flow:

1. configure MQTT in `config/config.yaml`
2. run `jk-bms-ha-poller`
3. wait for valid RS485 frames
4. Home Assistant creates the entities through MQTT discovery
5. point `jk-bms-card` at the configured pack prefix

Example prefix:

- `jk_bms_pack_1`

Example entities:

- `sensor.jk_bms_pack_1_total_voltage`
- `sensor.jk_bms_pack_1_current`
- `sensor.jk_bms_pack_1_cell_voltage_1`
- `sensor.jk_bms_pack_1_cell_resistance_1`
- `switch.jk_bms_pack_1_charging`
- `binary_sensor.jk_bms_pack_1_balancing`

See [docs/home-assistant.md](docs/home-assistant.md) for:

- end-to-end setup
- example `jk-bms-card` configuration
- troubleshooting
- a more detailed HA explanation

For Grafana / VictoriaMetrics users, see:

- [docs/grafana.md](docs/grafana.md)
- [docs/grafana-dashboard-plain.json](docs/grafana-dashboard-plain.json)

For a ready-to-adapt service file, see:

- [docs/systemd.md](docs/systemd.md)

## Screenshots

Original `jk-bms-card` layout:

![Original jk-bms-card layout](docs/images/jk-bms-card-example_original.png)

Core Reactor layout:

![Core Reactor jk-bms-card layout](docs/images/jk-bms-card-example_core_reactor.png)

## Limitations

- Not all JK information appears passively on the bus
- Version / about blocks such as `0x1400` are not currently available in passive mode on the tested setup
- The project is intentionally conservative and avoids active reads on the production bus
- More JK hardware / firmware variants need field validation

For protocol notes and passive dump examples, see:

- [docs/architecture.md](docs/architecture.md)
- [docs/protocol-notes.md](docs/protocol-notes.md)

## Development

Run tests:

```bash
pip install -e .[dev]
pytest
```

## License

MIT

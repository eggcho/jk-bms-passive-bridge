# Home Assistant

This project is designed to solve the Home Assistant side of the problem as
well, not only the RS485 decoding side.

The intended end-to-end flow is:

1. JK packs exchange data on UART2 / RS485
2. this bridge listens passively to that traffic
3. the bridge publishes MQTT discovery + state
4. Home Assistant auto-creates the entities
5. `jk-bms-card` reads those entities and renders the battery view

## What problem this solves in HA

The usual pain points are:

- multiple JK BMS packs on one bus
- another master already owns the bus
- Home Assistant should not break inverter/BMS communication
- users still want full battery dashboards in HA

This bridge addresses that by publishing normal MQTT-discovered entities with
names that match what `jk-bms-card` expects.

## Prerequisites

You need:

- a working MQTT broker
- Home Assistant MQTT integration configured and connected to that broker
- the bridge running on a machine that can read the JK RS485 adapter
- a `config/config.yaml` file for this project

## Bridge configuration

Start from:

```bash
cp config/config.example.yaml config/config.yaml
```

Important settings:

- `serial.port`
- `mqtt.broker`
- `mqtt.username`
- `mqtt.password`
- `mqtt.discovery_prefix`
- `mqtt.state_root`
- `packs[].address`
- `packs[].prefix`

Example:

```yaml
serial:
  port: /dev/ttyUSB0
  baud_rate: 115200

mqtt:
  broker: 192.168.1.10
  port: 1883
  username: your_mqtt_username
  password: your_mqtt_password
  discovery_prefix: homeassistant
  state_root: jk_bms_passive_bridge

packs:
  - address: 0x00
    name: JK BMS Pack 1
    prefix: jk_bms_pack_1
  - address: 0x02
    name: JK BMS Pack 2
    prefix: jk_bms_pack_2
```

The most important HA-facing value is the `prefix`.

## Running the bridge

Run the poller:

```bash
jk-bms-ha-poller --config config/config.yaml
```

When valid realtime frames arrive, the bridge will:

- publish MQTT discovery topics under `homeassistant/...`
- publish state JSON under:
  - `<state_root>/<pack_prefix>/state`

Example state topic:

- `jk_bms_passive_bridge/jk_bms_pack_1/state`

## Discovery

The poller publishes Home Assistant MQTT discovery topics under:

- `homeassistant/`

State payloads are published under:

- `<state_root>/<pack_prefix>/state`

Default `state_root` from the example config:

- `jk_bms_passive_bridge`

After the poller starts and receives valid data, Home Assistant should create
entities automatically.

## Expected entities

For a pack prefix like:

- `jk_bms_pack_1`

you should see entities such as:

- `sensor.jk_bms_pack_1_total_voltage`
- `sensor.jk_bms_pack_1_current`
- `sensor.jk_bms_pack_1_power`
- `sensor.jk_bms_pack_1_state_of_charge`
- `sensor.jk_bms_pack_1_capacity_remaining`
- `sensor.jk_bms_pack_1_average_cell_voltage`
- `sensor.jk_bms_pack_1_delta_cell_voltage`
- `sensor.jk_bms_pack_1_min_voltage_cell`
- `sensor.jk_bms_pack_1_max_voltage_cell`
- `sensor.jk_bms_pack_1_cell_voltage_1`
- `sensor.jk_bms_pack_1_cell_resistance_1`
- `sensor.jk_bms_pack_1_temperature_sensor_1`
- `sensor.jk_bms_pack_1_power_tube_temperature`
- `sensor.jk_bms_pack_1_total_runtime_formatted`
- `sensor.jk_bms_pack_1_errors`
- `switch.jk_bms_pack_1_charging`
- `switch.jk_bms_pack_1_discharging`
- `switch.jk_bms_pack_1_balancer`
- `binary_sensor.jk_bms_pack_1_balancing`

## `jk-bms-card` compatibility

The entity names are aligned with the naming convention used by:

- <https://github.com/Pho3niX90/jk-bms-card>

The important part is the configured pack prefix.

Example:

- prefix: `jk_bms_pack_1`

Then the card can use entities such as:

- `sensor.jk_bms_pack_1_total_voltage`
- `sensor.jk_bms_pack_1_current`
- `sensor.jk_bms_pack_1_state_of_charge`
- `sensor.jk_bms_pack_1_delta_cell_voltage`
- `sensor.jk_bms_pack_1_cell_voltage_1`
- `sensor.jk_bms_pack_1_cell_resistance_1`
- `switch.jk_bms_pack_1_charging`
- `switch.jk_bms_pack_1_discharging`
- `switch.jk_bms_pack_1_balancer`
- `binary_sensor.jk_bms_pack_1_balancing`

## `jk-bms-card` setup example

Install the card first:

- <https://github.com/Pho3niX90/jk-bms-card>

Then create one card per pack.

Example for pack 1:

```yaml
type: custom:jk-bms-card
title: JK BMS Pack 1
prefix: jk_bms_pack_1
batteryName: Pack 1
cellCount: 16
tempSensorsCount: 3
showButtons: true
showMain: true
showCells: true
showResistances: true
```

Example for pack 2:

```yaml
type: custom:jk-bms-card
title: JK BMS Pack 2
prefix: jk_bms_pack_2
batteryName: Pack 2
cellCount: 16
tempSensorsCount: 3
showButtons: true
showMain: true
showCells: true
showResistances: true
```

The `prefix` value in the card must match the `prefix` configured in
`config/config.yaml`.

## Refresh behavior

The poller does **not** publish on a fixed 60 second interval.

- state is published every time a new valid `0x02` realtime frame is decoded
- the `60s` interval in logs is only for internal statistics logging

This is important because the bus traffic is usually much faster than one
minute.

## Cleaning old retained topics

If you previously tested another MQTT naming scheme, clear the old retained
topics before validating the final integration:

```bash
jk-bms-mqtt-cleanup --config config/config.yaml
```

That prevents Home Assistant from showing stale or duplicate entities.

## Troubleshooting

### No entities appear in Home Assistant

Check:

- MQTT integration is connected
- broker credentials are correct
- the bridge is running
- the bridge is actually receiving valid `300-byte` frames

Useful command:

```bash
jk-bms-live-monitor --config config/config.yaml
```

### Entities appear, but the card is empty

Usually this means:

- the `prefix` in the card does not match the configured pack prefix
- or the card expects entities from a different naming scheme

This bridge uses entity names intentionally aligned with `jk-bms-card`.

### Duplicate or old entities remain

Run:

```bash
jk-bms-mqtt-cleanup --config config/config.yaml
```

## Notes

- `hardware_version` and `software_version` currently default to `unknown`
  because these fields are not available from the passive frame set on the
  tested installation.
- The poller publishes state whenever a new valid realtime frame is received.
- The `60s` interval in logs is only for statistics logging, not for state refresh.

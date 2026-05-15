# Home Assistant

## Discovery

The poller publishes Home Assistant MQTT discovery topics under:

- `homeassistant/`

State payloads are published under:

- `<state_root>/<pack_prefix>/state`

Default `state_root` from the example config:

- `jk_bms_passive_bridge`

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

## Notes

- `hardware_version` and `software_version` currently default to `unknown`
  because these fields are not available from the passive frame set on the
  tested installation.
- The poller publishes state whenever a new valid realtime frame is received.
- The `60s` interval in logs is only for statistics logging, not for state refresh.

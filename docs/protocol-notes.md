# Protocol Notes

This document describes what the project actually sees on a passive JK RS485
bus, based on real captures from a working multi-pack installation.

It is intentionally practical. The goal is not to restate a full JK Modbus
specification, but to explain the observed traffic well enough for others to
understand what the bridge is decoding.

## Observed frame layout

The parser looks for:

1. JK header:

```text
55 AA EB 90
```

2. A short delimiter after the JK payload:

```text
<pack_addr> 10 16 <block> 00 01 <crc_lo> <crc_hi>
```

Examples seen on the tested bus:

```text
00 10 16 1E 00 01 64 56
00 10 16 20 00 01 05 9A
02 10 16 1E 00 01 65 B4
02 10 16 20 00 01 04 78
```

Interpretation:

- first byte = source pack address
- `1E` = config/settings block
- `20` = realtime/status block
- last two bytes = Modbus CRC over the first 6 delimiter bytes

The bridge validates this CRC before accepting the frame.

## How packs are identified

The JK frame body itself is not enough to reliably identify the source pack on
the observed bus. The important signal is the short delimiter after the frame.

Examples:

### Master pack realtime

```text
55 AA EB 90 02 00 ...
00 10 16 20 00 01 05 9A
```

- JK frame type: `0x02`
- source pack from delimiter: `0x00`
- meaning: realtime frame from the master pack

### Master pack config

```text
55 AA EB 90 01 00 ...
00 10 16 1E 00 01 64 56
```

- JK frame type: `0x01`
- source pack from delimiter: `0x00`
- meaning: config block from the master pack

### Slave pack realtime

```text
55 AA EB 90 02 00 ...
02 10 16 20 00 01 04 78
```

- JK frame type: `0x02`
- source pack from delimiter: `0x02`
- meaning: realtime frame from slave pack address `0x02`

## Observed frame types

On the tested installation, only two useful JK frame types were seen
passively:

- `0x01` = config/settings
- `0x02` = realtime/status

No passive `0x03` block was observed in the captures used for this project.

## What `0x02` carries

The `0x02` realtime block is the main state source used by the Home Assistant
bridge.

Observed fields include:

- per-cell voltages
- average cell voltage
- delta cell voltage
- min/max cell number
- per-cell resistance
- MOS temperature
- total battery voltage
- battery current
- battery power
- temperature sensor 1
- temperature sensor 2
- temperature sensor 3
- alarm bitmap
- balancing current
- balancing state
- state of charge
- remaining capacity
- total capacity
- charging cycles
- total charging cycle capacity
- state of health
- runtime
- charge status
- discharge status
- precharge status
- charger status word

Example values observed in a clean 60 second capture:

- pack `0x00`
  - `state_of_charge = 70`
  - `total_voltage_v = 53.317 ... 53.336`
  - `current_a = 3.992 ... 4.741`
  - `alarm_bitmap = 0`
  - `charge_status = 1`
  - `discharge_status = 1`
  - `temp3_c = 3.3`

- pack `0x02`
  - `state_of_charge = 69`
  - `total_voltage_v = 53.257 ... 53.277`
  - `current_a = 3.905 ... 4.759`
  - `alarm_bitmap = 0`
  - `charge_status = 1`
  - `discharge_status = 1`
  - `temp3_c = 3.3`

## What `0x01` carries

The `0x01` config block contains settings and thresholds.

Observed fields include:

- sleep voltage
- cell undervoltage threshold
- cell undervoltage recovery
- cell overvoltage threshold
- cell overvoltage recovery
- balance trigger voltage
- 100% SOC voltage
- 0% SOC voltage
- max charge current
- max discharge current
- charge over-temperature threshold
- charge under-temperature threshold
- MOS over-temperature threshold
- configured cell count
- charge enable
- discharge enable
- balance enable
- configured capacity
- short circuit delay
- balance starting voltage
- device address
- smart sleep hours

Example values observed on the tested system:

- `sleep_voltage_mv = 3285`
- `cell_uvp_mv = 2750`
- `cell_uvpr_mv = 2900`
- `cell_ovp_mv = 3550`
- `cell_ovpr_mv = 3444`
- `balance_trigger_mv = 5`
- `soc100_voltage_mv = 3445`
- `soc0_voltage_mv = 2850`
- `max_charge_current_ma = 80000`
- `max_discharge_current_ma = 65000`
- `cell_count_setting = 16`
- `charge_enable = 1`
- `discharge_enable = 1`
- `balance_enable = 1`
- `total_battery_capacity_setting = 320 Ah`
- `balance_starting_voltage_mv = 3450`

Differences between packs were also visible:

- master pack `device_address = 0`
- slave pack `device_address = 2`

## What was not observed passively

The captures used for this project did not show:

- a passive `0x03` JK payload
- `0x1400` style about/version/model data
- serial number strings
- hardware/software ASCII blocks

For the tested bus, those data blocks should be treated as not passively
available until proven otherwise.

## Active `0x03` / `0x1400` about query

Although `0x03` was not seen passively in the captured traffic, it can be
queried actively on installations where a dedicated JK RS485 port is available.

The request is a Modbus `0x10` write frame which triggers a bulk reply:

```text
02 10 16 1C 00 01 02 00 00 C7 3D
```

Observed response header:

```text
55 AA EB 90 03 00 ...
```

Example parsed result from a real pack, with sensitive values masked:

```json
{
  "manufacturer_device_id": "JK-PB2A16S20P",
  "hardware_version": "19A",
  "software_version": "19.31",
  "serial_number": "51**********3560",
  "bluetooth_name": "Battery 2",
  "bluetooth_pin": "1****4",
  "first_on_date": "260507",
  "power_on_times": 9,
  "password": "ka***n2",
  "user_private_data": "JK-BMS",
  "user_data_2": "JK-BMS"
}
```

This is the source for fields such as:

- hardware version
- software version
- serial number
- Bluetooth name
- first-on date
- power-on count

In this project, the bridge may use this query infrequently to enrich Home
Assistant metadata, while sensitive values are published only in masked form.

## Why the bridge prefers full 300-byte frames

The project has also seen shorter frames such as:

- `224`
- `236`
- `251`
- `268`
- `288`

Those shorter frames can still be real traffic, but they are not as safe for
state publication because fields near the end of the payload may be missing or
misaligned.

For that reason the poller:

- counts partial frames
- ignores them for MQTT state publication
- uses only full `300-byte` frames for stable output

# Architecture

## Bus model

The bridge assumes a shared JK RS485 bus already driven by another master.

On the tested setup:

- master pack address: `0x00`
- slave pack address: `0x02`
- JK frames are followed by a short-form Modbus delimiter
- the first byte of that delimiter is used as the source pack address

## Parser approach

1. Search for JK frame header: `55 aa eb 90`
2. Search after it for a short-form delimiter:
   - `addr 10 16 xx 00 01 crc`
3. Validate delimiter CRC
4. Treat the bytes before the delimiter as one JK frame
5. Parse:
   - `0x01` as config/settings
   - `0x02` as realtime/status

See [protocol-notes.md](protocol-notes.md) for concrete passive dump examples.

## State publication model

- `0x01` updates pack configuration state
- `0x02` updates realtime state and triggers MQTT state publication
- MQTT discovery is sent once per pack per process lifetime, or again after reconnect

## Why full 300-byte frames

Shorter frames were observed in some captures and can produce misleading values
for fields near the end of the payload. For that reason:

- partial frames are counted
- full `300-byte` frames are preferred for state publication

## Why passive only

The primary use case is coexistence with another bus master. Active reads would
change the safety profile of the project and can cause collisions or undefined
interactions with inverter/master traffic.

# Beginner Step-by-Step Guide

This guide is for users who:

- have little or no Linux experience
- want to read **one or more JK BMS units over RS485**
- want to see the data in **Home Assistant**
- do **not** want to actively poll the BMS bus

The goal is simple:

1. connect a USB to RS485 adapter to the JK BMS bus
2. make Linux see that adapter
3. run this bridge
4. let Home Assistant discover the entities automatically
5. use `jk-bms-card` to display the battery data

## 1. What hardware to use

You need:

- a Linux machine that can run Python 3
- network access to your MQTT broker
- one USB to RS485 adapter
- RS485 wires connected to the JK BMS

This project was built for **passive listening** on the JK RS485 bus.

## 2. Which JK BMS port to use

Use:

- **UART2 / RS485**
- on the tested JK BMS models, this is the **right-most RJ45 port**

Do not connect to the Bluetooth/UART port used for direct serial tools.

This bridge is intended to observe the **shared RS485 bus** where:

- the master pack talks to slave packs
- and/or an inverter such as Deye is already connected

## 3. Connect the USB to RS485 adapter

Connect the adapter to your Linux machine.

Then verify that Linux sees it.

Useful commands:

```bash
ls /dev/ttyUSB*
```

```bash
dmesg | tail -n 30
```

```bash
lsusb
```

Typical result:

- `/dev/ttyUSB0`

If you have more than one USB serial adapter connected, you may see:

- `/dev/ttyUSB0`
- `/dev/ttyUSB1`

In that case, unplug and re-plug the adapter and run:

```bash
dmesg | tail -n 30
```

again. The newest log lines usually show which device name was assigned.

## 4. Clone the repository

Pick a directory and clone:

```bash
git clone https://github.com/eggcho/jk-bms-passive-bridge.git
cd jk-bms-passive-bridge
```

If `git` is not installed:

```bash
sudo apt update
sudo apt install -y git
```

## 5. Install Python and the virtual environment tools

On Debian / Ubuntu / Proxmox / LXC:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

## 6. Create the Python virtual environment

From inside the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

After activation, your shell usually shows:

```text
(.venv)
```

at the beginning of the prompt.

## 7. Create the config file

Copy the example config:

```bash
mkdir -p config
cp config/config.example.yaml config/config.yaml
```

Now edit:

```bash
nano config/config.yaml
```

## 8. What to change in the config

At minimum, change these values:

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

What each important setting means:

- `serial.port`
  - the Linux serial device, for example `/dev/ttyUSB0`
- `serial.baud_rate`
  - for the tested setup this is `115200`
- `mqtt.broker`
  - IP address or hostname of your MQTT server
- `mqtt.username`
  - your MQTT username
- `mqtt.password`
  - your MQTT password
- `packs[].address`
  - JK pack address seen on the RS485 bus
- `packs[].prefix`
  - the entity prefix Home Assistant will use

For a two-pack setup, typical addresses are:

- `0x00` for the master pack
- `0x02` for the second pack

## 9. Test the serial connection before touching Home Assistant

Run the live monitor first:

```bash
jk-bms-live-monitor --config config/config.yaml
```

If everything is correct, you should start seeing:

- Pack 1
- Pack 2
- voltage
- current
- SoC
- cell voltages

If you do **not** see data:

- check the cable wiring
- check the JK port
- check the USB serial port in `config/config.yaml`
- check that the adapter really appears as `/dev/ttyUSB0` or `/dev/ttyUSB1`

Exit the monitor with:

```text
q
```

## 10. Prepare Home Assistant

Home Assistant needs:

- a working MQTT integration
- access to the same MQTT broker configured in `config/config.yaml`

In Home Assistant:

1. go to `Settings`
2. go to `Devices & Services`
3. make sure the `MQTT` integration is installed and connected

If MQTT is not configured yet, configure it first in Home Assistant.

## 11. Start the bridge

From the project directory:

```bash
source .venv/bin/activate
jk-bms-ha-poller --config config/config.yaml
```

Leave it running.

What the bridge does:

- listens to the RS485 bus
- waits for valid JK frames
- publishes MQTT discovery topics
- publishes state topics
- Home Assistant auto-creates the entities

## 12. Check that Home Assistant found the BMS

After a few seconds, Home Assistant should create devices and entities.

Look for devices such as:

- `JK BMS Pack 1`
- `JK BMS Pack 2`

And entities such as:

- `sensor.jk_bms_pack_1_total_voltage`
- `sensor.jk_bms_pack_1_current`
- `sensor.jk_bms_pack_1_state_of_charge`
- `sensor.jk_bms_pack_1_cell_voltage_1`

If the entities do not appear:

- make sure the poller is still running
- make sure MQTT is connected in Home Assistant
- run the live monitor again and confirm that frames are actually being decoded

## 13. Install `jk-bms-card`

This project is designed to work with:

- <https://github.com/Pho3niX90/jk-bms-card>

Install that card in Home Assistant first.

Then add a card for each pack.

Example for Pack 1:

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

Example for Pack 2:

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

The most important field is:

- `prefix`

It must exactly match the `prefix` in `config/config.yaml`.

## 14. If you tested older versions before

If you previously used another naming scheme or another poller, clear old MQTT
discovery topics first:

```bash
jk-bms-mqtt-cleanup --config config/config.yaml
```

Then start the poller again:

```bash
jk-bms-ha-poller --config config/config.yaml
```

## 15. Run it automatically on boot

If you want the bridge to start automatically after reboot, use the systemd
guide:

- [docs/systemd.md](systemd.md)

## 16. Quick fault checklist

### I do not know which USB port is correct

Run:

```bash
ls /dev/ttyUSB*
```

and:

```bash
dmesg | tail -n 30
```

### The monitor starts but no battery data appears

Check:

- the cable is connected to **UART2 / RS485**
- the adapter is detected by Linux
- the configured serial port is correct
- the JK bus is active

### Home Assistant sees nothing

Check:

- MQTT integration is installed
- MQTT credentials are correct
- the poller is running
- the live monitor can see frames

### The card is empty or wrong

Check:

- the `prefix` in the card
- the `prefix` in `config/config.yaml`

They must match exactly.

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass

import paho.mqtt.client as mqtt
import serial
from loguru import logger

from .config import AppConfig, PackConfig, load_config
from .protocol import build_card_state, find_frame_and_delimiter, parse_type_01, parse_type_02


@dataclass
class PackState:
    config: PackConfig
    type01: dict | None = None
    type02: dict | None = None
    discovery_sent: bool = False
    last_publish_ts: float = 0.0


class HAPoller:
    def __init__(self, config: AppConfig):
        self.config = config
        self.ser = None
        self.mqtt = None
        self.buffer = bytearray()
        self.stats = {"frames": 0, "partial": 0, "rejected": 0, "unknown": 0}
        self.packs: dict[int, PackState] = {
            addr: PackState(cfg) for addr, cfg in config.packs.items()
        }
        self.last_stats_log = time.time()

    def get_pack(self, pack_addr: int) -> PackState:
        if pack_addr not in self.packs:
            cfg = PackConfig(
                address=pack_addr,
                name=f"JK BMS Pack 0x{pack_addr:02X}",
                prefix=f"jk_bms_pack_0x{pack_addr:02x}",
                cells=self.config.default_cells,
            )
            self.packs[pack_addr] = PackState(cfg)
        return self.packs[pack_addr]

    def setup(self):
        self.ser = serial.Serial(self.config.serial_port, self.config.baud_rate, timeout=0.1)
        logger.info(f"Serial {self.config.serial_port} @ {self.config.baud_rate}")
        self.mqtt = mqtt.Client(client_id="jk-bms-passive-bridge")
        self.mqtt.username_pw_set(self.config.mqtt.username, self.config.mqtt.password)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_disconnect = lambda c, u, rc: logger.warning(f"MQTT disconnect rc={rc}")
        self.mqtt.connect(self.config.mqtt.broker, self.config.mqtt.port, 60)
        self.mqtt.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.success("MQTT connected")
            client.publish(f"{self.config.mqtt.state_root}/availability", "online", retain=True, qos=1)
            for pack in self.packs.values():
                pack.discovery_sent = False
        else:
            logger.error(f"MQTT rc={rc}")

    def _state_topic(self, pack: PackState) -> str:
        return f"{self.config.mqtt.state_root}/{pack.config.prefix}/state"

    def _availability_topic(self) -> str:
        return f"{self.config.mqtt.state_root}/availability"

    def publish_discovery(self, pack: PackState):
        if pack.discovery_sent:
            return
        device = {
            "identifiers": [pack.config.prefix],
            "name": pack.config.name,
            "manufacturer": "JK BMS",
            "model": "JK-PB2A16S20P",
        }
        state_topic = self._state_topic(pack)
        availability_topic = self._availability_topic()
        sensor_defs = [
            ("delta_cell_voltage", "Delta Cell Voltage", "V", "voltage", "measurement", 3),
            ("balancing_current", "Balancing Current", "A", "current", "measurement", 3),
            ("power", "Power", "W", "power", "measurement", 1),
            ("balance_trigger_voltage", "Balance Trigger Voltage", "V", "voltage", None, 3),
            ("balance_starting_voltage", "Balance Starting Voltage", "V", "voltage", None, 3),
            ("total_runtime_formatted", "Total Runtime", None, None, None, 0),
            ("charging_power", "Charging Power", "W", "power", "measurement", 1),
            ("discharging_power", "Discharging Power", "W", "power", "measurement", 1),
            ("total_voltage", "Total Voltage", "V", "voltage", "measurement", 3),
            ("total_battery_capacity_setting", "Total Battery Capacity Setting", "Ah", None, None, 3),
            ("total_charging_cycle_capacity", "Total Charging Cycle Capacity", "Ah", None, "total_increasing", 3),
            ("average_cell_voltage", "Average Cell Voltage", "V", "voltage", "measurement", 3),
            ("current", "Current", "A", "current", "measurement", 3),
            ("state_of_charge", "State Of Charge", "%", "battery", "measurement", 0),
            ("capacity_remaining", "Capacity Remaining", "Ah", None, "measurement", 3),
            ("charging_cycles", "Charging Cycles", None, None, "total_increasing", 0),
            ("power_tube_temperature", "Power Tube Temperature", "°C", "temperature", "measurement", 1),
            ("min_voltage_cell", "Min Voltage Cell", None, None, None, 0),
            ("max_voltage_cell", "Max Voltage Cell", None, None, None, 0),
            ("min_cell_voltage", "Min Cell Voltage", "V", "voltage", "measurement", 3),
            ("max_cell_voltage", "Max Cell Voltage", "V", "voltage", "measurement", 3),
            ("errors", "Errors", None, None, None, 0),
            ("software_version", "Software Version", None, None, None, 0),
            ("hardware_version", "Hardware Version", None, None, None, 0),
            ("temperature_sensor_1", "Temperature Sensor 1", "°C", "temperature", "measurement", 1),
            ("temperature_sensor_2", "Temperature Sensor 2", "°C", "temperature", "measurement", 1),
            ("temperature_sensor_3", "Temperature Sensor 3", "°C", "temperature", "measurement", 1),
            ("temperature_sensor_4", "Temperature Sensor 4", "°C", "temperature", "measurement", 1),
            ("state_of_health", "State Of Health", "%", None, "measurement", 0),
            ("charge_mos_state", "Charge MOS State", None, None, None, 0),
            ("discharge_mos_state", "Discharge MOS State", None, None, None, 0),
            ("precharge_status", "Precharge Status", None, None, None, 0),
            ("charger_status_word", "Charger Status Word", None, None, None, 0),
        ]
        for i in range(pack.config.cells):
            sensor_defs.append((f"cell_voltage_{i + 1}", f"Cell Voltage {i + 1}", "V", "voltage", "measurement", 3))
            sensor_defs.append((f"cell_resistance_{i + 1}", f"Cell Resistance {i + 1}", "mΩ", None, "measurement", 0))
        for key, name, unit, device_class, state_class, precision in sensor_defs:
            payload = {
                "name": name,
                "unique_id": f"{pack.config.prefix}_{key}",
                "object_id": f"{pack.config.prefix}_{key}",
                "default_entity_id": f"sensor.{pack.config.prefix}_{key}",
                "state_topic": state_topic,
                "value_template": f"{{{{ value_json.{key} }}}}",
                "availability_topic": availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": device,
                "suggested_display_precision": precision,
            }
            if unit:
                payload["unit_of_measurement"] = unit
            if device_class:
                payload["device_class"] = device_class
            if state_class:
                payload["state_class"] = state_class
            self.mqtt.publish(
                f"{self.config.mqtt.discovery_prefix}/sensor/{pack.config.prefix}_{key}/config",
                json.dumps(payload),
                retain=True,
                qos=1,
            )
        binary_payload = {
            "name": "Balancing",
            "unique_id": f"{pack.config.prefix}_balancing",
            "object_id": f"{pack.config.prefix}_balancing",
            "default_entity_id": f"binary_sensor.{pack.config.prefix}_balancing",
            "state_topic": state_topic,
            "value_template": "{{ value_json.balancing }}",
            "payload_on": "ON",
            "payload_off": "OFF",
            "availability_topic": availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": device,
        }
        self.mqtt.publish(
            f"{self.config.mqtt.discovery_prefix}/binary_sensor/{pack.config.prefix}_balancing/config",
            json.dumps(binary_payload),
            retain=True,
            qos=1,
        )
        for key, name in [("charging", "Charging"), ("discharging", "Discharging"), ("balancer", "Balancer"), ("heater", "Heater")]:
            payload = {
                "name": name,
                "unique_id": f"{pack.config.prefix}_{key}",
                "object_id": f"{pack.config.prefix}_{key}",
                "default_entity_id": f"switch.{pack.config.prefix}_{key}",
                "state_topic": state_topic,
                "value_template": f"{{{{ value_json.{key} }}}}",
                "command_topic": f"{self.config.mqtt.state_root}/{pack.config.prefix}/command/{key}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_on": "ON",
                "state_off": "OFF",
                "availability_topic": availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": device,
                "optimistic": False,
            }
            self.mqtt.publish(
                f"{self.config.mqtt.discovery_prefix}/switch/{pack.config.prefix}_{key}/config",
                json.dumps(payload),
                retain=True,
                qos=1,
            )
        pack.discovery_sent = True
        logger.success(f"Discovery published for {pack.config.name} ({pack.config.prefix})")

    def publish_state(self, pack: PackState):
        if not pack.type02:
            return
        state = build_card_state(pack.type01, pack.type02, num_cells=pack.config.cells)
        self.publish_discovery(pack)
        self.mqtt.publish(self._state_topic(pack), json.dumps(state), retain=True, qos=0)
        pack.last_publish_ts = time.time()

    def handle_frame(self, pack_addr: int, frame: bytes):
        pack = self.get_pack(pack_addr)
        if len(frame) < 300:
            self.stats["partial"] += 1
            return
        frame_type = frame[4]
        if frame_type == 0x01:
            pack.type01 = parse_type_01(frame)
        elif frame_type == 0x02:
            parsed = parse_type_02(frame)
            if not parsed:
                self.stats["rejected"] += 1
                return
            pack.type02 = parsed
            self.publish_state(pack)
        else:
            self.stats["unknown"] += 1
            return
        self.stats["frames"] += 1

    def process_buffer(self):
        while True:
            pack_addr, frame, consumed = find_frame_and_delimiter(self.buffer)
            if consumed == 0:
                return
            if frame is None:
                self.buffer = self.buffer[consumed:]
                continue
            self.buffer = self.buffer[consumed:]
            if len(frame) >= 6:
                self.handle_frame(pack_addr, frame)

    def run(self):
        self.setup()
        time.sleep(1)
        logger.info("Passive JK BMS -> Home Assistant poller started")
        try:
            while True:
                if self.ser.in_waiting:
                    self.buffer.extend(self.ser.read(self.ser.in_waiting))
                if len(self.buffer) > 40000:
                    self.buffer = self.buffer[-20000:]
                self.process_buffer()
                if time.time() - self.last_stats_log > 60:
                    logger.info(f"Stats: {self.stats}")
                    self.last_stats_log = time.time()
                time.sleep(0.02)
        except KeyboardInterrupt:
            logger.info("Stopping")
        finally:
            if self.mqtt is not None:
                self.mqtt.publish(self._availability_topic(), "offline", retain=True, qos=1)
                self.mqtt.loop_stop()
                self.mqtt.disconnect()
            if self.ser is not None:
                self.ser.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    config = load_config(args.config)
    HAPoller(config).run()
    return 0

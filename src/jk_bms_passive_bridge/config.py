from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class MqttConfig:
    broker: str
    port: int
    username: str
    password: str
    discovery_prefix: str = "homeassistant"
    state_root: str = "jk_bms_passive_bridge"


@dataclass
class PackConfig:
    address: int
    name: str
    prefix: str
    cells: int = 16


@dataclass
class AppConfig:
    serial_port: str
    baud_rate: int
    mqtt: MqttConfig
    packs: dict[int, PackConfig]
    default_cells: int = 16


def _parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"Cannot parse integer from {value!r}")


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    serial_cfg = raw.get("serial", {})
    mqtt_cfg = raw.get("mqtt", {})
    packs_cfg = raw.get("packs", [])

    mqtt = MqttConfig(
        broker=mqtt_cfg["broker"],
        port=int(mqtt_cfg.get("port", 1883)),
        username=mqtt_cfg["username"],
        password=mqtt_cfg["password"],
        discovery_prefix=mqtt_cfg.get("discovery_prefix", "homeassistant"),
        state_root=mqtt_cfg.get("state_root", "jk_bms_passive_bridge"),
    )

    packs: dict[int, PackConfig] = {}
    default_cells = int(raw.get("defaults", {}).get("cells", 16))
    for item in packs_cfg:
        address = _parse_int(item["address"])
        packs[address] = PackConfig(
            address=address,
            name=item["name"],
            prefix=item["prefix"],
            cells=int(item.get("cells", default_cells)),
        )

    return AppConfig(
        serial_port=serial_cfg.get("port", "/dev/ttyUSB0"),
        baud_rate=int(serial_cfg.get("baud_rate", 115200)),
        mqtt=mqtt,
        packs=packs,
        default_cells=default_cells,
    )

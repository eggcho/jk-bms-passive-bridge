from pathlib import Path

from jk_bms_passive_bridge.config import load_config


def test_load_config(tmp_path: Path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        """
serial:
  port: /dev/test0
  baud_rate: 115200

mqtt:
  broker: 127.0.0.1
  port: 1883
  username: u
  password: p

defaults:
  cells: 16

packs:
  - address: 0x00
    name: Pack 1
    prefix: pack_1
""".strip()
    )
    cfg = load_config(cfg_file)
    assert cfg.serial_port == "/dev/test0"
    assert cfg.baud_rate == 115200
    assert cfg.mqtt.broker == "127.0.0.1"
    assert 0x00 in cfg.packs
    assert cfg.packs[0x00].prefix == "pack_1"

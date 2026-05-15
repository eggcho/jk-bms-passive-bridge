from __future__ import annotations

import argparse
import time

import paho.mqtt.client as mqtt

from .config import load_config


def should_clear(topic: str, state_root: str) -> bool:
    lowered = topic.lower()
    if lowered.startswith("homeassistant/") and ("jk_pack_" in lowered or "jk_bms_pack_" in lowered or "jkbms" in lowered):
        return True
    if lowered.startswith(state_root.lower() + "/"):
        return True
    return False


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--seconds", type=int, default=10)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    cfg = load_config(args.config)
    cleared: list[str] = []

    def on_message(client, userdata, msg):
        if msg.retain and should_clear(msg.topic, cfg.mqtt.state_root):
            client.publish(msg.topic, payload=None, retain=True, qos=1)
            cleared.append(msg.topic)
            print(f"cleared {msg.topic}")

    client = mqtt.Client(client_id="jk-bms-passive-bridge-cleanup")
    client.username_pw_set(cfg.mqtt.username, cfg.mqtt.password)
    client.on_message = on_message
    client.connect(cfg.mqtt.broker, cfg.mqtt.port, 60)
    client.subscribe("#")
    client.loop_start()
    print(f"Scanning retained MQTT topics for {args.seconds}s...")
    time.sleep(args.seconds)
    client.loop_stop()
    client.disconnect()
    print(f"Cleared {len(cleared)} retained topics")
    return 0

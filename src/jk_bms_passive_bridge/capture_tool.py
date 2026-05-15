from __future__ import annotations

import argparse
import time
from pathlib import Path

import serial

from .config import load_config


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--seconds", type=int, default=60)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    cfg = load_config(args.config)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    ser = serial.Serial(cfg.serial_port, cfg.baud_rate, timeout=0.1)
    buf = bytearray()
    start = time.time()
    try:
        while time.time() - start < args.seconds:
            if ser.in_waiting:
                buf.extend(ser.read(ser.in_waiting))
            else:
                time.sleep(0.02)
    finally:
        ser.close()

    output.write_bytes(bytes(buf))
    print(f"saved={output}")
    print(f"bytes={len(buf)}")
    print(f"seconds={args.seconds}")
    return 0

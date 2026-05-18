from __future__ import annotations

import argparse
import json
import time
from typing import Any

import serial

from .protocol import build_active_query, parse_type_01, parse_type_02, parse_type_03

QUERY_MAP = {
    "about": {"reg": 0x1C, "expected_type": 0x03},
    "config": {"reg": 0x1E, "expected_type": 0x01},
    "realtime": {"reg": 0x20, "expected_type": 0x02},
}


def read_response(ser: serial.Serial, expected_type: int, timeout: float, idle_timeout: float) -> bytes:
    deadline = time.time() + timeout
    buf = bytearray()
    header_pos = -1
    last_rx = 0.0
    while time.time() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf.extend(chunk)
            last_rx = time.time()
            if header_pos < 0:
                header_pos = buf.find(b"\x55\xAA\xEB\x90")
        else:
            time.sleep(0.01)
        if header_pos >= 0 and last_rx and (time.time() - last_rx) > idle_timeout:
            frame = bytes(buf[header_pos:])
            if len(frame) >= 6 and frame[4] == expected_type:
                return frame
    raise TimeoutError(f"Timed out waiting for JK response type 0x{expected_type:02X}")


def probe(port: str, baud: int, pack_addr: int, query: str, timeout: float, idle_timeout: float) -> dict[str, Any]:
    reg = QUERY_MAP[query]["reg"]
    expected_type = QUERY_MAP[query]["expected_type"]
    request = build_active_query(pack_addr, reg)
    with serial.Serial(port, baud, timeout=0.05) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(request)
        ser.flush()
        frame = read_response(ser, expected_type=expected_type, timeout=timeout, idle_timeout=idle_timeout)
    if expected_type == 0x03:
        parsed = parse_type_03(frame)
    elif expected_type == 0x01:
        parsed = parse_type_01(frame)
    else:
        parsed = parse_type_02(frame) or {}
    return {
        "port": port,
        "baud": baud,
        "pack_addr": f"0x{pack_addr:02X}",
        "query": query,
        "request_hex": request.hex(" "),
        "response_len": len(frame),
        "response_type": f"0x{frame[4]:02X}" if len(frame) >= 5 else None,
        "response_hex": frame.hex(" "),
        "parsed": parsed,
    }


def parse_pack_addr(value: str) -> int:
    return int(value, 0)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Actively query JK BMS bulk blocks")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", default=115200, type=int)
    parser.add_argument("--pack", default="0x00", type=parse_pack_addr, help="pack address, e.g. 0x00 or 0x02")
    parser.add_argument("--query", choices=sorted(QUERY_MAP), default="about")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--idle-timeout", type=float, default=0.15)
    parser.add_argument("--hex", action="store_true", help="include raw response hex in output")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = probe(
        port=args.port,
        baud=args.baud,
        pack_addr=args.pack,
        query=args.query,
        timeout=args.timeout,
        idle_timeout=args.idle_timeout,
    )
    if not args.hex:
        result.pop("response_hex", None)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0

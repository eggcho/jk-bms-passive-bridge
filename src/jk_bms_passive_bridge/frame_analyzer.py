from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .protocol import find_frame_and_delimiter, parse_type_02


def iter_frames(data: bytes):
    buffer = bytearray(data)
    while True:
        pack_addr, frame, consumed = find_frame_and_delimiter(buffer)
        if consumed == 0:
            return
        if frame is None:
            buffer = buffer[consumed:]
            continue
        yield {
            "pack_addr": pack_addr,
            "frame_type": frame[4],
            "frame_len": len(frame),
            "frame": frame,
        }
        buffer = buffer[consumed:]


def summarize(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    frame_list = list(iter_frames(data))
    combos = Counter()
    lengths = defaultdict(set)
    observed = defaultdict(list)
    for item in frame_list:
        key = f"pack_0x{item['pack_addr']:02X}_type_0x{item['frame_type']:02X}"
        combos[key] += 1
        lengths[key].add(item["frame_len"])
        if item["frame_type"] == 0x02 and item["frame_len"] >= 300:
            parsed = parse_type_02(item["frame"])
            if parsed:
                observed[f"0x{item['pack_addr']:02X}"].append(parsed)
    observed_summary = {}
    for pack, rows in observed.items():
        field_values = defaultdict(set)
        for row in rows:
            for k, v in row.items():
                field_values[k].add(repr(v))
        observed_summary[pack] = {k: sorted(v) for k, v in sorted(field_values.items())}
    return {
        "file": str(path),
        "bytes": len(data),
        "frames": len(frame_list),
        "combos": {k: {"count": combos[k], "lengths": sorted(lengths[k])} for k in sorted(combos)},
        "type_02_observed": observed_summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    print(json.dumps(summarize(Path(args.capture)), indent=2, sort_keys=True))
    return 0

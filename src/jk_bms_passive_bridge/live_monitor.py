from __future__ import annotations

import argparse
import curses
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import serial

from .config import AppConfig, PackConfig, load_config
from .protocol import find_frame_and_delimiter, parse_type_01, parse_type_02


def fmt_age(ts: float | None) -> str:
    if not ts:
        return "-"
    delta = max(0.0, time.time() - ts)
    if delta < 60:
        return f"{delta:.0f}s"
    return f"{delta / 60:.1f}m"


@dataclass
class PackState:
    config: PackConfig
    type01: dict[str, Any] | None = None
    type02: dict[str, Any] | None = None
    last_type01_ts: float | None = None
    last_type02_ts: float | None = None
    frame_counts: Counter = field(default_factory=Counter)
    partial_counts: Counter = field(default_factory=Counter)
    parse_errors: Counter = field(default_factory=Counter)


class LiveMonitor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.ser: serial.Serial | None = None
        self.buffer = bytearray()
        self.packs: dict[int, PackState] = {
            addr: PackState(cfg) for addr, cfg in config.packs.items()
        }
        self.global_counts = Counter()
        self.started = time.time()
        self.last_key = "-"

    def get_pack(self, pack_addr: int) -> PackState:
        if pack_addr not in self.packs:
            self.packs[pack_addr] = PackState(PackConfig(pack_addr, f"Pack 0x{pack_addr:02X}", f"pack_0x{pack_addr:02x}", self.config.default_cells))
        return self.packs[pack_addr]

    def open(self) -> None:
        self.ser = serial.Serial(self.config.serial_port, self.config.baud_rate, timeout=0.05)

    def close(self) -> None:
        if self.ser is not None:
            self.ser.close()
            self.ser = None

    def poll_serial(self) -> None:
        if self.ser is None:
            return
        if self.ser.in_waiting:
            self.buffer.extend(self.ser.read(self.ser.in_waiting))
        if len(self.buffer) > 40000:
            self.buffer = self.buffer[-20000:]
        self.process_buffer()

    def process_buffer(self) -> None:
        while True:
            pack_addr, frame, consumed = find_frame_and_delimiter(self.buffer)
            if consumed == 0:
                return
            if frame is None:
                self.buffer = self.buffer[consumed:]
                continue
            self.buffer = self.buffer[consumed:]
            pack = self.get_pack(pack_addr)
            frame_type = frame[4]
            pack.frame_counts[frame_type] += 1
            if len(frame) < 300:
                pack.partial_counts[frame_type] += 1
                self.global_counts["partial"] += 1
                continue
            try:
                if frame_type == 0x01:
                    pack.type01 = parse_type_01(frame)
                    pack.last_type01_ts = time.time()
                elif frame_type == 0x02:
                    pack.type02 = parse_type_02(frame)
                    pack.last_type02_ts = time.time()
            except Exception:
                pack.parse_errors[frame_type] += 1
                self.global_counts["errors"] += 1


def draw(stdscr, monitor: LiveMonitor) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    title = f"JK BMS Live Monitor  port={monitor.config.serial_port}  keys: q quit  last_key={monitor.last_key}"
    stdscr.addstr(0, 0, title[: max(0, w - 1)], curses.A_REVERSE)
    row = 2
    for addr in sorted(monitor.packs):
        pack = monitor.packs[addr]
        t02 = pack.type02 or {}
        t01 = pack.type01 or {}
        lines = [
            f"{pack.config.name} ({pack.config.prefix})  rt={fmt_age(pack.last_type02_ts)} cfg={fmt_age(pack.last_type01_ts)} f01={pack.frame_counts[0x01]} f02={pack.frame_counts[0x02]} partial={sum(pack.partial_counts.values())}",
            f"  V={t02.get('total_voltage_v', '-')}  I={t02.get('current_a', '-')}A  P={t02.get('power_w', '-')}W  SoC={t02.get('state_of_charge', '-')}",
            f"  T1={t02.get('temp1_c', '-')}  T2={t02.get('temp2_c', '-')}  T3={t02.get('temp3_c', '-')}  MOS={t02.get('mos_temp_c', '-')}",
            f"  min_cell={t02.get('min_cell_num', '-')}  max_cell={t02.get('max_cell_num', '-')}  delta_mv={t02.get('delta_cell_mv', '-')}",
            f"  cfg_addr={t01.get('device_address', '-')}  capacity={t01.get('total_battery_capacity_setting', '-')}Ah  uvp={t01.get('cell_uvp_mv', '-')}  ovp={t01.get('cell_ovp_mv', '-')}",
        ]
        for line in lines:
            if row < h:
                stdscr.addstr(row, 0, line[: max(0, w - 1)])
            row += 1
        row += 1
    stdscr.refresh()


def curses_main(stdscr, config: AppConfig) -> None:
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)
    stdscr.timeout(200)
    monitor = LiveMonitor(config)
    monitor.open()
    try:
        while True:
            monitor.poll_serial()
            draw(stdscr, monitor)
            key = stdscr.getch()
            if key != -1:
                monitor.last_key = chr(key) if 32 <= key <= 126 else str(key)
            if key in (ord("q"), ord("Q")):
                break
    finally:
        stdscr.keypad(False)
        monitor.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    config = load_config(args.config)
    curses.wrapper(curses_main, config)
    return 0

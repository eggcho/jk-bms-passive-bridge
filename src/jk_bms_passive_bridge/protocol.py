from __future__ import annotations

import re
import struct
from typing import Any

JK_HEADER = b"\x55\xAA\xEB\x90"
SHORT_DELIMITER = re.compile(rb"[\x00-\x0F]\x10\x16[\x1C\x1E\x20\x22\x24]\x00\x01")

ALARM_BITS = {
    0: "wire_resistance",
    1: "mos_overtemperature",
    2: "cell_count_mismatch",
    3: "current_sensor_error",
    4: "cell_overvoltage",
    5: "battery_overvoltage",
    6: "charge_overcurrent",
    7: "charge_short_circuit",
    8: "charge_overtemperature",
    9: "charge_low_temperature",
    10: "internal_communication",
    11: "cell_undervoltage",
    12: "battery_undervoltage",
    13: "discharge_overcurrent",
    14: "discharge_short_circuit",
    15: "discharge_overtemperature",
    16: "charge_mos_fault",
    17: "discharge_mos_fault",
    18: "gps_disconnected",
    19: "password_change_required",
    20: "discharge_start_failed",
    21: "battery_overtemperature_alarm",
    22: "temperature_sensor_error",
    23: "parallel_module_error",
}


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def find_frame_and_delimiter(buffer: bytearray):
    idx = buffer.find(JK_HEADER)
    if idx < 0:
        return None, None, max(0, len(buffer) - 4)
    if idx > 0:
        return None, None, idx
    if len(buffer) < 230:
        return None, None, 0

    search_end = min(400, len(buffer))
    match = SHORT_DELIMITER.search(buffer[100:search_end])
    if not match:
        if len(buffer) >= 500:
            return None, None, 4
        return None, None, 0

    delim_offset = 100 + match.start()
    if delim_offset + 8 > len(buffer):
        return None, None, 0

    delim = buffer[delim_offset : delim_offset + 8]
    expected_crc = struct.unpack("<H", delim[6:8])[0]
    if expected_crc != crc16_modbus(delim[:6]):
        return None, None, 4

    return delim[0], bytes(buffer[:delim_offset]), delim_offset + 8


def parse_type_02(frame: bytes) -> dict[str, Any] | None:
    data: dict[str, Any] = {
        "cells_mv": list(struct.unpack_from("<16H", frame, 6)),
        "cell_status_bitmap": struct.unpack_from("<I", frame, 70)[0],
        "avg_cell_mv": struct.unpack_from("<H", frame, 74)[0],
        "delta_cell_mv": struct.unpack_from("<H", frame, 76)[0],
        "max_cell_num": frame[78] + 1,
        "min_cell_num": frame[79] + 1,
        "resistances_mohm": list(struct.unpack_from("<16H", frame, 80)),
        "mos_temp_c": struct.unpack_from("<h", frame, 144)[0] / 10.0,
        "total_voltage_v": struct.unpack_from("<I", frame, 150)[0] / 1000.0,
        "power_w": struct.unpack_from("<i", frame, 154)[0] / 1000.0,
        "current_a": struct.unpack_from("<i", frame, 158)[0] / 1000.0,
        "temp1_c": struct.unpack_from("<h", frame, 162)[0] / 10.0,
        "temp2_c": struct.unpack_from("<h", frame, 164)[0] / 10.0,
        "alarm_bitmap": struct.unpack_from("<I", frame, 166)[0],
        "balancing_current_a": struct.unpack_from("<h", frame, 170)[0] / 1000.0,
        "balancing_state": frame[172],
        "state_of_charge": frame[173],
        "capacity_remaining_ah": struct.unpack_from("<I", frame, 174)[0] / 1000.0,
        "capacity_total_ah": struct.unpack_from("<I", frame, 178)[0] / 1000.0,
        "charging_cycles": struct.unpack_from("<I", frame, 182)[0],
        "total_charging_cycle_capacity_ah": struct.unpack_from("<I", frame, 186)[0] / 1000.0,
        "state_of_health": frame[190],
        "precharge_status": frame[191],
        "user_alarm_1": struct.unpack_from("<H", frame, 192)[0],
        "runtime_sec": struct.unpack_from("<I", frame, 194)[0],
        "charging_status": bool(frame[198]),
        "discharging_status": bool(frame[199]),
        "user_alarm_2": struct.unpack_from("<H", frame, 200)[0],
        "time_dcocpr_s": struct.unpack_from("<H", frame, 202)[0],
        "time_dcscpr_s": struct.unpack_from("<H", frame, 204)[0],
        "time_cocpr_s": struct.unpack_from("<H", frame, 206)[0],
        "time_cscpr_s": struct.unpack_from("<H", frame, 208)[0],
        "sensor_presence_word": struct.unpack_from("<H", frame, 214)[0],
        "battery_voltage_0p01v": struct.unpack_from("<H", frame, 228)[0],
        "heating_current_ma": struct.unpack_from("<h", frame, 230)[0],
        "charger_status_word": struct.unpack_from("<H", frame, 238)[0],
        "system_beat_0p1s": struct.unpack_from("<I", frame, 240)[0],
        "temp3_c": struct.unpack_from("<h", frame, 248)[0] / 10.0,
        "temp4_c": struct.unpack_from("<h", frame, 250)[0] / 10.0,
        "temp5_c": struct.unpack_from("<h", frame, 252)[0] / 10.0,
        "rtc_ticks": struct.unpack_from("<I", frame, 256)[0],
        "sleep_time_sec": struct.unpack_from("<I", frame, 264)[0],
        "pcl_status_word": struct.unpack_from("<H", frame, 268)[0],
    }
    valid = [c for c in data["cells_mv"] if 1000 < c < 5000]
    if not valid:
        return None
    if not (30 < data["total_voltage_v"] < 70):
        return None
    if abs(data["current_a"]) > 300:
        return None
    if not (-40 < data["mos_temp_c"] < 120):
        return None
    return data


def parse_type_01(frame: bytes) -> dict[str, Any]:
    return {
        "sleep_voltage_mv": struct.unpack_from("<I", frame, 6)[0],
        "cell_uvp_mv": struct.unpack_from("<I", frame, 10)[0],
        "cell_uvpr_mv": struct.unpack_from("<I", frame, 14)[0],
        "cell_ovp_mv": struct.unpack_from("<I", frame, 18)[0],
        "cell_ovpr_mv": struct.unpack_from("<I", frame, 22)[0],
        "balance_trigger_mv": struct.unpack_from("<I", frame, 26)[0],
        "soc100_voltage_mv": struct.unpack_from("<I", frame, 30)[0],
        "soc0_voltage_mv": struct.unpack_from("<I", frame, 34)[0],
        "max_charge_current_ma": struct.unpack_from("<I", frame, 50)[0],
        "max_discharge_current_ma": struct.unpack_from("<I", frame, 62)[0],
        "charge_otp_deci_c": struct.unpack_from("<i", frame, 82)[0],
        "charge_utp_deci_c": struct.unpack_from("<i", frame, 98)[0],
        "mos_otp_deci_c": struct.unpack_from("<i", frame, 106)[0],
        "cell_count_setting": struct.unpack_from("<I", frame, 114)[0],
        "charge_enable": bool(struct.unpack_from("<I", frame, 118)[0]),
        "discharge_enable": bool(struct.unpack_from("<I", frame, 122)[0]),
        "balance_enable": bool(struct.unpack_from("<I", frame, 126)[0]),
        "total_battery_capacity_setting": struct.unpack_from("<I", frame, 130)[0] / 1000.0,
        "short_circuit_delay_us": struct.unpack_from("<I", frame, 134)[0],
        "balance_starting_voltage_mv": struct.unpack_from("<I", frame, 138)[0],
        "device_address": struct.unpack_from("<I", frame, 270)[0],
        "flags_0x1114": struct.unpack_from("<H", frame, 282)[0],
        "smart_sleep_hours": frame[286],
    }


def build_active_query(pack_addr: int, reg: int) -> bytes:
    payload = bytes(
        [
            pack_addr & 0xFF,
            0x10,
            0x16,
            reg & 0xFF,
            0x00,
            0x01,
            0x02,
            0x00,
            0x00,
        ]
    )
    return payload + struct.pack("<H", crc16_modbus(payload))


def parse_ascii(frame: bytes, offset: int, length: int) -> str:
    raw = frame[offset : offset + length]
    raw = raw.split(b"\x00", 1)[0].strip()
    return raw.decode("ascii", errors="replace").strip()


def parse_type_03(frame: bytes) -> dict[str, Any]:
    return {
        "manufacturer_device_id": parse_ascii(frame, 6, 16),
        "hardware_version": parse_ascii(frame, 22, 8),
        "software_version": parse_ascii(frame, 30, 8),
        "odd_runtime_sec": struct.unpack_from("<I", frame, 38)[0] if len(frame) >= 42 else 0,
        "power_on_times": struct.unpack_from("<I", frame, 42)[0] if len(frame) >= 46 else 0,
        "bluetooth_name": parse_ascii(frame, 46, 16),
        "bluetooth_pin": parse_ascii(frame, 62, 16),
        "first_on_date": parse_ascii(frame, 78, 8),
        "serial_number": parse_ascii(frame, 86, 16),
        "user_private_data": parse_ascii(frame, 102, 16),
        "password": parse_ascii(frame, 118, 16),
        "user_data_2": parse_ascii(frame, 134, 16),
    }


def mask_middle(value: str, head: int, tail: int, stars: int) -> str:
    if not value:
        return ""
    if len(value) <= head + tail:
        return "*" * stars
    return f"{value[:head]}{'*' * stars}{value[-tail:]}"


def format_runtime(seconds: int) -> str:
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours:02d}h {minutes:02d}m"


def decode_errors(alarm_bitmap: int) -> str:
    if not alarm_bitmap:
        return "0"
    errors = [name for bit, name in ALARM_BITS.items() if alarm_bitmap & (1 << bit)]
    return ", ".join(errors) if errors else f"0x{alarm_bitmap:08X}"


def build_card_state(
    type01: dict[str, Any] | None,
    type02: dict[str, Any] | None,
    type03: dict[str, Any] | None,
    num_cells: int = 16,
) -> dict[str, Any]:
    state: dict[str, Any] = {}
    if type02:
        cells = type02["cells_mv"][:num_cells]
        min_cell_voltage = min(cells) / 1000.0
        max_cell_voltage = max(cells) / 1000.0
        current = type02["current_a"]
        power_abs = abs(type02["power_w"])
        heater_on = abs(type02["heating_current_ma"]) > 10
        state.update(
            {
                "delta_cell_voltage": round(type02["delta_cell_mv"] / 1000.0, 3),
                "balancing_current": round(type02["balancing_current_a"], 3),
                "balancing": "ON" if abs(type02["balancing_current_a"]) > 0.001 or type02["balancing_state"] != 0 else "OFF",
                "power": round(type02["power_w"], 3),
                "total_runtime_formatted": format_runtime(type02["runtime_sec"]),
                "charging_power": round(power_abs if current > 0.02 else 0.0, 3),
                "discharging_power": round(power_abs if current < -0.02 else 0.0, 3),
                "heater": "ON" if heater_on else "OFF",
                "total_voltage": round(type02["total_voltage_v"], 3),
                "total_charging_cycle_capacity": round(type02["total_charging_cycle_capacity_ah"], 3),
                "average_cell_voltage": round(type02["avg_cell_mv"] / 1000.0, 3),
                "current": round(current, 3),
                "state_of_charge": int(type02["state_of_charge"]),
                "capacity_remaining": round(type02["capacity_remaining_ah"], 3),
                "charging_cycles": int(type02["charging_cycles"]),
                "power_tube_temperature": round(type02["mos_temp_c"], 1),
                "min_voltage_cell": int(type02["min_cell_num"]),
                "max_voltage_cell": int(type02["max_cell_num"]),
                "min_cell_voltage": round(min_cell_voltage, 3),
                "max_cell_voltage": round(max_cell_voltage, 3),
                "errors": decode_errors(type02["alarm_bitmap"]),
                "temperature_sensor_1": round(type02["temp1_c"], 1),
                "temperature_sensor_2": round(type02["temp2_c"], 1),
                "temperature_sensor_3": round(type02["temp3_c"], 1),
                "temperature_sensor_4": round(type02["temp4_c"], 1),
                "charging": "ON" if type02["charging_status"] else "OFF",
                "discharging": "ON" if type02["discharging_status"] else "OFF",
                "charge_mos_state": "ON" if type02["charging_status"] else "OFF",
                "discharge_mos_state": "ON" if type02["discharging_status"] else "OFF",
                "precharge_status": int(type02["precharge_status"]),
                "charger_status_word": int(type02["charger_status_word"]),
                "state_of_health": int(type02["state_of_health"]),
            }
        )
        for i in range(num_cells):
            state[f"cell_voltage_{i + 1}"] = round(cells[i] / 1000.0, 3)
            state[f"cell_resistance_{i + 1}"] = int(type02["resistances_mohm"][i])
    if type01:
        state.update(
            {
                "balance_trigger_voltage": round(type01["balance_trigger_mv"] / 1000.0, 3),
                "balance_starting_voltage": round(type01["balance_starting_voltage_mv"] / 1000.0, 3),
                "charging": "ON" if type01["charge_enable"] else state.get("charging", "OFF"),
                "discharging": "ON" if type01["discharge_enable"] else state.get("discharging", "OFF"),
                "balancer": "ON" if type01["balance_enable"] else "OFF",
                "total_battery_capacity_setting": round(type01["total_battery_capacity_setting"], 3),
            }
        )
    if type03:
        state.update(
            {
                "manufacturer_device_id": type03.get("manufacturer_device_id", "") or "unknown",
                "hardware_version": type03.get("hardware_version", "") or "unknown",
                "software_version": type03.get("software_version", "") or "unknown",
                "serial_number": type03.get("serial_number", "") or "unknown",
                "bluetooth_name": type03.get("bluetooth_name", "") or "unknown",
                "bluetooth_pin_masked": mask_middle(type03.get("bluetooth_pin", ""), 1, 1, 4) or "unknown",
                "password_masked": mask_middle(type03.get("password", ""), 2, 2, 3) or "unknown",
                "first_on_date": type03.get("first_on_date", "") or "unknown",
                "power_on_times": int(type03.get("power_on_times", 0)),
            }
        )
    state.setdefault("manufacturer_device_id", "unknown")
    state.setdefault("hardware_version", "unknown")
    state.setdefault("software_version", "unknown")
    state.setdefault("serial_number", "unknown")
    state.setdefault("bluetooth_name", "unknown")
    state.setdefault("bluetooth_pin_masked", "unknown")
    state.setdefault("password_masked", "unknown")
    state.setdefault("first_on_date", "unknown")
    state.setdefault("power_on_times", 0)
    state.setdefault("charging", "OFF")
    state.setdefault("discharging", "OFF")
    state.setdefault("balancer", "OFF")
    state.setdefault("heater", "OFF")
    return state

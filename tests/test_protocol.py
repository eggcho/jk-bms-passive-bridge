from jk_bms_passive_bridge.protocol import build_card_state, crc16_modbus, decode_errors, find_frame_and_delimiter


def test_crc16_modbus_known_value():
    assert crc16_modbus(bytes.fromhex("00 10 16 20 00 01")) == 0x9A05


def test_decode_errors_zero():
    assert decode_errors(0) == "0"


def test_decode_errors_named_bits():
    decoded = decode_errors((1 << 4) | (1 << 11))
    assert "cell_overvoltage" in decoded
    assert "cell_undervoltage" in decoded


def test_build_card_state_basic_mapping():
    type01 = {
        "balance_trigger_mv": 5,
        "balance_starting_voltage_mv": 3450,
        "charge_enable": True,
        "discharge_enable": True,
        "balance_enable": True,
        "total_battery_capacity_setting": 320.0,
    }
    type02 = {
        "cells_mv": [3300] * 16,
        "delta_cell_mv": 2,
        "balancing_current_a": 0.0,
        "balancing_state": 0,
        "power_w": 120.0,
        "runtime_sec": 90061,
        "current_a": 4.0,
        "heating_current_ma": 0,
        "total_voltage_v": 52.8,
        "total_charging_cycle_capacity_ah": 100.0,
        "avg_cell_mv": 3300,
        "state_of_charge": 77,
        "capacity_remaining_ah": 200.0,
        "charging_cycles": 10,
        "mos_temp_c": 20.5,
        "min_cell_num": 1,
        "max_cell_num": 2,
        "alarm_bitmap": 0,
        "temp1_c": 21.0,
        "temp2_c": 22.0,
        "temp3_c": 23.0,
        "temp4_c": 0.0,
        "charging_status": True,
        "discharging_status": False,
        "precharge_status": 0,
        "charger_status_word": 256,
        "state_of_health": 100,
        "resistances_mohm": [10] * 16,
    }
    state = build_card_state(type01, type02, num_cells=16)
    assert state["charging"] == "ON"
    assert state["discharging"] == "OFF"
    assert state["balancer"] == "ON"
    assert state["state_of_charge"] == 77
    assert state["cell_voltage_1"] == 3.3
    assert state["cell_resistance_1"] == 10
    assert state["total_runtime_formatted"] == "1d 01h 01m"


def test_find_frame_and_delimiter_extracts_pack_addr():
    frame = bytes.fromhex("55 aa eb 90 02 00") + bytes(230)
    delimiter_data = bytes.fromhex("02 10 16 20 00 01")
    crc = crc16_modbus(delimiter_data).to_bytes(2, "little")
    buffer = bytearray(frame + delimiter_data + crc)
    pack_addr, extracted_frame, consumed = find_frame_and_delimiter(buffer)
    assert pack_addr == 0x02
    assert extracted_frame.startswith(bytes.fromhex("55 aa eb 90"))
    assert consumed == len(buffer)

# Grafana Dashboard

This repository includes a ready-to-import Grafana dashboard:

- [docs/grafana-dashboard.json](grafana-dashboard.json)
- [docs/grafana-dashboard-plain.json](grafana-dashboard-plain.json)

## What it shows

- both JK BMS packs side by side
- SoC, voltage, current, power
- remaining capacity and cycle capacity
- MOS temperature and cell delta
- charging / discharging / balancing status
- all 16 cell voltages per pack
- all 16 cell resistances per pack
- short trend panels for both packs

## Datasource

The dashboard expects a **Prometheus-compatible datasource** in Grafana.
VictoriaMetrics works with the standard Prometheus datasource plugin.

The queries are based on Home Assistant Prometheus exporter metrics such as:

- `ha_sensor_voltage_v`
- `ha_sensor_current_a`
- `ha_sensor_power_w`
- `ha_sensor_battery_percent`
- `ha_sensor_temperature_celsius`
- `ha_switch_state`
- `ha_binary_sensor_state`

## Import

Use **one** of these methods:

### Method 1: normal Grafana import

1. Open Grafana
2. Go to `Dashboards`
3. Click `New` -> `Import`
4. Upload `docs/grafana-dashboard.json`
5. Select your VictoriaMetrics / Prometheus datasource
6. Import

### Method 2: paste into JSON model

If Grafana creates an empty dashboard when importing the wrapped file, use the
plain dashboard model instead:

1. Create a new empty dashboard
2. Open dashboard settings
3. Open `JSON Model`
4. Replace the content with `docs/grafana-dashboard-plain.json`
5. Save

## Notes

- string states such as `hardware_version`, `software_version`, `errors`, and `total_runtime_formatted` are not exposed as numeric Prometheus series by Home Assistant, so they are not included in this dashboard
- if your Home Assistant Prometheus metric names differ, inspect `/api/prometheus` first and adjust the queries accordingly
- if Grafana shows a completely empty dashboard after import, the usual cause is importing the wrapped file into `JSON Model`; in that case use `docs/grafana-dashboard-plain.json`

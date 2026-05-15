# systemd Service Example

This project does not require systemd, but many installations will want to run
the poller as a long-lived service.

## Example unit

Create:

- `/etc/systemd/system/jk-bms-passive-bridge.service`

Example:

```ini
[Unit]
Description=JK BMS Passive Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=iot
Group=iot
WorkingDirectory=/opt/jk-bms-passive-bridge
ExecStart=/opt/jk-bms-passive-bridge/.venv/bin/jk-bms-ha-poller --config /opt/jk-bms-passive-bridge/config/config.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
MemoryMax=200M

[Install]
WantedBy=multi-user.target
```

Adjust:

- `User`
- `Group`
- `WorkingDirectory`
- virtualenv path
- config file path

## Enable it

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jk-bms-passive-bridge.service
```

## Check status

```bash
systemctl status jk-bms-passive-bridge.service
journalctl -u jk-bms-passive-bridge.service -f
```

## Notes

- keep the service passive: do not replace it with an active polling design on
  a shared production bus without understanding the bus ownership model
- if you change MQTT prefixes or naming schemes, clear retained topics before
  restarting production validation

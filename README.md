# Kobo Homelab Monitor

An e-ink friendly homelab dashboard designed for Kobo's older WebKit browser. It displays host utilization, Prometheus target health and Docker inventory, and can control allow-listed WiZ lights over the local network.

![Kobo Homelab Monitor preview](docs/preview.png)

## Features

- CPU, memory and disk utilization
- Prometheus target summary
- Running, stopped and unhealthy container counts
- Container name, image, state and published ports
- Host uptime, one-minute load and Tailscale service state
- Automatic refresh every 60 seconds
- ES5 and XMLHttpRequest; no frontend build step or external assets
- Read-only interface with no container control actions
- Local WiZ light status, power, brightness, white temperature and reading presets
- WiZ bridge has no published host port and accepts only allow-listed commands and devices

## Requirements

- Docker Engine with Compose
- `jq` on the host
- Permission to run read-only Docker CLI commands
- An existing HTTP endpoint returning the health schema below
- A trusted LAN or private overlay network; do not expose this dashboard directly to the public internet
- WiZ local communication enabled for bulbs already joined to the same LAN

## Quick start

```sh
cp .env.example .env
# Edit .env with private, environment-specific values.
chmod +x update-extra.sh
./update-extra.sh
docker compose up -d
```

`WIZ_LIGHTS` stays in the ignored `.env` file. Do not commit real device addresses.

Refresh host and container metadata once per minute:

```cron
* * * * * /path/to/kobo-homelab-monitor/update-extra.sh >/dev/null 2>&1
```

The Docker network configured in `.env` must already exist and be shared with the service behind `STATUS_UPSTREAM`.

## Health endpoint schema

`GET /api/status` must return JSON shaped like:

```json
{
  "status": "ok",
  "cpu_pct": 12.5,
  "ram_pct": 37.2,
  "disk_pct": 48.1,
  "targets_up": "3/3",
  "down_list": "none",
  "checked_at": "2026-01-01T12:00:00Z"
}
```

## Kobo NickelMenu

Copy `nickelmenu.example` to the NickelMenu configuration directory and replace `SERVER_IP` with the dashboard host's private address. The file intentionally contains no real network identifiers.

## Security model

- No credentials, tokens, hostnames or real IP addresses are committed.
- `.env` and generated runtime JSON files are ignored by Git.
- Nginx sets restrictive browser headers and disables caching.
- The UI is read-only and exposes no Docker control endpoint.
- The WiZ page can change only the explicitly configured bulbs using a fixed command allow-list.
- The WiZ bridge is reachable only from the shared internal Docker network; it publishes no host port.
- Bind the service only to a trusted private interface and apply firewall rules appropriate to your network.

## License

MIT


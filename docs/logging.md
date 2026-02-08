# Logging (Grafana + Loki)

This project ships with a self-hosted logging stack using Grafana + Loki + Promtail.

## Services

- **Grafana**: http://localhost:3000 (admin/admin)
- **Loki**: http://localhost:3100
- **Promtail**: http://localhost:9080 (metrics/status), scrapes Docker container logs and ships them to Loki

## How It Works

```mermaid
graph TD
  APP[App Containers] --> PROMTAIL[Promtail]
  PROMTAIL --> LOKI[Loki]
  GRAFANA[Grafana] --> LOKI
```

Promtail discovers Docker containers and forwards their logs to Loki. Grafana is pre-provisioned with Loki as the default datasource.

## Quick Start

```bash
docker compose up --build
```

## Example Queries

- Backend logs: `{service="backend"}`
- Geo logs: `{service="geo"}`
- Recon logs: `{service="recon"}`
- Frontend logs: `{service="frontend"}`

## Files

- `logging/loki-config.yml`
- `logging/promtail-config.yml`
- `logging/grafana/provisioning/datasources/loki.yml`

If you want structured JSON logs with user identifiers, I can wire that in next.

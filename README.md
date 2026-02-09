# Pointr

A geospatial data platform for discovering, analyzing, and investigating businesses and points of interest using interactive maps.

## Features

### Map View
- **Interactive Drawing**: Draw polygons and circles to define areas of interest
- **Business Discovery**: Automatically discover businesses, POIs, and government entities within drawn areas
- **Custom POIs**: Right-click anywhere on the map to add your own points of interest
- **Custom Areas**: Draw a polygon, enrich it, then save it as a named area — rendered as a dashed amber overlay with label
- **Projects & ACLs**: Project-scoped data with admin/member roles and per-project uploads
- **Location Search**: Search for locations worldwide using OpenStreetMap Nominatim
- **Routing**: Driving (OSRM) and flight modes, draggable waypoints
- **Color-Coded Markers**: Visual categorization by business type (Food, Retail, Healthcare, Government, etc.)
- **Amber Ring**: Custom POIs are distinguished from OSM data with an amber outline ring
- **Contact Badges**: Visual indicators showing which businesses have phone, email, or website data
- **Heatmap Visualization**: Toggle density heatmaps for individual categories to identify business clusters
- **Find in List**: Click any business marker to search for it in the list view

### Data Visualization
- **Point Markers**: Standard view showing individual businesses as colored markers
- **Category Heatmaps**: Density visualization for analyzing business distribution

### List View
- **Full-Text Search**: Search across all business data fields
- **Category Filtering**: Filter by 10 business categories
- **Contact Filtering**: Filter by availability of phone, email, or website
- **Sorting**: Sort by any column (ascending/descending/none)
- **Pagination**: Navigate through large datasets
- **Selection**: Multi-select businesses for reconnaissance

### Contacts View
- Pre-filtered view showing only businesses with contact information

### Recon View
- **Dual Mode Reconnaissance**: Silent (passive) or Full (active)
- **DNS, SSL, WHOIS, ASN, DMARC, Blocklists**
- **Real-Time Streaming**: Live log updates via Server-Sent Events
- **Parallel Execution**: Up to 5 concurrent workers

## Architecture

```
Frontend (Svelte 5 + MapLibre GL) :5173
        ↓ REST (via proxy)
Nginx (Dev proxy :8081 / Prod proxy :8080)
        ↓ REST
Backend (FastAPI) :8000
        ↓ gRPC
├── Geo Data Service :50051  →  Overpass API + PostGIS
└── Recon Service    :50052  →  DNS, SSL, WHOIS, ASN
        ↓
PostGIS (PostgreSQL 16) :5432
Adminer (DB viewer) :8080
Loki + Promtail :3100
Grafana :3000
```

```mermaid
graph TD
  FE[Frontend :5173] -->|REST| NGX[Nginx Proxy :8081/8080]
  NGX -->|REST| BE[Backend :8000]
  BE -->|gRPC| GEO[Geo Service :50051]
  BE -->|gRPC| RECON[Recon Service :50052]
  GEO -->|SQL| PG[PostGIS :5432]
  PG --> ADMINER[Adminer :8080]
  FE -. logs .-> PROMTAIL[Promtail]
  BE -. logs .-> PROMTAIL
  GEO -. logs .-> PROMTAIL
  RECON -. logs .-> PROMTAIL
  PROMTAIL --> LOKI[Loki :3100]
  GRAFANA[Grafana :3000] --> LOKI
```

**Data Flow:**

1. **Map Enrichment**: User draws polygon → Frontend → Nginx proxy → Backend REST → Geo gRPC → Overpass + PostGIS → blended results
2. **Custom POI/Area**: Right-click / save area → Frontend → Nginx proxy → Backend REST → Geo gRPC → PostGIS
3. **Reconnaissance**: User selects businesses → Frontend → Nginx proxy → Backend REST → Recon gRPC → free network tools
4. **Location Search**: User searches → Frontend → Nginx proxy → Backend REST → Nominatim API

## Project Structure

```
pointr/
├── proto/
│   ├── geo.proto             # Geo data service (enrichment + custom data CRUD)
│   └── recon.proto           # Network recon service
├── backend/                  # FastAPI REST API — [README](backend/README.md)
│   ├── main.py
│   ├── config.py
│   └── Dockerfile
├── geo/                      # gRPC geo data service — [README](geo/README.md)
│   ├── main.py               # Overpass queries + PostGIS CRUD
│   ├── config.py
│   └── Dockerfile
├── recon/                    # gRPC recon service — [README](recon/README.md)
│   ├── main.py
│   ├── config.py
│   └── Dockerfile
├── frontend/                 # Svelte 5 + MapLibre UI — [README](frontend/README.md)
│   └── src/
├── docker-compose-dev.yml    # Dev stack (hot reload + dev proxy)
├── docker-compose-prod.yml   # Prod stack (Nginx front + uvicorn workers)
├── .env                      # Secrets (gitignored)
├── .env.example              # Template for secrets
├── nginx/                    # Dev + prod proxy configs (X-User injection in dev)
├── logging/                  # Grafana/Loki/Promtail configs
└── README.md
```

## Prerequisites

- Docker + Docker Compose

## Quick Start

```bash
cp .env.example .env        # configure credentials
docker compose -f docker-compose-dev.yml up --build
```

Services:
- Frontend: http://localhost:5173
- Backend API + docs: http://localhost:8000/docs
- Dev API proxy (injects `X-User`): http://localhost:8081
- Adminer (DB): http://localhost:8080
- Grafana: http://localhost:3000
- Loki: http://localhost:3100
- Promtail: http://localhost:9080

Notes:
- In dev, all frontend API calls go through the Nginx dev proxy at `:8081`, which injects `X-User` (configurable via `AUTH_USER_HEADER`).
- `DEV_MODE=true` enables the optional `X-Dev-Impersonate` header for local testing only.
- Promtail has no UI. Use Grafana to view logs; Promtail exposes metrics at `http://localhost:9080/metrics`.

## Nginx Proxy

This project uses Nginx as a thin HTTP proxy in both dev and prod:

- **Dev** (`nginx/dev.conf`): runs on `:8081`, forwards `/api`, `/docs`, `/openapi.json` to the backend and injects an `X-User` header for local auth.
- **Prod** (`nginx/prod.conf`): runs on `:8080`, forwards `/api`, `/docs`, `/openapi.json` to the backend and serves the frontend at `/` (no header injection).

This keeps the frontend using a single base URL (`/api`) in production while allowing a simple dev auth proxy locally.

### Production

```bash
cp .env.prod.example .env.prod   # then edit values
docker compose --env-file .env.prod -f docker-compose-prod.yml up --build
```

Services:
- App (Nginx): http://localhost:8080
- Backend API + docs: http://localhost:8000/docs
- Grafana: http://localhost:3000

Grafana login (default): `admin` / `admin` (configurable via env vars).

## Docker Compose Variants

- **`docker-compose-dev.yml`**: hot-reload for frontend + backend, dev Nginx proxy with `X-User` injection, suitable for local iteration.
- **`docker-compose-prod.yml`**: production settings (no code mounts), Nginx fronting frontend + backend, and Uvicorn with workers.

## Configuration

Credentials live in `.env` (gitignored). Copy `.env.example` to get started:

```env
POSTGRES_DB=pointr
POSTGRES_USER=pointr
POSTGRES_PASSWORD=changeme
GEO_DB_URL=postgresql://pointr:changeme@postgis:5432/pointr
```

To rebrand, update `app_name` in `backend/config.py` and `recon/config.py`.

See [docs/data-sources.md](docs/data-sources.md) for how to add additional PostGIS databases as enrichment sources.

See [docs/data-upload.md](docs/data-upload.md) for how to upload GeoJSON datasources, update them, and the required format.
See [docs/projects.md](docs/projects.md) for projects and access control.
See [docs/logging.md](docs/logging.md) for the self-hosted Grafana + Loki setup.
See [docs/env.md](docs/env.md) for all environment variables (including a brief OSRM self-hosting guide).

Demo upload dataset: [demo-data/gamla-stan-upload.geojson](demo-data/gamla-stan-upload.geojson)
Demo upload dataset (unmapped fields): [demo-data/gamla-stan-upload-unmapped.geojson](demo-data/gamla-stan-upload-unmapped.geojson)
Demo upload dataset (ambiguous fields): [demo-data/gamla-stan-upload-ambiguous.geojson](demo-data/gamla-stan-upload-ambiguous.geojson)

See [docs/proto-grpc.md](docs/proto-grpc.md) for how to work with the gRPC service definitions.

## Database

### Connecting with Adminer

Navigate to http://localhost:8080 and log in:

| Field    | Value        |
|----------|--------------|
| System   | PostgreSQL   |
| Server   | `postgis`    |
| Username | `pointr`     |
| Password | *(from .env)*|
| Database | `pointr`     |

### Schema

**`custom_pois`** — user-defined points of interest

| Column     | Type                   | Notes                        |
|------------|------------------------|------------------------------|
| id         | UUID                   | Primary key, auto-generated  |
| name       | TEXT                   | Display name                 |
| category   | TEXT                   | Maps to business categories  |
| location   | GEOMETRY(Point, 4326)  | WGS84 lat/lng, spatially indexed |
| tags       | JSONB                  | Arbitrary key/value metadata |
| project_id | UUID                   | Project scope (FK → projects)|
| created_at | TIMESTAMPTZ            |                              |

**`custom_areas`** — named annotated polygons

| Column      | Type                     | Notes                        |
|-------------|--------------------------|------------------------------|
| id          | UUID                     | Primary key, auto-generated  |
| name        | TEXT                     | Label shown on map           |
| description | TEXT                     | Optional notes               |
| geom        | GEOMETRY(Polygon, 4326)  | WGS84 polygon, spatially indexed |
| metadata    | JSONB                    | Arbitrary key/value metadata |
| project_id  | UUID                     | Project scope (FK → projects)|
| created_at  | TIMESTAMPTZ              |                              |

**`projects`** — project registry

| Column          | Type        | Notes |
|-----------------|-------------|-------|
| id              | UUID        | Primary key |
| name            | TEXT        | Unique project name |
| created_by      | TEXT        | Username |
| default_acl_mode| TEXT        | `NONE` (default), `ALL` reserved |
| created_at      | TIMESTAMPTZ | |

**`project_members`** — project ACLs

| Column     | Type | Notes |
|------------|------|-------|
| project_id | UUID | FK → projects |
| username   | TEXT | Member identity |
| role       | TEXT | `owner`, `admin`, `member` |

**`uploaded_sources`** — uploaded GeoJSON sources

| Column     | Type | Notes |
|------------|------|-------|
| id         | UUID | Primary key |
| name       | TEXT | Source name |
| project_id | UUID | Project scope |
| created_at | TIMESTAMPTZ | |

**`uploaded_pois`** — uploaded POIs

| Column     | Type | Notes |
|------------|------|-------|
| id         | UUID | Primary key |
| source_id  | UUID | FK → uploaded_sources |
| project_id | UUID | Project scope |
| location   | GEOMETRY(Point, 4326) | |

Both tables use PostGIS GIST spatial indexes for fast `ST_Within` / `ST_Intersects` queries.

Custom POIs appear blended with OSM results when you enrich a polygon — distinguished by an amber ring on the map and a `Custom` badge in popups. Custom areas that intersect your query polygon are fetched and rendered as dashed overlays.

### Useful Queries

```sql
-- List all custom POIs
SELECT id, name, category, ST_Y(location) AS lat, ST_X(location) AS lng FROM custom_pois;

-- List all custom areas
SELECT id, name, description, ST_AsGeoJSON(geom) FROM custom_areas;

-- Clear all custom data
TRUNCATE custom_pois, custom_areas;
```

### Reset Database

To wipe the database volume entirely:

```bash
docker compose down -v
```

## API Reference

Full interactive docs at http://localhost:8000/docs.

**Enrichment**
- `POST /api/map/enrich` — polygon enrichment (OSM + custom POIs blended)

**Custom POIs**
- `POST /api/pois` — add a custom POI
- `GET /api/pois` — list all (optional bbox filter)
- `DELETE /api/pois/{id}` — delete

**Custom Areas**
- `POST /api/areas` — add a named area
- `GET /api/areas` — list all
- `PATCH /api/areas/{id}` — rename/re-describe
- `DELETE /api/areas/{id}` — delete

**Recon**
- `POST /api/recon/stream` — streaming recon via SSE

**Search / Routing**
- `GET /api/search?q=` — Nominatim geocoding
- `POST /api/route` — OSRM driving directions

## Tech Stack

- **Frontend**: Svelte 5, Vite, Tailwind CSS v4, MapLibre GL JS, Mapbox GL Draw, Turf.js
- **Backend**: FastAPI, Uvicorn, Pydantic, gRPC, httpx
- **Geo Service**: gRPC, Shapely, httpx, psycopg3, psycopg-pool
- **Recon Service**: gRPC, dnspython, python-whois, httpx
- **Database**: PostgreSQL 16 + PostGIS 3.4
- **Package manager**: uv (Python), npm (Node)
- **Transport**: REST (Frontend↔Backend), gRPC (Backend↔Services)

## License

MIT

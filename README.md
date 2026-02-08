# Pointr

A geospatial data platform for discovering, analyzing, and investigating businesses and points of interest using interactive maps.

## Features

### Map View
- **Interactive Drawing**: Draw polygons and circles to define areas of interest
- **Business Discovery**: Automatically discover businesses, POIs, and government entities within drawn areas
- **Custom POIs**: Right-click anywhere on the map to add your own points of interest
- **Custom Areas**: Draw a polygon, enrich it, then save it as a named area — rendered as a dashed amber overlay with label
- **Location Search**: Search for locations worldwide using OpenStreetMap Nominatim
- **Routing**: Get driving directions between two points via OSRM
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
        ↓ REST
Backend (FastAPI) :8000
        ↓ gRPC
├── Geo Data Service :50051  →  Overpass API + PostGIS
└── Recon Service    :50052  →  DNS, SSL, WHOIS, ASN
        ↓
PostGIS (PostgreSQL 16) :5432
Adminer (DB viewer) :8080
```

**Data Flow:**

1. **Map Enrichment**: User draws polygon → Frontend → Backend REST → Geo gRPC → Overpass + PostGIS → blended results
2. **Custom POI/Area**: Right-click / save area → Frontend → Backend REST → Geo gRPC → PostGIS
3. **Reconnaissance**: User selects businesses → Frontend → Backend REST → Recon gRPC → free network tools
4. **Location Search**: User searches → Frontend → Backend REST → Nominatim API

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
├── docker-compose.yml
├── .env                      # Secrets (gitignored)
├── .env.example              # Template for secrets
└── README.md
```

## Prerequisites

- Docker + Docker Compose

## Quick Start

```bash
cp .env.example .env        # configure credentials
docker compose up --build
```

Services:
- Frontend: http://localhost:5173
- Backend API + docs: http://localhost:8000/docs
- Adminer (DB): http://localhost:8080

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
| created_at | TIMESTAMPTZ            |                              |

**`custom_areas`** — named annotated polygons

| Column      | Type                     | Notes                        |
|-------------|--------------------------|------------------------------|
| id          | UUID                     | Primary key, auto-generated  |
| name        | TEXT                     | Label shown on map           |
| description | TEXT                     | Optional notes               |
| geom        | GEOMETRY(Polygon, 4326)  | WGS84 polygon, spatially indexed |
| metadata    | JSONB                    | Arbitrary key/value metadata |
| created_at  | TIMESTAMPTZ              |                              |

Both tables use PostGIS GIST spatial indexes for fast `ST_Within` / `ST_Intersects` queries.

Custom POIs appear blended with OSM results when you enrich a polygon — distinguished by an amber ring on the map and a `Custom` badge in popups. Custom areas that intersect your query polygon are surfaced in the `INSIDE: ...` banner.

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

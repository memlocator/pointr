# Backend

FastAPI REST API gateway that orchestrates the geo and recon gRPC microservices.

## Environment

- **Python**: 3.14
- **Package manager**: uv
- **Framework**: FastAPI + Uvicorn
- **Port**: 8000

## Configuration

All settings are read from environment variables (or `.env` at the repo root). See `config.py` for defaults.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Pointr` | Application name used in user-agent strings |
| `APP_VERSION` | `1.0` | Application version |
| `BACKEND_HOST` | `0.0.0.0` | Bind address |
| `BACKEND_PORT` | `8000` | HTTP port |
| `GEO_HOST` | `geo` | Geo service hostname |
| `GEO_PORT` | `50051` | Geo service gRPC port |
| `RECON_HOST` | `recon` | Recon service hostname |
| `RECON_PORT` | `50052` | Recon service gRPC port |
| `NOMINATIM_API_URL` | `https://nominatim.openstreetmap.org` | Geocoding endpoint |
| `OSRM_API_URL` | `http://router.project-osrm.org` | Routing endpoint |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| `GEO_ADDITIONAL_DBS` | `[]` | JSON array of additional PostGIS sources (see [docs/data-sources.md](../docs/data-sources.md)) |
| `NOMINATIM_RATE_LIMIT` | `60` | Requests per minute to Nominatim |

## API Endpoints

Interactive docs: http://localhost:8000/docs

### System

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Welcome message |
| `GET` | `/api/health` | Service health + datasource status |

The health endpoint returns status for the backend, geo service, recon service, and all configured datasources (primary PostGIS + any additional ones).

### Enrichment

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/enrich` | Enrich a polygon with POI data |
| `POST` | `/api/map/enrich` | Alias for `/api/enrich` |

Request body (`PolygonRequest`):
```json
{
  "coordinates": [
    {"lat": 59.33, "lng": 18.06},
    {"lat": 59.34, "lng": 18.06},
    {"lat": 59.34, "lng": 18.07}
  ]
}
```

### Search

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/search?q=` | Forward geocoding via Nominatim (min 3 chars, max 5 results) |

### Custom POIs

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pois` | Create a custom POI |
| `GET` | `/api/pois` | List custom POIs (optional `min_lat`, `min_lng`, `max_lat`, `max_lng` bbox) |
| `PATCH` | `/api/pois/{poi_id}` | Update name / category / description |
| `DELETE` | `/api/pois/{poi_id}` | Delete |

### Custom Areas

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/areas` | Create a named polygon area |
| `GET` | `/api/areas` | List all areas |
| `PATCH` | `/api/areas/{area_id}` | Update name / description |
| `DELETE` | `/api/areas/{area_id}` | Delete |

### Routing

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/route` | Calculate driving route via OSRM (≥2 waypoints, returns GeoJSON + distance/duration) |
| `POST` | `/api/routes/saved` | Save a named route with stops |
| `GET` | `/api/routes/saved` | List saved routes |
| `DELETE` | `/api/routes/saved/{route_id}` | Delete saved route |

### Reconnaissance

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/recon` | Run domain recon (returns when complete) |
| `POST` | `/api/recon/stream` | Same but streams progress via SSE (`log`, `result`, `complete`, `error` events) |

## Development

```bash
cd backend
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The Docker setup mounts source files as volumes so the `--reload` flag picks up edits without rebuilding.

# Geo Service

gRPC microservice for spatial data enrichment and custom geospatial data management.

## Environment

- **Python**: 3.14
- **Package manager**: uv
- **Framework**: gRPC
- **Port**: 50051

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GEO_DB_URL` | *(required)* | Primary PostGIS connection string |
| `GEO_ADDITIONAL_DBS` | `[]` | JSON array of additional PostGIS sources |
| `GEO_PORT` | `50051` | gRPC listen port |
| `OVERPASS_API_URL` | `https://overpass-api.de/api/interpreter` | OSM Overpass endpoint |
| `OVERPASS_RATE_LIMIT` | `120` | Requests per minute to Overpass |

See [docs/data-sources.md](../docs/data-sources.md) for the `GEO_ADDITIONAL_DBS` schema and setup guide.

## gRPC API

Defined in `proto/geo.proto`.

### Enrichment

| Method | Description |
|---|---|
| `Health` | Service health status |
| `EnrichPolygon` | Query all sources within a polygon; returns blended POI list |

`EnrichPolygon` queries in priority order: custom POIs → additional PostGIS sources → OpenStreetMap (Overpass). Results from each source are tagged with their `source` field.

### Custom POIs

| Method | Description |
|---|---|
| `AddCustomPOI` | Create a point of interest |
| `UpdateCustomPOI` | Update name / category / description |
| `DeleteCustomPOI` | Delete by UUID |
| `ListCustomPOIs` | List all, optionally filtered by bounding box |

### Custom Areas

| Method | Description |
|---|---|
| `AddCustomArea` | Create a named polygon area |
| `UpdateCustomArea` | Update name / description |
| `DeleteCustomArea` | Delete by UUID |
| `ListCustomAreas` | List all areas with coordinates |

### Routes

| Method | Description |
|---|---|
| `AddRoute` | Save a named route with stops |
| `ListRoutes` | List saved routes (newest first) |
| `DeleteRoute` | Delete by UUID |

## Database Schema

Managed via `init_db()` at startup — tables are created if they don't exist.

**`custom_pois`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | TEXT | |
| `category` | TEXT | |
| `description` | TEXT | |
| `location` | GEOMETRY(Point, 4326) | Spatially indexed |
| `tags` | JSONB | |
| `created_at` | TIMESTAMPTZ | |

**`custom_areas`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | TEXT | |
| `description` | TEXT | |
| `geom` | GEOMETRY(Polygon, 4326) | Spatially indexed |
| `metadata` | JSONB | |
| `created_at` | TIMESTAMPTZ | |

**`saved_routes`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | TEXT | |
| `route_type` | TEXT | |
| `stops` | JSONB | Array of stop objects |
| `created_at` | TIMESTAMPTZ | |

**`uploaded_sources`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | TEXT | Unique datasource name |
| `created_at` | TIMESTAMPTZ | |

**`uploaded_pois`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `source_id` | UUID | FK → `uploaded_sources(id)` |
| `name` | TEXT | |
| `category` | TEXT | |
| `description` | TEXT | |
| `phone` | TEXT | |
| `website` | TEXT | |
| `email` | TEXT | |
| `location` | GEOMETRY(Point, 4326) | Spatially indexed |
| `properties` | JSONB | Raw properties payload |
| `created_at` | TIMESTAMPTZ | |

Uploaded datasources are persisted in PostGIS. Re-uploading with the same datasource name replaces all existing POIs for that source.

## OSM Enrichment

Polygon coordinates are sent to the Overpass API as a union of OSM queries (amenity, shop, office, tourism, healthcare, etc.). Results are enriched with:

- **Wikidata descriptions** — fetched in batch for any `wikidata=Q*` tags via `wikidata.org/w/api.php`
- **Wikipedia summaries** — 2-sentence extracts fetched per `wikipedia=lang:Title` tag via the MediaWiki API

## Development

```bash
cd geo
uv sync
uv run python main.py
```

The Docker setup mounts source files as volumes. The service uses `watchdog` to auto-restart on `.py` file changes.

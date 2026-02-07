# Enrichment Service

gRPC microservice for enriching map polygon data with geographic information and points of interest from OpenStreetMap.

## Features

- Calculates polygon area in km²
- Estimates population density
- Queries OpenStreetMap Overpass API for entities within polygons:
  - Businesses (restaurants, cafes, banks, pharmacies, etc.)
  - Government facilities (town halls, courthouses, police stations, etc.)
  - Historic structures (palaces, castles, monuments, memorials)
  - Educational institutions (schools, universities, colleges)
  - Military installations
  - Public transportation hubs
  - Utilities and infrastructure
  - Tourism attractions and museums
  - Parks and nature reserves

## Environment

- **Python**: 3.14
- **Package Manager**: uv
- **Framework**: gRPC
- **Port**: 50051
- **Dependencies**: See `pyproject.toml`

## Development

### Hot Reload

The service includes automatic hot reload in development mode using `watchdog`. Any changes to `.py` files will automatically restart the server.

### Running Locally

With uv:
```bash
cd enrichment
uv sync
uv run python main.py
```

With Docker:
```bash
docker-compose up enrichment
```

The Docker setup mounts source files as volumes, enabling hot reload without rebuilding the container.

## API

### EnrichPolygon

Enriches a polygon with geographic and POI data.

**Request**: `PolygonRequest`
- `coordinates`: Array of lat/lng coordinate pairs

**Response**: `EnrichmentResponse`
- `area_km2`: Polygon area in square kilometers
- `estimated_population`: Rough population estimate
- `region_type`: Classification (small/medium/large)
- `nearby_features`: List of nearby features
- `businesses`: Array of businesses/POIs with name, location, type, contact info

## Configuration

Set via environment variables or `config.py`:
- `ENRICHMENT_PORT`: gRPC server port (default: 50051)
- `OVERPASS_API_URL`: Overpass API endpoint (default: https://overpass-api.de/api/interpreter)

## OpenStreetMap Data

The service queries comprehensive OSM data including:
- All `shop=*` tags
- Business amenities
- Government offices (`office=government`, `government=*`)
- Government buildings (`building=government`, `building=public`)
- Historic sites (`historic=castle`, `historic=monument`, etc.)
- Tourism attractions and museums
- Educational facilities
- Military installations
- Public transport infrastructure
- Power and water utilities
- Parks and nature reserves

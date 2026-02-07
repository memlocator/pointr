# Backend API Service

FastAPI REST API that orchestrates the enrichment and reconnaissance microservices, providing a unified HTTP interface for the Pointr application.

## Features

- RESTful HTTP API gateway for gRPC microservices
- Geographic search using Nominatim
- Polygon enrichment with POI data
- Domain reconnaissance with real-time streaming
- CORS-enabled for frontend integration
- Automatic hot reload in development

## Environment

- **Python**: 3.14
- **Package Manager**: uv
- **Framework**: FastAPI + Uvicorn
- **Port**: 8000
- **Dependencies**: See `pyproject.toml`

## Development

### Hot Reload

The service runs with Uvicorn's `--reload` flag, providing automatic hot reload when Python files change. No additional setup needed.

### Running Locally

With uv:
```bash
cd backend
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

With Docker:
```bash
docker-compose up backend
```

The Docker setup mounts source files as volumes and runs with the `--reload` flag.

## API Endpoints

### Health Check
```
GET /
GET /api/health
```

Returns service status.

### Geographic Search
```
GET /api/search?q={query}
```

Search for locations using OpenStreetMap Nominatim.

**Query Parameters**:
- `q`: Search query (e.g., "Paris, France", "Times Square")

**Response**: `NominatimSearchResponse`
- Array of search results with coordinates, display name, type, importance

### Polygon Enrichment
```
POST /api/enrich
POST /api/map/enrich
```

Enrich a polygon with geographic data and POIs.

**Request**: `PolygonRequest`
```json
{
  "coordinates": [
    {"lat": 40.7589, "lng": -73.9851},
    {"lat": 40.7580, "lng": -73.9851},
    {"lat": 40.7580, "lng": -73.9840}
  ]
}
```

**Response**: `EnrichmentResponse`
- Area in km²
- Population estimate
- Region type
- Businesses and POIs with contact details

### Domain Reconnaissance

#### Batch Mode
```
POST /api/recon
```

Run reconnaissance on multiple domains (batch).

**Request**: `ReconRequest`
```json
{
  "domains": ["example.com", "github.com"],
  "silent_mode": false
}
```

**Response**: `ReconResponse`
- Complete reconnaissance results for all domains

#### Streaming Mode
```
POST /api/recon/stream
```

Real-time reconnaissance with Server-Sent Events (SSE).

**Request**: Same as batch mode

**Response**: SSE stream with:
- `type: "log"` - Progress updates
- `type: "result"` - Completed domain results
- `type: "complete"` - All domains finished

## Architecture

The backend acts as an API gateway, forwarding requests to:
- **Enrichment Service** (gRPC on port 50051)
- **Recon Service** (gRPC on port 50052)
- **Nominatim API** (external HTTP)

## Configuration

Set via environment variables or `config.py`:
- `BACKEND_PORT`: HTTP server port (default: 8000)
- `ENRICHMENT_HOST`: Enrichment service host (default: localhost)
- `ENRICHMENT_PORT`: Enrichment service port (default: 50051)
- `RECON_HOST`: Recon service host (default: localhost)
- `RECON_PORT`: Recon service port (default: 50052)
- `NOMINATIM_URL`: Nominatim API endpoint
- `CORS_ORIGINS`: Allowed CORS origins (default: http://localhost:5173)

## Documentation

Interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

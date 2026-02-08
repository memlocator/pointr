# Environment Variables

All services read configuration from environment variables (Pydantic `BaseSettings`). For local dev, `.env` is loaded automatically; for containers/Kubernetes, set these in your runtime environment.

## Common / Database

Required for PostGIS:

- `POSTGRES_DB` (default in `.env.example`: `pointr`)
- `POSTGRES_USER` (default: `pointr`)
- `POSTGRES_PASSWORD` (default: `changeme`)
- `GEO_DB_URL` (example: `postgresql://pointr:changeme@postgis:5432/pointr`)

Optional additional PostGIS sources:

- `GEO_ADDITIONAL_DBS` (JSON array of sources)

Example:

```env
GEO_ADDITIONAL_DBS=[{"name":"Municipal","url":"postgresql://user:pass@host:5432/db","table":"pois","geom_col":"geom","name_col":"name","category_col":"type","description_col":"description"}]
```

## Backend (FastAPI)

- `APP_NAME` (default: `Pointr`)
- `APP_VERSION` (default: `1.0`)
- `BACKEND_HOST` (default: `0.0.0.0`)
- `BACKEND_PORT` (default: `8000`)
- `GEO_HOST` (default: `geo`)
- `GEO_PORT` (default: `50051`)
- `RECON_HOST` (default: `recon`)
- `RECON_PORT` (default: `50052`)
- `NOMINATIM_API_URL` (default: `https://nominatim.openstreetmap.org`)
- `OSRM_API_URL` (default: `http://router.project-osrm.org`)
- `CORS_ORIGINS` (default: `['http://localhost:5173']`)
- `NOMINATIM_RATE_LIMIT` (default: `60`)

### Self-hosting OSRM (brief)

If you want to run your own OSRM instance, you can point `OSRM_API_URL` to it. A minimal local setup using Docker:

```bash
# 1) Download a PBF (example: Sweden)
curl -L -o sweden-latest.osm.pbf https://download.geofabrik.de/europe/sweden-latest.osm.pbf

# 2) Prepare the routing data (car profile)
docker run --rm -v "$(pwd):/data" ghcr.io/project-osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/sweden-latest.osm.pbf
docker run --rm -v "$(pwd):/data" ghcr.io/project-osrm/osrm-backend \
  osrm-partition /data/sweden-latest.osrm
docker run --rm -v "$(pwd):/data" ghcr.io/project-osrm/osrm-backend \
  osrm-customize /data/sweden-latest.osrm

# 3) Run the OSRM HTTP server
docker run --rm -p 5000:5000 -v "$(pwd):/data" ghcr.io/project-osrm/osrm-backend \
  osrm-routed --algorithm mld /data/sweden-latest.osrm
```

Then set:

```env
OSRM_API_URL=http://localhost:5000
```

Reference: https://github.com/Project-OSRM/osrm-backend

## Geo Service (gRPC)

- `GEO_PORT` (default: `50051`)
- `GEO_DB_URL` (required)
- `GEO_ADDITIONAL_DBS` (optional)
- `OVERPASS_API_URL` (default: `https://overpass-api.de/api/interpreter`)
- `OVERPASS_RATE_LIMIT` (default: `120`)

## Recon Service (gRPC)

- `APP_NAME` (default: `Pointr`)
- `APP_VERSION` (default: `1.0`)
- `RECON_PORT` (default: `50052`)
- `MAX_WORKERS` (default: `5`)
- `CRT_SH_API_URL` (default: `https://crt.sh/`)
- `CRT_SH_RATE_LIMIT` (default: `300`)
- `CYMRU_ASN_DOMAIN` (default: `origin.asn.cymru.com`)
- `CYMRU_ASN_DETAILS_DOMAIN` (default: `asn.cymru.com`)

## Frontend (Vite)

- `VITE_API_URL` (base URL for API requests)
  - dev proxy: `http://localhost:8081`
  - prod nginx: `/api`

## Logging Stack (Docker Compose)

Set in `docker-compose.yml` (Grafana defaults):

- `GF_SECURITY_ADMIN_USER` (default: `admin`)
- `GF_SECURITY_ADMIN_PASSWORD` (default: `admin`)

## Kubernetes Example

Example snippet for setting env vars in a Deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pointr-backend
spec:
  template:
    spec:
      containers:
        - name: backend
          image: your-registry/pointr-backend:latest
          env:
            - name: POSTGRES_DB
              value: pointr
            - name: POSTGRES_USER
              value: pointr
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgis-secret
                  key: password
            - name: GEO_DB_URL
              value: postgresql://pointr:$(POSTGRES_PASSWORD)@postgis:5432/pointr
            - name: DEV_USER
              value: ""
            - name: CORS_ORIGINS
              value: "[\"https://your-frontend.example\"]"
```

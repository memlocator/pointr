# Data Sources

Pointr queries POIs from multiple sources and blends the results. This document explains how to add external PostGIS databases as additional data sources, and how uploaded GeoJSON datasources are auto-mapped.

## Sources and Priority

When enriching a polygon, results are merged in this order (highest priority first):

1. **Custom POIs** — user-created points stored in the local PostGIS DB
2. **Additional PostGIS sources** — external databases you configure
3. **OpenStreetMap** — queried via Overpass API

Each result carries a `source` field identifying where it came from.

---

## Adding a PostGIS Data Source

### 1. Prepare the remote table

The target table must have at minimum a geometry column and a name column:

```sql
CREATE TABLE my_pois (
    name        TEXT,
    geom        GEOMETRY(Point, 4326),  -- WGS84 required
    category    TEXT,                   -- optional
    description TEXT                    -- optional
);

CREATE INDEX ON my_pois USING GIST (geom);
```

The geometry column must use **SRID 4326** (WGS84 lat/lon). Any geometry type works as long as `ST_Within` is meaningful for it — Point is the typical case.

### 2. Configure `GEO_ADDITIONAL_DBS`

Set the environment variable to a JSON array of datasource objects in your `.env`:

```env
GEO_ADDITIONAL_DBS=[{"name":"Municipal","url":"postgresql://user:pass@host:5432/db","table":"my_pois","geom_col":"geom","name_col":"name","category_col":"category","description_col":"description"}]
```

For multiple sources:

```env
GEO_ADDITIONAL_DBS=[
  {"name":"Municipal","url":"postgresql://user:pass@db1:5432/city","table":"pois","geom_col":"geom","name_col":"name","category_col":"type","description_col":"desc"},
  {"name":"Heritage","url":"postgresql://ro_user:pass@db2:5432/heritage","table":"landmarks","geom_col":"location","name_col":"title","category_col":"era"}
]
```

(The value must be on one line in `.env` — the multi-line form above is for readability only.)

### 3. Field reference

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Display name shown in the health panel and `source` field of results |
| `url` | Yes | Standard PostgreSQL connection URI |
| `table` | Yes | Table name in the remote database |
| `geom_col` | Yes | Geometry column name |
| `name_col` | Yes | Column used as the feature name |
| `category_col` | No | Column used as the feature type/category |
| `description_col` | No | Column used for longer descriptive text |

### 4. Restart the geo service

```bash
docker compose up -d geo
```

The geo service creates a connection pool (up to 5 connections) for each configured source at startup. Failed connections are logged but do not prevent startup.

---

## Uploaded Datasources (GeoJSON)

Custom GeoJSON uploads are treated as a data source named by the dataset you upload. The frontend includes a **column-mapping heuristic** to help files that don’t match the expected field names.

When you upload a GeoJSON, the UI will:

1. Inspect available `properties` fields.
2. Propose a mapping to the expected fields (e.g. `name`, `category`, `description`, `phone`, `website`, `email`).
3. Let you review and edit the mapping before upload.

The heuristic is intentionally conservative:
- It matches on common field name variants (case-insensitive), e.g. `title`, `label` → `name`, `type` → `category`, `desc` → `description`, `tel` → `phone`, `url` → `website`.
- If it can’t confidently match a required field (like `name`), it leaves it empty so you can choose manually.

For details on the required GeoJSON format and update workflow, see [docs/data-upload.md](docs/data-upload.md).

---

## Monitoring

The `/api/health` endpoint returns a `datasources` array:

```json
{
  "datasources": [
    { "name": "Primary (PostGIS)", "status": "online", "message": "healthy" },
    { "name": "Municipal",         "status": "online", "message": "reachable" },
    { "name": "Heritage",          "status": "error",  "message": "[Errno 111] Connection refused" }
  ]
}
```

Status is determined by a TCP reachability check from the backend container. This is visible in the topbar health dropdown.

---

## Troubleshooting

**Source shows `error` in health panel**
- Verify the host/port is reachable from inside Docker: `docker exec -it pointr-backend-1 nc -zv <host> <port>`
- Check that the `url` uses the correct hostname (container name for Docker-internal DBs, or the external IP/hostname otherwise)

**No results returned from additional source**
- Check geo service logs: `docker compose logs geo`
- Confirm the geometry column SRID is 4326: `SELECT ST_SRID(geom) FROM my_pois LIMIT 1;`
- Confirm `ST_Within` works: draw a polygon covering known features and check the query manually

**Column not found error**
- Column names are case-sensitive. Match exactly what `\d my_pois` shows in psql.

---

## Connection to geo service

The `geo` gRPC service (port 50051) owns all data source connections. The backend proxies requests to it. If you need to add a source type other than PostGIS, implement a new query method in `geo/main.py` following the same pattern as `_get_additional_db_pois_in_polygon`.

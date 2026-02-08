# Data Upload (GeoJSON Datasources)

This project supports uploading a GeoJSON dataset as a custom datasource. Uploaded datasources are stored in PostGIS and are blended into polygon enrichment results.

## How It Works

1. The frontend (or any client) sends a POST request to the backend endpoint `/api/datasources`.
2. The backend forwards the request to the geo gRPC service (`UploadSource`).
3. The geo service validates and stores the GeoJSON in PostGIS (`uploaded_sources` + `uploaded_pois`).
4. During polygon enrichment, uploaded datasource features are blended into results alongside custom POIs and OSM data.

## API Endpoint

**POST** `/api/datasources`

Request body fields:
- `name`: String identifier for the datasource.
- `geojson`: A **string** containing a GeoJSON `FeatureCollection`.

Response fields:
- `name`: The stored datasource name.
- `feature_count`: Number of features stored.
- `error`: Empty string on success, or a message on failure.

## Format Requirements

The GeoJSON must be:
- A `FeatureCollection` at the top level.
- Each feature **must** be a `Point` geometry.
- Each feature **must** include a `properties.name` field.

Other properties are optional and can be used by the UI (for example `category`, `phone`, `website`, `email`, `description`).

## Updating An Existing Dataset

Re-uploading with the same `name` **replaces** the dataset:
- The source row is upserted.
- Existing features for that source are deleted.
- New features are inserted.

This makes updates deterministic and keeps names stable even if the filename changes.

## Minimal Example

This is the smallest valid payload:

```json
{
  "name": "My Custom Dataset",
  "geojson": "{\"type\":\"FeatureCollection\",\"features\":[{\"type\":\"Feature\",\"geometry\":{\"type\":\"Point\",\"coordinates\":[18.0686,59.3293]},\"properties\":{\"name\":\"Test POI\"}}]}"
}
```

## Recommended GeoJSON Example

This is a readable GeoJSON file that can be stringified and sent via `geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [18.0707, 59.3250]},
      "properties": {
        "name": "Stortorget Cafe",
        "category": "Food & Dining",
        "phone": "+46-8-555-0101",
        "website": "https://stortorget-cafe.example"
      }
    }
  ]
}
```

## Example cURL

```bash
curl -X POST http://localhost:8000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Gamla Stan Sample",
    "geojson": "{\"type\":\"FeatureCollection\",\"features\":[{\"type\":\"Feature\",\"geometry\":{\"type\":\"Point\",\"coordinates\":[18.0707,59.3250]},\"properties\":{\"name\":\"Stortorget Cafe\",\"category\":\"Food & Dining\",\"phone\":\"+46-8-555-0101\",\"website\":\"https://stortorget-cafe.example\"}}]}"
  }'
```

## Limitations

- Uploaded datasources are stored in **PostGIS** (persistent).
- Only `Point` features are supported at the moment.
- Authentication is not enforced yet.

If you want this documented elsewhere (e.g. `docs/data-sources.md`), say the word and I can merge it in.

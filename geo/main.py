from concurrent import futures
import grpc
import geo_pb2
import geo_pb2_grpc
from shapely.geometry import Polygon, Point, box
import math
import httpx
import json
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from config import settings


_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.geo_db_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row}
        )
    return _pool


def init_db():
    """Create tables if they don't exist"""
    with get_pool().connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_pois (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'custom',
                description TEXT DEFAULT '',
                location GEOMETRY(Point, 4326) NOT NULL,
                tags JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        conn.execute("""
            ALTER TABLE custom_pois ADD COLUMN IF NOT EXISTS description TEXT DEFAULT ''
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS custom_pois_location_idx
                ON custom_pois USING GIST (location)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_areas (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                geom GEOMETRY(Polygon, 4326) NOT NULL,
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS custom_areas_geom_idx
                ON custom_areas USING GIST (geom)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_routes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                route_type TEXT NOT NULL DEFAULT 'road',
                stops JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        conn.commit()
    print("Database initialized")


class GeoDataServicer(geo_pb2_grpc.GeoDataServiceServicer):
    def Health(self, request, context):
        return geo_pb2.HealthResponse(
            status="healthy",
            message="Geo data service operational"
        )

    def EnrichPolygon(self, request, context):
        """Enrich a polygon with OSM data and custom POIs blended together"""
        coords = [(coord.lng, coord.lat) for coord in request.coordinates]

        if len(coords) < 3:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Polygon must have at least 3 points')
            return geo_pb2.EnrichmentResponse()

        polygon = Polygon(coords)
        area_km2 = self._calculate_area_km2(polygon)
        estimated_population = int(area_km2 * 1000)
        region_type = self._classify_region(area_km2)

        # Query OSM via Overpass
        osm_businesses, error = self._get_businesses_from_overpass(coords)

        # Query custom POIs from PostGIS
        try:
            custom_businesses = self._get_custom_pois_in_polygon(coords)
        except Exception as e:
            print(f"PostGIS query error (POIs): {e}")
            custom_businesses = []

        # Query custom areas that intersect the polygon
        try:
            area_names = self._get_intersecting_area_names(coords)
        except Exception as e:
            print(f"PostGIS query error (areas): {e}")
            area_names = []

        # Blend: custom first so they appear at top of list
        all_businesses = custom_businesses + osm_businesses

        if error:
            print(f"Enrichment error: {error}")
        else:
            print(f"Enriched polygon: {area_km2:.2f} km², pop: {estimated_population}, {len(osm_businesses)} OSM + {len(custom_businesses)} custom")

        return geo_pb2.EnrichmentResponse(
            area_km2=area_km2,
            estimated_population=estimated_population,
            region_type=region_type,
            nearby_features=area_names,
            businesses=all_businesses,
            error=error or ""
        )

    def AddCustomPOI(self, request, context):
        try:
            with get_pool().connection() as conn:
                row = conn.execute("""
                    INSERT INTO custom_pois (name, category, description, location, tags)
                    VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s::jsonb)
                    RETURNING id::text, name, category, description,
                              ST_Y(location) AS lat, ST_X(location) AS lng,
                              tags::text AS tags_json
                """, (
                    request.name,
                    request.category or 'custom',
                    request.description or '',
                    request.lng, request.lat,
                    request.tags_json or '{}'
                )).fetchone()
                conn.commit()
            return geo_pb2.CustomPOIResponse(
                id=row['id'],
                name=row['name'],
                category=row['category'],
                description=row['description'],
                lat=row['lat'],
                lng=row['lng'],
                tags_json=row['tags_json'],
                error=''
            )
        except Exception as e:
            return geo_pb2.CustomPOIResponse(error=str(e))

    def DeleteCustomPOI(self, request, context):
        try:
            with get_pool().connection() as conn:
                result = conn.execute(
                    "DELETE FROM custom_pois WHERE id = %s::uuid",
                    (request.id,)
                )
                conn.commit()
                if result.rowcount == 0:
                    return geo_pb2.DeleteResponse(success=False, error='POI not found')
            return geo_pb2.DeleteResponse(success=True, error='')
        except Exception as e:
            return geo_pb2.DeleteResponse(success=False, error=str(e))

    def UpdateCustomPOI(self, request, context):
        try:
            with get_pool().connection() as conn:
                row = conn.execute("""
                    UPDATE custom_pois SET name = %s, category = %s, description = %s
                    WHERE id = %s::uuid
                    RETURNING id::text, name, category, description,
                              ST_Y(location) AS lat, ST_X(location) AS lng,
                              tags::text AS tags_json
                """, (request.name, request.category, request.description or '', request.id)).fetchone()
                conn.commit()
                if not row:
                    return geo_pb2.CustomPOIResponse(error='POI not found')
            return geo_pb2.CustomPOIResponse(
                id=row['id'],
                name=row['name'],
                category=row['category'],
                description=row['description'],
                lat=row['lat'],
                lng=row['lng'],
                tags_json=row['tags_json'],
                error=''
            )
        except Exception as e:
            return geo_pb2.CustomPOIResponse(error=str(e))

    def ListCustomPOIs(self, request, context):
        try:
            with get_pool().connection() as conn:
                # If bounding box provided, filter by it
                if request.min_lat or request.max_lat:
                    rows = conn.execute("""
                        SELECT id::text, name, category, description,
                               ST_Y(location) AS lat, ST_X(location) AS lng,
                               tags::text AS tags_json
                        FROM custom_pois
                        WHERE ST_Within(location, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
                        ORDER BY created_at DESC
                    """, (request.min_lng, request.min_lat, request.max_lng, request.max_lat)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT id::text, name, category, description,
                               ST_Y(location) AS lat, ST_X(location) AS lng,
                               tags::text AS tags_json
                        FROM custom_pois
                        ORDER BY created_at DESC
                    """).fetchall()
            pois = [
                geo_pb2.CustomPOIResponse(
                    id=r['id'], name=r['name'], category=r['category'],
                    description=r['description'],
                    lat=r['lat'], lng=r['lng'], tags_json=r['tags_json']
                )
                for r in rows
            ]
            return geo_pb2.ListCustomPOIsResponse(pois=pois, error='')
        except Exception as e:
            return geo_pb2.ListCustomPOIsResponse(error=str(e))

    def AddCustomArea(self, request, context):
        try:
            # Build WKT polygon from coordinates
            coords = [(c.lng, c.lat) for c in request.coordinates]
            # Ensure polygon is closed
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            wkt_coords = ", ".join(f"{lng} {lat}" for lng, lat in coords)
            polygon_wkt = f"POLYGON(({wkt_coords}))"

            with get_pool().connection() as conn:
                row = conn.execute("""
                    INSERT INTO custom_areas (name, description, geom, metadata)
                    VALUES (%s, %s, ST_GeomFromText(%s, 4326), %s::jsonb)
                    RETURNING id::text, name, description, metadata::text AS metadata_json,
                              ST_AsText(geom) AS geom_wkt
                """, (
                    request.name,
                    request.description or '',
                    polygon_wkt,
                    request.metadata_json or '{}'
                )).fetchone()
                conn.commit()

            # Parse coordinates back from WKT for response
            resp_coords = self._wkt_to_coords(row['geom_wkt'])
            return geo_pb2.CustomAreaResponse(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                coordinates=resp_coords,
                metadata_json=row['metadata_json'],
                error=''
            )
        except Exception as e:
            return geo_pb2.CustomAreaResponse(error=str(e))

    def UpdateCustomArea(self, request, context):
        try:
            with get_pool().connection() as conn:
                row = conn.execute("""
                    UPDATE custom_areas SET name = %s, description = %s
                    WHERE id = %s::uuid
                    RETURNING id::text, name, description, metadata::text AS metadata_json,
                              ST_AsText(geom) AS geom_wkt
                """, (request.name, request.description, request.id)).fetchone()
                conn.commit()
                if not row:
                    return geo_pb2.CustomAreaResponse(error='Area not found')
            return geo_pb2.CustomAreaResponse(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                coordinates=self._wkt_to_coords(row['geom_wkt']),
                metadata_json=row['metadata_json'],
                error=''
            )
        except Exception as e:
            return geo_pb2.CustomAreaResponse(error=str(e))

    def DeleteCustomArea(self, request, context):
        try:
            with get_pool().connection() as conn:
                result = conn.execute(
                    "DELETE FROM custom_areas WHERE id = %s::uuid",
                    (request.id,)
                )
                conn.commit()
                if result.rowcount == 0:
                    return geo_pb2.DeleteResponse(success=False, error='Area not found')
            return geo_pb2.DeleteResponse(success=True, error='')
        except Exception as e:
            return geo_pb2.DeleteResponse(success=False, error=str(e))

    def ListCustomAreas(self, request, context):
        try:
            with get_pool().connection() as conn:
                rows = conn.execute("""
                    SELECT id::text, name, description,
                           metadata::text AS metadata_json,
                           ST_AsText(geom) AS geom_wkt
                    FROM custom_areas
                    ORDER BY created_at DESC
                """).fetchall()
            areas = [
                geo_pb2.CustomAreaResponse(
                    id=r['id'],
                    name=r['name'],
                    description=r['description'],
                    coordinates=self._wkt_to_coords(r['geom_wkt']),
                    metadata_json=r['metadata_json']
                )
                for r in rows
            ]
            return geo_pb2.ListCustomAreasResponse(areas=areas, error='')
        except Exception as e:
            return geo_pb2.ListCustomAreasResponse(error=str(e))

    def AddRoute(self, request, context):
        try:
            with get_pool().connection() as conn:
                row = conn.execute("""
                    INSERT INTO saved_routes (name, route_type, stops)
                    VALUES (%s, %s, %s::jsonb)
                    RETURNING id::text, name, route_type, stops::text AS stops_json, created_at::text
                """, (request.name, request.route_type, request.stops_json)).fetchone()
                conn.commit()
            return geo_pb2.RouteResponse(
                id=row['id'], name=row['name'], route_type=row['route_type'],
                stops_json=row['stops_json'], created_at=row['created_at']
            )
        except Exception as e:
            return geo_pb2.RouteResponse(error=str(e))

    def ListRoutes(self, request, context):
        try:
            with get_pool().connection() as conn:
                rows = conn.execute("""
                    SELECT id::text, name, route_type, stops::text AS stops_json, created_at::text
                    FROM saved_routes ORDER BY created_at DESC
                """).fetchall()
            return geo_pb2.ListRoutesResponse(routes=[
                geo_pb2.RouteResponse(
                    id=r['id'], name=r['name'], route_type=r['route_type'],
                    stops_json=r['stops_json'], created_at=r['created_at']
                ) for r in rows
            ])
        except Exception as e:
            return geo_pb2.ListRoutesResponse(error=str(e))

    def DeleteRoute(self, request, context):
        try:
            with get_pool().connection() as conn:
                conn.execute("DELETE FROM saved_routes WHERE id = %s::uuid", (request.id,))
                conn.commit()
            return geo_pb2.DeleteResponse(success=True)
        except Exception as e:
            return geo_pb2.DeleteResponse(success=False, error=str(e))

    def _get_custom_pois_in_polygon(self, coords) -> list:
        """Query PostGIS for custom POIs within a polygon using ST_Within"""
        wkt_coords = ", ".join(f"{lng} {lat}" for lng, lat in coords)
        polygon_wkt = f"POLYGON(({wkt_coords}))"

        with get_pool().connection() as conn:
            rows = conn.execute("""
                SELECT id::text, name, category, description,
                       ST_Y(location) AS lat, ST_X(location) AS lng,
                       tags::text AS tags_json
                FROM custom_pois
                WHERE ST_Within(location, ST_GeomFromText(%s, 4326))
            """, (polygon_wkt,)).fetchall()

        return [
            geo_pb2.Business(
                name=row['name'],
                lat=row['lat'],
                lng=row['lng'],
                type=row['category'],
                address='',
                phone='',
                website='',
                email='',
                source='custom',
                id=row['id'],
                description=row['description']
            )
            for row in rows
        ]

    def _get_intersecting_area_names(self, coords) -> list[str]:
        """Query PostGIS for custom areas that intersect the given polygon"""
        wkt_coords = ", ".join(f"{lng} {lat}" for lng, lat in coords)
        polygon_wkt = f"POLYGON(({wkt_coords}))"

        with get_pool().connection() as conn:
            rows = conn.execute("""
                SELECT name FROM custom_areas
                WHERE ST_Intersects(geom, ST_GeomFromText(%s, 4326))
                ORDER BY name
            """, (polygon_wkt,)).fetchall()

        return [row['name'] for row in rows]

    def _wkt_to_coords(self, wkt: str) -> list:
        """Parse POLYGON((lng lat, ...)) WKT into Coordinate list"""
        # Extract coordinate string from POLYGON((...))
        inner = wkt.replace('POLYGON((', '').replace('))', '').strip()
        coords = []
        for pair in inner.split(','):
            parts = pair.strip().split()
            if len(parts) == 2:
                coords.append(geo_pb2.Coordinate(lat=float(parts[1]), lng=float(parts[0])))
        return coords

    def _calculate_area_km2(self, polygon):
        area_deg2 = polygon.area
        area_km2 = area_deg2 * 12100
        return round(area_km2, 2)

    def _classify_region(self, area_km2):
        if area_km2 < 1:
            return "small"
        elif area_km2 < 10:
            return "medium"
        else:
            return "large"

    def _detect_circle(self, coords):
        if len(coords) < 10:
            return None

        polygon = Polygon(coords)
        center = polygon.centroid
        center_lat, center_lng = center.y, center.x

        distances = []
        for lng, lat in coords[:-1]:
            dlat = math.radians(lat - center_lat)
            dlng = math.radians(lng - center_lng)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(center_lat)) * math.cos(math.radians(lat)) * math.sin(dlng/2)**2
            c = 2 * math.asin(math.sqrt(a))
            distance = 6371000 * c
            distances.append(distance)

        if not distances:
            return None

        avg_distance = sum(distances) / len(distances)
        max_deviation = max(abs(d - avg_distance) for d in distances)

        if max_deviation / avg_distance < 0.05:
            return (center_lat, center_lng, int(avg_distance))

        return None

    def _get_businesses_from_overpass(self, coords):
        """Query Overpass API for businesses in polygon or circle"""
        circle_params = self._detect_circle(coords)

        polygon = Polygon(coords)

        business_amenities = [
            "restaurant", "cafe", "fast_food", "bar", "pub", "food_court",
            "bank", "pharmacy", "clinic", "doctors", "dentist", "hospital",
            "fuel", "car_rental", "car_wash", "veterinary",
            "marketplace", "post_office", "bureau_de_change"
        ]

        government_amenities = [
            "townhall", "courthouse", "police", "fire_station",
            "community_centre", "social_facility", "public_building",
            "government", "embassy", "prison", "ranger_station",
            "public_bath", "library", "courthouse", "archive"
        ]

        amenity_filter = "|".join(business_amenities + government_amenities)

        government_types = [
            "parliament", "legislative", "legislature", "ministry",
            "administrative", "regional", "local", "national",
            "government", "public_service", "tax", "social_security",
            "register_office", "customs", "bailiff", "prosecutor"
        ]

        government_filter = "|".join(government_types)

        lats = [lat for lng, lat in coords]
        lngs = [lng for lng, lat in coords]
        bbox = f"{min(lats)},{min(lngs)},{max(lats)},{max(lngs)}"

        if circle_params:
            center_lat, center_lng, radius_m = circle_params
            print(f"Querying Overpass with bbox (circle detected: center=({center_lat:.6f}, {center_lng:.6f}), radius={radius_m}m): {bbox}")
        else:
            print(f"Querying Overpass with bbox: {bbox}")

        query = f"""
        [out:json][timeout:60][bbox:{bbox}];
        (
          nwr["office"="government"];
          nwr["government"];
          nwr["building"~"^(government|public|palace|castle)$"];
          nwr["historic"~"^(castle|palace|monument|memorial|fort)$"];
          nwr["tourism"~"^(attraction|museum)$"];
          nwr["amenity"~"^(restaurant|cafe|bank|hospital|townhall|courthouse|police|embassy|post_office|bus_station|ferry_terminal)$"];
          nwr["shop"];
          nwr["office"~"^(telecommunication|energy|it|company|transport|railway|airline|logistics|courier|delivery|water_utility)$"];
          nwr["aeroway"~"^(aerodrome|terminal|hangar)$"];
          nwr["railway"~"^(station|halt)$"];
          nwr["public_transport"="station"];
          nwr["man_made"~"^(mast|communications_tower|water_tower|water_works|wastewater_plant)$"];
          nwr["power"~"^(plant|substation|generator)$"];
          nwr["landuse"~"^(port|industrial)$"];
          nwr["amenity"="post_depot"];
        );
        out bb center;
        """

        try:
            response = httpx.post(
                settings.overpass_api_url,
                data={"data": query},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            businesses = []
            qid_to_indices = {}   # {wikidata_qid: [business_index]}
            wiki_to_indices = {}  # {"lang:title": [business_index]}
            elements = data.get('elements', [])
            print(f"Overpass returned {len(elements)} elements")

            aerodromes = [e for e in elements if e.get('tags', {}).get('aeroway') == 'aerodrome']
            if aerodromes:
                print(f"  Found {len(aerodromes)} aerodrome(s):")
                for a in aerodromes:
                    print(f"    - {a.get('tags', {}).get('name', 'Unnamed')} (id={a.get('id')}, type={a.get('type')})")

            for element in elements:
                tags = element.get('tags', {})
                name = tags.get('name', 'Unnamed')

                historic_val = tags.get('historic')
                if historic_val:
                    castle_type = tags.get('castle_type')
                    business_type = f"{historic_val}:{castle_type}" if castle_type else historic_val
                else:
                    landuse_val = tags.get('landuse')
                    landuse_type = None
                    if landuse_val in ['port', 'industrial', 'military']:
                        landuse_type = landuse_val

                    business_type = (
                        tags.get('tourism') or
                        tags.get('military') or
                        tags.get('aeroway') or
                        landuse_type or
                        tags.get('shop') or
                        tags.get('amenity') or
                        tags.get('government') or
                        tags.get('office') or
                        tags.get('public_transport') or
                        tags.get('railway') or
                        tags.get('power') or
                        tags.get('man_made') or
                        tags.get('leisure') or
                        (tags.get('building') if tags.get('building') in ['government', 'public', 'palace', 'castle'] else None) or
                        'business'
                    )

                address = tags.get('addr:street', '')
                phone = tags.get('phone') or tags.get('contact:phone', '')
                website = tags.get('website') or tags.get('contact:website', '')
                email = tags.get('email') or tags.get('contact:email', '')

                if 'lat' in element and 'lon' in element:
                    lat = element['lat']
                    lng = element['lon']
                elif 'center' in element:
                    lat = element['center']['lat']
                    lng = element['center']['lon']
                else:
                    print(f"  WARNING: No coordinates found for {name}, skipping")
                    continue

                if 'bounds' in element:
                    bounds = element['bounds']
                    entity_bbox = box(
                        bounds['minlon'], bounds['minlat'],
                        bounds['maxlon'], bounds['maxlat']
                    )
                    if not polygon.intersects(entity_bbox):
                        if tags.get('aeroway') == 'aerodrome':
                            print(f"  DEBUG: Aerodrome {name} filtered out - bbox doesn't intersect")
                        continue
                else:
                    point = Point(lng, lat)
                    if not polygon.contains(point):
                        if tags.get('aeroway') == 'aerodrome':
                            print(f"  DEBUG: Aerodrome {name} filtered out - center not in polygon")
                        continue

                idx = len(businesses)
                businesses.append(geo_pb2.Business(
                    name=name,
                    lat=lat,
                    lng=lng,
                    type=business_type,
                    address=address,
                    phone=phone,
                    website=website,
                    email=email,
                    source='osm',
                    id=''
                ))

                # Track wikidata/wikipedia for description enrichment
                if tags.get('wikidata'):
                    qid_to_indices.setdefault(tags['wikidata'], []).append(idx)
                elif tags.get('wikipedia'):
                    wiki_to_indices.setdefault(tags['wikipedia'], []).append(idx)

                if tags.get('aeroway') == 'aerodrome':
                    print(f"  ✓ Added aerodrome: {name} (center: {lat}, {lng})")
                elif any(tag in tags for tag in ['historic', 'tourism']) or tags.get('building') in ['palace', 'castle']:
                    print(f"  → {name} (type={business_type})")

            # Enrich with Wikidata/Wikipedia descriptions
            if qid_to_indices:
                descriptions = self._fetch_wikidata_descriptions(list(qid_to_indices.keys()))
                for qid, desc in descriptions.items():
                    for idx in qid_to_indices.get(qid, []):
                        businesses[idx].description = desc

            if wiki_to_indices:
                descriptions = self._fetch_wikipedia_summaries(list(wiki_to_indices.keys()))
                for wiki_key, desc in descriptions.items():
                    for idx in wiki_to_indices.get(wiki_key, []):
                        businesses[idx].description = desc

            return businesses, None
        except httpx.TimeoutException as e:
            error_msg = "Overpass API timeout - try a smaller area or try again later"
            print(f"Timeout querying Overpass API: {e}")
            return [], error_msg
        except Exception as e:
            error_msg = f"Error querying Overpass API: {str(e)}"
            print(error_msg)
            return [], error_msg


    def _fetch_wikidata_descriptions(self, qids: list) -> dict:
        """Batch fetch short descriptions from Wikidata for a list of QIDs"""
        if not qids:
            return {}
        results = {}
        try:
            for i in range(0, len(qids), 50):
                batch = qids[i:i + 50]
                resp = httpx.get(
                    'https://www.wikidata.org/w/api.php',
                    params={
                        'action': 'wbgetentities',
                        'ids': '|'.join(batch),
                        'props': 'descriptions',
                        'languages': 'en',
                        'format': 'json'
                    },
                    timeout=10.0
                )
                resp.raise_for_status()
                for qid, entity in resp.json().get('entities', {}).items():
                    desc = entity.get('descriptions', {}).get('en', {}).get('value', '')
                    if desc:
                        results[qid] = desc
        except Exception as e:
            print(f"Wikidata API error: {e}")
        return results

    def _fetch_wikipedia_summaries(self, wiki_keys: list) -> dict:
        """Fetch 2-sentence extracts from Wikipedia for 'lang:title' keys"""
        if not wiki_keys:
            return {}
        # Group by language
        by_lang = {}
        for key in wiki_keys:
            if ':' in key:
                lang, title = key.split(':', 1)
            else:
                lang, title = 'en', key
            by_lang.setdefault(lang, []).append((key, title))
        results = {}
        for lang, items in by_lang.items():
            try:
                for i in range(0, len(items), 20):
                    batch = items[i:i + 20]
                    title_to_key = {title: key for key, title in batch}
                    resp = httpx.get(
                        f'https://{lang}.wikipedia.org/w/api.php',
                        params={
                            'action': 'query',
                            'prop': 'extracts',
                            'exintro': '1',
                            'exsentences': '2',
                            'explaintext': '1',
                            'titles': '|'.join(title_to_key.keys()),
                            'format': 'json',
                            'redirects': '1'
                        },
                        timeout=10.0
                    )
                    resp.raise_for_status()
                    for page in resp.json().get('query', {}).get('pages', {}).values():
                        title = page.get('title', '')
                        extract = page.get('extract', '').strip()
                        if extract and title in title_to_key:
                            results[title_to_key[title]] = extract
            except Exception as e:
                print(f"Wikipedia API error ({lang}): {e}")
        return results


def serve():
    """Start the gRPC server"""
    init_db()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    geo_pb2_grpc.add_GeoDataServiceServicer_to_server(
        GeoDataServicer(), server
    )
    server.add_insecure_port(f'[::]:{settings.geo_port}')
    server.start()
    print(f"Geo data service listening on port {settings.geo_port}")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()

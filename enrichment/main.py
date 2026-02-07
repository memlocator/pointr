from concurrent import futures
import grpc
import enrichment_pb2
import enrichment_pb2_grpc
from shapely.geometry import Polygon, Point, box
import math
import httpx
from config import settings


class EnrichmentServicer(enrichment_pb2_grpc.EnrichmentServiceServicer):
    def Health(self, request, context):
        """Health check endpoint - returns service status without doing any actual enrichment"""
        return enrichment_pb2.HealthResponse(
            status="healthy",
            message="Enrichment service operational"
        )

    def EnrichPolygon(self, request, context):
        """Enrich a polygon with calculated data"""

        # Convert request coordinates to shapely polygon
        coords = [(coord.lng, coord.lat) for coord in request.coordinates]

        if len(coords) < 3:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Polygon must have at least 3 points')
            return enrichment_pb2.EnrichmentResponse()

        # Calculate polygon area
        polygon = Polygon(coords)
        area_km2 = self._calculate_area_km2(polygon)

        # Calculate enrichment data
        estimated_population = int(area_km2 * 1000)  # Mock: 1000 people per km²
        region_type = self._classify_region(area_km2)

        # Query Overpass API for businesses
        businesses, error = self._get_businesses_from_overpass(coords)

        if error:
            print(f"Enrichment error: {error}")
        else:
            print(f"Enriched polygon: {area_km2:.2f} km², pop: {estimated_population}, {len(businesses)} businesses")

        return enrichment_pb2.EnrichmentResponse(
            area_km2=area_km2,
            estimated_population=estimated_population,
            region_type=region_type,
            nearby_features=[],
            businesses=businesses,
            error=error or ""
        )

    def _calculate_area_km2(self, polygon):
        """Calculate approximate area in km² using shapely"""
        # This is a rough approximation
        # For production, use proper geographic projections
        area_deg2 = polygon.area
        # Rough conversion: 1 degree² ≈ 12,100 km² at equator
        area_km2 = area_deg2 * 12100
        return round(area_km2, 2)

    def _classify_region(self, area_km2):
        """Classify region type based on area"""
        if area_km2 < 1:
            return "small"
        elif area_km2 < 10:
            return "medium"
        else:
            return "large"

    def _detect_circle(self, coords):
        """Detect if polygon is actually a circle and return (center_lat, center_lng, radius_m)"""
        if len(coords) < 10:
            return None  # Not enough points to be a circle

        # Calculate centroid
        polygon = Polygon(coords)
        center = polygon.centroid
        center_lat, center_lng = center.y, center.x

        # Calculate distances from center to all points
        distances = []
        for lng, lat in coords[:-1]:  # Exclude last point if it duplicates first
            # Haversine distance in meters
            dlat = math.radians(lat - center_lat)
            dlng = math.radians(lng - center_lng)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(center_lat)) * math.cos(math.radians(lat)) * math.sin(dlng/2)**2
            c = 2 * math.asin(math.sqrt(a))
            distance = 6371000 * c  # Earth radius in meters
            distances.append(distance)

        if not distances:
            return None

        # Check if all distances are similar (within 5% tolerance)
        avg_distance = sum(distances) / len(distances)
        max_deviation = max(abs(d - avg_distance) for d in distances)

        if max_deviation / avg_distance < 0.05:  # 5% tolerance
            return (center_lat, center_lng, int(avg_distance))

        return None

    def _get_businesses_from_overpass(self, coords):
        """Query Overpass API for businesses in polygon or circle"""
        # Check if this is actually a circle
        circle_params = self._detect_circle(coords)

        # Create polygon for filtering results
        from shapely.geometry import Point
        polygon = Polygon(coords)

        # Business-related amenities only (exclude bike_parking, benches, etc.)
        business_amenities = [
            "restaurant", "cafe", "fast_food", "bar", "pub", "food_court",
            "bank", "pharmacy", "clinic", "doctors", "dentist", "hospital",
            "fuel", "car_rental", "car_wash", "veterinary",
            "marketplace", "post_office", "bureau_de_change"
        ]

        # Government-related amenities
        government_amenities = [
            "townhall", "courthouse", "police", "fire_station",
            "community_centre", "social_facility", "public_building",
            "government", "embassy", "prison", "ranger_station",
            "public_bath", "library", "courthouse", "archive"
        ]

        amenity_filter = "|".join(business_amenities + government_amenities)

        # All government tag values (very permissive)
        government_types = [
            "parliament", "legislative", "legislature", "ministry",
            "administrative", "regional", "local", "national",
            "government", "public_service", "tax", "social_security",
            "register_office", "customs", "bailiff", "prosecutor"
        ]

        government_filter = "|".join(government_types)

        # Calculate bounding box from polygon (works for both polygons and circles)
        lats = [lat for lng, lat in coords]
        lngs = [lng for lng, lat in coords]
        bbox = f"{min(lats)},{min(lngs)},{max(lats)},{max(lngs)}"  # south,west,north,east

        if circle_params:
            center_lat, center_lng, radius_m = circle_params
            print(f"Querying Overpass with bbox (circle detected: center=({center_lat:.6f}, {center_lng:.6f}), radius={radius_m}m): {bbox}")
        else:
            print(f"Querying Overpass with bbox: {bbox}")

        # Overpass QL query - optimized with essential entity types
        # Using 'out bb center' to get both bounding boxes and center coordinates
        # Note: order matters! 'out bb center' works, 'out center bb' doesn't return centers for relations
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
            elements = data.get('elements', [])
            print(f"Overpass returned {len(elements)} elements")

            # Debug: log any aeroway=aerodrome entities
            aerodromes = [e for e in elements if e.get('tags', {}).get('aeroway') == 'aerodrome']
            if aerodromes:
                print(f"  Found {len(aerodromes)} aerodrome(s):")
                for a in aerodromes:
                    print(f"    - {a.get('tags', {}).get('name', 'Unnamed')} (id={a.get('id')}, type={a.get('type')})")

            for element in elements:
                tags = element.get('tags', {})
                name = tags.get('name', 'Unnamed')

                # Prioritize specific tags for entity type classification
                # Priority: historic > tourism > military > aeroway > landuse > shop > amenity >
                # government > office > public_transport > railway > power > man_made > leisure > building
                historic_val = tags.get('historic')
                if historic_val:
                    # Add palace subtype if available
                    castle_type = tags.get('castle_type')
                    business_type = f"{historic_val}:{castle_type}" if castle_type else historic_val
                else:
                    # Check landuse for infrastructure types (port, industrial, military)
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

                # Extract contact information from OSM tags
                phone = tags.get('phone') or tags.get('contact:phone', '')
                website = tags.get('website') or tags.get('contact:website', '')
                email = tags.get('email') or tags.get('contact:email', '')

                # Get coordinates - for relations, Overpass returns center coordinates
                # in the 'center' object, for nodes/ways it's directly in lat/lon
                if 'lat' in element and 'lon' in element:
                    lat = element['lat']
                    lng = element['lon']
                elif 'center' in element:
                    lat = element['center']['lat']
                    lng = element['center']['lon']
                else:
                    print(f"  WARNING: No coordinates found for {name}, skipping")
                    continue

                # Filter: check if entity intersects with polygon
                # For entities with bounding box (large areas like airports), check intersection
                # For point entities, check if point is inside polygon
                if 'bounds' in element:
                    # Entity has bounding box - check if bbox intersects with polygon
                    bounds = element['bounds']
                    entity_bbox = box(
                        bounds['minlon'], bounds['minlat'],
                        bounds['maxlon'], bounds['maxlat']
                    )
                    if not polygon.intersects(entity_bbox):
                        if tags.get('aeroway') == 'aerodrome':
                            print(f"  DEBUG: Aerodrome {name} filtered out - bbox doesn't intersect")
                            print(f"    Entity bbox: {bounds}")
                            print(f"    Polygon bbox: {polygon.bounds}")
                        continue
                else:
                    # Point entity - check if center point is inside polygon
                    point = Point(lng, lat)
                    if not polygon.contains(point):
                        if tags.get('aeroway') == 'aerodrome':
                            print(f"  DEBUG: Aerodrome {name} filtered out - center not in polygon")
                            print(f"    Center: ({lng}, {lat})")
                        continue

                businesses.append(enrichment_pb2.Business(
                    name=name,
                    lat=lat,
                    lng=lng,
                    type=business_type,
                    address=address,
                    phone=phone,
                    website=website,
                    email=email
                ))

                # Log interesting entities (palaces, castles, historic sites, airports)
                if tags.get('aeroway') == 'aerodrome':
                    print(f"  ✓ Added aerodrome: {name} (center: {lat}, {lng})")
                elif any(tag in tags for tag in ['historic', 'tourism']) or tags.get('building') in ['palace', 'castle']:
                    print(f"  → {name} (type={business_type}, building={tags.get('building', 'N/A')}, historic={tags.get('historic', 'N/A')}, tourism={tags.get('tourism', 'N/A')})")

            return businesses, None  # Success, no error
        except httpx.TimeoutException as e:
            error_msg = "Overpass API timeout - try a smaller area or try again later"
            print(f"Timeout querying Overpass API: {e}")
            return [], error_msg
        except Exception as e:
            error_msg = f"Error querying Overpass API: {str(e)}"
            print(error_msg)
            return [], error_msg


def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    enrichment_pb2_grpc.add_EnrichmentServiceServicer_to_server(
        EnrichmentServicer(), server
    )
    server.add_insecure_port(f'[::]:{ settings.enrichment_port}')
    server.start()
    print(f"Enrichment service listening on port {settings.enrichment_port}")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()

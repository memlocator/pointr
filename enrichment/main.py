from concurrent import futures
import grpc
import enrichment_pb2
import enrichment_pb2_grpc
from shapely.geometry import Polygon
import math
import httpx


class EnrichmentServicer(enrichment_pb2_grpc.EnrichmentServiceServicer):
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
        businesses = self._get_businesses_from_overpass(coords)

        print(f"Enriched polygon: {area_km2:.2f} km², pop: {estimated_population}, {len(businesses)} businesses")

        return enrichment_pb2.EnrichmentResponse(
            area_km2=area_km2,
            estimated_population=estimated_population,
            region_type=region_type,
            nearby_features=[],
            businesses=businesses
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

    def _get_businesses_from_overpass(self, coords):
        """Query Overpass API for businesses in polygon"""
        # Format polygon coordinates for Overpass query
        poly_str = " ".join([f"{lat} {lng}" for lng, lat in coords])

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

        # Overpass QL query - very permissive to catch all businesses, government, and public buildings
        # Query nodes, ways, and relations to catch complex buildings
        query = f"""
        [out:json];
        (
          node["shop"](poly:"{poly_str}");
          way["shop"](poly:"{poly_str}");
          relation["shop"](poly:"{poly_str}");
          node["amenity"~"^({amenity_filter})$"](poly:"{poly_str}");
          way["amenity"~"^({amenity_filter})$"](poly:"{poly_str}");
          relation["amenity"~"^({amenity_filter})$"](poly:"{poly_str}");
          node["office"](poly:"{poly_str}");
          way["office"](poly:"{poly_str}");
          relation["office"](poly:"{poly_str}");
          node["building"="government"](poly:"{poly_str}");
          way["building"="government"](poly:"{poly_str}");
          relation["building"="government"](poly:"{poly_str}");
          node["building"="public"](poly:"{poly_str}");
          way["building"="public"](poly:"{poly_str}");
          relation["building"="public"](poly:"{poly_str}");
          node["government"](poly:"{poly_str}");
          way["government"](poly:"{poly_str}");
          relation["government"](poly:"{poly_str}");
          node["aeroway"~"^(aerodrome|terminal|heliport)$"](poly:"{poly_str}");
          way["aeroway"~"^(aerodrome|terminal|heliport)$"](poly:"{poly_str}");
          relation["aeroway"~"^(aerodrome|terminal|heliport)$"](poly:"{poly_str}");
        );
        out center;
        """

        try:
            response = httpx.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            businesses = []
            for element in data.get('elements', []):
                tags = element.get('tags', {})
                name = tags.get('name', 'Unnamed')

                # Prioritize specific tags: aeroway > shop > amenity > government > office > building
                business_type = (
                    tags.get('aeroway') or
                    tags.get('shop') or
                    tags.get('amenity') or
                    tags.get('government') or
                    tags.get('office') or
                    (tags.get('building') if tags.get('building') in ['government', 'public'] else None) or
                    'business'
                )
                address = tags.get('addr:street', '')

                # Extract contact information from OSM tags
                phone = tags.get('phone') or tags.get('contact:phone', '')
                website = tags.get('website') or tags.get('contact:website', '')
                email = tags.get('email') or tags.get('contact:email', '')

                businesses.append(enrichment_pb2.Business(
                    name=name,
                    lat=element.get('lat', 0),
                    lng=element.get('lon', 0),
                    type=business_type,
                    address=address,
                    phone=phone,
                    website=website,
                    email=email
                ))

            return businesses
        except Exception as e:
            print(f"Error querying Overpass API: {e}")
            return []


def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    enrichment_pb2_grpc.add_EnrichmentServiceServicer_to_server(
        EnrichmentServicer(), server
    )
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Enrichment service listening on port 50051")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()

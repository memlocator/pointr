from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import grpc
import geo_pb2
import geo_pb2_grpc
import recon_pb2
import recon_pb2_grpc
import httpx
import json
import asyncio
from config import settings

app = FastAPI(title=f"{settings.app_name} API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class Coordinate(BaseModel):
    lat: float
    lng: float

class PolygonRequest(BaseModel):
    coordinates: list[Coordinate]

class Business(BaseModel):
    name: str
    lat: float
    lng: float
    type: str
    address: str
    phone: str = ''
    website: str = ''
    email: str = ''
    source: str = 'osm'
    id: str = ''

class EnrichmentResponse(BaseModel):
    area_km2: float
    estimated_population: int
    region_type: str
    nearby_features: list[str]
    businesses: list[Business]
    error: str = ''

# Recon models
class ReconRequest(BaseModel):
    domains: list[str]
    silent_mode: bool = False

class DNSRecord(BaseModel):
    type: str
    value: str
    ttl: int

class SSLCertificate(BaseModel):
    issuer: str
    subject: str
    not_before: str
    not_after: str
    san_domains: list[str]

class SecurityHeaders(BaseModel):
    strict_transport_security: str = ''
    content_security_policy: str = ''
    x_frame_options: str = ''
    x_content_type_options: str = ''
    referrer_policy: str = ''
    permissions_policy: str = ''

class WhoisData(BaseModel):
    registrar: str = ''
    creation_date: str = ''
    expiration_date: str = ''
    name_servers: list[str] = []
    registrant_org: str = ''
    status: str = ''

class ASNInfo(BaseModel):
    asn: str = ''
    organization: str = ''
    ip_ranges: list[str] = []
    country: str = ''
    prefixes_v4: list[str] = []
    prefixes_v6: list[str] = []
    prefix_count_v4: int = 0
    prefix_count_v6: int = 0
    peers: list[str] = []
    upstreams: list[str] = []
    downstreams: list[str] = []
    peering_policy: str = ''
    network_type: str = ''
    peering_facilities: list[str] = []
    rir: str = ''
    abuse_contacts: list[str] = []
    bgp_prefix: str = ''

class DomainRecon(BaseModel):
    domain: str
    dns_records: list[DNSRecord] = []
    ssl_certificates: list[SSLCertificate] = []
    security_headers: SecurityHeaders = SecurityHeaders()
    whois: WhoisData = WhoisData()
    asn_info: ASNInfo = ASNInfo()
    subdomains: list[str] = []
    error: str = ''

class ReconResponse(BaseModel):
    results: list[DomainRecon]

# Nominatim models
class NominatimResult(BaseModel):
    place_id: int
    display_name: str
    lat: float
    lon: float
    type: str
    importance: float

class NominatimSearchResponse(BaseModel):
    results: list[NominatimResult]

# Custom geo data models
class CustomPOIRequest(BaseModel):
    name: str
    category: str
    lat: float
    lng: float
    tags: dict = {}

class CustomPOIResponse(BaseModel):
    id: str
    name: str
    category: str
    lat: float
    lng: float
    tags: dict = {}
    error: str = ''

class CustomAreaRequest(BaseModel):
    name: str
    description: str = ''
    coordinates: list[Coordinate]
    metadata: dict = {}

class CustomAreaResponse(BaseModel):
    id: str
    name: str
    description: str = ''
    coordinates: list[Coordinate] = []
    metadata: dict = {}
    error: str = ''

class UpdateCustomPOIRequest(BaseModel):
    name: str
    category: str

class UpdateCustomAreaRequest(BaseModel):
    name: str
    description: str = ''

# Routing models
class RouteRequest(BaseModel):
    start: Coordinate
    end: Coordinate

class RouteResponse(BaseModel):
    geometry: dict
    distance_meters: float
    duration_seconds: float
    error: str = ''

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.app_name} API"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint that tests all services"""
    health_status = {
        "status": "healthy",
        "services": {
            "backend": {"status": "healthy", "message": "Backend API operational"},
            "geo": {"status": "unknown", "message": "Not checked"},
            "recon": {"status": "unknown", "message": "Not checked"}
        }
    }

    # Check geo service
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.Health(
                geo_pb2.HealthRequest(),
                timeout=2.0
            )
            health_status["services"]["geo"] = {
                "status": response.status,
                "message": response.message
            }
    except grpc.RpcError as e:
        health_status["services"]["geo"] = {
            "status": "unhealthy",
            "message": f"gRPC error: {e.code().name}"
        }
        health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["geo"] = {
            "status": "unhealthy",
            "message": f"Connection failed: {str(e)}"
        }
        health_status["status"] = "degraded"

    # Check recon service
    try:
        with grpc.insecure_channel(f'{settings.recon_host}:{settings.recon_port}') as channel:
            stub = recon_pb2_grpc.ReconServiceStub(channel)
            # Call health check endpoint (doesn't hit external services)
            response = stub.Health(
                recon_pb2.HealthRequest(),
                timeout=2.0
            )
            health_status["services"]["recon"] = {
                "status": response.status,
                "message": response.message
            }
    except grpc.RpcError as e:
        health_status["services"]["recon"] = {
            "status": "unhealthy",
            "message": f"gRPC error: {e.code().name}"
        }
        health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["recon"] = {
            "status": "unhealthy",
            "message": f"Connection failed: {str(e)}"
        }
        health_status["status"] = "degraded"

    return health_status

@app.post("/api/enrich", response_model=EnrichmentResponse)
@app.post("/api/map/enrich", response_model=EnrichmentResponse)
async def enrich_polygon(request: PolygonRequest):
    """Call the geo service via gRPC to enrich polygon data"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)

            proto_coords = [
                geo_pb2.Coordinate(lat=coord.lat, lng=coord.lng)
                for coord in request.coordinates
            ]

            response = stub.EnrichPolygon(
                geo_pb2.PolygonRequest(coordinates=proto_coords)
            )

            businesses = [
                Business(
                    name=b.name,
                    lat=b.lat,
                    lng=b.lng,
                    type=b.type,
                    address=b.address,
                    phone=b.phone,
                    website=b.website,
                    email=b.email,
                    source=b.source,
                    id=b.id
                )
                for b in response.businesses
            ]

            return EnrichmentResponse(
                area_km2=response.area_km2,
                estimated_population=response.estimated_population,
                region_type=response.region_type,
                nearby_features=list(response.nearby_features),
                businesses=businesses,
                error=response.error
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")

@app.post("/api/recon", response_model=ReconResponse)
async def run_recon(request: ReconRequest):
    """Call the recon service via gRPC to perform network reconnaissance"""
    try:
        # Connect to recon service
        with grpc.insecure_channel(f'{settings.recon_host}:{settings.recon_port}') as channel:
            stub = recon_pb2_grpc.ReconServiceStub(channel)

            # Make RPC call
            response = stub.RunRecon(
                recon_pb2.ReconRequest(domains=request.domains, silent_mode=request.silent_mode)
            )

            # Convert proto response to pydantic
            results = []
            for domain_recon in response.results:
                # Convert DNS records
                dns_records = [
                    DNSRecord(type=r.type, value=r.value, ttl=r.ttl)
                    for r in domain_recon.dns_records
                ]

                # Convert SSL certificates
                ssl_certificates = [
                    SSLCertificate(
                        issuer=cert.issuer,
                        subject=cert.subject,
                        not_before=cert.not_before,
                        not_after=cert.not_after,
                        san_domains=list(cert.san_domains)
                    )
                    for cert in domain_recon.ssl_certificates
                ]

                # Convert security headers
                sec_headers = SecurityHeaders(
                    strict_transport_security=domain_recon.security_headers.strict_transport_security,
                    content_security_policy=domain_recon.security_headers.content_security_policy,
                    x_frame_options=domain_recon.security_headers.x_frame_options,
                    x_content_type_options=domain_recon.security_headers.x_content_type_options,
                    referrer_policy=domain_recon.security_headers.referrer_policy,
                    permissions_policy=domain_recon.security_headers.permissions_policy
                )

                # Convert WHOIS data
                whois = WhoisData(
                    registrar=domain_recon.whois.registrar,
                    creation_date=domain_recon.whois.creation_date,
                    expiration_date=domain_recon.whois.expiration_date,
                    name_servers=list(domain_recon.whois.name_servers),
                    registrant_org=domain_recon.whois.registrant_org,
                    status=domain_recon.whois.status
                )

                # Convert ASN info
                asn = ASNInfo(
                    asn=domain_recon.asn_info.asn,
                    organization=domain_recon.asn_info.organization,
                    ip_ranges=list(domain_recon.asn_info.ip_ranges),
                    country=domain_recon.asn_info.country,
                    prefixes_v4=list(domain_recon.asn_info.prefixes_v4),
                    prefixes_v6=list(domain_recon.asn_info.prefixes_v6),
                    prefix_count_v4=domain_recon.asn_info.prefix_count_v4,
                    prefix_count_v6=domain_recon.asn_info.prefix_count_v6,
                    peers=list(domain_recon.asn_info.peers),
                    upstreams=list(domain_recon.asn_info.upstreams),
                    downstreams=list(domain_recon.asn_info.downstreams),
                    peering_policy=domain_recon.asn_info.peering_policy,
                    network_type=domain_recon.asn_info.network_type,
                    peering_facilities=list(domain_recon.asn_info.peering_facilities),
                    rir=domain_recon.asn_info.rir,
                    abuse_contacts=list(domain_recon.asn_info.abuse_contacts),
                    bgp_prefix=domain_recon.asn_info.bgp_prefix
                )

                results.append(DomainRecon(
                    domain=domain_recon.domain,
                    dns_records=dns_records,
                    ssl_certificates=ssl_certificates,
                    security_headers=sec_headers,
                    whois=whois,
                    asn_info=asn,
                    subdomains=list(domain_recon.subdomains),
                    error=domain_recon.error
                ))

            return ReconResponse(results=results)

    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Recon service error: {e.details()}")

@app.post("/api/recon/stream")
async def run_recon_stream(request: ReconRequest):
    """Stream recon progress and results using Server-Sent Events"""
    async def event_generator():
        try:
            # Connect to recon service
            with grpc.insecure_channel(f'{settings.recon_host}:{settings.recon_port}') as channel:
                stub = recon_pb2_grpc.ReconServiceStub(channel)

                # Call streaming RPC
                for update in stub.RunReconStream(recon_pb2.ReconRequest(domains=request.domains, silent_mode=request.silent_mode)):
                    # Convert update type
                    update_type = "log" if update.type == recon_pb2.ReconUpdate.LOG else \
                                  "result" if update.type == recon_pb2.ReconUpdate.RESULT else \
                                  "complete"

                    # Prepare event data
                    event_data = {
                        "type": update_type,
                        "message": update.message
                    }

                    # Include result if it's a RESULT update
                    if update.type == recon_pb2.ReconUpdate.RESULT and update.HasField('result'):
                        domain_recon = update.result

                        # Convert proto result to dict (similar to non-streaming endpoint)
                        dns_records = [
                            {"type": r.type, "value": r.value, "ttl": r.ttl}
                            for r in domain_recon.dns_records
                        ]

                        ssl_certificates = [
                            {
                                "issuer": cert.issuer,
                                "subject": cert.subject,
                                "not_before": cert.not_before,
                                "not_after": cert.not_after,
                                "san_domains": list(cert.san_domains)
                            }
                            for cert in domain_recon.ssl_certificates
                        ]

                        event_data["result"] = {
                            "domain": domain_recon.domain,
                            "dns_records": dns_records,
                            "ssl_certificates": ssl_certificates,
                            "security_headers": {
                                "strict_transport_security": domain_recon.security_headers.strict_transport_security,
                                "content_security_policy": domain_recon.security_headers.content_security_policy,
                                "x_frame_options": domain_recon.security_headers.x_frame_options,
                                "x_content_type_options": domain_recon.security_headers.x_content_type_options,
                                "referrer_policy": domain_recon.security_headers.referrer_policy,
                                "permissions_policy": domain_recon.security_headers.permissions_policy
                            },
                            "whois": {
                                "registrar": domain_recon.whois.registrar,
                                "creation_date": domain_recon.whois.creation_date,
                                "expiration_date": domain_recon.whois.expiration_date,
                                "name_servers": list(domain_recon.whois.name_servers),
                                "registrant_org": domain_recon.whois.registrant_org,
                                "status": domain_recon.whois.status
                            },
                            "asn_info": {
                                "asn": domain_recon.asn_info.asn,
                                "organization": domain_recon.asn_info.organization,
                                "ip_ranges": list(domain_recon.asn_info.ip_ranges),
                                "country": domain_recon.asn_info.country,
                                "prefixes_v4": list(domain_recon.asn_info.prefixes_v4),
                                "prefixes_v6": list(domain_recon.asn_info.prefixes_v6),
                                "prefix_count_v4": domain_recon.asn_info.prefix_count_v4,
                                "prefix_count_v6": domain_recon.asn_info.prefix_count_v6,
                                "peers": list(domain_recon.asn_info.peers),
                                "upstreams": list(domain_recon.asn_info.upstreams),
                                "downstreams": list(domain_recon.asn_info.downstreams),
                                "peering_policy": domain_recon.asn_info.peering_policy,
                                "network_type": domain_recon.asn_info.network_type,
                                "peering_facilities": list(domain_recon.asn_info.peering_facilities),
                                "rir": domain_recon.asn_info.rir,
                                "abuse_contacts": list(domain_recon.asn_info.abuse_contacts),
                                "bgp_prefix": domain_recon.asn_info.bgp_prefix
                            },
                            "subdomains": list(domain_recon.subdomains),
                            "error": domain_recon.error
                        }

                    # Send Server-Sent Event
                    yield f"data: {json.dumps(event_data)}\n\n"

                    # Small delay to ensure events are sent
                    await asyncio.sleep(0.01)

        except grpc.RpcError as e:
            error_event = {
                "type": "error",
                "message": f"Recon service error: {e.details()}"
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/pois", response_model=CustomPOIResponse)
async def add_custom_poi(request: CustomPOIRequest):
    """Add a custom POI"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.AddCustomPOI(geo_pb2.AddCustomPOIRequest(
                name=request.name,
                category=request.category,
                lat=request.lat,
                lng=request.lng,
                tags_json=json.dumps(request.tags)
            ))
            if response.error:
                raise HTTPException(status_code=400, detail=response.error)
            return CustomPOIResponse(
                id=response.id,
                name=response.name,
                category=response.category,
                lat=response.lat,
                lng=response.lng,
                tags=json.loads(response.tags_json) if response.tags_json else {}
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.get("/api/pois", response_model=list[CustomPOIResponse])
async def list_custom_pois(
    min_lat: float | None = None,
    min_lng: float | None = None,
    max_lat: float | None = None,
    max_lng: float | None = None
):
    """List custom POIs, optionally filtered by bounding box"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.ListCustomPOIs(geo_pb2.ListCustomPOIsRequest(
                min_lat=min_lat or 0.0,
                min_lng=min_lng or 0.0,
                max_lat=max_lat or 0.0,
                max_lng=max_lng or 0.0
            ))
            return [
                CustomPOIResponse(
                    id=p.id, name=p.name, category=p.category,
                    lat=p.lat, lng=p.lng,
                    tags=json.loads(p.tags_json) if p.tags_json else {}
                )
                for p in response.pois
            ]
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.patch("/api/pois/{poi_id}", response_model=CustomPOIResponse)
async def update_custom_poi(poi_id: str, request: UpdateCustomPOIRequest):
    """Rename/recategorize a custom POI"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.UpdateCustomPOI(geo_pb2.UpdateCustomPOIRequest(
                id=poi_id,
                name=request.name,
                category=request.category
            ))
            if response.error:
                raise HTTPException(status_code=404, detail=response.error)
            return CustomPOIResponse(
                id=response.id,
                name=response.name,
                category=response.category,
                lat=response.lat,
                lng=response.lng,
                tags=json.loads(response.tags_json) if response.tags_json else {}
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.delete("/api/pois/{poi_id}")
async def delete_custom_poi(poi_id: str):
    """Delete a custom POI"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.DeleteCustomPOI(geo_pb2.DeleteCustomPOIRequest(id=poi_id))
            if not response.success:
                raise HTTPException(status_code=404, detail=response.error)
            return {"success": True}
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.post("/api/areas", response_model=CustomAreaResponse)
async def add_custom_area(request: CustomAreaRequest):
    """Add a custom annotated area"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            proto_coords = [geo_pb2.Coordinate(lat=c.lat, lng=c.lng) for c in request.coordinates]
            response = stub.AddCustomArea(geo_pb2.AddCustomAreaRequest(
                name=request.name,
                description=request.description,
                coordinates=proto_coords,
                metadata_json=json.dumps(request.metadata)
            ))
            if response.error:
                raise HTTPException(status_code=400, detail=response.error)
            return CustomAreaResponse(
                id=response.id,
                name=response.name,
                description=response.description,
                coordinates=[Coordinate(lat=c.lat, lng=c.lng) for c in response.coordinates],
                metadata=json.loads(response.metadata_json) if response.metadata_json else {}
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.get("/api/areas", response_model=list[CustomAreaResponse])
async def list_custom_areas():
    """List all custom areas"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.ListCustomAreas(geo_pb2.ListCustomAreasRequest())
            return [
                CustomAreaResponse(
                    id=a.id, name=a.name, description=a.description,
                    coordinates=[Coordinate(lat=c.lat, lng=c.lng) for c in a.coordinates],
                    metadata=json.loads(a.metadata_json) if a.metadata_json else {}
                )
                for a in response.areas
            ]
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.patch("/api/areas/{area_id}", response_model=CustomAreaResponse)
async def update_custom_area(area_id: str, request: UpdateCustomAreaRequest):
    """Rename/update a custom area"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.UpdateCustomArea(geo_pb2.UpdateCustomAreaRequest(
                id=area_id,
                name=request.name,
                description=request.description
            ))
            if response.error:
                raise HTTPException(status_code=404, detail=response.error)
            return CustomAreaResponse(
                id=response.id,
                name=response.name,
                description=response.description,
                coordinates=[Coordinate(lat=c.lat, lng=c.lng) for c in response.coordinates],
                metadata=json.loads(response.metadata_json) if response.metadata_json else {}
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.delete("/api/areas/{area_id}")
async def delete_custom_area(area_id: str):
    """Delete a custom area"""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.DeleteCustomArea(geo_pb2.DeleteCustomAreaRequest(id=area_id))
            if not response.success:
                raise HTTPException(status_code=404, detail=response.error)
            return {"success": True}
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.get("/api/search", response_model=NominatimSearchResponse)
async def search_location(q: str):
    """Search for locations using Nominatim (OpenStreetMap geocoding)"""
    if not q or len(q.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.nominatim_api_url}/search",
                params={
                    "q": q,
                    "format": "json",
                    "limit": 5,
                    "addressdetails": 1
                },
                headers={
                    "User-Agent": settings.user_agent
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            results = [
                NominatimResult(
                    place_id=item["place_id"],
                    display_name=item["display_name"],
                    lat=float(item["lat"]),
                    lon=float(item["lon"]),
                    type=item.get("type", "unknown"),
                    importance=item.get("importance", 0.0)
                )
                for item in data
            ]

            return NominatimSearchResponse(results=results)

    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Nominatim service error: {str(e)}")

@app.post("/api/route", response_model=RouteResponse)
async def get_route(request: RouteRequest):
    """Get driving route between two points using OSRM"""
    try:
        # OSRM expects coordinates as "lng,lat;lng,lat"
        coords = f"{request.start.lng},{request.start.lat};{request.end.lng},{request.end.lat}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.osrm_api_url}/route/v1/driving/{coords}",
                params={
                    "overview": "full",
                    "geometries": "geojson"
                },
                headers={
                    "User-Agent": settings.user_agent
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            if data.get('code') != 'Ok':
                return RouteResponse(
                    geometry={},
                    distance_meters=0,
                    duration_seconds=0,
                    error=f"OSRM error: {data.get('message', 'Unknown error')}"
                )

            route = data['routes'][0]

            return RouteResponse(
                geometry=route['geometry'],
                distance_meters=route['distance'],
                duration_seconds=route['duration'],
                error=''
            )

    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"OSRM service error: {str(e)}")

def main():
    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port, reload=True)

if __name__ == "__main__":
    main()

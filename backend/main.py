from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
import logging
import time
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tags_metadata = [
    {
        "name": "system",
        "description": "Health checks and system status across all services.",
    },
    {
        "name": "geo",
        "description": "Spatial enrichment via Overpass API and geocoding via Nominatim.",
    },
    {
        "name": "custom-pois",
        "description": "CRUD for custom points of interest stored in PostGIS.",
    },
    {
        "name": "custom-areas",
        "description": "CRUD for custom annotated polygon areas stored in PostGIS.",
    },
    {
        "name": "datasources",
        "description": "Upload and manage user-provided GeoJSON datasources (stored in PostGIS).",
    },
    {
        "name": "recon",
        "description": "Network reconnaissance: DNS records, SSL certificates, WHOIS, ASN info.",
    },
    {
        "name": "routing",
        "description": "Driving route calculation via OSRM.",
    },
]

app = FastAPI(
    title=f"{settings.app_name} API",
    description=(
        "Geospatial intelligence platform. "
        "Enrich map polygons with OSM data, manage custom POIs and areas, "
        "run domain reconnaissance, and calculate routes."
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_USER_HEADER = "X-User"

@app.middleware("http")
async def auth_and_log(request: Request, call_next):
    start = time.perf_counter()
    user = request.headers.get(AUTH_USER_HEADER)

    if request.method != "OPTIONS" and not user:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            f'REQ user="-" method={request.method} path="{request.url.path}" '
            f'status=401 success=false duration_ms={duration_ms}'
        )
        return JSONResponse(status_code=401, content={"detail": f"Missing {AUTH_USER_HEADER} header"})

    if user:
        request.state.user = user

    try:
        response = await call_next(request)
        status = response.status_code
        success = status < 400
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            f'REQ user="{user or "-"}" method={request.method} path="{request.url.path}" '
            f'status={status} success={str(success).lower()} duration_ms={duration_ms}'
        )
        return response
    except Exception:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.exception(
            f'REQ user="{user or "-"}" method={request.method} path="{request.url.path}" '
            f'status=500 success=false duration_ms={duration_ms}'
        )
        raise

# Pydantic models for API
class Coordinate(BaseModel):
    lat: float
    lng: float

    model_config = {
        "json_schema_extra": {
            "example": {"lat": 51.5074, "lng": -0.1278}
        }
    }

class PolygonRequest(BaseModel):
    coordinates: list[Coordinate]
    sources: list[str] = []

    model_config = {
        "json_schema_extra": {
            "example": {
                "coordinates": [
                    {"lat": 51.505, "lng": -0.092},
                    {"lat": 51.510, "lng": -0.092},
                    {"lat": 51.510, "lng": -0.080},
                    {"lat": 51.505, "lng": -0.080},
                    {"lat": 51.505, "lng": -0.092},
                ]
            }
        }
    }

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
    description: str = ''

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

    model_config = {
        "json_schema_extra": {
            "example": {
                "domains": ["example.com", "subdomain.example.com"],
                "silent_mode": False,
            }
        }
    }

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
    description: str = ''
    phone: str = ''
    website: str = ''
    lat: float
    lng: float
    tags: dict = {}

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "HQ Office",
                "category": "Offices",
                "description": "Main headquarters building.",
                "phone": "+1 555 0100",
                "website": "https://example.com",
                "lat": 51.5074,
                "lng": -0.1278,
                "tags": {"floor": "3", "access": "private"},
            }
        }
    }

class CustomPOIResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str = ''
    phone: str = ''
    website: str = ''
    lat: float
    lng: float
    tags: dict = {}
    error: str = ''

class CustomAreaRequest(BaseModel):
    name: str
    description: str = ''
    coordinates: list[Coordinate]
    metadata: dict = {}

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Industrial Zone A",
                "description": "Northern industrial district boundary.",
                "coordinates": [
                    {"lat": 51.505, "lng": -0.092},
                    {"lat": 51.510, "lng": -0.092},
                    {"lat": 51.510, "lng": -0.080},
                    {"lat": 51.505, "lng": -0.080},
                    {"lat": 51.505, "lng": -0.092},
                ],
                "metadata": {"zone_type": "industrial", "priority": "high"},
            }
        }
    }

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
    description: str = ''
    phone: str = ''
    website: str = ''

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "HQ Office (Renamed)",
                "category": "Offices",
                "description": "Updated description.",
                "phone": "+1 555 0100",
                "website": "https://example.com",
            }
        }
    }

class UpdateCustomAreaRequest(BaseModel):
    name: str
    description: str = ''

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Industrial Zone A (Updated)",
                "description": "Revised boundary notes.",
            }
        }
    }

# Datasource models (uploaded GeoJSON)
class UploadSourceRequest(BaseModel):
    name: str
    geojson: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "My Custom Dataset",
                "geojson": '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[18.0686,59.3293]},"properties":{"name":"Test POI","category":"Food & Dining"}}]}'
            }
        }
    }

class UploadSourceResponse(BaseModel):
    name: str
    feature_count: int
    error: str = ''

class UploadedSource(BaseModel):
    name: str
    feature_count: int

# Routing models
class RouteRequest(BaseModel):
    waypoints: list[Coordinate]

    model_config = {
        "json_schema_extra": {
            "example": {
                "waypoints": [
                    {"lat": 51.5074, "lng": -0.1278},
                    {"lat": 51.5115, "lng": -0.1200},
                    {"lat": 51.5155, "lng": -0.0922},
                ]
            }
        }
    }

class RouteResponse(BaseModel):
    geometry: dict
    distance_meters: float
    duration_seconds: float
    error: str = ''

class RouteStop(BaseModel):
    lat: float | None = None
    lng: float | None = None
    name: str = ''
    description: str = ''

class SaveRouteRequest(BaseModel):
    name: str
    route_type: str = 'road'
    stops: list[RouteStop]

class SavedRouteResponse(BaseModel):
    id: str
    name: str
    route_type: str
    stops: list[RouteStop]
    created_at: str

@app.get("/", tags=["system"], include_in_schema=False)
async def root():
    return {"message": f"Welcome to {settings.app_name} API"}

@app.get("/api/health", tags=["system"], summary="Service health")
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

    # Probe additional PostGIS datasources via TCP
    import socket
    from urllib.parse import urlparse as _urlparse

    datasources = [
        {
            "name": "Primary (PostGIS)",
            "status": "online" if health_status["services"]["geo"]["status"] == "healthy" else "error",
            "message": health_status["services"]["geo"]["message"]
        }
    ]

    try:
        additional = json.loads(settings.geo_additional_dbs)
    except Exception:
        additional = []

    for db in additional:
        try:
            parsed = _urlparse(db.get("url", ""))
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            sock = socket.create_connection((host, port), timeout=2.0)
            sock.close()
            datasources.append({"name": db["name"], "status": "online", "message": "reachable"})
        except Exception as e:
            datasources.append({"name": db.get("name", "unknown"), "status": "error", "message": str(e)})

    # Add uploaded sources (in-memory)
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.ListUploadedSources(geo_pb2.ListUploadedSourcesRequest())
            for src in response.sources:
                datasources.append({
                    "name": src.name,
                    "status": "online",
                    "message": f"{src.feature_count} features (uploaded)"
                })
    except Exception as e:
        pass  # Silently skip if geo service unavailable

    health_status["datasources"] = datasources

    return health_status

@app.post("/api/enrich", response_model=EnrichmentResponse, tags=["geo"], summary="Enrich polygon with OSM data")
@app.post("/api/map/enrich", response_model=EnrichmentResponse, tags=["geo"], include_in_schema=False)
async def enrich_polygon(request: PolygonRequest):
    """
    Query Overpass API and PostGIS for all businesses/POIs inside the given polygon.

    Returns area statistics (km², estimated population, region type) and a
    blended list of OSM and custom POIs with `source` tagged as `"osm"` or `"custom"`.
    """
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)

            proto_coords = [
                geo_pb2.Coordinate(lat=coord.lat, lng=coord.lng)
                for coord in request.coordinates
            ]

            response = stub.EnrichPolygon(
                geo_pb2.PolygonRequest(coordinates=proto_coords, sources=request.sources)
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
                    id=b.id,
                    description=b.description
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

@app.post("/api/recon", response_model=ReconResponse, tags=["recon"], summary="Run domain reconnaissance")
async def run_recon(request: ReconRequest):
    """
    Perform full reconnaissance on one or more domains.

    Collects DNS records, SSL certificates, security headers, WHOIS registration
    data, ASN/BGP info, and subdomain enumeration. Set `silent_mode: true` to
    suppress passive checks that generate traffic.
    """
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

@app.post("/api/recon/stream", tags=["recon"], summary="Stream recon progress (SSE)")
async def run_recon_stream(request: ReconRequest):
    """
    Same as `/api/recon` but streams progress via **Server-Sent Events**.

    Each event is a JSON object with `type` (`"log"`, `"result"`, `"complete"`, `"error"`)
    and an optional `result` payload when `type == "result"`.
    """
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

@app.post("/api/pois", response_model=CustomPOIResponse, tags=["custom-pois"], summary="Create custom POI")
async def add_custom_poi(request: CustomPOIRequest):
    """Create a new custom point of interest. Returns the created POI with its assigned UUID."""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.AddCustomPOI(geo_pb2.AddCustomPOIRequest(
                name=request.name,
                category=request.category,
                description=request.description,
                phone=request.phone,
                website=request.website,
                lat=request.lat,
                lng=request.lng,
                tags_json=json.dumps(request.tags)
            ))
            if response.error:
                logger.error(f"[POI CREATE] gRPC error: {response.error}")
                raise HTTPException(status_code=400, detail=response.error)
            result = CustomPOIResponse(
                id=response.id,
                name=response.name,
                category=response.category,
                description=response.description,
                phone=response.phone,
                website=response.website,
                lat=response.lat,
                lng=response.lng,
                tags=json.loads(response.tags_json) if response.tags_json else {}
            )
            return result
    except grpc.RpcError as e:
        logger.error(f"[POI CREATE] gRPC exception: {e.code()} {e.details()}")
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.get("/api/pois", response_model=list[CustomPOIResponse], tags=["custom-pois"], summary="List custom POIs")
async def list_custom_pois(
    min_lat: float | None = None,
    min_lng: float | None = None,
    max_lat: float | None = None,
    max_lng: float | None = None
):
    """
    List all custom POIs. Optionally filter by bounding box by providing all four
    `min_lat`, `min_lng`, `max_lat`, `max_lng` query parameters.
    """
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
                    description=p.description, phone=p.phone, website=p.website,
                    lat=p.lat, lng=p.lng,
                    tags=json.loads(p.tags_json) if p.tags_json else {}
                )
                for p in response.pois
            ]
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.patch("/api/pois/{poi_id}", response_model=CustomPOIResponse, tags=["custom-pois"], summary="Update custom POI")
async def update_custom_poi(poi_id: str, request: UpdateCustomPOIRequest):
    """Update the name, category, or description of an existing custom POI."""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.UpdateCustomPOI(geo_pb2.UpdateCustomPOIRequest(
                id=poi_id,
                name=request.name,
                category=request.category,
                description=request.description,
                phone=request.phone,
                website=request.website
            ))
            if response.error:
                raise HTTPException(status_code=404, detail=response.error)
            return CustomPOIResponse(
                id=response.id,
                name=response.name,
                category=response.category,
                description=response.description,
                phone=response.phone,
                website=response.website,
                lat=response.lat,
                lng=response.lng,
                tags=json.loads(response.tags_json) if response.tags_json else {}
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.delete("/api/pois/{poi_id}", tags=["custom-pois"], summary="Delete custom POI")
async def delete_custom_poi(poi_id: str):
    """Permanently delete a custom POI by its UUID."""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.DeleteCustomPOI(geo_pb2.DeleteCustomPOIRequest(id=poi_id))
            if not response.success:
                raise HTTPException(status_code=404, detail=response.error)
            return {"success": True}
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.post("/api/datasources", response_model=UploadSourceResponse, tags=["datasources"], summary="Upload GeoJSON datasource")
async def upload_datasource(request: UploadSourceRequest):
    """
    Upload a GeoJSON FeatureCollection as a custom datasource (stored in PostGIS).

    Required GeoJSON properties per feature: name (string)
    Optional properties: category, description, phone, website

    Future: add authentication check before upload
    """
    # TODO: check authentication when auth is implemented
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.UploadSource(geo_pb2.UploadSourceRequest(
                name=request.name,
                geojson=request.geojson
            ))
            if response.error:
                raise HTTPException(status_code=400, detail=response.error)
            return UploadSourceResponse(
                name=response.name,
                feature_count=response.feature_count
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.get("/api/datasources", response_model=list[UploadedSource], tags=["datasources"], summary="List uploaded datasources")
async def list_datasources():
    """
    List all uploaded datasources currently stored in PostGIS.

    Future: add authentication check to filter by user
    """
    # TODO: check authentication when auth is implemented
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.ListUploadedSources(geo_pb2.ListUploadedSourcesRequest())
            return [
                UploadedSource(name=src.name, feature_count=src.feature_count)
                for src in response.sources
            ]
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.delete("/api/datasources/{name}", tags=["datasources"], summary="Delete uploaded datasource")
async def delete_datasource(name: str):
    """
    Delete an uploaded datasource from PostGIS.

    Future: add authentication check to verify ownership
    """
    # TODO: check authentication when auth is implemented
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.DeleteUploadedSource(geo_pb2.DeleteUploadedSourceRequest(name=name))
            if not response.success:
                raise HTTPException(status_code=404, detail=response.error)
            return {"success": True}
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.post("/api/areas", response_model=CustomAreaResponse, tags=["custom-areas"], summary="Create custom area")
async def add_custom_area(request: CustomAreaRequest):
    """Create a new custom polygon area. The polygon is stored in PostGIS and returned with its UUID."""
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


@app.get("/api/areas", response_model=list[CustomAreaResponse], tags=["custom-areas"], summary="List custom areas")
async def list_custom_areas():
    """List all custom polygon areas with their coordinate rings and metadata."""
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

@app.post("/api/areas/intersect", response_model=list[CustomAreaResponse], tags=["custom-areas"], summary="List custom areas intersecting polygon")
async def list_intersecting_custom_areas(request: PolygonRequest):
    """Return only custom areas that intersect the provided polygon."""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)

            proto_coords = [
                geo_pb2.Coordinate(lat=coord.lat, lng=coord.lng)
                for coord in request.coordinates
            ]

            response = stub.ListIntersectingAreas(
                geo_pb2.PolygonRequest(coordinates=proto_coords, sources=request.sources)
            )

            if response.error:
                raise HTTPException(status_code=500, detail=response.error)

            return [
                CustomAreaResponse(
                    id=a.id,
                    name=a.name,
                    description=a.description,
                    coordinates=[{"lat": c.lat, "lng": c.lng} for c in a.coordinates],
                    metadata_json=a.metadata_json,
                    error=a.error,
                )
                for a in response.areas
            ]
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.patch("/api/areas/{area_id}", response_model=CustomAreaResponse, tags=["custom-areas"], summary="Update custom area")
async def update_custom_area(area_id: str, request: UpdateCustomAreaRequest):
    """Update the name or description of an existing custom area."""
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


@app.delete("/api/areas/{area_id}", tags=["custom-areas"], summary="Delete custom area")
async def delete_custom_area(area_id: str):
    """Permanently delete a custom area by its UUID."""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.DeleteCustomArea(geo_pb2.DeleteCustomAreaRequest(id=area_id))
            if not response.success:
                raise HTTPException(status_code=404, detail=response.error)
            return {"success": True}
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.get("/api/search", response_model=NominatimSearchResponse, tags=["geo"], summary="Geocode location")
async def search_location(q: str):
    """
    Forward geocoding via Nominatim (OpenStreetMap). Returns up to 5 candidate
    locations with coordinates, display name, and importance score.
    Query must be at least 3 characters.
    """
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

@app.post("/api/route", response_model=RouteResponse, tags=["routing"], summary="Calculate driving route")
async def get_route(request: RouteRequest):
    """
    Calculate the fastest driving route through two or more waypoints using OSRM.

    Returns a GeoJSON geometry, total distance in metres, and duration in seconds.
    Requires at least 2 waypoints.
    """
    if len(request.waypoints) < 2:
        raise HTTPException(status_code=400, detail="At least 2 waypoints required")
    try:
        # OSRM expects coordinates as "lng,lat;lng,lat;..."
        coords = ";".join(f"{w.lng},{w.lat}" for w in request.waypoints)

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


@app.post("/api/routes/saved", response_model=SavedRouteResponse, tags=["routing"], summary="Save route")
async def save_route(request: SaveRouteRequest):
    """Save a named route with stops to the database."""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.AddRoute(geo_pb2.AddRouteRequest(
                name=request.name,
                route_type=request.route_type,
                stops_json=json.dumps([s.model_dump() for s in request.stops])
            ))
            if response.error:
                raise HTTPException(status_code=400, detail=response.error)
            return SavedRouteResponse(
                id=response.id, name=response.name, route_type=response.route_type,
                stops=[RouteStop(**s) for s in json.loads(response.stops_json)],
                created_at=response.created_at
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.get("/api/routes/saved", response_model=list[SavedRouteResponse], tags=["routing"], summary="List saved routes")
async def list_saved_routes():
    """List all saved routes ordered by creation date descending."""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.ListRoutes(geo_pb2.ListRoutesRequest())
            if response.error:
                raise HTTPException(status_code=500, detail=response.error)
            return [
                SavedRouteResponse(
                    id=r.id, name=r.name, route_type=r.route_type,
                    stops=[RouteStop(**s) for s in json.loads(r.stops_json)],
                    created_at=r.created_at
                ) for r in response.routes
            ]
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


@app.delete("/api/routes/saved/{route_id}", tags=["routing"], summary="Delete saved route")
async def delete_saved_route(route_id: str):
    """Delete a saved route by ID."""
    try:
        with grpc.insecure_channel(f'{settings.geo_host}:{settings.geo_port}') as channel:
            stub = geo_pb2_grpc.GeoDataServiceStub(channel)
            response = stub.DeleteRoute(geo_pb2.DeleteRouteRequest(id=route_id))
            if not response.success:
                raise HTTPException(status_code=400, detail=response.error)
            return {"success": True}
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Geo service error: {e.details()}")


def main():
    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port, reload=True)

if __name__ == "__main__":
    main()

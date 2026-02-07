from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import grpc
import enrichment_pb2
import enrichment_pb2_grpc
import recon_pb2
import recon_pb2_grpc
import httpx
import json
import asyncio
from config import settings

app = FastAPI(title="Pointr API")

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

class EnrichmentResponse(BaseModel):
    area_km2: float
    estimated_population: int
    region_type: str
    nearby_features: list[str]
    businesses: list[Business]

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

@app.get("/")
async def root():
    return {"message": "Welcome to Pointr API"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/enrich", response_model=EnrichmentResponse)
@app.post("/api/map/enrich", response_model=EnrichmentResponse)
async def enrich_polygon(request: PolygonRequest):
    """Call the enrichment service via gRPC to enrich polygon data"""
    try:
        # Connect to enrichment service
        with grpc.insecure_channel(f'{settings.enrichment_host}:{settings.enrichment_port}') as channel:
            stub = enrichment_pb2_grpc.EnrichmentServiceStub(channel)

            # Convert coordinates to proto format
            proto_coords = [
                enrichment_pb2.Coordinate(lat=coord.lat, lng=coord.lng)
                for coord in request.coordinates
            ]

            # Make RPC call
            response = stub.EnrichPolygon(
                enrichment_pb2.PolygonRequest(coordinates=proto_coords)
            )

            # Convert businesses from proto to pydantic
            businesses = [
                Business(
                    name=b.name,
                    lat=b.lat,
                    lng=b.lng,
                    type=b.type,
                    address=b.address,
                    phone=b.phone,
                    website=b.website,
                    email=b.email
                )
                for b in response.businesses
            ]

            return EnrichmentResponse(
                area_km2=response.area_km2,
                estimated_population=response.estimated_population,
                region_type=response.region_type,
                nearby_features=list(response.nearby_features),
                businesses=businesses
            )
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"Enrichment service error: {e.details()}")

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
                    country=domain_recon.asn_info.country
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
                                "country": domain_recon.asn_info.country
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

def main():
    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port, reload=True)

if __name__ == "__main__":
    main()

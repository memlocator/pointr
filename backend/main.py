from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import grpc
import enrichment_pb2
import enrichment_pb2_grpc
import recon_pb2
import recon_pb2_grpc
import httpx

app = FastAPI(title="Pointr API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
        with grpc.insecure_channel('enrichment:50051') as channel:
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
        with grpc.insecure_channel('recon:50052') as channel:
            stub = recon_pb2_grpc.ReconServiceStub(channel)

            # Make RPC call
            response = stub.RunRecon(
                recon_pb2.ReconRequest(domains=request.domains)
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

@app.get("/api/search", response_model=NominatimSearchResponse)
async def search_location(q: str):
    """Search for locations using Nominatim (OpenStreetMap geocoding)"""
    if not q or len(q.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": q,
                    "format": "json",
                    "limit": 5,
                    "addressdetails": 1
                },
                headers={
                    "User-Agent": "Pointr/1.0"  # Nominatim requires a user agent
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()

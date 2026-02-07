# Reconnaissance Service

gRPC microservice for performing domain reconnaissance and OSINT gathering.

## Features

Comprehensive domain reconnaissance including:
- **DNS Records**: A, AAAA, MX, TXT, NS, CNAME records
- **SSL Certificates**: Certificate transparency logs from crt.sh
- **Subdomain Enumeration**: Discover subdomains from various sources
- **Security Headers**: HTTP security header analysis
- **WHOIS Data**: Domain registration information
- **ASN Information**: Autonomous System Number and network details

## Modes

### Silent Mode
Passive reconnaissance only - no direct HTTP requests to target domain:
- DNS queries
- SSL certificate transparency logs
- WHOIS lookups
- ASN information

### Full Mode
Includes all silent mode features plus:
- Security header analysis (requires HTTP request)
- Additional active probing

## Environment

- **Python**: 3.14
- **Package Manager**: uv
- **Framework**: gRPC
- **Port**: 50052
- **Dependencies**: See `pyproject.toml`

## Development

### Hot Reload

The service includes automatic hot reload in development mode using `watchdog`. Any changes to `.py` files will automatically restart the server.

### Running Locally

With uv:
```bash
cd recon
uv sync
uv run python main.py
```

With Docker:
```bash
docker-compose up recon
```

The Docker setup mounts source files as volumes, enabling hot reload without rebuilding the container.

## API

### RunRecon

Batch reconnaissance on multiple domains.

**Request**: `ReconRequest`
- `domains`: Array of domain names to recon
- `silent_mode`: Boolean for passive-only reconnaissance

**Response**: `ReconResponse`
- `results`: Array of `DomainRecon` objects

### RunReconStream

Real-time streaming reconnaissance with live progress updates.

**Request**: `ReconRequest`
- `domains`: Array of domain names to recon
- `silent_mode`: Boolean for passive-only reconnaissance

**Response Stream**: `ReconUpdate`
- `type`: LOG or RESULT
- `message`: Progress log message
- `result`: Completed domain reconnaissance result

Domains are processed in parallel with real-time streaming updates.

## Configuration

Set via environment variables or `config.py`:
- `RECON_PORT`: gRPC server port (default: 50052)

## Data Sources

- DNS: Standard DNS resolvers
- SSL Certificates: crt.sh certificate transparency logs
- WHOIS: python-whois library
- ASN: DNS-based ASN lookups
- Subdomains: Multiple enumeration techniques

# Recon Service

gRPC microservice for domain reconnaissance and OSINT gathering.

## Environment

- **Python**: 3.14
- **Package manager**: uv
- **Framework**: gRPC
- **Port**: 50052

## Configuration

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Pointr` | Application name |
| `APP_VERSION` | `1.0` | Application version |
| `RECON_PORT` | `50052` | gRPC listen port |
| `MAX_WORKERS` | `5` | Thread pool size for parallel domain processing |
| `CRT_SH_API_URL` | `https://crt.sh/` | Certificate transparency log endpoint |
| `CYMRU_ASN_DOMAIN` | `origin.asn.cymru.com` | Team Cymru ASN lookup domain |
| `CRT_SH_RATE_LIMIT` | `300` | Requests per minute to crt.sh |

## Modes

### Silent (passive)
No direct contact with the target domain:
- DNS records (A, AAAA, MX, NS, TXT, SOA)
- SSL certificates from crt.sh
- Subdomain enumeration from certificate SANs
- WHOIS registration data
- ASN / BGP information
- DMARC record
- DNS blocklist checks

### Full (active)
Everything in silent mode plus:
- HTTP security header analysis (makes a request to the target)

## gRPC API

Defined in `proto/recon.proto`.

| Method | Description |
|---|---|
| `Health` | Returns service status without external calls |
| `RunRecon` | Synchronous recon; returns when all domains complete |
| `RunReconStream` | Streaming recon; emits `LOG`, `RESULT`, and `COMPLETE` updates in real time |

Domains are processed in parallel (up to `MAX_WORKERS` concurrently).

## Data Collected

| Category | Source | Notes |
|---|---|---|
| DNS records | System resolvers | A, AAAA, MX, NS, TXT, SOA |
| SSL certificates | crt.sh | Up to 10 most recent |
| Subdomains | crt.sh SANs | Up to 50 |
| Security headers | Direct HTTP | Full mode only |
| WHOIS | python-whois | Registrar, dates, nameservers |
| ASN / BGP | Team Cymru, RIPEstat, BGPView, PeeringDB | Multiple fallback sources |
| DMARC | DNS (`_dmarc.<domain>`) | Policy, subdomain policy, RUA/RUF URIs |
| Blocklist status | Spamhaus ZEN, Spamhaus DBL, URIBL, SURBL | TCP-based RBL lookups |

## Development

```bash
cd recon
uv sync
uv run python main.py
```

The Docker setup mounts source files as volumes. The service uses `watchdog` to auto-restart on `.py` file changes.

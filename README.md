# Pointr

A geospatial data platform for discovering, analyzing, and investigating businesses and points of interest using interactive maps.

## Features

### Map View
- **Interactive Drawing**: Draw polygons and circles to define areas of interest
- **Business Discovery**: Automatically discover businesses, POIs, and government entities within drawn areas
- **Location Search**: Search for locations worldwide using OpenStreetMap Nominatim
- **Color-Coded Markers**: Visual categorization by business type (Food, Retail, Healthcare, Government, etc.)
- **Contact Badges**: Visual indicators showing which businesses have phone, email, or website data
- **Heatmap Visualization**: Toggle density heatmaps for individual categories to identify business clusters
- **Find in List**: Click any business marker to search for it in the list view

### Data Visualization
- **Point Markers**: Standard view showing individual businesses as colored markers
- **Category Heatmaps**: Density visualization for analyzing business distribution
  - Toggle between point markers and heatmap view
  - Select one category at a time for focused analysis
  - Category-specific color gradients for visual consistency
  - Zoom-responsive intensity and radius
  - Useful for identifying market saturation and underserved areas

### List View
- **Full-Text Search**: Search across all business data fields
- **Category Filtering**: Filter by 10 business categories
- **Contact Filtering**: Filter by availability of phone, email, or website
- **Sorting**: Sort by any column (ascending/descending/none)
- **Pagination**: Navigate through large datasets
- **Selection**: Multi-select businesses for reconnaissance

### Contacts View
- **Pre-Filtered Data**: Shows only businesses with contact information (phone, email, or website)
- **Quick Access**: Streamlined view of phone numbers, emails, and websites
- **Clickable Links**: Direct phone (tel:), email (mailto:), and website links
- **Selection Sync**: Selection state synchronized with List View

### Recon View
- **Dual Mode Reconnaissance**: Choose between Silent (passive) or Full (active) recon
  - **Silent Mode**: DNS, SSL certificates, WHOIS, ASN - no HTTP requests to target
  - **Full Mode**: All silent features plus security headers (requires HTTP request)
- **Target Management**: View, remove individual targets, or clear all at once
- **Real-Time Streaming**: Live log updates in resizable sidebar
- **Color-Coded UI**: Purple for silent mode, orange for full mode
- **DNS Records**: Query A, AAAA, MX, TXT, NS records via dnspython
- **SSL Certificates**: Certificate details from Certificate Transparency logs (crt.sh)
- **Subdomain Discovery**: Automated subdomain enumeration from SSL certificates
- **Security Headers**: HTTP security header analysis (HSTS, CSP, X-Frame-Options, etc.)
- **WHOIS Data**: Domain registration and ownership information
- **ASN Information**: Autonomous system number, network range, and ISP data
- **Parallel Execution**: Process multiple domains concurrently (up to 5 workers)
- **Result Management**: Remove individual results or clear all at once
- **All Free Tools**: No API keys required

## Architecture

```mermaid
flowchart TB
    User([User])

    subgraph Frontend["Frontend :5173<br/>(Svelte 5 + MapLibre GL)"]
        MapView[Map View<br/>Draw Polygons/Circles]
        ListView[List View<br/>Search & Filter]
        ContactsView[Contacts View<br/>Contact Info Only]
        ReconView[Recon View<br/>Network Analysis]
    end

    subgraph Backend["Backend :8000<br/>(FastAPI REST API)"]
        API[REST Endpoints<br/>/api/enrich<br/>/api/recon<br/>/api/search]
    end

    subgraph Services["Microservices"]
        Enrichment[Enrichment :50051<br/>gRPC Service]
        Recon[Recon :50052<br/>gRPC Service]
    end

    subgraph External["External APIs"]
        OSM[OpenStreetMap<br/>Overpass API]
        Nominatim[Nominatim<br/>Geocoding API]
        CrtSh[crt.sh<br/>Certificate Transparency]
        DNS[DNS Servers<br/>dnspython]
        WHOIS[WHOIS Servers<br/>python-whois]
        Cymru[Team Cymru<br/>ASN Lookup]
    end

    User -->|Draws polygons<br/>Searches locations| MapView
    User -->|Filters & searches<br/>Selects businesses| ListView
    User -->|Views contacts<br/>Selects businesses| ContactsView
    User -->|Views recon results| ReconView

    MapView -->|POST /api/map/enrich| API
    MapView -->|GET /api/search| API
    ListView -->|POST /api/recon| API
    ContactsView -->|POST /api/recon| API

    API -->|gRPC EnrichPolygon| Enrichment
    API -->|gRPC RunRecon| Recon
    API -->|HTTP GET| Nominatim

    Enrichment -->|HTTP POST| OSM
    Recon -->|HTTP GET| CrtSh
    Recon -->|DNS Queries| DNS
    Recon -->|WHOIS Queries| WHOIS
    Recon -->|DNS Queries| Cymru

    OSM -.->|Business data| Enrichment
    CrtSh -.->|SSL certs & subdomains| Recon
    DNS -.->|DNS records| Recon
    WHOIS -.->|Domain info| Recon
    Cymru -.->|ASN info| Recon

    Enrichment -.->|gRPC Response| API
    Recon -.->|gRPC Response| API
    Nominatim -.->|Location results| API

    API -.->|JSON Response| MapView
    API -.->|JSON Response| ListView
    API -.->|JSON Response| ContactsView

    style User fill:#f97316,stroke:#ea580c,color:#fff
    style Frontend fill:#1f2937,stroke:#374151,color:#fff
    style Backend fill:#1f2937,stroke:#374151,color:#fff
    style Services fill:#1f2937,stroke:#374151,color:#fff
    style External fill:#374151,stroke:#4b5563,color:#fff
```

**Data Flow:**

1. **Map Enrichment**: User draws polygon → Frontend → Backend REST → Enrichment gRPC → OSM Overpass → Business data returned
2. **Reconnaissance**: User selects businesses → Frontend → Backend REST → Recon gRPC → Free network tools → Recon data returned
3. **Location Search**: User searches → Frontend → Backend REST → Nominatim API → Location results returned

## Project Structure

```
leadmaker/
├── proto/                # Protocol Buffer definitions
│   ├── enrichment.proto  # Map enrichment service
│   └── recon.proto       # Network recon service
├── backend/              # FastAPI REST API
│   ├── main.py
│   ├── config.py         # Pydantic settings
│   ├── enrichment_pb2*.py
│   ├── recon_pb2*.py
│   ├── pyproject.toml
│   └── Dockerfile
├── enrichment/           # gRPC enrichment service
│   ├── main.py
│   ├── config.py         # Pydantic settings
│   ├── requirements.txt
│   └── Dockerfile
├── recon/                # gRPC recon service
│   ├── main.py
│   ├── config.py         # Pydantic settings
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/             # Svelte 5 + MapLibre UI
│   ├── src/
│   │   ├── lib/
│   │   │   ├── Map.svelte
│   │   │   ├── ListView.svelte
│   │   │   ├── ContactsView.svelte
│   │   │   ├── ReconView.svelte
│   │   │   ├── ReconResults.svelte
│   │   │   └── components/
│   │   │       └── DataTable/
│   │   ├── App.svelte
│   │   └── main.js
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml    # Docker orchestration
└── README.md
```

## Prerequisites

### Option 1: Docker (Recommended)
- Docker
- Docker Compose

### Option 2: Local Development
- Python 3.14+
- Node.js (v20+ recommended)
- uv (Python package manager)

## Configuration & Branding

The application can be easily rebranded by changing the app name in central configuration files. All UI elements, API titles, and user agents are generated from these settings.

### Rebranding the Application

To change the application name from "Pointr" to your own brand:

1. **Frontend Configuration** - Update `frontend/src/config.js`:
   ```javascript
   export const APP_NAME = 'YourAppName'
   export const APP_TITLE = 'YourAppName - Location Platform'
   export const APP_VERSION = '1.0'
   ```

2. **Backend Configuration** - Update `backend/config.py`:
   ```python
   app_name: str = "YourAppName"
   app_version: str = "1.0"
   ```

3. **Recon Service Configuration** - Update `recon/config.py`:
   ```python
   app_name: str = "YourAppName"
   app_version: str = "1.0"
   ```

These changes will automatically update:
- Browser tab title
- Logo in top navigation bar
- FastAPI documentation title
- API welcome message
- User-Agent headers for external API requests
- Recon service User-Agent headers

No rebuild is required for frontend changes (hot reload). Backend and recon services will need restart or rebuild for changes to take effect.

## Development

### With Docker (Recommended)

The easiest way to run the entire stack with hot reloading:

```bash
docker compose up
```

This will start all services:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Enrichment gRPC: `localhost:50051`
- Recon gRPC: `localhost:50052`

All services support hot reloading - changes to your code will automatically reload.

To rebuild after dependency changes:

```bash
docker compose up --build
```

To stop the services:

```bash
docker compose down
```

### Local Development (Alternative)

#### Setup

Backend dependencies:

```bash
cd backend
uv sync
```

Enrichment service:

```bash
cd enrichment
pip install -r requirements.txt
```

Recon service:

```bash
cd recon
pip install -r requirements.txt
```

Frontend dependencies:

```bash
cd frontend
npm install
```

#### Running Services

You'll need to run 4 terminals:

**Terminal 1** (Backend):
```bash
cd backend
uv run python main.py
```

**Terminal 2** (Enrichment):
```bash
cd enrichment
python main.py
```

**Terminal 3** (Recon):
```bash
cd recon
python main.py
```

**Terminal 4** (Frontend):
```bash
cd frontend
npm run dev
```

## API Documentation

FastAPI provides automatic API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### REST API Endpoints (Backend)

**General**
- `GET /` - Welcome message
- `GET /api/health` - Health check

**Map Enrichment**
- `POST /api/enrich` - Enrich polygon data (legacy endpoint)
- `POST /api/map/enrich` - Enrich polygon with business/POI data
  - Input: `{ coordinates: [{ lat, lng }] }`
  - Output: Area, population, businesses with contact info

**Network Reconnaissance**
- `POST /api/recon` - Run network recon on domains (deprecated, use /api/recon/stream)
- `POST /api/recon/stream` - Run streaming network recon on domains
  - Input: `{ domains: ["example.com", "example.org"], silent_mode: true/false }`
  - Output: Server-Sent Events stream with real-time logs and results
  - Silent mode (true): DNS, SSL, WHOIS, ASN only (passive reconnaissance)
  - Full mode (false): All silent features plus security headers (active reconnaissance)

**Location Search**
- `GET /api/search?q={query}` - Search for locations
  - Input: Query string (min 3 characters)
  - Output: Location results from Nominatim

### gRPC Services

**Enrichment Service (port 50051)**
- `EnrichPolygon(PolygonRequest) -> EnrichmentResponse`
  - Queries OpenStreetMap Overpass API
  - Returns businesses with contact information

**Recon Service (port 50052)**
- `RunReconStream(ReconRequest) -> stream ReconUpdate`
  - Input: domains list and silent_mode flag
  - Parallel execution with up to 5 concurrent workers
  - Real-time streaming of logs and results
  - DNS lookups via dnspython (passive)
  - SSL certificates from crt.sh API (passive)
  - Subdomain enumeration from Certificate Transparency (passive)
  - WHOIS lookups via public servers (passive)
  - ASN data from Team Cymru DNS service (passive)
  - Security header checks via HTTP requests (active - skipped in silent mode)

## Tech Stack

### Backend (REST API)
- FastAPI - Modern Python web framework
- Uvicorn - ASGI server
- Pydantic - Data validation
- Pydantic Settings - Configuration management
- gRPC - RPC client for microservices
- httpx - Async HTTP client

### Enrichment Service (gRPC)
- gRPC - High-performance RPC framework
- Protocol Buffers - Interface definition
- Pydantic Settings - Configuration management
- Shapely - Geometric calculations
- requests - HTTP client for Overpass API

### Recon Service (gRPC)
- gRPC - High-performance RPC framework
- Protocol Buffers - Interface definition
- Pydantic Settings - Configuration management
- dnspython - DNS queries
- python-whois - WHOIS lookups
- httpx - HTTP client for crt.sh and security headers
- ThreadPoolExecutor - Parallel domain processing

### Frontend
- Svelte 5 - Reactive UI framework with runes (`$state`, `$derived`, `$effect`)
- Vite - Build tool and dev server
- Tailwind CSS v4 - Utility-first CSS framework
- MapLibre GL JS - WebGL-based interactive maps
- Mapbox GL Draw - Polygon and circle drawing tools
- Turf.js - Geospatial analysis
- Custom DataTable - Reusable table component with search, filtering, sorting, pagination

## Business Categories

The application categorizes businesses into 11 types with mathematically distinct colors:

1. **Food & Dining** - Restaurants, cafes, bars, fast food, bakeries
2. **Retail** - Supermarkets, stores, shops, malls, markets, electronics
3. **Healthcare** - Hospitals, clinics, pharmacies, doctors, dentists, veterinary
4. **Services** - Banks, hairdressers, beauty services
5. **Government** - Government offices, embassies, post offices, police, fire stations, libraries
6. **Offices** - Office buildings, business centers
7. **Transportation** - Train stations, bus stations, ferry terminals
8. **Infrastructure** - Airports, telecom towers, utilities, ports, industrial facilities
9. **Automotive** - Gas stations, car rentals, car washes
10. **Historic & Tourism** - Castles, monuments, museums, schools, universities
11. **Other** - Everything else

Colors are generated using the golden angle method (137.508°) for maximum visual distinction.

## Free Reconnaissance Tools

The recon service uses only free tools with no API key requirements:

### Passive Reconnaissance (Silent Mode)
All of these tools do NOT contact the target website directly:

- **DNS Records**: dnspython library (queries public DNS servers for A, AAAA, MX, TXT, NS records)
- **SSL Certificates**: crt.sh API (queries Certificate Transparency logs)
- **Subdomains**: Extracted from SSL certificate Subject Alternative Names
- **WHOIS**: python-whois library (queries public WHOIS servers for registration data)
- **ASN Information**: Team Cymru DNS-based ASN lookup service (passive DNS queries only)

### Active Reconnaissance (Full Mode Only)
This feature requires making an HTTP request to the target:

- **Security Headers**: Direct HTTP HEAD request to analyze HSTS, CSP, X-Frame-Options, etc.

### Parallel Processing
- Concurrent execution of up to 5 domains simultaneously using ThreadPoolExecutor
- Real-time streaming of logs and results via Server-Sent Events (SSE)

## License

MIT

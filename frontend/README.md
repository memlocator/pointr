# Frontend

Svelte 5 single-page application providing the map interface, list views, and recon UI.

## Environment

- **Node**: via Docker / local install
- **Package manager**: npm
- **Framework**: Svelte 5 + Vite
- **Port**: 5173

## Views

| View | Description |
|---|---|
| **Map** | Interactive map with drawing tools, POI discovery, custom areas, and routing |
| **List** | Tabular view of discovered businesses with search, filtering, sorting, and export |
| **Contacts** | Filtered view showing only businesses that have contact information |
| **Recon** | Domain reconnaissance interface with live streaming results |
| **Projects** | Project selector with admin/member roles and access control |

## Key Components

| Component | Description |
|---|---|
| `Topbar` | Navigation bar, view switcher, business counter, project selector, dev mode badge |
| `Map` | MapLibre GL map; polygon/circle drawing; business markers; heatmap; routing layer |
| `DrawingToolbar` | Polygon, rectangle, and circle drawing controls |
| `LocationSearchBar` | Nominatim geocoding with autocomplete |
| `RoutingPanel` | Multi-stop route planning with GeoJSON export/import |
| `CategoryFilter` | Toggle visibility by business category |
| `ListView` / `DataTable` | Sortable, filterable table with CSV and JSON export |
| `ReconView` / `ReconResults` | Domain recon UI with streaming log and structured results |

## Map Features

- Draw polygons, rectangles, and circles to define search areas
- Right-click to add custom POIs or save drawn areas to the database
- Custom POIs appear with an amber ring; custom areas as dashed amber overlays
- Business markers are color-coded by category
- Heatmap toggle per category
- Routing panel for multi-stop driving directions via OSRM

## Projects

- The active project is stored client-side and sent with API requests.
- Project membership and roles are managed in the Topbar modal.
- In dev mode, the Topbar shows a **DEV MODE** badge that can set an impersonation user.

## Development

```bash
cd frontend
npm install
npm run dev
```

With Docker:
```bash
docker compose up frontend
```

Source files are mounted as volumes so Vite HMR works without rebuilding the image.

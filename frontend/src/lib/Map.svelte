<script>
  import { onMount } from 'svelte'
  import maplibregl from 'maplibre-gl'
  import MapboxDraw from '@mapbox/mapbox-gl-draw'
  import circle from '@turf/circle'
  import { BUSINESS_CATEGORIES, generateColorExpression, generateIconExpression } from './businessCategories.js'
  import LocationSearchBar from './components/LocationSearchBar.svelte'
  import DrawingToolbar from './components/DrawingToolbar.svelte'
  import CategoryFilter from './components/CategoryFilter.svelte'
  import RoutingPanel from './components/RoutingPanel.svelte'
  import DetailModal from './components/DetailModal.svelte'

  let {
    businesses = $bindable([]),
    polygons = $bindable([]),
    mapCenter = $bindable([-0.09, 51.505]),
    mapZoom = $bindable(13),
    currentView = $bindable('map'),
    searchQuery = $bindable(''),
    enabledCategories = $bindable({}),
    showContactsOnly = $bindable(false),
    heatmapEnabled = $bindable(false),
    heatmapCategory = $bindable(''),
    routingEnabled = $bindable(false),
    stops = $bindable([]),
    routeData = $bindable(null)
  } = $props()
  let mapContainer
  let map
  let draw
  let isEnriching = $state(false)
  let mapLoaded = $state(false)
  let stopMarkers = []
  let isDraggingMarker = false

  // Custom areas loaded from DB
  let customAreas = $state([])

  // Custom POI form (right-click)
  let poiForm = $state(null) // { lat, lng, x, y } or null
  let poiName = $state('')
  let poiCategory = $state(BUSINESS_CATEGORIES[0].name)
  let poiDescription = $state('')
  let poiContextMenu = $state(null) // { poiId, poiName, poiCategory, x, y, mode: 'view' | 'edit', inputName, inputCategory }
  let detailModal = $state(null) // entity object for DetailModal

  // Tracks which draw feature IDs have been saved as areas (session only)
  let drawnPolygonSaves = $state({}) // { [drawFeatureId]: { id, name } }

  // Polygon right-click context menu
  let polygonContextMenu = $state(null) // { featureId, coordinates, x, y, mode, inputName, inputDescription }

  // Filter businesses based on enabled categories and contact info
  let filteredBusinesses = $derived.by(() => {
    // Force tracking of enabledCategories object
    const enabled = enabledCategories
    return businesses.filter(business => {
      // Filter by category
      const category = BUSINESS_CATEGORIES.find(cat =>
        cat.types.includes(business.type)
      )
      const categoryName = category ? category.name : 'Other'
      if (!enabled[categoryName]) {
        return false
      }

      // Filter by contact info if enabled
      if (showContactsOnly) {
        return business.phone || business.email || business.website
      }

      return true
    })
  })

  // Filter businesses for heatmap (single category)
  let heatmapBusinesses = $derived.by(() => {
    if (!heatmapEnabled || !heatmapCategory) return []

    return filteredBusinesses.filter(business => {
      const category = BUSINESS_CATEGORIES.find(cat =>
        cat.types.includes(business.type)
      )
      return category?.name === heatmapCategory
    })
  })

  // Update map when filtered businesses change
  $effect(() => {
    // Explicitly track enabledCategories to ensure reactivity
    const categories = enabledCategories

    if (mapLoaded && map && map.getSource('businesses')) {
      const geojson = {
        type: 'FeatureCollection',
        features: filteredBusinesses.map(business => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [business.lng, business.lat]
          },
          properties: {
            name: business.name,
            type: business.type,
            address: business.address,
            phone: business.phone,
            website: business.website,
            email: business.email,
            source: business.source || 'osm',
            id: business.id || '',
            description: business.description || ''
          }
        }))
      }
      map.getSource('businesses').setData(geojson)
    }
  })

  // Update heatmap data and visibility
  $effect(() => {
    if (!mapLoaded || !map) return

    const heatmapSource = map.getSource('businesses-heatmap')
    if (!heatmapSource) return

    // Update heatmap data
    if (heatmapEnabled && heatmapBusinesses.length > 0) {
      const geojson = {
        type: 'FeatureCollection',
        features: heatmapBusinesses.map(business => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [business.lng, business.lat]
          },
          properties: {
            name: business.name,
            type: business.type
          }
        }))
      }
      heatmapSource.setData(geojson)

      // Update heatmap color gradient based on selected category
      const category = BUSINESS_CATEGORIES.find(c => c.name === heatmapCategory)
      if (category) {
        // Convert hex color to rgba for gradient
        const color = category.color
        const r = parseInt(color.slice(1, 3), 16)
        const g = parseInt(color.slice(3, 5), 16)
        const b = parseInt(color.slice(5, 7), 16)

        map.setPaintProperty('businesses-heatmap-layer', 'heatmap-color', [
          'interpolate', ['linear'], ['heatmap-density'],
          0, 'rgba(0, 0, 0, 0)',
          0.2, `rgba(${r}, ${g}, ${b}, 0.4)`,
          0.4, `rgba(${r}, ${g}, ${b}, 0.6)`,
          0.6, `rgba(${r}, ${g}, ${b}, 0.8)`,
          1, `rgba(${r}, ${g}, ${b}, 1)`
        ])
      }

      // Show heatmap, hide points
      map.setLayoutProperty('businesses-heatmap-layer', 'visibility', 'visible')
      map.setLayoutProperty('businesses-layer', 'visibility', 'none')
      map.setLayoutProperty('phone-badge', 'visibility', 'none')
      map.setLayoutProperty('website-badge', 'visibility', 'none')
      map.setLayoutProperty('email-badge', 'visibility', 'none')
    } else {
      // Hide heatmap, show points
      map.setLayoutProperty('businesses-heatmap-layer', 'visibility', 'none')
      map.setLayoutProperty('businesses-layer', 'visibility', 'visible')
      map.setLayoutProperty('phone-badge', 'visibility', 'visible')
      map.setLayoutProperty('website-badge', 'visibility', 'visible')
      map.setLayoutProperty('email-badge', 'visibility', 'visible')
    }
  })

  // Update route line on map
  $effect(() => {
    if (!mapLoaded || !map) return

    const routeSource = map.getSource('route')
    if (!routeSource) return

    // Update route line
    if (routeData && routeData.geometry) {
      routeSource.setData({
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: routeData.geometry
        }]
      })

      // Only fit bounds on initial route calculation, not on drag-triggered recalculation
      if (!isDraggingMarker) {
        const coordinates = routeData.geometry.coordinates
        const bounds = coordinates.reduce((bounds, coord) => {
          return bounds.extend(coord)
        }, new maplibregl.LngLatBounds(coordinates[0], coordinates[0]))

        map.fitBounds(bounds, {
          padding: { top: 100, bottom: 100, left: 400, right: 100 }
        })
      }
    } else {
      routeSource.setData({ type: 'FeatureCollection', features: [] })
      map.getSource('route-bbox')?.setData({ type: 'FeatureCollection', features: [] })
    }
  })

  // Sync stop markers to map
  // NOTE: Marker dragging has been stubborn. Attempts so far:
  // 1. MapLibre `draggable: true` with map.dragPan.disable() on dragstart — map still panned
  // 2. Added mousedown/touchstart stopPropagation on custom element — no change
  // 3. Switched to manual pointerdown + setPointerCapture + pointermove/pointerup — map still panned
  // Hypothesis: something (MapboxDraw? MapLibre canvas-container?) captures pointer events
  // before our element, or the custom element isn't in the hit-test path despite being visible.
  $effect(() => {
    if (!mapLoaded || !map) return

    // Remove all markers when routing disabled
    if (!routingEnabled || stops.length === 0) {
      stopMarkers.forEach(m => m.remove())
      stopMarkers = []
      return
    }

    // Remove excess markers
    while (stopMarkers.length > stops.length) {
      stopMarkers.pop().remove()
    }

    // Create or update markers
    stops.forEach((stop, i) => {
      const color = i === 0 ? '#22c55e' : i === stops.length - 1 ? '#ef4444' : '#f97316'

      if (!stopMarkers[i]) {
        const el = document.createElement('div')
        el.style.width = '22px'
        el.style.height = '22px'
        el.style.borderRadius = '50%'
        el.style.backgroundColor = color
        el.style.border = '2px solid white'
        el.style.cursor = 'grab'
        el.style.boxShadow = '0 2px 6px rgba(0,0,0,0.5)'
        el.style.display = 'flex'
        el.style.alignItems = 'center'
        el.style.justifyContent = 'center'
        el.style.fontSize = '10px'
        el.style.fontWeight = '700'
        el.style.color = 'white'
        el.style.userSelect = 'none'
        el.textContent = String(i + 1)

        if (stop.lat != null) {
          const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
            .setLngLat([stop.lng, stop.lat])
            .addTo(map)
          stopMarkers[i] = marker
        }
      } else {
        // Update existing marker
        const el = stopMarkers[i].getElement()
        el.style.backgroundColor = color
        el.textContent = String(i + 1)
        // Description badge
        const badge = el.querySelector('.stop-desc-badge')
        if (stop.description && !badge) {
          const dot = document.createElement('span')
          dot.className = 'stop-desc-badge'
          dot.style.cssText = 'position:absolute;top:-3px;right:-3px;width:8px;height:8px;border-radius:50%;background:#facc15;border:1px solid white;'
          el.style.position = 'relative'
          el.appendChild(dot)
        } else if (!stop.description && badge) {
          badge.remove()
        }
        if (stop.lat != null && !isDraggingMarker) {
          stopMarkers[i].setLngLat([stop.lng, stop.lat])
        }
      }
    })
  })

  // Sync custom areas to map
  $effect(() => {
    if (!mapLoaded || !map) return
    const source = map.getSource('custom-areas')
    if (!source) return
    source.setData({
      type: 'FeatureCollection',
      features: customAreas.map(area => ({
        type: 'Feature',
        properties: { name: area.name, id: area.id, description: area.description || '' },
        geometry: {
          type: 'Polygon',
          coordinates: [area.coordinates.map(c => [c.lng, c.lat])]
        }
      }))
    })
  })

  // Load custom areas and category icons once map is ready
  $effect(() => {
    if (mapLoaded) {
      loadCustomAreas()
      loadCategoryIcons()
    }
  })

  // Resize map when routing panel opens/closes
  $effect(() => {
    if (routingEnabled !== undefined && map && mapLoaded) {
      // Small delay to let flexbox settle
      setTimeout(() => map.resize(), 50)
    }
  })

  function handleLocationSelect(result) {
    if (map) {
      map.flyTo({
        center: [result.lon, result.lat],
        zoom: 15,
        duration: 1500
      })
    }
  }

  function savePolygons() {
    if (draw) {
      polygons = draw.getAll().features
    }
  }

  function clearAll() {
    if (draw) {
      draw.deleteAll()
    }
    polygons = []
    clearBusinessMarkers()

    // Cancel any active drawing
    if (isDrawingCircle) {
      cancelCircleDrawing()
    }
    if (isDrawingPolygon) {
      draw.changeMode('simple_select')
      isDrawingPolygon = false
    }
  }

  function deletePolygon(polygonId) {
    if (draw) {
      draw.delete(polygonId)
    }
    savePolygons()
  }

  function goToPolygon(polygon) {
    if (!map || !polygon.geometry) return

    const coords = polygon.geometry.coordinates[0]

    // Calculate bounds
    let minLng = Infinity, minLat = Infinity
    let maxLng = -Infinity, maxLat = -Infinity

    coords.forEach(([lng, lat]) => {
      minLng = Math.min(minLng, lng)
      minLat = Math.min(minLat, lat)
      maxLng = Math.max(maxLng, lng)
      maxLat = Math.max(maxLat, lat)
    })

    map.fitBounds(
      [[minLng, minLat], [maxLng, maxLat]],
      { padding: 100, duration: 1500 }
    )
  }

  let isDrawingCircle = $state(false)
  let isDrawingPolygon = $state(false)
  let circleCenter = null
  let circleClickHandler = null
  let circleMoveHandler = null

  // Calculate distance between two points using Haversine formula (returns km)
  function haversineDistance(point1, point2) {
    const R = 6371 // Earth's radius in km
    const [lon1, lat1] = point1
    const [lon2, lat2] = point2

    const dLat = (lat2 - lat1) * Math.PI / 180
    const dLon = (lon2 - lon1) * Math.PI / 180

    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2)

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))

    return R * c
  }
  let previewCircleSource = null

  function startPolygonDrawing() {
    if (draw) {
      // Cancel circle drawing if active
      if (isDrawingCircle) {
        cancelCircleDrawing()
      }
      draw.changeMode('draw_polygon')
      isDrawingPolygon = true
    }
  }

  function cancelCircleDrawing() {
    if (circleClickHandler) {
      map.off('click', circleClickHandler)
    }
    if (circleMoveHandler) {
      map.off('mousemove', circleMoveHandler)
    }
    if (map.getSource('preview-circle')) {
      map.getSource('preview-circle').setData({
        type: 'FeatureCollection',
        features: []
      })
    }
    map.getCanvas().style.cursor = ''
    isDrawingCircle = false
    circleCenter = null
  }

  function startCircleDrawing() {
    // Cancel polygon drawing if active
    if (isDrawingPolygon) {
      draw.changeMode('simple_select')
      isDrawingPolygon = false
    }

    isDrawingCircle = true
    circleCenter = null
    map.getCanvas().style.cursor = 'crosshair'

    circleClickHandler = (e) => {
      if (!circleCenter) {
        // First click: set center
        circleCenter = [e.lngLat.lng, e.lngLat.lat]

        // Start showing preview on mouse move
        circleMoveHandler = (moveEvent) => {
          const currentPoint = [moveEvent.lngLat.lng, moveEvent.lngLat.lat]
          const radius = haversineDistance(circleCenter, currentPoint)

          const options = { steps: 64, units: 'kilometers' }
          const circlePolygon = circle(circleCenter, Math.max(0.1, radius), options)

          map.getSource('preview-circle').setData(circlePolygon)
        }
        map.on('mousemove', circleMoveHandler)
      } else {
        // Second click: finalize circle
        const currentPoint = [e.lngLat.lng, e.lngLat.lat]
        const radius = haversineDistance(circleCenter, currentPoint)

        if (radius > 0.05) { // minimum radius 50 meters
          const options = { steps: 64, units: 'kilometers' }
          const circlePolygon = circle(circleCenter, radius, options)
          draw.add(circlePolygon)
          savePolygons()
        }

        // Clean up
        map.getCanvas().style.cursor = ''
        map.off('click', circleClickHandler)
        if (circleMoveHandler) {
          map.off('mousemove', circleMoveHandler)
        }
        map.getSource('preview-circle').setData({
          type: 'FeatureCollection',
          features: []
        })
        isDrawingCircle = false
        circleCenter = null
      }
    }

    map.on('click', circleClickHandler)
  }

  function clearBusinessMarkers() {
    if (map && map.getSource('businesses')) {
      map.getSource('businesses').setData({
        type: 'FeatureCollection',
        features: []
      })
    }
    businesses = []
  }

  async function enrichCoordinates(coordinates) {
    const response = await fetch('http://localhost:8000/api/map/enrich', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ coordinates })
    })
    if (!response.ok) throw new Error('Failed to enrich polygon')
    const data = await response.json()
    if (data.error) {
      console.warn('Enrichment error:', data.error)
      alert(`⚠️ ${data.error}`)
    }
    return data.businesses || []
  }

  async function enrichPolygons() {
    const data = draw.getAll()
    if (!data.features || data.features.length === 0) {
      alert('Please draw a polygon first!')
      return
    }
    isEnriching = true
    clearBusinessMarkers()
    try {
      const allBusinesses = []
      for (const feature of data.features) {
        if (feature.geometry.type !== 'Polygon') continue
        const coordinates = feature.geometry.coordinates[0].map(([lng, lat]) => ({ lat, lng }))
        const results = await enrichCoordinates(coordinates)
        allBusinesses.push(...results)
      }
      businesses = allBusinesses
    } catch (error) {
      console.error('Error enriching polygon:', error)
      alert('Failed to enrich polygon: ' + error.message)
    } finally {
      isEnriching = false
    }
  }

  function pointInPolygon(point, ring) {
    const [x, y] = point
    let inside = false
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j]
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside
    }
    return inside
  }

  function mergeBusinesses(existing, incoming) {
    const seen = new Set(existing.map(b => `${b.lat}|${b.lng}`))
    return [...existing, ...incoming.filter(b => !seen.has(`${b.lat}|${b.lng}`))]
  }

  async function enrichAlongRoute(bboxCoords) {
    // Draw the bbox on the map
    map.getSource('route-bbox').setData({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [bboxCoords.map(c => [c.lng, c.lat])]
        }
      }]
    })
    isEnriching = true
    try {
      const results = await enrichCoordinates(bboxCoords)
      businesses = mergeBusinesses(businesses, results)
    } catch (e) {
      alert('Route search failed: ' + e.message)
    } finally {
      isEnriching = false
    }
  }

  async function polygonContextGeoLookup() {
    if (!polygonContextMenu) return
    const coords = polygonContextMenu.coordinates
    polygonContextMenu = null
    isEnriching = true
    try {
      const results = await enrichCoordinates(coords)
      businesses = mergeBusinesses(businesses, results)
    } catch (e) {
      alert('Geo lookup failed: ' + e.message)
    } finally {
      isEnriching = false
    }
  }

  async function polygonContextSaveArea() {
    if (!polygonContextMenu?.inputName?.trim()) return
    const featureId = polygonContextMenu.featureId
    try {
      const resp = await fetch('http://localhost:8000/api/areas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '', coordinates: polygonContextMenu.coordinates })
      })
      if (!resp.ok) throw new Error('Failed to save area')
      const saved = await resp.json()
      drawnPolygonSaves = { ...drawnPolygonSaves, [featureId]: { id: saved.id, name: saved.name } }
      // Remove the draw feature — it's now represented by the amber area overlay
      draw.delete(featureId)
      savePolygons()
      await loadCustomAreas()
    } catch (e) {
      alert('Error saving area: ' + e.message)
    }
    polygonContextMenu = null
  }

  async function polygonContextUpdateArea() {
    if (!polygonContextMenu?.inputName?.trim()) return
    const areaId = drawnPolygonSaves[polygonContextMenu.featureId]?.id
    if (!areaId) return
    try {
      const resp = await fetch(`http://localhost:8000/api/areas/${areaId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' })
      })
      if (!resp.ok) throw new Error('Failed to update area')
      drawnPolygonSaves = { ...drawnPolygonSaves, [polygonContextMenu.featureId]: { id: areaId, name: polygonContextMenu.inputName.trim() } }
      await loadCustomAreas()
    } catch (e) {
      alert('Error updating area: ' + e.message)
    }
    polygonContextMenu = null
  }

  async function deleteCustomArea(id) {
    try {
      const resp = await fetch(`http://localhost:8000/api/areas/${id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('Failed to delete area')
      // Remove from session tracking
      drawnPolygonSaves = Object.fromEntries(Object.entries(drawnPolygonSaves).filter(([, v]) => v.id !== id))
      await loadCustomAreas()
    } catch (e) {
      alert('Error deleting area: ' + e.message)
    }
    polygonContextMenu = null
  }

  async function loadCategoryIcons() {
    for (const cat of BUSINESS_CATEGORIES) {
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="14" fill="${cat.color}" stroke="#f59e0b" stroke-width="2.5"/>${cat.icon}</svg>`
      const url = 'data:image/svg+xml,' + encodeURIComponent(svg)
      await new Promise((resolve) => {
        const img = new Image(32, 32)
        img.onload = () => { map.addImage(`poi-icon-${cat.name}`, img); resolve() }
        img.onerror = resolve
        img.src = url
      })
    }
  }

  async function loadCustomAreas() {
    try {
      const resp = await fetch('http://localhost:8000/api/areas')
      if (!resp.ok) return
      customAreas = await resp.json()
    } catch (e) {
      console.warn('Failed to load custom areas:', e)
    }
  }

  async function saveCustomPOI() {
    if (!poiName.trim() || !poiForm) return
    try {
      const resp = await fetch('http://localhost:8000/api/pois', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: poiName.trim(), category: poiCategory, description: poiDescription, lat: poiForm.lat, lng: poiForm.lng, tags: {} })
      })
      if (!resp.ok) throw new Error('Failed to save POI')
      const poi = await resp.json()
      businesses = [...businesses, { name: poi.name, lat: poi.lat, lng: poi.lng, type: poi.category, address: '', phone: '', website: '', email: '', source: 'custom', id: poi.id, description: poi.description || '' }]
    } catch (e) {
      alert('Error saving POI: ' + e.message)
    }
    poiForm = null
  }

  async function deleteCustomPOI(id) {
    try {
      const resp = await fetch(`http://localhost:8000/api/pois/${id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('Failed to delete POI')
      businesses = businesses.filter(b => b.id !== id)
    } catch (e) {
      alert('Error deleting POI: ' + e.message)
    }
    poiContextMenu = null
  }

  async function updateCustomPOI() {
    if (!poiContextMenu?.inputName?.trim()) return
    try {
      const resp = await fetch(`http://localhost:8000/api/pois/${poiContextMenu.poiId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: poiContextMenu.inputName.trim(), category: poiContextMenu.inputCategory, description: poiContextMenu.inputDescription || '' })
      })
      if (!resp.ok) throw new Error('Failed to update POI')
      businesses = businesses.map(b => b.id === poiContextMenu.poiId
        ? { ...b, name: poiContextMenu.inputName.trim(), type: poiContextMenu.inputCategory, description: poiContextMenu.inputDescription || '' }
        : b)
    } catch (e) {
      alert('Error updating POI: ' + e.message)
    }
    poiContextMenu = null
  }

  async function saveCustomArea() {
    if (!areaName.trim() || !areaPrompt) return
    try {
      const resp = await fetch('http://localhost:8000/api/areas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: areaName.trim(), coordinates: areaPrompt.coordinates })
      })
      if (!resp.ok) throw new Error('Failed to save area')
      await loadCustomAreas()
    } catch (e) {
      alert('Error saving area: ' + e.message)
    }
    areaPrompt = null
  }

  onMount(() => {
    // Initialize map
    map = new maplibregl.Map({
      container: mapContainer,
      style: {
        version: 8,
        sources: {
          'carto-dark': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
              'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
              'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
              'https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
            ],
            tileSize: 256,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          }
        },
        layers: [
          {
            id: 'carto-dark-layer',
            type: 'raster',
            source: 'carto-dark',
            minzoom: 0,
            maxzoom: 22
          }
        ]
      },
      center: mapCenter,
      zoom: mapZoom
    })

    // Save map position when user moves or zooms
    map.on('moveend', () => {
      mapCenter = [map.getCenter().lng, map.getCenter().lat]
      mapZoom = map.getZoom()
    })

    // Add navigation controls
    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    // Add drawing controls (all disabled, we'll use custom buttons)
    draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: {},
      styles: [
        // Polygon fill
        {
          'id': 'gl-draw-polygon-fill',
          'type': 'fill',
          'filter': ['all', ['==', '$type', 'Polygon']],
          'paint': {
            'fill-color': '#6b7280',
            'fill-opacity': 0.2
          }
        },
        // Polygon outline
        {
          'id': 'gl-draw-polygon-stroke',
          'type': 'line',
          'filter': ['all', ['==', '$type', 'Polygon']],
          'paint': {
            'line-color': '#9ca3af',
            'line-width': 2
          }
        },
        // Vertices
        {
          'id': 'gl-draw-polygon-and-line-vertex-active',
          'type': 'circle',
          'filter': ['all', ['==', 'meta', 'vertex'], ['==', '$type', 'Point']],
          'paint': {
            'circle-radius': 5,
            'circle-color': '#f97316'
          }
        }
      ]
    })
    map.addControl(draw, 'top-left')

    // Restore saved polygons
    if (polygons.length > 0) {
      draw.set({
        type: 'FeatureCollection',
        features: polygons
      })
    }

    // Save polygons when drawing changes
    map.on('draw.create', () => {
      savePolygons()
      isDrawingPolygon = false
    })
    map.on('draw.update', savePolygons)
    map.on('draw.delete', savePolygons)

    // Handle Ctrl key for enabling/disabling draw interaction
    let ctrlPressed = false
    const handleKeyDown = (e) => {
      if (e.key === 'Control' || e.key === 'Meta') {
        ctrlPressed = true
      }
    }
    const handleKeyUp = (e) => {
      if (e.key === 'Control' || e.key === 'Meta') {
        ctrlPressed = false
        // Deselect any selected features when Ctrl is released
        const mode = draw.getMode()
        if (mode === 'direct_select' || mode === 'simple_select') {
          draw.changeMode('simple_select')
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)

    // Prevent selecting drawn features unless Ctrl is held
    map.on('draw.modechange', (e) => {
      if (!ctrlPressed && !isDrawingPolygon && !isDrawingCircle) {
        // If entering a select mode without Ctrl, go back to simple_select with nothing selected
        if (e.mode === 'direct_select') {
          setTimeout(() => {
            if (!ctrlPressed) {
              draw.changeMode('simple_select')
            }
          }, 0)
        }
      }
    })

    console.log('Draw control added:', draw)

    // Add businesses source and layer after map loads
    map.on('load', () => {
      // Add preview circle source for circle drawing
      map.addSource('preview-circle', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: []
        }
      })

      map.addLayer({
        id: 'preview-circle-fill',
        type: 'fill',
        source: 'preview-circle',
        paint: {
          'fill-color': '#6b7280',
          'fill-opacity': 0.2
        }
      })

      map.addLayer({
        id: 'preview-circle-stroke',
        type: 'line',
        source: 'preview-circle',
        paint: {
          'line-color': '#9ca3af',
          'line-width': 2,
          'line-dasharray': [2, 2]
        }
      })

      // Add source for business points
      map.addSource('businesses', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: []
        }
      })

      // Don't restore businesses here - let the $effect handle it
      // This ensures proper filtering based on enabledCategories

      // Add heatmap source for density visualization
      map.addSource('businesses-heatmap', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: []
        }
      })

      // Add circle layer for OSM businesses only
      map.addLayer({
        id: 'businesses-layer',
        type: 'circle',
        source: 'businesses',
        filter: ['!=', ['get', 'source'], 'custom'],
        paint: {
          'circle-radius': 6,
          'circle-color': generateColorExpression(),
          'circle-stroke-width': 2,
          'circle-stroke-color': '#1f2937'
        }
      })

      // Custom POI icons — symbol layer with category-specific SVG icons
      map.addLayer({
        id: 'businesses-layer-custom',
        type: 'symbol',
        source: 'businesses',
        filter: ['==', ['get', 'source'], 'custom'],
        layout: {
          'icon-image': generateIconExpression(),
          'icon-size': 0.75,
          'icon-allow-overlap': true,
          'icon-anchor': 'center'
        }
      })

      // Add badge indicators for contact info using text symbols
      // Phone badge (top-right) - #
      map.addLayer({
        id: 'phone-badge',
        type: 'symbol',
        source: 'businesses',
        filter: ['all',
          ['has', 'phone'],
          ['!=', ['get', 'phone'], ''],
          ['!=', ['get', 'phone'], null]
        ],
        layout: {
          'text-field': '#',
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
          'text-size': 14,
          'text-offset': [0.5, -0.5],
          'text-anchor': 'center'
        },
        paint: {
          'text-color': '#10b981',
          'text-halo-color': '#000000',
          'text-halo-width': 2,
          'text-halo-blur': 0.5
        }
      })

      // Website badge (top-left) - ⌘ or ⊕
      map.addLayer({
        id: 'website-badge',
        type: 'symbol',
        source: 'businesses',
        filter: ['all',
          ['has', 'website'],
          ['!=', ['get', 'website'], ''],
          ['!=', ['get', 'website'], null]
        ],
        layout: {
          'text-field': '⊕',
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
          'text-size': 14,
          'text-offset': [-0.5, -0.5],
          'text-anchor': 'center'
        },
        paint: {
          'text-color': '#3b82f6',
          'text-halo-color': '#000000',
          'text-halo-width': 2,
          'text-halo-blur': 0.5
        }
      })

      // Email badge (bottom) - @
      map.addLayer({
        id: 'email-badge',
        type: 'symbol',
        source: 'businesses',
        filter: ['all',
          ['has', 'email'],
          ['!=', ['get', 'email'], ''],
          ['!=', ['get', 'email'], null]
        ],
        layout: {
          'text-field': '@',
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
          'text-size': 14,
          'text-offset': [0, 0.6],
          'text-anchor': 'center'
        },
        paint: {
          'text-color': '#f97316',
          'text-halo-color': '#000000',
          'text-halo-width': 2,
          'text-halo-blur': 0.5
        }
      })

      // Add heatmap layer (initially hidden)
      map.addLayer({
        id: 'businesses-heatmap-layer',
        type: 'heatmap',
        source: 'businesses-heatmap',
        paint: {
          // Heatmap weight
          'heatmap-weight': 1,

          // Intensity by zoom level
          'heatmap-intensity': [
            'interpolate', ['linear'], ['zoom'],
            0, 1,
            15, 3
          ],

          // Radius of influence (in pixels)
          'heatmap-radius': [
            'interpolate', ['linear'], ['zoom'],
            0, 20,
            9, 40,
            15, 80
          ],

          // Opacity
          'heatmap-opacity': 0.8,

          // Color gradient (will be updated dynamically)
          'heatmap-color': [
            'interpolate', ['linear'], ['heatmap-density'],
            0, 'rgba(0, 0, 0, 0)',
            0.2, 'rgba(255, 0, 0, 0.4)',
            0.4, 'rgba(255, 0, 0, 0.6)',
            0.6, 'rgba(255, 0, 0, 0.8)',
            1, 'rgba(255, 0, 0, 1)'
          ]
        },
        layout: {
          'visibility': 'none'
        }
      })

      // Add route source and layers
      map.addSource('route', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: []
        }
      })

      // Add route line layer
      map.addLayer({
        id: 'route-line',
        type: 'line',
        source: 'route',
        paint: {
          'line-color': '#f97316',
          'line-width': 4,
          'line-opacity': 0.8
        },
        layout: {
          'line-cap': 'round',
          'line-join': 'round'
        }
      })

      // Add route bbox source and dashed outline layer
      map.addSource('route-bbox', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
      })
      map.addLayer({
        id: 'route-bbox-outline',
        type: 'line',
        source: 'route-bbox',
        paint: {
          'line-color': '#f97316',
          'line-width': 2,
          'line-opacity': 0.6,
          'line-dasharray': [4, 4]
        }
      })

      // Add custom areas source and layers
      map.addSource('custom-areas', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
      })

      map.addLayer({
        id: 'custom-areas-fill',
        type: 'fill',
        source: 'custom-areas',
        paint: {
          'fill-color': '#f59e0b',
          'fill-opacity': 0.08
        }
      })

      map.addLayer({
        id: 'custom-areas-line',
        type: 'line',
        source: 'custom-areas',
        paint: {
          'line-color': '#f59e0b',
          'line-width': 2,
          'line-opacity': 0.6,
          'line-dasharray': [3, 2]
        }
      })

      map.addLayer({
        id: 'custom-areas-label',
        type: 'symbol',
        source: 'custom-areas',
        layout: {
          'text-field': ['get', 'name'],
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
          'text-size': 11,
          'text-anchor': 'center'
        },
        paint: {
          'text-color': '#f59e0b',
          'text-halo-color': '#111827',
          'text-halo-width': 2
        }
      })

      // Add popup on click - shared handler for all business layers
      const showPopup = (e) => {
        const coordinates = e.features[0].geometry.coordinates.slice()
        const { name, type, address, phone, website, email, source } = e.features[0].properties

        new maplibregl.Popup()
          .setLngLat(coordinates)
          .setHTML(`
            <div class="p-3 min-w-[200px]">
              <div class="flex items-center justify-between mb-1">
                <h3 class="font-bold text-gray-900">${name}</h3>
                <span class="text-xs px-1.5 py-0.5 rounded ${source === 'custom' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-500'}">${source === 'custom' ? 'Custom' : 'OSM'}</span>
              </div>
              <p class="text-xs text-gray-600 mb-2">${type}</p>
              ${address ? `<p class="text-xs text-gray-500 mb-1">${address}</p>` : ''}
              ${phone ? `<p class="text-xs text-gray-700"><strong>Phone:</strong> <a href="tel:${phone}" class="text-blue-600">${phone}</a></p>` : ''}
              ${website ? `<p class="text-xs text-gray-700"><strong>Web:</strong> <a href="${website}" target="_blank" class="text-blue-600 underline">${website.replace(/^https?:\/\//, '').substring(0, 30)}...</a></p>` : ''}
              ${email ? `<p class="text-xs text-gray-700"><strong>Email:</strong> <a href="mailto:${email}" class="text-blue-600">${email}</a></p>` : ''}
              <button
                data-find-in-list="${name}"
                class="mt-2 w-full px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium transition-colors"
              >
                FIND IN LIST
              </button>
            </div>
          `)
          .addTo(map)
      }

      // Listen for Find in List button clicks
      mapContainer.addEventListener('click', (e) => {
        const button = e.target.closest('[data-find-in-list]')
        if (button) {
          const businessName = button.getAttribute('data-find-in-list')
          searchQuery = businessName
          currentView = 'list'
        }
      })

      // Add click handlers to all layers
      map.on('click', 'businesses-layer', showPopup)
      map.on('click', 'businesses-layer-custom', showPopup)
      map.on('click', 'phone-badge', showPopup)
      map.on('click', 'website-badge', showPopup)
      map.on('click', 'email-badge', showPopup)

      // Handle map clicks for routing
      function handleMapClick(e) {
        if (!routingEnabled) return

        const { lng, lat } = e.lngLat

        // Add a new stop at end (max 10)
        if (stops.length < 10) {
          stops = [...stops, { lat, lng, name: `${lat.toFixed(4)}, ${lng.toFixed(4)}`, description: '' }]
        }
      }

      map.on('click', handleMapClick)

      // Close POI form and area popup on map click
      map.on('click', () => {
        if (poiForm) poiForm = null
        if (polygonContextMenu) polygonContextMenu = null
        if (poiContextMenu) poiContextMenu = null
      })

      map.on('mouseenter', 'custom-areas-fill', () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'custom-areas-fill', () => { map.getCanvas().style.cursor = '' })

      // Keep context menus anchored to their geographic position
      map.on('move', () => {
        if (poiContextMenu?.lngLat) {
          const pt = map.project(poiContextMenu.lngLat)
          poiContextMenu.x = pt.x
          poiContextMenu.y = pt.y
        }
        if (polygonContextMenu?.lngLat) {
          const pt = map.project(polygonContextMenu.lngLat)
          polygonContextMenu.x = pt.x
          polygonContextMenu.y = pt.y
        }
      })

      // Right-click → check if on drawn polygon or empty map
      map.on('contextmenu', (e) => {
        e.preventDefault()
        const clickPt = [e.lngLat.lng, e.lngLat.lat]

        // Check custom POI markers first
        const poiFeatures = map.queryRenderedFeatures(e.point, { layers: ['businesses-layer-custom'] })
        if (poiFeatures.length > 0) {
          const { name, type, id, description: poiDesc } = poiFeatures[0].properties
          poiContextMenu = { poiId: id, poiName: name, poiCategory: type, poiDescription: poiDesc || '', lngLat: [e.lngLat.lng, e.lngLat.lat], x: e.point.x, y: e.point.y, mode: 'view' }
          poiForm = null
          polygonContextMenu = null
          return
        }

        // Check saved area overlays first
        const areaFeatures = map.queryRenderedFeatures(e.point, { layers: ['custom-areas-fill'] })
        if (areaFeatures.length > 0) {
          const { id, name, description } = areaFeatures[0].properties
          polygonContextMenu = { mode: 'saved-area', areaId: id, areaName: name, areaDescription: description || '', lngLat: [e.lngLat.lng, e.lngLat.lat], x: e.point.x, y: e.point.y }
          poiForm = null
          return
        }

        // Check drawn polygons
        const allDrawn = draw.getAll()
        let hit = null
        for (const f of allDrawn.features) {
          if (f.geometry.type === 'Polygon' && pointInPolygon(clickPt, f.geometry.coordinates[0])) {
            hit = f
            break
          }
        }
        if (hit) {
          const saved = drawnPolygonSaves[hit.id]
          polygonContextMenu = {
            featureId: hit.id,
            coordinates: hit.geometry.coordinates[0].map(([lng, lat]) => ({ lat, lng })),
            lngLat: [e.lngLat.lng, e.lngLat.lat],
            x: e.point.x, y: e.point.y,
            mode: 'menu',
            inputName: saved?.name || '',
            inputDescription: ''
          }
          poiForm = null
        } else {
          poiForm = { lat: e.lngLat.lat, lng: e.lngLat.lng, x: e.point.x, y: e.point.y }
          poiName = ''
          poiCategory = BUSINESS_CATEGORIES[0].name
          poiDescription = ''
          polygonContextMenu = null
        }
      })

      // Change cursor on hover for all layers
      const layers = ['businesses-layer', 'businesses-layer-custom', 'phone-badge', 'website-badge', 'email-badge']
      layers.forEach(layer => {
        map.on('mouseenter', layer, () => {
          map.getCanvas().style.cursor = 'pointer'
        })
        map.on('mouseleave', layer, () => {
          map.getCanvas().style.cursor = ''
        })
      })

      // Mark map as fully loaded - this triggers the $effect to render businesses
      mapLoaded = true
    })

    return () => {
      if (circleClickHandler) {
        map.off('click', circleClickHandler)
      }
      if (circleMoveHandler) {
        map.off('mousemove', circleMoveHandler)
      }
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)

      // Clean up route markers
      stopMarkers.forEach(m => m.remove())
      stopMarkers = []

      map.remove()
    }
  })
</script>

<div class="relative w-full h-full flex transition-all duration-300">
  <!-- Routing Panel -->
  <RoutingPanel
    bind:routingEnabled
    bind:stops
    bind:routeData
    onFindAlongRoute={enrichAlongRoute}
  />

  <!-- Map Container -->
  <div class="relative flex-1 h-full transition-all duration-300">
    <div bind:this={mapContainer} class="w-full h-full"></div>

  <!-- Location search -->
  <LocationSearchBar onLocationSelect={handleLocationSelect} />

  <!-- Custom drawing controls -->
  <DrawingToolbar
    {polygons}
    {isDrawingPolygon}
    {isDrawingCircle}
    {isEnriching}
    {circleCenter}
    bind:routingEnabled
    onStartPolygonDrawing={startPolygonDrawing}
    onStartCircleDrawing={startCircleDrawing}
    onEnrich={enrichPolygons}
    onClearAll={clearAll}
    onGoToPolygon={goToPolygon}
    onDeletePolygon={deletePolygon}
  />

  <!-- Custom POI form (right-click) -->
  {#if poiForm}
    <div
      class="absolute bg-gray-900 border-2 border-gray-700 p-3 shadow-lg w-56"
      style="z-index: 1001; left: {Math.min(poiForm.x, mapContainer?.clientWidth - 240)}px; top: {Math.min(poiForm.y, mapContainer?.clientHeight - 160)}px;"
    >
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-bold text-gray-400 tracking-wide">ADD CUSTOM POI</span>
        <button onclick={() => poiForm = null} class="text-gray-500 hover:text-gray-300 text-xs">✕</button>
      </div>
      <input
        type="text"
        bind:value={poiName}
        placeholder="Name"
        class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-orange-500 focus:outline-none mb-2"
        onkeydown={(e) => e.key === 'Enter' && saveCustomPOI()}
      />
      <select
        bind:value={poiCategory}
        class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs focus:border-orange-500 focus:outline-none mb-2"
      >
        {#each BUSINESS_CATEGORIES as cat}
          <option value={cat.name}>{cat.name}</option>
        {/each}
      </select>
      <textarea
        bind:value={poiDescription}
        placeholder="Description (optional)"
        rows="2"
        class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-orange-500 focus:outline-none mb-2 resize-none"
      ></textarea>
      <button
        onclick={saveCustomPOI}
        disabled={!poiName.trim()}
        class="w-full py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-xs font-medium transition-colors"
      >SAVE</button>
    </div>
  {/if}

  <!-- Custom POI right-click context menu -->
  {#if poiContextMenu}
    <div
      class="absolute bg-gray-900 border-2 border-gray-600 shadow-lg w-52"
      style="z-index: 1001; left: {Math.min(poiContextMenu.x, mapContainer?.clientWidth - 220)}px; top: {Math.min(poiContextMenu.y, mapContainer?.clientHeight - 200)}px;"
    >
      {#if poiContextMenu.mode === 'view'}
        <div class="px-3 py-2 border-b border-gray-700">
          <div class="text-xs font-semibold text-gray-200 truncate">{poiContextMenu.poiName}</div>
          <div class="text-xs text-gray-500 mt-0.5">{poiContextMenu.poiCategory}</div>
        </div>
        <button
          onclick={() => { detailModal = { type: 'poi', id: poiContextMenu.poiId, name: poiContextMenu.poiName, category: poiContextMenu.poiCategory, description: poiContextMenu.poiDescription, lat: poiContextMenu.lngLat[1], lng: poiContextMenu.lngLat[0] }; poiContextMenu = null }}
          class="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-gray-800 flex items-center gap-2"
        ><span>📋</span> View Details</button>
        <button
          onclick={() => poiContextMenu = { ...poiContextMenu, mode: 'edit', inputName: poiContextMenu.poiName, inputCategory: poiContextMenu.poiCategory, inputDescription: poiContextMenu.poiDescription }}
          class="w-full px-3 py-2 text-left text-xs text-amber-400 hover:bg-gray-800 flex items-center gap-2"
        ><span>✎</span> Edit POI</button>
        <button
          onclick={() => deleteCustomPOI(poiContextMenu.poiId)}
          class="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-gray-800 flex items-center gap-2"
        ><span>✕</span> Delete POI</button>
        <button onclick={() => poiContextMenu = null} class="w-full px-3 py-2 text-left text-xs text-gray-500 hover:bg-gray-800">Cancel</button>
      {:else if poiContextMenu.mode === 'edit'}
        <div class="p-3">
          <div class="text-xs font-bold text-amber-500 tracking-wide mb-2">EDIT POI</div>
          <input
            type="text"
            bind:value={poiContextMenu.inputName}
            placeholder="Name"
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-amber-500 focus:outline-none mb-2"
            onkeydown={(e) => { if (e.key === 'Enter') updateCustomPOI() }}
          />
          <select
            bind:value={poiContextMenu.inputCategory}
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs focus:border-amber-500 focus:outline-none mb-2"
          >
            {#each BUSINESS_CATEGORIES as cat}
              <option value={cat.name}>{cat.name}</option>
            {/each}
          </select>
          <textarea
            bind:value={poiContextMenu.inputDescription}
            placeholder="Description (optional)"
            rows="2"
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-amber-500 focus:outline-none mb-2 resize-none"
          ></textarea>
          <div class="flex gap-2">
            <button
              onclick={updateCustomPOI}
              disabled={!poiContextMenu.inputName.trim()}
              class="flex-1 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-xs font-medium"
            >SAVE</button>
            <button onclick={() => poiContextMenu = { ...poiContextMenu, mode: 'view' }} class="px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs">BACK</button>
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Detail modal for POIs and areas -->
  {#if detailModal}
    <DetailModal
      entity={detailModal}
      onClose={() => detailModal = null}
      onSave={async (updated) => {
        if (detailModal.type === 'poi') {
          const resp = await fetch(`http://localhost:8000/api/pois/${detailModal.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: updated.name, category: updated.category, description: updated.description })
          })
          if (!resp.ok) { alert('Failed to update POI'); return }
          businesses = businesses.map(b => b.id === detailModal.id
            ? { ...b, name: updated.name, type: updated.category, description: updated.description }
            : b)
          detailModal = { ...detailModal, ...updated }
        } else {
          const resp = await fetch(`http://localhost:8000/api/areas/${detailModal.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: updated.name, description: updated.description })
          })
          if (!resp.ok) { alert('Failed to update area'); return }
          await loadCustomAreas()
          detailModal = { ...detailModal, ...updated }
        }
      }}
    />
  {/if}

  <!-- Polygon right-click context menu -->
  {#if polygonContextMenu}
    {@const saved = drawnPolygonSaves[polygonContextMenu.featureId]}
    <div
      class="absolute bg-gray-900 border-2 border-gray-600 shadow-lg w-52"
      style="z-index: 1001; left: {Math.min(polygonContextMenu.x, mapContainer?.clientWidth - 220)}px; top: {Math.min(polygonContextMenu.y, mapContainer?.clientHeight - 200)}px;"
    >
      {#if polygonContextMenu.mode === 'saved-area'}
        <div class="px-3 py-2 border-b border-gray-700">
          <div class="text-xs font-semibold text-gray-200 truncate">{polygonContextMenu.areaName}</div>
          {#if polygonContextMenu.areaDescription}
            <div class="text-xs text-gray-500 mt-0.5 truncate">{polygonContextMenu.areaDescription}</div>
          {/if}
        </div>
        <button
          onclick={async () => {
            const area = customAreas.find(a => a.id === polygonContextMenu.areaId)
            polygonContextMenu = null
            if (!area) return
            isEnriching = true
            try {
              const results = await enrichCoordinates(area.coordinates)
              businesses = mergeBusinesses(businesses, results)
            } catch (e) {
              alert('Geo lookup failed: ' + e.message)
            } finally {
              isEnriching = false
            }
          }}
          class="w-full px-3 py-2 text-left text-xs text-blue-400 hover:bg-gray-800 flex items-center gap-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Geo Lookup
        </button>
        <button
          onclick={() => { detailModal = { type: 'area', id: polygonContextMenu.areaId, name: polygonContextMenu.areaName, description: polygonContextMenu.areaDescription }; polygonContextMenu = null }}
          class="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-gray-800 flex items-center gap-2"
        ><span>📋</span> View Details</button>
        <button
          onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'saved-area-edit', inputName: polygonContextMenu.areaName, inputDescription: polygonContextMenu.areaDescription }}
          class="w-full px-3 py-2 text-left text-xs text-amber-400 hover:bg-gray-800 flex items-center gap-2"
        >
          <span>✎</span> Edit Area
        </button>
        <button
          onclick={() => deleteCustomArea(polygonContextMenu.areaId)}
          class="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-gray-800 flex items-center gap-2"
        >
          <span>✕</span> Delete Area
        </button>
        <button onclick={() => polygonContextMenu = null} class="w-full px-3 py-2 text-left text-xs text-gray-500 hover:bg-gray-800">Cancel</button>
      {:else if polygonContextMenu.mode === 'saved-area-edit'}
        <div class="p-3">
          <div class="text-xs font-bold text-amber-500 tracking-wide mb-2">EDIT AREA</div>
          <input
            type="text"
            bind:value={polygonContextMenu.inputName}
            placeholder="Name"
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-amber-500 focus:outline-none mb-2"
            onkeydown={async (e) => {
              if (e.key === 'Enter') {
                await fetch(`http://localhost:8000/api/areas/${polygonContextMenu.areaId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' }) })
                await loadCustomAreas()
                polygonContextMenu = null
              }
            }}
          />
          <input
            type="text"
            bind:value={polygonContextMenu.inputDescription}
            placeholder="Description (optional)"
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-amber-500 focus:outline-none mb-2"
          />
          <div class="flex gap-2">
            <button
              onclick={async () => {
                if (!polygonContextMenu.inputName.trim()) return
                try {
                  const resp = await fetch(`http://localhost:8000/api/areas/${polygonContextMenu.areaId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' }) })
                  if (!resp.ok) throw new Error('Failed to update area')
                  await loadCustomAreas()
                } catch (e) { alert('Error: ' + e.message) }
                polygonContextMenu = null
              }}
              disabled={!polygonContextMenu.inputName.trim()}
              class="flex-1 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-xs font-medium"
            >SAVE</button>
            <button onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'saved-area' }} class="px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs">BACK</button>
          </div>
        </div>
      {:else if polygonContextMenu.mode === 'menu'}
        <button
          onclick={polygonContextGeoLookup}
          class="w-full px-3 py-2 text-left text-xs text-gray-200 hover:bg-gray-800 flex items-center gap-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Geo Lookup
        </button>
        <div class="border-t border-gray-700"></div>
        {#if saved}
          <button
            onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'edit', inputName: saved.name, inputDescription: '' }}
            class="w-full px-3 py-2 text-left text-xs text-amber-400 hover:bg-gray-800 flex items-center gap-2"
          >
            <span>✎</span> Edit Area
          </button>
          <button
            onclick={() => deleteCustomArea(saved.id)}
            class="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-gray-800 flex items-center gap-2"
          >
            <span>✕</span> Delete Area
          </button>
        {:else}
          <button
            onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'save', inputName: '', inputDescription: '' }}
            class="w-full px-3 py-2 text-left text-xs text-amber-400 hover:bg-gray-800 flex items-center gap-2"
          >
            <span>+</span> Save Area
          </button>
        {/if}
        <div class="border-t border-gray-700"></div>
        <button onclick={() => polygonContextMenu = null} class="w-full px-3 py-2 text-left text-xs text-gray-500 hover:bg-gray-800">Cancel</button>
      {:else if polygonContextMenu.mode === 'save' || polygonContextMenu.mode === 'edit'}
        <div class="p-3">
          <div class="text-xs font-bold text-amber-500 tracking-wide mb-2">{polygonContextMenu.mode === 'save' ? 'SAVE AREA' : 'EDIT AREA'}</div>
          <input
            type="text"
            bind:value={polygonContextMenu.inputName}
            placeholder="Name"
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-amber-500 focus:outline-none mb-2"
            onkeydown={(e) => e.key === 'Enter' && (polygonContextMenu.mode === 'save' ? polygonContextSaveArea() : polygonContextUpdateArea())}
          />
          <input
            type="text"
            bind:value={polygonContextMenu.inputDescription}
            placeholder="Description (optional)"
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-amber-500 focus:outline-none mb-2"
          />
          <div class="flex gap-2">
            <button
              onclick={polygonContextMenu.mode === 'save' ? polygonContextSaveArea : polygonContextUpdateArea}
              disabled={!polygonContextMenu.inputName.trim()}
              class="flex-1 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-xs font-medium"
            >SAVE</button>
            <button onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'menu' }} class="px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs">BACK</button>
          </div>
        </div>
      {/if}
    </div>
  {/if}


  <!-- Category Filter -->
  <div class="absolute bottom-6 right-6" style="z-index: 1000; max-width: 280px;">
    <CategoryFilter {businesses} bind:enabledCategories bind:showContactsOnly bind:heatmapEnabled bind:heatmapCategory />
  </div>

  <!-- Legend -->
  <div class="absolute bottom-6 left-6 bg-gray-900 border-2 border-gray-700 p-3 shadow-lg" style="z-index: 1000;">
    <div class="text-xs font-bold text-gray-400 mb-2 tracking-wide">LEGEND</div>
    <div class="flex flex-col gap-1.5">
      {#each BUSINESS_CATEGORIES as category}
        <div class="flex items-center gap-2">
          <div class="w-3 h-3 border border-gray-700" style="background-color: {category.color}"></div>
          <span class="text-xs text-gray-300">{category.name}</span>
        </div>
      {/each}
    </div>
  </div>
  </div>
</div>

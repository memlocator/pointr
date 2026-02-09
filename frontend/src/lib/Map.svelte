<script>
  import { onMount } from 'svelte'
  import maplibregl from 'maplibre-gl'
  import MapboxDraw from '@mapbox/mapbox-gl-draw'
  import circle from '@turf/circle'
  import { BUSINESS_CATEGORIES, generateColorExpression, generateIconExpression } from './businessCategories.js'
  import { getSourceColor } from './sourceColors.js'
  import { apiFetch } from './api.js'
  import { loadFromStorage, saveToStorage } from './stores/persistence.js'
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
    routeData = $bindable(null),
    routeType = $bindable('road'),
    showCustomAreas = $bindable(true),
    pickingStop = $bindable(null),
    enabledSources = $bindable(null)
  } = $props()
  let mapContainer
  let map
  let draw
  let isEnriching = $state(false)
  let mapLoaded = $state(false)
  let stopMarkers = []
  let isDraggingMarker = false
  let dragIndex = null
  let suppressNextRouteFit = false
  let syncStopMarkersOnMove = null

  function isAutoNamedStop(name) {
    if (!name) return false
    return /^-?\\d+(\\.\\d+)?,\\s*-?\\d+(\\.\\d+)?$/.test(name)
  }

  function gradientColor(index, total, startHex, endHex) {
    if (total <= 1) return startHex
    const t = index / (total - 1)
    const s = startHex.replace('#', '')
    const e = endHex.replace('#', '')
    const sr = parseInt(s.slice(0, 2), 16)
    const sg = parseInt(s.slice(2, 4), 16)
    const sb = parseInt(s.slice(4, 6), 16)
    const er = parseInt(e.slice(0, 2), 16)
    const eg = parseInt(e.slice(2, 4), 16)
    const eb = parseInt(e.slice(4, 6), 16)
    const r = Math.round(sr + (er - sr) * t)
    const g = Math.round(sg + (eg - sg) * t)
    const b = Math.round(sb + (eb - sb) * t)
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
  }

  function attachMarkerDragHandlers(marker, index) {
    const el = marker.getElement()
    el.style.touchAction = 'none'

    el.addEventListener('pointerdown', (e) => {
      e.preventDefault()
      e.stopPropagation()

      isDraggingMarker = true
      dragIndex = index
      map.dragPan.disable()
      map.getCanvas().style.cursor = 'grabbing'

      const containerRect = map.getCanvasContainer().getBoundingClientRect()
      const markerPoint = map.project(marker.getLngLat())
      const pointerPoint = {
        x: e.clientX - containerRect.left,
        y: e.clientY - containerRect.top
      }
      const dragOffset = {
        x: pointerPoint.x - markerPoint.x,
        y: pointerPoint.y - markerPoint.y
      }

      const onMove = (ev) => {
        const rect = map.getCanvasContainer().getBoundingClientRect()
        const x = ev.clientX - rect.left - dragOffset.x
        const y = ev.clientY - rect.top - dragOffset.y
        const pt = map.unproject([x, y])
        marker.setLngLat([pt.lng, pt.lat])
      }

      const onUp = () => {
        const lngLat = marker.getLngLat()
        const lat = Number(lngLat.lat)
        const lng = Number(lngLat.lng)
        const prev = stops[index]
        const name = isAutoNamedStop(prev?.name)
          ? `${lat.toFixed(4)}, ${lng.toFixed(4)}`
          : (prev?.name || `${lat.toFixed(4)}, ${lng.toFixed(4)}`)
        suppressNextRouteFit = true
        stops = stops.map((s, i) => i === index ? { ...s, lat, lng, name } : s)
        isDraggingMarker = false
        dragIndex = null
        map.dragPan.enable()
        map.getCanvas().style.cursor = ''
        el.removeEventListener('pointermove', onMove)
        el.removeEventListener('pointerup', onUp)
        el.removeEventListener('pointercancel', onUp)
        try { el.releasePointerCapture(e.pointerId) } catch {}
      }
      el.setPointerCapture(e.pointerId)
      el.addEventListener('pointermove', onMove)
      el.addEventListener('pointerup', onUp)
      el.addEventListener('pointercancel', onUp)
    }, { capture: true })
  }
  let lastRoutePolygonId = null

  // Custom areas (intersecting selection) persisted locally
  let customAreas = $state(loadFromStorage('customAreas', []))

  // Custom POI form (right-click)
  let poiForm = $state(null) // { lat, lng, x, y } or null
  let poiSavedToast = $state(false)
  let nearbyRegions = $state([])
  let poiName = $state('')
  let poiCategory = $state(BUSINESS_CATEGORIES[0].name)
  let poiDescription = $state('')
  let poiPhone = $state('')
  let poiWebsite = $state('')
  let poiContextMenu = $state(null) // { poiId, poiName, poiCategory, x, y, mode: 'view' | 'edit', inputName, inputCategory }
  let detailModal = $state(null) // entity object for DetailModal
  let lastEnrichPolygons = $state([]) // array of polygons used to fetch intersecting areas

  // Tracks which draw feature IDs have been saved as areas (session only)
  let drawnPolygonSaves = $state({}) // { [drawFeatureId]: { id, name } }

  // Polygon right-click context menu
  let polygonContextMenu = $state(null) // { featureId, coordinates, x, y, mode, inputName, inputDescription }

  // Filter businesses based on enabled categories and contact info
  let filteredBusinesses = $derived.by(() => {
    // Force tracking of enabledCategories object
    const enabled = enabledCategories
    const sources = enabledSources
    return businesses.filter(business => {
      // Filter by source toggle
      if (sources && sources.length > 0 && !sources.includes(business.source || 'osm')) return false

      // Filter by category (also match custom POIs where type === category name)
      const category = BUSINESS_CATEGORIES.find(cat =>
        cat.types.includes(business.type) || cat.name === business.type
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
        cat.types.includes(business.type) || cat.name === business.type
      )
      return category?.name === heatmapCategory
    })
  })

  function syncMapSource() {
    if (!mapLoaded || !map || !map.getSource('businesses')) return
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
          source_color: getSourceColor(business.source || 'osm'),
          id: business.id || '',
          description: business.description || ''
        }
      }))
    }
    map.getSource('businesses').setData(geojson)
  }

  // Update map when filtered businesses change
  $effect(() => {
    // Explicitly track state to ensure reactivity with $bindable props
    const categories = enabledCategories
    const _b = businesses

    syncMapSource()
  })

  $effect(() => {
    saveToStorage('customAreas', customAreas)
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
    const isFlight = routeType === 'flight' || routeData?.route_type === 'flight' || routeData?.duration_seconds == null
    const flightCoords = isFlight
      ? stops
        .map((s) => {
          if (s?.lat == null || s?.lng == null) return null
          const lat = Number(s.lat)
          const lng = Number(s.lng)
          if (Number.isNaN(lat) || Number.isNaN(lng)) return null
          return [lng, lat]
        })
        .filter(Boolean)
      : null

    if ((isFlight && flightCoords && flightCoords.length >= 2) || (routeData && routeData.geometry)) {
      routeSource.setData({
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: isFlight && flightCoords && flightCoords.length >= 2
            ? { type: 'LineString', coordinates: flightCoords }
            : routeData.geometry
        }]
      })

      // Only fit bounds on initial route calculation, not on drag-triggered recalculation
      if (!isDraggingMarker && !suppressNextRouteFit) {
        const coordinates = isFlight && flightCoords && flightCoords.length >= 2
          ? flightCoords
          : routeData.geometry.coordinates
        const bounds = coordinates.reduce((bounds, coord) => {
          return bounds.extend(coord)
        }, new maplibregl.LngLatBounds(coordinates[0], coordinates[0]))

        map.fitBounds(bounds, {
          padding: { top: 100, bottom: 100, left: 400, right: 100 }
        })
      } else if (suppressNextRouteFit) {
        suppressNextRouteFit = false
      }
    } else {
      routeSource.setData({ type: 'FeatureCollection', features: [] })
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
      const pos = stop
      const color = gradientColor(i, stops.length, '#22c55e', '#ef4444')

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

        if (pos?.lat != null) {
          el.style.pointerEvents = 'auto'
          el.style.zIndex = '9999'
          el.addEventListener('pointerdown', (e) => e.stopPropagation(), { capture: true })
          const lat = Number(pos.lat)
          const lng = Number(pos.lng)
          const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
            .setLngLat([lng, lat])
            .addTo(map)
          attachMarkerDragHandlers(marker, i)
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
          el.appendChild(dot)
        } else if (!stop.description && badge) {
          badge.remove()
        }
        if (pos?.lat != null && !isDraggingMarker) {
          const lat = Number(pos.lat)
          const lng = Number(pos.lng)
          stopMarkers[i].setLngLat([lng, lat])
        }
      }
    })
  })

  // Sync custom areas to map
  $effect(() => {
    if (!mapLoaded || !map) return
    const source = map.getSource('custom-areas')
    if (!source) return
    if (!showCustomAreas) {
      source.setData({ type: 'FeatureCollection', features: [] })
      try {
        map.setLayoutProperty('custom-areas-fill', 'visibility', 'none')
        map.setLayoutProperty('custom-areas-line', 'visibility', 'none')
        map.setLayoutProperty('custom-areas-label', 'visibility', 'none')
      } catch {}
      return
    }
    try {
      map.setLayoutProperty('custom-areas-fill', 'visibility', 'visible')
      map.setLayoutProperty('custom-areas-line', 'visibility', 'visible')
      map.setLayoutProperty('custom-areas-label', 'visibility', 'visible')
    } catch {}
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

  // Load category icons once map is ready
  $effect(() => {
    if (mapLoaded) {
      loadCategoryIcons()
    }
  })

  // Change cursor when in stop-pick mode
  $effect(() => {
    if (!map || !mapLoaded) return
    map.getCanvas().style.cursor = pickingStop !== null ? 'crosshair' : ''
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

  function downloadJSON(obj, filename) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
    URL.revokeObjectURL(a.href)
  }

  function exportPolygons() {
    const fc = { type: 'FeatureCollection', features: draw.getAll().features }
    downloadJSON(fc, 'polygons.geojson')
  }

  function exportCustomPOIs() {
    const fc = {
      type: 'FeatureCollection',
      features: businesses
        .filter(b => b.source === 'custom')
        .map(b => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [b.lng, b.lat] },
          properties: { name: b.name, category: b.type, description: b.description || '' }
        }))
    }
    downloadJSON(fc, 'custom-pois.geojson')
  }

  async function importGeoJSON(file) {
    const text = await file.text()
    try {
      const fc = JSON.parse(text)
      if (fc.type !== 'FeatureCollection') return alert('Expected a GeoJSON FeatureCollection')

      const polygonFeatures = fc.features.filter(f =>
        f.geometry?.type === 'Polygon' || f.geometry?.type === 'MultiPolygon'
      )
      const pointFeatures = fc.features.filter(f => f.geometry?.type === 'Point')

      if (polygonFeatures.length > 0) {
        draw.add({ type: 'FeatureCollection', features: polygonFeatures })
        savePolygons()
      }

      if (pointFeatures.length > 0) {
        for (const f of pointFeatures) {
          const [lng, lat] = f.geometry.coordinates
          const { name = 'Imported', category = 'Other', description = '' } = f.properties || {}
          try {
            const resp = await apiFetch('/api/pois', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ name, category, description, lat, lng, tags: {} })
            })
            if (resp.ok) {
              const poi = await resp.json()
              businesses = [...businesses, { name: poi.name, lat: poi.lat, lng: poi.lng, type: poi.category, address: '', phone: '', website: '', email: '', source: 'custom', id: poi.id, description: poi.description || '' }]
            }
          } catch {}
        }
      }
    } catch {
      alert('Invalid GeoJSON file')
    }
  }

  function clearAll() {
    if (draw) {
      draw.deleteAll()
    }
    polygons = []
    customAreas = []
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

  export function clearAllState() {
    clearAll()
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
          const circlePolygon = circle(circleCenter, Math.max(0.001, radius), options)

          map.getSource('preview-circle').setData(circlePolygon)
        }
        map.on('mousemove', circleMoveHandler)
      } else {
        // Second click: finalize circle
        const currentPoint = [e.lngLat.lng, e.lngLat.lat]
        const radius = haversineDistance(circleCenter, currentPoint)

        if (radius > 0.01) { // minimum radius 10 meters
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
    nearbyRegions = []
  }

  async function enrichCoordinates(coordinates) {
    const response = await apiFetch('/api/map/enrich', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ coordinates, sources: enabledSources ?? [] })
    })
    if (!response.ok) throw new Error('Failed to enrich polygon')
    const data = await response.json()
    if (data.error) {
      console.warn('Enrichment error:', data.error)
      alert(data.error)
    }
    return {
      businesses: data.businesses || [],
      nearby: data.nearby_features || []
    }
  }

  async function enrichPolygons() {
    const data = draw.getAll()
    const hasDrawn = data.features?.some(f => f.geometry.type === 'Polygon')
    if (!hasDrawn && customAreas.length === 0) {
      alert('Please draw a polygon first!')
      return
    }
    isEnriching = true
    nearbyRegions = []
    clearBusinessMarkers()
    try {
      const allBusinesses = []
      const nearby = new Set()
      const polygonsToQuery = []
      for (const feature of data.features) {
        if (feature.geometry.type !== 'Polygon') continue
        const coordinates = feature.geometry.coordinates[0].map(([lng, lat]) => ({ lat, lng }))
        polygonsToQuery.push(coordinates)
        const result = await enrichCoordinates(coordinates)
        allBusinesses.push(...result.businesses)
        result.nearby.forEach((name) => nearby.add(name))
      }
      for (const area of customAreas) {
        const result = await enrichCoordinates(area.coordinates)
        allBusinesses.push(...result.businesses)
        result.nearby.forEach((name) => nearby.add(name))
      }
      businesses = allBusinesses
      nearbyRegions = Array.from(nearby)
      lastEnrichPolygons = polygonsToQuery
      await loadIntersectingAreasForPolygons(polygonsToQuery)
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

  async function enrichAlongRoute(polygonCoords) {
    // Remove previous unsaved route polygon
    if (lastRoutePolygonId && !drawnPolygonSaves[lastRoutePolygonId]) {
      draw.delete(lastRoutePolygonId)
      savePolygons()
    }

    // Add buffer polygon to draw so it can be saved/edited like any other polygon
    const feature = {
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [polygonCoords.map(c => [c.lng, c.lat])]
      }
    }
    const ids = draw.add(feature)
    lastRoutePolygonId = ids[0]
    savePolygons()

    // Show hatch overlay on the unsaved buffer polygon
    map.getSource('route-buffer-overlay')?.setData({ type: 'FeatureCollection', features: [{ ...feature, id: lastRoutePolygonId }] })

    isEnriching = true
    nearbyRegions = []
    try {
      const result = await enrichCoordinates(polygonCoords)
      businesses = mergeBusinesses(businesses, result.businesses)
      nearbyRegions = result.nearby
      lastEnrichPolygons = [polygonCoords]
      await loadIntersectingAreasForPolygons([polygonCoords])
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
    nearbyRegions = []
    try {
      const result = await enrichCoordinates(coords)
      businesses = mergeBusinesses(businesses, result.businesses)
      nearbyRegions = result.nearby
      lastEnrichPolygons = [coords]
      await loadIntersectingAreasForPolygons([coords])
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
      const resp = await apiFetch('/api/areas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '', coordinates: polygonContextMenu.coordinates })
      })
      if (!resp.ok) throw new Error('Failed to save area')
      const saved = await resp.json()
      drawnPolygonSaves = { ...drawnPolygonSaves, [featureId]: { id: saved.id, name: saved.name } }
      // Clear hatch overlay if this was the route buffer polygon
      if (featureId === lastRoutePolygonId) {
        lastRoutePolygonId = null
        map.getSource('route-buffer-overlay')?.setData({ type: 'FeatureCollection', features: [] })
      }
      // Remove the draw feature — it's now represented by the amber area overlay
      draw.delete(featureId)
      savePolygons()
      if (lastEnrichPolygons && lastEnrichPolygons.length > 0) {
        await loadIntersectingAreasForPolygons(lastEnrichPolygons)
        if (!customAreas.find(a => a.id === saved.id)) {
          customAreas = [...customAreas, saved]
        }
      } else {
        customAreas = [...customAreas, saved]
      }
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
      const resp = await apiFetch(`/api/areas/${areaId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' })
      })
      if (!resp.ok) throw new Error('Failed to update area')
      drawnPolygonSaves = { ...drawnPolygonSaves, [polygonContextMenu.featureId]: { id: areaId, name: polygonContextMenu.inputName.trim() } }
      if (lastEnrichPolygons && lastEnrichPolygons.length > 0) {
        await loadIntersectingAreasForPolygons(lastEnrichPolygons)
      } else {
        customAreas = customAreas.map(a => a.id === areaId ? { ...a, name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' } : a)
      }
    } catch (e) {
      alert('Error updating area: ' + e.message)
    }
    polygonContextMenu = null
  }

  async function deleteCustomArea(id) {
    try {
      const resp = await apiFetch(`/api/areas/${id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('Failed to delete area')
      drawnPolygonSaves = Object.fromEntries(Object.entries(drawnPolygonSaves).filter(([, v]) => v.id !== id))
      customAreas = customAreas.filter(a => a.id !== id)
      if (lastEnrichPolygons && lastEnrichPolygons.length > 0) {
        await loadIntersectingAreasForPolygons(lastEnrichPolygons)
      }
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

  async function loadIntersectingAreasForPolygons(polygons) {
    if (!polygons || polygons.length === 0) {
      customAreas = []
      return
    }
    try {
      const seen = new Set()
      const merged = []
      for (const coords of polygons) {
        const resp = await apiFetch('/api/areas/intersect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ coordinates: coords, sources: [] })
        })
        if (!resp.ok) continue
        const areas = await resp.json()
        for (const area of areas) {
          if (seen.has(area.id)) continue
          seen.add(area.id)
          merged.push(area)
        }
      }
      customAreas = merged
    } catch (e) {
      console.warn('Failed to load intersecting areas:', e)
    }
  }

  async function saveCustomPOI() {
    if (!poiName.trim() || !poiForm) return
    try {
      const resp = await apiFetch('/api/pois', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: poiName.trim(), category: poiCategory, description: poiDescription, phone: poiPhone, website: poiWebsite, lat: poiForm.lat, lng: poiForm.lng, tags: {} })
      })
      if (!resp.ok) throw new Error('Failed to save POI')
      const poi = await resp.json()
      businesses = [...businesses, { name: poi.name, lat: poi.lat, lng: poi.lng, type: poi.category, address: '', phone: poi.phone || '', website: poi.website || '', email: '', source: 'custom', id: poi.id, description: poi.description || '' }]
      syncMapSource()
      poiSavedToast = true
      setTimeout(() => { poiSavedToast = false }, 2500)
    } catch (e) {
      alert('Error saving POI: ' + e.message)
    }
    poiForm = null
    poiPhone = ''
    poiWebsite = ''
  }

  async function deleteCustomPOI(id) {
    try {
      const resp = await apiFetch(`/api/pois/${id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('Failed to delete POI')
      businesses = businesses.filter(b => b.id !== id)
      syncMapSource()
    } catch (e) {
      alert('Error deleting POI: ' + e.message)
    }
    poiContextMenu = null
  }

  async function updateCustomPOI() {
    if (!poiContextMenu?.inputName?.trim()) return
    try {
      const resp = await apiFetch(`/api/pois/${poiContextMenu.poiId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: poiContextMenu.inputName.trim(), category: poiContextMenu.inputCategory, description: poiContextMenu.inputDescription || '', phone: poiContextMenu.inputPhone || '', website: poiContextMenu.inputWebsite || '' })
      })
      if (!resp.ok) throw new Error('Failed to update POI')
      businesses = businesses.map(b => b.id === poiContextMenu.poiId
        ? { ...b, name: poiContextMenu.inputName.trim(), type: poiContextMenu.inputCategory, description: poiContextMenu.inputDescription || '', phone: poiContextMenu.inputPhone || '', website: poiContextMenu.inputWebsite || '' }
        : b)
      syncMapSource()
    } catch (e) {
      alert('Error updating POI: ' + e.message)
    }
    poiContextMenu = null
  }

  async function saveCustomArea() {
    if (!areaName.trim() || !areaPrompt) return
    try {
      const resp = await apiFetch('/api/areas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: areaName.trim(), coordinates: areaPrompt.coordinates })
      })
      if (!resp.ok) throw new Error('Failed to save area')
      const saved = await resp.json()
      if (lastEnrichPolygons && lastEnrichPolygons.length > 0) {
        await loadIntersectingAreasForPolygons(lastEnrichPolygons)
      } else {
        customAreas = [...customAreas, saved]
      }
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

    syncStopMarkersOnMove = () => {
      if (!routingEnabled || isDraggingMarker) return
      stops.forEach((stop, i) => {
        if (!stopMarkers[i] || stop?.lat == null || stop?.lng == null) return
        const lat = Number(stop.lat)
        const lng = Number(stop.lng)
        if (Number.isNaN(lat) || Number.isNaN(lng)) return
        stopMarkers[i].setLngLat([lng, lat])
      })
    }
    map.on('move', syncStopMarkersOnMove)

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
    map.on('draw.update', (e) => {
      savePolygons()
      // Sync route buffer hatch overlay if its geometry changed
      if (lastRoutePolygonId && e.features.some(f => f.id === lastRoutePolygonId)) {
        const f = draw.get(lastRoutePolygonId)
        if (f) map.getSource('route-buffer-overlay')?.setData({ type: 'FeatureCollection', features: [f] })
      }
    })
    map.on('draw.delete', (e) => {
      savePolygons()
      // Clear overlay if route buffer was deleted
      if (lastRoutePolygonId && e.features.some(f => f.id === lastRoutePolygonId)) {
        lastRoutePolygonId = null
        map.getSource('route-buffer-overlay')?.setData({ type: 'FeatureCollection', features: [] })
      }
    })

    // Handle Ctrl key for enabling/disabling draw interaction
    let ctrlPressed = false
    const handleKeyDown = (e) => {
      if (e.key === 'Control' || e.key === 'Meta') {
        ctrlPressed = true
      }
      if ((e.key === 'Delete' || e.key === 'Backspace') && polygonContextMenu?.mode === 'menu') {
        deletePolygon(polygonContextMenu.featureId)
        polygonContextMenu = null
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
      // Create diagonal hatch pattern for route buffer overlay
      const sz = 10
      const patternData = new Uint8Array(sz * sz * 4)
      for (let y = 0; y < sz; y++) {
        for (let x = 0; x < sz; x++) {
          const i = (y * sz + x) * 4
          const onLine = ((x + y) % sz) < 2
          patternData[i] = 249; patternData[i+1] = 115; patternData[i+2] = 22
          patternData[i+3] = onLine ? 100 : 0
        }
      }
      map.addImage('route-hatch', { width: sz, height: sz, data: patternData })

      // Add route buffer overlay source (for hatch pattern on unsaved buffer polygon)
      map.addSource('route-buffer-overlay', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
      })
      map.addLayer({
        id: 'route-buffer-hatch',
        type: 'fill',
        source: 'route-buffer-overlay',
        paint: { 'fill-pattern': 'route-buffer-hatch' }
      })
      map.addLayer({
        id: 'route-buffer-hatch-outline',
        type: 'line',
        source: 'route-buffer-overlay',
        paint: { 'line-color': '#f97316', 'line-width': 1.5, 'line-opacity': 0.7, 'line-dasharray': [4, 3] }
      })

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

      // Add circle layer for non-custom businesses (OSM + additional DBs)
      map.addLayer({
        id: 'businesses-layer',
        type: 'circle',
        source: 'businesses',
        filter: ['!=', ['get', 'source'], 'custom'],
        paint: {
          'circle-radius': 6,
          'circle-color': generateColorExpression(),
          'circle-stroke-width': 2.5,
          'circle-stroke-color': ['get', 'source_color']
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
      function sourceBadgeHtml(src) {
        if (src === 'osm') return `<span style="font-size:10px;padding:1px 5px;background:#f3f4f6;color:#6b7280">${src.toUpperCase()}</span>`
        if (src === 'custom') return `<span style="font-size:10px;padding:1px 5px;background:#fef3c7;color:#b45309">${src.toUpperCase()}</span>`
        return `<span style="font-size:10px;padding:1px 5px;background:#dbeafe;color:#1d4ed8">${src}</span>`
      }

      const showPopup = (e) => {
        const coordinates = e.features[0].geometry.coordinates.slice()
        const { name, type, address, phone, website, email, source, description } = e.features[0].properties

        new maplibregl.Popup()
          .setLngLat(coordinates)
          .setHTML(`
            <div class="p-3 min-w-[200px]">
              <div class="flex items-center justify-between mb-1">
                <h3 class="font-bold text-gray-900">${name}</h3>
                ${sourceBadgeHtml(source || 'osm')}
              </div>
              <p class="text-xs text-gray-600 mb-2">${type}</p>
              ${description ? `<p class="text-xs text-gray-600 italic mb-2">${description}</p>` : ''}
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
        const name = `${lat.toFixed(4)}, ${lng.toFixed(4)}`

        if (pickingStop !== null) {
          // Set coords on the targeted stop
          stops = stops.map((s, i) => i === pickingStop ? { ...s, lat, lng, name } : s)
          pickingStop = null
          map.getCanvas().style.cursor = ''
        } else if (e.originalEvent.altKey && stops.length < 10) {
          // Alt+click adds a new stop
          stops = [...stops, { lat, lng, name, description: '' }]
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
        const altClick = e.originalEvent.altKey

        // Check custom POI markers first
        const poiFeatures = map.queryRenderedFeatures(e.point, { layers: ['businesses-layer-custom'] })
        if (poiFeatures.length > 0 && !altClick) {
          const { name, type, id, description: poiDesc, phone: poiPhone_, website: poiWebsite_ } = poiFeatures[0].properties
          poiContextMenu = { poiId: id, poiName: name, poiCategory: type, poiDescription: poiDesc || '', poiPhone: poiPhone_ || '', poiWebsite: poiWebsite_ || '', lngLat: [e.lngLat.lng, e.lngLat.lat], x: e.point.x, y: e.point.y, mode: 'view' }
          poiForm = null
          polygonContextMenu = null
          return
        }

        // Alt+right-click always opens POI form, skipping area/polygon checks
        if (altClick) {
          poiForm = { lat: e.lngLat.lat, lng: e.lngLat.lng, x: e.point.x, y: e.point.y }
          poiName = ''
          poiCategory = BUSINESS_CATEGORIES[0].name
          poiDescription = ''
          poiPhone = ''
          poiWebsite = ''
          polygonContextMenu = null
          poiContextMenu = null
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
          poiPhone = ''
          poiWebsite = ''
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
      if (syncStopMarkersOnMove) {
        map.off('move', syncStopMarkersOnMove)
      }
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
    bind:routeType
    bind:pickingStop
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
    {businesses}
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
    onExportPolygons={exportPolygons}
    onExportPOIs={exportCustomPOIs}
    onImport={importGeoJSON}
  />

  <!-- Custom POI form (right-click) -->
  {#if poiForm}
    <div
      class="absolute bg-gray-900 border-2 border-gray-700 p-3 shadow-lg w-56"
      style="z-index: 1001; left: {Math.min(poiForm.x, mapContainer?.clientWidth - 240)}px; top: {Math.min(poiForm.y, mapContainer?.clientHeight - 160)}px;"
    >
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-bold text-gray-400 tracking-wide">ADD CUSTOM POI</span>
        <button onclick={() => poiForm = null} class="text-gray-500 hover:text-gray-300">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2 L10 10 M10 2 L2 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
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
      <input
        type="tel"
        bind:value={poiPhone}
        placeholder="Phone (optional)"
        class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-orange-500 focus:outline-none mb-2"
      />
      <input
        type="url"
        bind:value={poiWebsite}
        placeholder="Website (optional)"
        class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-orange-500 focus:outline-none mb-2"
      />
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
          onclick={() => { detailModal = { type: 'poi', id: poiContextMenu.poiId, name: poiContextMenu.poiName, category: poiContextMenu.poiCategory, description: poiContextMenu.poiDescription, phone: poiContextMenu.poiPhone, website: poiContextMenu.poiWebsite, lat: poiContextMenu.lngLat[1], lng: poiContextMenu.lngLat[0] }; poiContextMenu = null }}
          class="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-gray-800 flex items-center gap-2"
        ><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg> View Details</button>
        <button
          onclick={() => poiContextMenu = { ...poiContextMenu, mode: 'edit', inputName: poiContextMenu.poiName, inputCategory: poiContextMenu.poiCategory, inputDescription: poiContextMenu.poiDescription, inputPhone: poiContextMenu.poiPhone, inputWebsite: poiContextMenu.poiWebsite }}
          class="w-full px-3 py-2 text-left text-xs text-amber-400 hover:bg-gray-800 flex items-center gap-2"
        ><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit POI</button>
        <button
          onclick={() => deleteCustomPOI(poiContextMenu.poiId)}
          class="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-gray-800 flex items-center gap-2"
        ><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg> Delete POI</button>
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
          <input
            type="tel"
            bind:value={poiContextMenu.inputPhone}
            placeholder="Phone (optional)"
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-amber-500 focus:outline-none mb-2"
          />
          <input
            type="url"
            bind:value={poiContextMenu.inputWebsite}
            placeholder="Website (optional)"
            class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs placeholder-gray-500 focus:border-amber-500 focus:outline-none mb-2"
          />
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
          const resp = await apiFetch(`/api/pois/${detailModal.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: updated.name, category: updated.category, description: updated.description, phone: updated.phone || '', website: updated.website || '' })
          })
          if (!resp.ok) { alert('Failed to update POI'); return }
          businesses = businesses.map(b => b.id === detailModal.id
            ? { ...b, name: updated.name, type: updated.category, description: updated.description, phone: updated.phone || '', website: updated.website || '' }
            : b)
          detailModal = { ...detailModal, ...updated }
        } else {
          const resp = await apiFetch(`/api/areas/${detailModal.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: updated.name, description: updated.description })
          })
          if (!resp.ok) { alert('Failed to update area'); return }
          if (lastEnrichPolygons && lastEnrichPolygons.length > 0) {
            await loadIntersectingAreasForPolygons(lastEnrichPolygons)
          } else {
            customAreas = customAreas.map(a => a.id === detailModal.id ? { ...a, name: updated.name, description: updated.description } : a)
          }
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
            nearbyRegions = []
            try {
              const result = await enrichCoordinates(area.coordinates)
              businesses = mergeBusinesses(businesses, result.businesses)
              nearbyRegions = result.nearby
              lastEnrichPolygons = [area.coordinates]
              await loadIntersectingAreasForPolygons([area.coordinates])
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
        ><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg> View Details</button>
        <button
          onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'saved-area-edit', inputName: polygonContextMenu.areaName, inputDescription: polygonContextMenu.areaDescription }}
          class="w-full px-3 py-2 text-left text-xs text-amber-400 hover:bg-gray-800 flex items-center gap-2"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit Area
        </button>
        <button
          onclick={() => {
            customAreas = customAreas.filter(a => a.id !== polygonContextMenu.areaId)
            polygonContextMenu = null
          }}
          class="w-full px-3 py-2 text-left text-xs text-orange-400 hover:bg-gray-800 flex items-center gap-2"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg> Remove from map
        </button>
        <button
          onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'confirm-delete-area' }}
          class="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-gray-800 flex items-center gap-2"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg> Delete from DB
        </button>
        <button onclick={() => polygonContextMenu = null} class="w-full px-3 py-2 text-left text-xs text-gray-500 hover:bg-gray-800">Cancel</button>
      {:else if polygonContextMenu.mode === 'confirm-delete-area'}
        <div class="p-3">
          <div class="flex items-center gap-2 mb-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            <span class="text-xs font-bold text-red-400 tracking-wide">DELETE AREA</span>
          </div>
          <p class="text-xs text-gray-300 mb-1">Permanently delete <span class="font-semibold text-white">{polygonContextMenu.areaName}</span> from the database?</p>
          <p class="text-xs text-gray-500 mb-3">This cannot be undone. The polygon will be removed from all views and cannot be recovered.</p>
          <div class="flex gap-2">
            <button
              onclick={() => deleteCustomArea(polygonContextMenu.areaId)}
              class="flex-1 py-1.5 bg-red-700 hover:bg-red-600 text-white text-xs font-medium"
            >DELETE</button>
            <button onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'saved-area' }} class="px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs">BACK</button>
          </div>
        </div>
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
                await apiFetch(`/api/areas/${polygonContextMenu.areaId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' }) })
                if (lastEnrichPolygons && lastEnrichPolygons.length > 0) {
                  await loadIntersectingAreasForPolygons(lastEnrichPolygons)
                } else {
                  customAreas = customAreas.map(a => a.id === polygonContextMenu.areaId ? { ...a, name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' } : a)
                }
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
                  const resp = await apiFetch(`/api/areas/${polygonContextMenu.areaId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' }) })
                  if (!resp.ok) throw new Error('Failed to update area')
                  if (lastEnrichPolygons && lastEnrichPolygons.length > 0) {
                    await loadIntersectingAreasForPolygons(lastEnrichPolygons)
                  } else {
                    customAreas = customAreas.map(a => a.id === polygonContextMenu.areaId ? { ...a, name: polygonContextMenu.inputName.trim(), description: polygonContextMenu.inputDescription || '' } : a)
                  }
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
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit Area
          </button>
          <button
            onclick={() => deleteCustomArea(saved.id)}
            class="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-gray-800 flex items-center gap-2"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg> Delete Area
          </button>
        {:else}
          <button
            onclick={() => polygonContextMenu = { ...polygonContextMenu, mode: 'save', inputName: '', inputDescription: '' }}
            class="w-full px-3 py-2 text-left text-xs text-amber-400 hover:bg-gray-800 flex items-center gap-2"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg> Save Area
          </button>
        {/if}
        <button
          onclick={() => { deletePolygon(polygonContextMenu.featureId); polygonContextMenu = null }}
          class="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-gray-800 flex items-center gap-2"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg> Delete Polygon
        </button>
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


  <!-- POI saved toast -->
  {#if poiSavedToast}
    <div class="absolute bottom-6 left-1/2 -translate-x-1/2 bg-gray-900 border-2 border-orange-500 px-4 py-2 text-xs text-white font-medium tracking-wide" style="z-index: 2000;">
      POI SAVED
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

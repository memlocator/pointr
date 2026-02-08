<script>
  import { onMount } from 'svelte'
  import maplibregl from 'maplibre-gl'
  import MapboxDraw from '@mapbox/mapbox-gl-draw'
  import circle from '@turf/circle'
  import { BUSINESS_CATEGORIES, generateColorExpression } from './businessCategories.js'
  import LocationSearchBar from './components/LocationSearchBar.svelte'
  import DrawingToolbar from './components/DrawingToolbar.svelte'
  import CategoryFilter from './components/CategoryFilter.svelte'
  import RoutingPanel from './components/RoutingPanel.svelte'

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
    routeStart = $bindable(null),
    routeEnd = $bindable(null),
    routeData = $bindable(null)
  } = $props()
  let mapContainer
  let map
  let draw
  let isEnriching = $state(false)
  let mapLoaded = $state(false)
  let startMarker = null
  let endMarker = null

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
            email: business.email
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

      // Fit map to route bounds
      const coordinates = routeData.geometry.coordinates
      const bounds = coordinates.reduce((bounds, coord) => {
        return bounds.extend(coord)
      }, new maplibregl.LngLatBounds(coordinates[0], coordinates[0]))

      map.fitBounds(bounds, {
        padding: { top: 100, bottom: 100, left: 400, right: 100 }
      })
    } else {
      routeSource.setData({ type: 'FeatureCollection', features: [] })
    }
  })

  // Update draggable markers
  $effect(() => {
    if (!mapLoaded || !map) return

    // Clean up markers if routing is disabled
    if (!routingEnabled) {
      if (startMarker) {
        startMarker.remove()
        startMarker = null
      }
      if (endMarker) {
        endMarker.remove()
        endMarker = null
      }
      return
    }

    // Create or update start marker
    if (routeStart) {
      if (!startMarker) {
        // Create marker element
        const el = document.createElement('div')
        el.className = 'route-marker-start'
        el.style.width = '24px'
        el.style.height = '24px'
        el.style.borderRadius = '50%'
        el.style.backgroundColor = '#22c55e'
        el.style.border = '3px solid white'
        el.style.cursor = 'grab'
        el.style.boxShadow = '0 2px 8px rgba(0,0,0,0.4)'
        el.style.transition = 'transform 0.1s'

        startMarker = new maplibregl.Marker({
          element: el,
          draggable: true,
          anchor: 'center'
        })
          .setLngLat([routeStart.lng, routeStart.lat])
          .addTo(map)

        startMarker.on('dragstart', () => {
          el.style.cursor = 'grabbing'
          el.style.transform = 'scale(1.2)'
          map.dragPan.disable()
        })

        startMarker.on('drag', () => {
          // Visual feedback during drag
        })

        startMarker.on('dragend', () => {
          el.style.cursor = 'grab'
          el.style.transform = 'scale(1)'
          map.dragPan.enable()

          const lngLat = startMarker.getLngLat()
          routeStart = {
            lat: lngLat.lat,
            lng: lngLat.lng,
            name: `${lngLat.lat.toFixed(4)}, ${lngLat.lng.toFixed(4)}`
          }
        })
      } else {
        startMarker.setLngLat([routeStart.lng, routeStart.lat])
      }
    } else if (startMarker) {
      startMarker.remove()
      startMarker = null
    }

    // Create or update end marker
    if (routeEnd) {
      if (!endMarker) {
        // Create marker element
        const el = document.createElement('div')
        el.className = 'route-marker-end'
        el.style.width = '20px'
        el.style.height = '20px'
        el.style.borderRadius = '50%'
        el.style.backgroundColor = '#ef4444'
        el.style.border = '3px solid white'
        el.style.cursor = 'grab'
        el.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)'

        endMarker = new maplibregl.Marker({ element: el, draggable: true })
          .setLngLat([routeEnd.lng, routeEnd.lat])
          .addTo(map)

        endMarker.on('dragend', () => {
          const lngLat = endMarker.getLngLat()
          routeEnd = {
            lat: lngLat.lat,
            lng: lngLat.lng,
            name: `${lngLat.lat.toFixed(4)}, ${lngLat.lng.toFixed(4)}`
          }
        })
      } else {
        endMarker.setLngLat([routeEnd.lng, routeEnd.lat])
      }
    } else if (endMarker) {
      endMarker.remove()
      endMarker = null
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

        // Convert polygon coordinates to lat/lng format
        const coordinates = feature.geometry.coordinates[0].map(([lng, lat]) => ({
          lat,
          lng
        }))

        // Call backend API
        const response = await fetch('http://localhost:8000/api/map/enrich', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ coordinates })
        })

        if (!response.ok) {
          throw new Error('Failed to enrich polygon')
        }

        const enrichmentData = await response.json()
        console.log('Enrichment response:', enrichmentData)

        // Check for errors from enrichment service
        if (enrichmentData.error) {
          console.warn('Enrichment error:', enrichmentData.error)
          alert(`⚠️ ${enrichmentData.error}`)
          // Continue with partial results if any businesses were returned
        }

        console.log(`Received ${enrichmentData.businesses.length} businesses`)
        allBusinesses.push(...enrichmentData.businesses)
      }

      // Update businesses array - the $effect will handle map updates with filtering
      businesses = allBusinesses
      console.log(`Added ${allBusinesses.length} businesses`)
    } catch (error) {
      console.error('Error enriching polygon:', error)
      alert('Failed to enrich polygon: ' + error.message)
    } finally {
      isEnriching = false
    }
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

      // Add circle layer for businesses
      map.addLayer({
        id: 'businesses-layer',
        type: 'circle',
        source: 'businesses',
        paint: {
          'circle-radius': 6,
          'circle-color': generateColorExpression(),
          'circle-stroke-width': 2,
          'circle-stroke-color': '#1f2937'
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

      // Add popup on click - shared handler for all business layers
      const showPopup = (e) => {
        const coordinates = e.features[0].geometry.coordinates.slice()
        const { name, type, address, phone, website, email } = e.features[0].properties

        new maplibregl.Popup()
          .setLngLat(coordinates)
          .setHTML(`
            <div class="p-3 min-w-[200px]">
              <h3 class="font-bold text-gray-900 mb-1">${name}</h3>
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
      map.on('click', 'phone-badge', showPopup)
      map.on('click', 'website-badge', showPopup)
      map.on('click', 'email-badge', showPopup)

      // Handle map clicks for routing
      function handleMapClick(e) {
        if (!routingEnabled) return

        const { lng, lat } = e.lngLat

        if (!routeStart) {
          routeStart = { lat, lng, name: `${lat.toFixed(4)}, ${lng.toFixed(4)}` }
        } else if (!routeEnd) {
          routeEnd = { lat, lng, name: `${lat.toFixed(4)}, ${lng.toFixed(4)}` }
        }
      }

      map.on('click', handleMapClick)

      // Change cursor on hover for all layers
      const layers = ['businesses-layer', 'phone-badge', 'website-badge', 'email-badge']
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
      if (startMarker) {
        startMarker.remove()
        startMarker = null
      }
      if (endMarker) {
        endMarker.remove()
        endMarker = null
      }

      map.remove()
    }
  })
</script>

<div class="relative w-full h-full flex transition-all duration-300">
  <!-- Routing Panel -->
  <RoutingPanel
    bind:routingEnabled
    bind:routeStart
    bind:routeEnd
    bind:routeData
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

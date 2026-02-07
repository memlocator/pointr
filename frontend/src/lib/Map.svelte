<script>
  import { onMount } from 'svelte'
  import maplibregl from 'maplibre-gl'
  import MapboxDraw from '@mapbox/mapbox-gl-draw'
  import circle from '@turf/circle'
  import { BUSINESS_CATEGORIES, generateColorExpression } from './businessCategories.js'
  import LocationSearchBar from './components/LocationSearchBar.svelte'
  import DrawingToolbar from './components/DrawingToolbar.svelte'
  import CategoryFilter from './components/CategoryFilter.svelte'

  let {
    businesses = $bindable([]),
    polygons = $bindable([]),
    mapCenter = $bindable([-0.09, 51.505]),
    mapZoom = $bindable(13),
    currentView = $bindable('map'),
    searchQuery = $bindable(''),
    enabledCategories = $bindable({})
  } = $props()
  let mapContainer
  let map
  let draw
  let isEnriching = $state(false)

  // Filter businesses based on enabled categories
  let filteredBusinesses = $derived.by(() => {
    return businesses.filter(business => {
      const category = BUSINESS_CATEGORIES.find(cat =>
        cat.types.includes(business.type)
      )
      const categoryName = category ? category.name : 'Other'
      return enabledCategories[categoryName]
    })
  })

  // Update map when filtered businesses change
  $effect(() => {
    if (map && map.getSource('businesses')) {
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
          const dx = currentPoint[0] - circleCenter[0]
          const dy = currentPoint[1] - circleCenter[1]
          const radius = Math.sqrt(dx * dx + dy * dy) * 111 // rough conversion to km

          const options = { steps: 64, units: 'kilometers' }
          const circlePolygon = circle(circleCenter, Math.max(0.1, radius), options)

          map.getSource('preview-circle').setData(circlePolygon)
        }
        map.on('mousemove', circleMoveHandler)
      } else {
        // Second click: finalize circle
        const currentPoint = [e.lngLat.lng, e.lngLat.lat]
        const dx = currentPoint[0] - circleCenter[0]
        const dy = currentPoint[1] - circleCenter[1]
        const radius = Math.sqrt(dx * dx + dy * dy) * 111 // rough conversion to km

        if (radius > 0.05) { // minimum radius
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

      // Restore businesses if any exist
      if (businesses.length > 0) {
        const geojson = {
          type: 'FeatureCollection',
          features: businesses.map(business => {
            const properties = {
              name: business.name,
              type: business.type,
              address: business.address
            }
            // Only add contact properties if they have values
            if (business.phone) properties.phone = business.phone
            if (business.website) properties.website = business.website
            if (business.email) properties.email = business.email

            return {
              type: 'Feature',
              geometry: {
                type: 'Point',
                coordinates: [business.lng, business.lat]
              },
              properties
            }
          })
        }
        map.getSource('businesses').setData(geojson)
      }

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
      map.remove()
    }
  })
</script>

<div class="relative w-full h-full">
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
    onStartPolygonDrawing={startPolygonDrawing}
    onStartCircleDrawing={startCircleDrawing}
    onEnrich={enrichPolygons}
    onClearAll={clearAll}
    onGoToPolygon={goToPolygon}
    onDeletePolygon={deletePolygon}
  />

  <!-- Category Filter -->
  <div class="absolute bottom-6 right-6" style="z-index: 1000; max-width: 280px;">
    <CategoryFilter {businesses} bind:enabledCategories />
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

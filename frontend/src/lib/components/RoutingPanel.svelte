<script>
  import LocationSearchBar from './LocationSearchBar.svelte'
  import buffer from '@turf/buffer'
  import simplify from '@turf/simplify'

  let {
    routingEnabled = $bindable(false),
    stops = $bindable([]),
    routeData = $bindable(null),
    pickingStop = $bindable(null),
    onFindAlongRoute = null
  } = $props()

  let routeType = $state('road')  // 'road' | 'flight'
  let isCalculating = $state(false)
  let routeError = $state('')
  let activeSearch = $state(null)   // index of stop with open search bar
  let activeDesc = $state(null)     // index of stop with open description editor
  let bufferMeters = $state(250)
  let isFinding = $state(false)
  let fileInput
  let savedRoutes = $state([])
  let saveRouteName = $state('')
  let showSaved = $state(false)

  // Ensure at least 2 stops exist when panel opens
  $effect(() => {
    if (routingEnabled && stops.length < 2) {
      stops = [
        { lat: null, lng: null, name: '', description: '' },
        { lat: null, lng: null, name: '', description: '' }
      ]
    }
  })

  // Clear route when panel closes
  $effect(() => {
    if (!routingEnabled) {
      stops = []
      routeData = null
      routeError = ''
      activeSearch = null
      activeDesc = null
      pickingStop = null
    }
  })

  // Auto-calculate when all stops have coordinates or route type changes
  $effect(() => {
    if (!routingEnabled) return
    const _type = routeType  // track for reactivity
    const allSet = stops.length >= 2 && stops.every(s => s.lat != null)
    if (allSet) calculateRoute()
  })

  function haversineMeters(lat1, lng1, lat2, lng2) {
    const R = 6371000
    const dLat = (lat2 - lat1) * Math.PI / 180
    const dLng = (lng2 - lng1) * Math.PI / 180
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  }

  async function calculateRoute() {
    isCalculating = true
    routeError = ''
    try {
      if (routeType === 'flight') {
        const coords = stops.map(s => [s.lng, s.lat])
        let dist = 0
        for (let i = 0; i < stops.length - 1; i++) {
          dist += haversineMeters(stops[i].lat, stops[i].lng, stops[i + 1].lat, stops[i + 1].lng)
        }
        routeData = {
          geometry: { type: 'LineString', coordinates: coords },
          distance_meters: dist,
          duration_seconds: null
        }
      } else {
        const response = await fetch('http://localhost:8000/api/route', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: stops.map(s => ({ lat: s.lat, lng: s.lng })) })
        })
        if (!response.ok) throw new Error('Failed to calculate route')
        const data = await response.json()
        if (data.error) { routeError = data.error; routeData = null }
        else routeData = data
      }
    } catch (e) {
      routeError = e.message
      routeData = null
    } finally {
      isCalculating = false
    }
  }

  function addStop() {
    stops = [...stops, { lat: null, lng: null, name: '', description: '' }]
  }

  function removeStop(i) {
    if (stops.length <= 2) return
    stops = stops.filter((_, idx) => idx !== i)
    if (activeSearch === i) activeSearch = null
    if (activeDesc === i) activeDesc = null
  }

  function onStopSelected(i, loc) {
    stops = stops.map((s, idx) => idx === i ? { ...s, lat: loc.lat, lng: loc.lng, name: loc.name } : s)
    activeSearch = null
    if (pickingStop === i) pickingStop = null
  }

  function stopColor(i) {
    if (i === 0) return '#22c55e'
    if (i === stops.length - 1) return '#ef4444'
    return '#f97316'
  }

  function formatDistance(m) {
    return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`
  }
  function formatDuration(s) {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
    return h > 0 ? `${h}h ${m}m` : `${m} min`
  }

  // --- GeoJSON export ---
  function exportLineString() {
    if (!routeData?.geometry) return
    const fc = {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: routeData.geometry,
        properties: {
          stops: stops.map((s, i) => ({ order: i, name: s.name, description: s.description, lat: s.lat, lng: s.lng })),
          distance_meters: routeData.distance_meters,
          duration_seconds: routeData.duration_seconds
        }
      }]
    }
    downloadJSON(fc, 'route-linestring.geojson')
  }

  function exportPoints() {
    const fc = {
      type: 'FeatureCollection',
      features: stops.filter(s => s.lat != null).map((s, i) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [s.lng, s.lat] },
        properties: { order: i, name: s.name, description: s.description }
      }))
    }
    downloadJSON(fc, 'route-stops.geojson')
  }

  function downloadJSON(obj, filename) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
    URL.revokeObjectURL(a.href)
  }

  // --- GeoJSON import ---
  function onImportFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const fc = JSON.parse(ev.target.result)
        let parsed = []
        if (fc.type === 'FeatureCollection') {
          const lineFeature = fc.features.find(f => f.geometry?.type === 'LineString')
          if (lineFeature?.properties?.stops) {
            parsed = lineFeature.properties.stops.map(s => ({
              lat: s.lat, lng: s.lng, name: s.name || '', description: s.description || ''
            }))
          } else {
            // FeatureCollection of Points
            parsed = fc.features
              .filter(f => f.geometry?.type === 'Point')
              .sort((a, b) => (a.properties.order ?? 0) - (b.properties.order ?? 0))
              .map(f => ({
                lat: f.geometry.coordinates[1],
                lng: f.geometry.coordinates[0],
                name: f.properties.name || '',
                description: f.properties.description || ''
              }))
          }
        }
        if (parsed.length >= 2) {
          stops = parsed
          routeData = null
        } else {
          alert('Could not parse stops from GeoJSON (need at least 2)')
        }
      } catch {
        alert('Invalid GeoJSON file')
      }
      e.target.value = ''
    }
    reader.readAsText(file)
  }

  // --- Saved routes ---
  async function loadSavedRoutes() {
    try {
      const res = await fetch('http://localhost:8000/api/routes/saved')
      if (res.ok) savedRoutes = await res.json()
    } catch {}
  }

  async function saveRoute() {
    if (!saveRouteName.trim()) return
    try {
      const res = await fetch('http://localhost:8000/api/routes/saved', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: saveRouteName.trim(), route_type: routeType, stops })
      })
      if (res.ok) {
        saveRouteName = ''
        await loadSavedRoutes()
      }
    } catch {}
  }

  async function deleteSavedRoute(id) {
    try {
      await fetch(`http://localhost:8000/api/routes/saved/${id}`, { method: 'DELETE' })
      savedRoutes = savedRoutes.filter(r => r.id !== id)
    } catch {}
  }

  function loadRoute(route) {
    stops = route.stops
    routeType = route.route_type
    routeData = null
  }

  $effect(() => {
    if (routingEnabled && showSaved) loadSavedRoutes()
  })

  // --- Find along route ---
  function computeRouteBuffer(radiusMeters) {
    // Use route geometry if available, otherwise fall back to straight lines between stops
    const line = routeData?.geometry ?? {
      type: 'LineString',
      coordinates: stops.filter(s => s.lat != null).map(s => [s.lng, s.lat])
    }
    if (line.coordinates.length < 2) return null

    // Simplify to remove redundant collinear points (tolerance in degrees ~= 5m)
    const simplified = simplify(
      { type: 'Feature', geometry: line },
      { tolerance: 0.00005, highQuality: false }
    )

    const buffered = buffer(simplified, radiusMeters, { units: 'meters' })
    if (!buffered?.geometry?.coordinates?.[0]) return null

    return buffered.geometry.coordinates[0].map(([lng, lat]) => ({ lat, lng }))
  }

  async function findAlongRoute() {
    if (!onFindAlongRoute) return
    const polygon = computeRouteBuffer(bufferMeters)
    if (!polygon) return
    isFinding = true
    try { await onFindAlongRoute(polygon) } finally { isFinding = false }
  }
</script>

<div class="h-full bg-gray-900 border-r-2 border-gray-700 shadow-xl z-[999] flex flex-col flex-shrink-0 transition-all duration-300 overflow-hidden"
     style={routingEnabled ? 'width: 320px;' : 'width: 0; border-right-width: 0;'}>
{#if routingEnabled}
  <!-- Header -->
  <div class="px-4 py-3 bg-gray-800 border-b-2 border-gray-700 flex-shrink-0">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class="text-orange-500">
          <circle cx="4" cy="3" r="2" stroke="currentColor" stroke-width="1.5" fill="none"/>
          <circle cx="12" cy="13" r="2" stroke="currentColor" stroke-width="1.5" fill="none"/>
          <path d="M5 4.5 Q8 8, 11 11.5" stroke="currentColor" stroke-width="1.5" fill="none"/>
        </svg>
        <span class="text-white text-sm font-bold tracking-wide">ROUTING</span>
      </div>
      <button onclick={() => routingEnabled = false} class="text-gray-400 hover:text-white transition-colors" title="Close">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
  </div>

  <div class="p-4 space-y-3 flex-1 overflow-y-auto">
    <!-- Pick-from-map hint -->
    {#if pickingStop !== null}
      <div class="px-2 py-1.5 bg-orange-900 border border-orange-700 text-xs text-orange-200 flex items-center justify-between">
        <span>Click map to set stop {pickingStop + 1}</span>
        <button onclick={() => pickingStop = null} class="text-orange-400 hover:text-orange-200">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1 1 L9 9 M9 1 L1 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
      </div>
    {/if}

    <!-- Stops list -->
    <div class="space-y-1">
      {#each stops as stop, i}
        <div class="space-y-1">
          <!-- Stop row -->
          <div class="flex items-center gap-2">
            <!-- Number badge -->
            <div class="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                 style="background-color: {stopColor(i)};">
              {i + 1}
            </div>
            <!-- Name -->
            <span class="flex-1 text-xs truncate {stop.name ? 'text-gray-200' : 'text-gray-500 italic'}">
              {stop.name || 'Not set'}
            </span>
            <!-- Description badge -->
            {#if stop.description}
              <span class="w-2 h-2 rounded-full bg-yellow-400 flex-shrink-0" title="Has description"></span>
            {/if}
            <!-- Description toggle -->
            <button
              onclick={() => activeDesc = activeDesc === i ? null : i}
              class="text-gray-500 hover:text-gray-300 transition-colors flex-shrink-0"
              title="Toggle description"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" class={activeDesc === i ? 'rotate-180' : ''} style="transition: transform 0.15s">
                <path d="M2 4 L6 8 L10 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
            <!-- Search toggle -->
            <button
              onclick={() => activeSearch = activeSearch === i ? null : i}
              class="text-gray-500 hover:text-orange-400 transition-colors flex-shrink-0"
              title="Search location"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </button>
            <!-- Pick from map -->
            <button
              onclick={() => pickingStop = pickingStop === i ? null : i}
              class="transition-colors flex-shrink-0 {pickingStop === i ? 'text-orange-400' : 'text-gray-500 hover:text-orange-400'}"
              title="Set from map"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="10" r="3"/><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
              </svg>
            </button>
            <!-- Remove -->
            {#if stops.length > 2}
              <button onclick={() => removeStop(i)} class="text-gray-600 hover:text-red-400 transition-colors flex-shrink-0" title="Remove stop">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 2 L10 10 M10 2 L2 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </button>
            {/if}
          </div>
          <!-- Search bar (inline) -->
          {#if activeSearch === i}
            <div class="ml-8">
              <LocationSearchBar
                placeholder="Search location..."
                bind:selectedLocation={stops[i]}
                inline={true}
                onLocationSelect={(loc) => onStopSelected(i, loc)}
              />
            </div>
          {/if}
          <!-- Description editor -->
          {#if activeDesc === i}
            <div class="ml-8">
              <textarea
                bind:value={stops[i].description}
                placeholder="Add notes for this stop..."
                rows="2"
                class="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 text-gray-200 text-xs placeholder-gray-600 focus:border-orange-500 focus:outline-none resize-none"
              ></textarea>
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <!-- Add stop -->
    <button
      onclick={addStop}
      class="w-full py-1.5 border border-dashed border-gray-600 hover:border-orange-500 text-gray-500 hover:text-orange-400 text-xs transition-colors"
    >
      + Add stop
    </button>

    <!-- Route type + Calculate -->
    <div class="flex gap-2">
      <select
        bind:value={routeType}
        class="px-2 py-2 bg-gray-800 border border-gray-700 text-gray-300 text-xs focus:border-orange-500 focus:outline-none"
      >
        <option value="road">Road</option>
        <option value="flight">Flight</option>
      </select>
      <button
        onclick={calculateRoute}
        disabled={stops.length < 2 || !stops.every(s => s.lat != null) || isCalculating}
        class="flex-1 px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
      >
        {isCalculating ? 'CALCULATING...' : 'CALCULATE'}
      </button>
    </div>

    <!-- Route info -->
    {#if routeData}
      <div class="p-3 bg-gray-800 border border-gray-700 space-y-2">
        <div class="flex justify-between text-xs">
          <span class="text-gray-400">Distance:</span>
          <span class="text-white font-mono">{formatDistance(routeData.distance_meters)}</span>
        </div>
        {#if routeData.duration_seconds != null}
          <div class="flex justify-between text-xs">
            <span class="text-gray-400">Duration:</span>
            <span class="text-white font-mono">{formatDuration(routeData.duration_seconds)}</span>
          </div>
        {/if}
      </div>

      <!-- Save route -->
      <div class="flex gap-2">
        <input
          type="text"
          bind:value={saveRouteName}
          placeholder="Route name..."
          class="flex-1 px-2 py-1.5 bg-gray-800 border border-gray-700 text-gray-200 text-xs placeholder-gray-600 focus:border-orange-500 focus:outline-none"
          onkeydown={(e) => e.key === 'Enter' && saveRoute()}
        />
        <button
          onclick={saveRoute}
          disabled={!saveRouteName.trim()}
          class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-300 text-xs transition-colors flex items-center gap-1"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          Save
        </button>
      </div>

      <!-- Find along route -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <label class="text-xs font-bold text-gray-400">FIND ALONG ROUTE</label>
          <div class="flex items-center gap-1">
            <input
              type="number"
              min="25"
              max="50000"
              bind:value={bufferMeters}
              class="w-16 px-1.5 py-0.5 bg-gray-800 border border-gray-700 text-gray-300 text-xs text-right focus:border-orange-500 focus:outline-none"
            />
            <span class="text-xs text-gray-500">m</span>
          </div>
        </div>
        <input
          type="range"
          min="25"
          max="1000"
          step="25"
          bind:value={bufferMeters}
          class="w-full accent-orange-500 cursor-pointer"
        />
        <button
          onclick={findAlongRoute}
          disabled={isFinding}
          class="w-full px-3 py-1.5 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-medium transition-colors flex items-center justify-center gap-1.5"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" class={isFinding ? 'animate-spin' : ''}>
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          {isFinding ? 'SEARCHING...' : 'SEARCH'}
        </button>
      </div>

    {/if}

    <!-- Import / Export -->
    <div class="border border-gray-700 divide-y divide-gray-700">
      <div class="px-3 py-2 bg-gray-800">
        <span class="text-xs font-bold text-gray-400 tracking-wide">IMPORT / EXPORT</span>
      </div>
      <div class="p-2 space-y-2">
        <input bind:this={fileInput} type="file" accept=".geojson,.json" class="hidden" onchange={onImportFile} />
        <button
          onclick={() => fileInput.click()}
          class="w-full py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 text-xs transition-colors flex items-center justify-center gap-1.5"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          Import GeoJSON
        </button>
        <div class="flex gap-2">
          <button
            onclick={exportLineString}
            disabled={!routeData}
            class="flex-1 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 border border-gray-700 text-gray-300 text-xs transition-colors flex items-center justify-center gap-1.5"
            title="Export route geometry + stops"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/><path d="M9 18H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/></svg>
            Line
          </button>
          <button
            onclick={exportPoints}
            disabled={!stops.some(s => s.lat != null)}
            class="flex-1 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 border border-gray-700 text-gray-300 text-xs transition-colors flex items-center justify-center gap-1.5"
            title="Export stops as points"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/><path d="M9 18H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/></svg>
            Points
          </button>
        </div>
      </div>
    </div>

    <!-- Saved routes -->
    <div class="border border-gray-700 divide-y divide-gray-700">
      <button
        onclick={() => { showSaved = !showSaved; if (showSaved) loadSavedRoutes() }}
        class="w-full px-3 py-2 bg-gray-800 flex items-center justify-between"
      >
        <span class="text-xs font-bold text-gray-400 tracking-wide">SAVED ROUTES</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" class={showSaved ? 'rotate-180' : ''} style="transition: transform 0.15s">
          <path d="M2 4 L6 8 L10 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
      {#if showSaved}
        <div class="divide-y divide-gray-800">
          {#if savedRoutes.length === 0}
            <div class="px-3 py-2 text-xs text-gray-600 italic">No saved routes</div>
          {:else}
            {#each savedRoutes as route}
              <div class="flex items-center gap-2 px-3 py-2 hover:bg-gray-800">
                <div class="flex-1 min-w-0">
                  <div class="text-xs text-gray-200 truncate">{route.name}</div>
                  <div class="text-xs text-gray-600">{route.route_type} · {route.stops.length} stops</div>
                </div>
                <button onclick={() => loadRoute(route)} class="text-orange-400 hover:text-orange-300 flex-shrink-0" title="Load">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/></svg>
                </button>
                <button onclick={() => deleteSavedRoute(route.id)} class="text-gray-600 hover:text-red-400 flex-shrink-0" title="Delete">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                </button>
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    </div>

    <!-- Error -->
    {#if routeError}
      <div class="p-2 bg-red-900 border border-red-700 text-xs text-red-200">{routeError}</div>
    {/if}

    <!-- Clear -->
    <button
      onclick={() => { stops = [{ lat: null, lng: null, name: '', description: '' }, { lat: null, lng: null, name: '', description: '' }]; routeData = null; routeError = '' }}
      class="w-full px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-medium transition-colors"
    >
      CLEAR
    </button>
  </div>
{/if}
</div>

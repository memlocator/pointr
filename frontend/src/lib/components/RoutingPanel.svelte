<script>
  import LocationSearchBar from './LocationSearchBar.svelte'

  let {
    routingEnabled = $bindable(false),
    routeStart = $bindable(null),
    routeEnd = $bindable(null),
    routeData = $bindable(null)
  } = $props()

  let isCalculating = $state(false)
  let routeError = $state('')

  async function calculateRoute() {
    if (!routeStart || !routeEnd) {
      routeError = 'Please select both start and end points'
      return
    }

    isCalculating = true
    routeError = ''

    try {
      const response = await fetch('http://localhost:8000/api/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start: { lat: routeStart.lat, lng: routeStart.lng },
          end: { lat: routeEnd.lat, lng: routeEnd.lng }
        })
      })

      if (!response.ok) {
        throw new Error('Failed to calculate route')
      }

      const data = await response.json()

      if (data.error) {
        routeError = data.error
        routeData = null
      } else {
        routeData = data
      }
    } catch (error) {
      routeError = error.message
      routeData = null
    } finally {
      isCalculating = false
    }
  }

  function clearRoute() {
    routeStart = null
    routeEnd = null
    routeData = null
    routeError = ''
  }

  function formatDistance(meters) {
    return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`
  }

  function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes} min`
  }

  // Auto-calculate when both points are set
  $effect(() => {
    if (routeStart && routeEnd && routingEnabled) {
      calculateRoute()
    }
  })

  // Clear route when panel is closed
  $effect(() => {
    if (!routingEnabled) {
      clearRoute()
    }
  })
</script>

<div class="h-full bg-gray-900 border-r-2 border-gray-700 shadow-xl z-[999] flex flex-col flex-shrink-0 transition-all duration-300 overflow-hidden"
     style={routingEnabled ? 'width: 320px;' : 'width: 0; border-right-width: 0;'}>
{#if routingEnabled}
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
      <button
        onclick={() => routingEnabled = false}
        class="text-gray-400 hover:text-white transition-colors"
        title="Close"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
  </div>

  <div class="p-4 space-y-3 flex-1 overflow-y-auto">
      <!-- Start Point -->
      <div>
        <label class="text-xs font-bold text-gray-400 mb-1 block">START POINT</label>
        <LocationSearchBar
          placeholder="Search or click map..."
          bind:selectedLocation={routeStart}
          inline={true}
        />
      </div>

      <!-- End Point -->
      <div>
        <label class="text-xs font-bold text-gray-400 mb-1 block">DESTINATION</label>
        <LocationSearchBar
          placeholder="Search or click map..."
          bind:selectedLocation={routeEnd}
          inline={true}
        />
      </div>

      <!-- Calculate Button -->
      <button
        onclick={calculateRoute}
        disabled={!routeStart || !routeEnd || isCalculating}
        class="w-full px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
      >
        {isCalculating ? 'CALCULATING...' : 'CALCULATE ROUTE'}
      </button>

      <!-- Route Info -->
      {#if routeData}
        <div class="p-3 bg-gray-800 border border-gray-700 space-y-2">
          <div class="flex justify-between text-xs">
            <span class="text-gray-400">Distance:</span>
            <span class="text-white font-mono">{formatDistance(routeData.distance_meters)}</span>
          </div>
          <div class="flex justify-between text-xs">
            <span class="text-gray-400">Duration:</span>
            <span class="text-white font-mono">{formatDuration(routeData.duration_seconds)}</span>
          </div>
        </div>
      {/if}

      <!-- Error Message -->
      {#if routeError}
        <div class="p-2 bg-red-900 border border-red-700 text-xs text-red-200">
          {routeError}
        </div>
      {/if}

      <!-- Clear Button -->
      <button
        onclick={clearRoute}
        class="w-full px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-medium transition-colors"
      >
        CLEAR ROUTE
      </button>
  </div>
{/if}
</div>

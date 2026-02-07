<script>
  let { polygons = [], onGoToPolygon, onDeletePolygon } = $props()

  let showPolygonList = $state(false)

  function getPolygonLabel(polygon, index) {
    // Try to generate a meaningful label
    if (polygon.properties?.name) {
      return polygon.properties.name
    }
    return `Polygon ${index + 1}`
  }
</script>

{#if polygons.length > 0}
  <button
    onclick={() => showPolygonList = !showPolygonList}
    class={`w-8 h-8 flex items-center justify-center transition-colors duration-200 ${
      showPolygonList
        ? 'bg-gray-700 border-l-2 border-orange-500'
        : 'bg-gray-900 hover:bg-gray-800'
    }`}
    title={`${polygons.length} polygon${polygons.length > 1 ? 's' : ''}`}
  >
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class={showPolygonList ? 'text-orange-500' : 'text-white'}>
      <path d="M2 4 L14 4 M2 8 L14 8 M2 12 L14 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
    </svg>
  </button>

  <!-- Dropdown List -->
  {#if showPolygonList}
    <div class="absolute top-0 left-full ml-2 bg-gray-900 border-2 border-gray-700 shadow-lg" style="max-height: 200px; min-width: 200px; z-index: 2000;">
      <div class="overflow-y-auto" style="max-height: 200px;">
        {#each polygons as polygon, index (polygon.id)}
          <div class="flex items-center gap-2 px-3 py-2 border-b border-gray-800 last:border-0 hover:bg-gray-800 transition-colors">
            <button
              onclick={() => onGoToPolygon(polygon)}
              class="flex-1 text-left text-xs text-gray-300 hover:text-orange-500 transition-colors"
              title="Go to polygon"
            >
              {getPolygonLabel(polygon, index)}
            </button>
            <button
              onclick={() => onDeletePolygon(polygon.id)}
              class="w-5 h-5 flex items-center justify-center text-gray-500 hover:text-red-500 hover:bg-gray-700 transition-colors"
              title="Delete polygon"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 2 L10 10 M10 2 L2 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        {/each}
      </div>
    </div>
  {/if}
{/if}

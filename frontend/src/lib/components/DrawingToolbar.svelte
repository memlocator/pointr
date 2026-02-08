<script>
  import PolygonListDropdown from './PolygonListDropdown.svelte'

  let {
    polygons = [],
    isDrawingPolygon = false,
    isDrawingCircle = false,
    isEnriching = false,
    circleCenter = null,
    routingEnabled = $bindable(false),
    onStartPolygonDrawing,
    onStartCircleDrawing,
    onEnrich,
    onClearAll,
    onGoToPolygon,
    onDeletePolygon
  } = $props()
</script>

<div class="absolute flex flex-col gap-2" style="top: 10px; left: 10px; z-index: 1000; pointer-events: auto;">
  <!-- Drawing tools -->
  <div class="bg-gray-900 border-2 border-gray-700 flex flex-col relative">
    <!-- Polygon List Button -->
    <PolygonListDropdown
      {polygons}
      {onGoToPolygon}
      {onDeletePolygon}
    />

    <!-- Polygon button -->
    <button
      onclick={onStartPolygonDrawing}
      class={`w-8 h-8 flex items-center justify-center transition-colors duration-200 ${
        isDrawingPolygon
          ? 'bg-gray-700 border-l-2 border-orange-500'
          : 'bg-gray-900 hover:bg-gray-800'
      }`}
      title="Draw Polygon"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class={isDrawingPolygon ? 'text-orange-500' : 'text-white'}>
        <path d="M2 6 L8 2 L14 6 L14 12 L8 14 L2 12 Z" stroke="currentColor" stroke-width="1.5" fill="none"/>
      </svg>
    </button>

    <!-- Circle button -->
    <button
      onclick={onStartCircleDrawing}
      class={`w-8 h-8 flex items-center justify-center transition-colors duration-200 border-t border-gray-700 ${
        isDrawingCircle
          ? 'bg-gray-700 border-l-2 border-orange-500'
          : 'bg-gray-900 hover:bg-gray-800'
      }`}
      title={circleCenter ? "Click to set radius" : "Draw Circle: Click center, then radius"}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class={isDrawingCircle ? 'text-orange-500' : 'text-white'}>
        <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/>
      </svg>
    </button>
  </div>

  <!-- Action buttons -->
  <div class="bg-gray-900 border-2 border-gray-700 flex flex-col">
    <button
      onclick={onEnrich}
      disabled={isEnriching}
      class={`w-8 h-8 flex items-center justify-center transition-colors duration-200 ${
        isEnriching
          ? 'bg-gray-900 cursor-not-allowed'
          : 'bg-gray-900 hover:bg-gray-800 hover:border-l-2 hover:border-orange-500'
      }`}
      title={isEnriching ? 'Enriching...' : 'Enrich Polygons'}
    >
      {#if isEnriching}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="animate-spin">
          <circle cx="11" cy="11" r="8" stroke-dasharray="28 14"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      {/if}
    </button>

    <button
      onclick={onClearAll}
      class="w-8 h-8 flex items-center justify-center bg-gray-900 hover:bg-gray-800 transition-colors duration-200 border-t border-gray-700"
      title="Clear All"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class="text-white">
        <path d="M3 4 L13 4 M5 4 L5 2 L11 2 L11 4 M6 7 L6 12 M10 7 L10 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M4 4 L4 13 C4 13.5 4.5 14 5 14 L11 14 C11.5 14 12 13.5 12 13 L12 4" stroke="currentColor" stroke-width="1.5" fill="none"/>
      </svg>
    </button>
  </div>

  <!-- Routing button -->
  <div class="bg-gray-900 border-2 border-gray-700 flex flex-col">
    <button
      onclick={() => routingEnabled = !routingEnabled}
      class={`w-8 h-8 flex items-center justify-center transition-colors duration-200 ${
        routingEnabled
          ? 'bg-gray-700 border-l-2 border-orange-500'
          : 'bg-gray-900 hover:bg-gray-800'
      }`}
      title="Routing"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class={routingEnabled ? 'text-orange-500' : 'text-white'}>
        <circle cx="4" cy="3" r="2" stroke="currentColor" stroke-width="1.5" fill="none"/>
        <circle cx="12" cy="13" r="2" stroke="currentColor" stroke-width="1.5" fill="none"/>
        <path d="M5 4.5 Q8 8, 11 11.5" stroke="currentColor" stroke-width="1.5" fill="none"/>
      </svg>
    </button>
  </div>
</div>

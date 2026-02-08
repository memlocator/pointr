<script>
  import PolygonListDropdown from './PolygonListDropdown.svelte'

  let {
    polygons = [],
    businesses = [],
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
    onDeletePolygon,
    onExportPolygons,
    onExportPOIs,
    onImport
  } = $props()

  let fileInput
  let showImportExport = $state(false)

  const customPOICount = $derived(businesses.filter(b => b.source === 'custom').length)
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

  <!-- Import / Export -->
  <div class="bg-gray-900 border-2 border-gray-700 flex flex-col relative">
    <input bind:this={fileInput} type="file" accept=".geojson,.json" class="hidden"
      onchange={(e) => { const f = e.target.files?.[0]; if (f) onImport?.(f); e.target.value = '' }} />
    <button
      onclick={() => showImportExport = !showImportExport}
      class={`w-8 h-8 flex items-center justify-center transition-colors duration-200 ${showImportExport ? 'bg-gray-700 border-l-2 border-orange-500' : 'bg-gray-900 hover:bg-gray-800'}`}
      title="Import / Export"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class={showImportExport ? 'text-orange-500' : 'text-white'}>
        <polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/>
        <path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/>
      </svg>
    </button>

    {#if showImportExport}
      <div class="absolute left-10 top-0 bg-gray-900 border-2 border-gray-700 shadow-lg w-44 z-50">
        <div class="px-3 py-1.5 border-b border-gray-700">
          <span class="text-xs font-bold text-gray-400 tracking-wide">IMPORT / EXPORT</span>
        </div>
        <button onclick={() => { showImportExport = false; fileInput.click() }}
          class="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-gray-800 flex items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          Import GeoJSON
        </button>
        <button onclick={() => { showImportExport = false; onExportPolygons?.() }}
          disabled={polygons.length === 0}
          class="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-gray-800 disabled:opacity-40 flex items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Export Polygons ({polygons.length})
        </button>
        <button onclick={() => { showImportExport = false; onExportPOIs?.() }}
          disabled={customPOICount === 0}
          class="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-gray-800 disabled:opacity-40 flex items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/></svg>
          Export Custom POIs ({customPOICount})
        </button>
      </div>
    {/if}
  </div>
</div>

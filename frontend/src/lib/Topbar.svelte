<script>
  import { APP_NAME } from '../config.js'
  import { saveToStorage } from './stores/persistence.js'
  import { getSourceColor } from './sourceColors.js'
  import ColumnMappingModal from './components/ColumnMappingModal.svelte'

  let { currentView = $bindable(), enabledSources = $bindable(null), businessCount = 0 } = $props()
  let apiStatus = $state('checking...')
  let healthData = $state({
    status: 'checking...',
    services: {}
  })
  let showHealthDetails = $state(false)
  let fileInput = $state(null)
  let mappingModal = $state(null)

  const API_URL = 'http://localhost:8000'

  async function checkAPI() {
    try {
      const response = await fetch(`${API_URL}/api/health`)
      const data = await response.json()
      apiStatus = data.status
      healthData = data
    } catch (error) {
      apiStatus = 'offline'
      healthData = {
        status: 'offline',
        services: {
          backend: { status: 'offline', message: 'Cannot connect to backend' },
          enrichment: { status: 'unknown', message: 'Backend offline' },
          recon: { status: 'unknown', message: 'Backend offline' }
        }
      }
    }
  }

  function getStatusColor(status) {
    if (!status) return 'bg-gray-500'
    if (status === 'healthy' || status === 'online') return 'bg-green-500'
    if (status === 'degraded') return 'bg-yellow-500'
    if (status === 'unhealthy' || status === 'error' || status === 'offline') return 'bg-red-500'
    return 'bg-gray-500'
  }

  function getStatusText(status) {
    if (!status) return 'text-gray-500'
    if (status === 'healthy' || status === 'online') return 'text-green-500'
    if (status === 'degraded') return 'text-yellow-500'
    return 'text-red-500'
  }

  // Run initial health check
  checkAPI()

  // Set up periodic health check every 5 seconds
  $effect(() => {
    const interval = setInterval(() => {
      checkAPI()
    }, 5000)

    // Cleanup on component destroy
    return () => clearInterval(interval)
  })

  // Initialise enabledSources from health data on first load
  $effect(() => {
    if (healthData.datasources && enabledSources === null) {
      const all = ['osm', 'custom']
      for (const ds of healthData.datasources) {
        if (ds.name !== 'Primary (PostGIS)') all.push(ds.name)
      }
      enabledSources = all
    }
  })

  let disabledSourceCount = $derived.by(() => {
    if (!enabledSources) return 0
    const all = ['osm', 'custom']
    if (healthData.datasources) {
      for (const ds of healthData.datasources) {
        if (ds.name !== 'Primary (PostGIS)') all.push(ds.name)
      }
    }
    return all.filter(s => !enabledSources.includes(s)).length
  })

  function toggleSource(key) {
    if (!enabledSources) return
    if (enabledSources.includes(key)) {
      enabledSources = enabledSources.filter(s => s !== key)
    } else {
      enabledSources = [...enabledSources, key]
    }
    saveToStorage('enabledSources', enabledSources)
  }

  function extractPropertyKeys(features) {
    const keys = new Set()
    for (const f of features) {
      const props = f?.properties || {}
      for (const k of Object.keys(props)) keys.add(k)
    }
    return [...keys].sort((a, b) => a.localeCompare(b))
  }

  function suggestMapping(availableFields) {
    const lower = availableFields.map(f => ({ raw: f, norm: f.toLowerCase() }))
    const synonyms = {
      name: ['name', 'title', 'label', 'poi', 'place', 'business', 'company'],
      category: ['category', 'type', 'kind', 'class', 'sector'],
      phone: ['phone', 'tel', 'telephone', 'mobile', 'contact_phone'],
      website: ['website', 'web', 'url', 'site', 'homepage'],
      email: ['email', 'mail', 'e-mail'],
      description: ['description', 'desc', 'notes', 'note', 'about', 'summary', 'details']
    }

    function pick(key) {
      const needles = synonyms[key] || []
      // Exact match first
      for (const n of needles) {
        const exact = lower.find(f => f.norm === n)
        if (exact) return exact.raw
      }
      // Partial match next
      for (const n of needles) {
        const partial = lower.find(f => f.norm.includes(n))
        if (partial) return partial.raw
      }
      return ''
    }

    return {
      name: pick('name'),
      category: pick('category'),
      phone: pick('phone'),
      website: pick('website'),
      email: pick('email'),
      description: pick('description')
    }
  }

  function hasValidNames(features) {
    return features.length > 0 && features.every(f => {
      const name = f?.properties?.name
      return typeof name === 'string' && name.trim().length > 0
    })
  }

  function applyMappingToGeojson(geojson, mapping) {
    const features = geojson.features.map((f) => {
      const props = f.properties || {}
      const mapped = { ...props }
      for (const [target, source] of Object.entries(mapping)) {
        if (!source) continue
        if (props[source] != null && (mapped[target] == null || mapped[target] === '')) {
          mapped[target] = String(props[source])
        }
      }
      return { ...f, properties: mapped }
    })
    return { ...geojson, features }
  }

  async function postDatasource(name, geojsonText) {
    const response = await fetch(`${API_URL}/api/datasources`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, geojson: geojsonText })
    })
    if (!response.ok) {
      const error = await response.json()
      alert(`Upload failed: ${error.detail}`)
      return false
    }
    await checkAPI()
    if (enabledSources && !enabledSources.includes(name)) {
      enabledSources = [...enabledSources, name]
      saveToStorage('enabledSources', enabledSources)
    }
    return true
  }

  async function uploadDatasource(file) {
    if (!file) return
    try {
      const text = await file.text()
      const name = file.name.replace(/\.(geo)?json$/i, '')
      const data = JSON.parse(text)
      if (data?.type !== 'FeatureCollection') {
        alert('Upload failed: GeoJSON must be a FeatureCollection')
        return
      }
      const features = data.features || []
      if (features.length === 0) {
        alert('Upload failed: GeoJSON FeatureCollection is empty')
        return
      }
      for (const f of features) {
        if (f?.geometry?.type !== 'Point') {
          alert('Upload failed: Only Point features are supported')
          return
        }
      }
      if (!hasValidNames(features)) {
        const availableFields = extractPropertyKeys(features)
        mappingModal = {
          fileName: file.name,
          datasetName: name,
          geojson: data,
          availableFields,
          suggestedMapping: suggestMapping(availableFields)
        }
        return
      }
      await postDatasource(name, text)
    } catch (e) {
      alert(`Upload error: ${e.message}`)
    }
  }

  async function deleteDatasource(name) {
    if (!confirm(`Delete datasource "${name}"?`)) return
    try {
      const response = await fetch(`${API_URL}/api/datasources/${encodeURIComponent(name)}`, {
        method: 'DELETE'
      })
      if (!response.ok) {
        alert('Delete failed')
        return
      }
      await checkAPI()
      if (enabledSources) {
        enabledSources = enabledSources.filter(s => s !== name)
        saveToStorage('enabledSources', enabledSources)
      }
    } catch (e) {
      alert(`Delete error: ${e.message}`)
    }
  }
</script>

<div class="w-full bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
  <div class="flex items-center gap-6">
    <div class="flex items-center">
      <svg width="120" height="32" viewBox="0 0 120 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <!-- P icon with location pin design -->
        <circle cx="12" cy="12" r="3" fill="#f97316"/>
        <path d="M12 2 C16.4 2 20 5.6 20 10 C20 14 12 22 12 22 C12 22 4 14 4 10 C4 5.6 7.6 2 12 2 Z" stroke="#f97316" stroke-width="2" fill="none"/>
        <!-- App name from config -->
        <text x="28" y="20" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700" fill="white" letter-spacing="1">{APP_NAME.toUpperCase()}</text>
      </svg>
    </div>
    <div class="flex items-center gap-0 bg-gray-800 border border-gray-700">
      <button
        onclick={() => currentView = 'map'}
        class={`w-24 py-2 text-sm font-medium transition-colors duration-200 ${
          currentView === 'map'
            ? 'bg-gray-700 text-white border-l-2 border-orange-500'
            : 'text-gray-400 hover:bg-gray-750 hover:text-gray-300'
        }`}
      >
        MAP
      </button>
      {#if businessCount > 0}
        <span class="text-gray-700 mx-1">▸</span>
        <button
          onclick={() => currentView = 'list'}
          class={`w-24 py-2 text-sm font-medium transition-colors duration-200 border-l border-gray-700 ${
            currentView === 'list'
              ? 'bg-gray-700 text-white border-l-2 border-orange-500'
              : 'text-gray-400 hover:bg-gray-750 hover:text-gray-300'
          }`}
        >
          LIST
        </button>
        <button
          onclick={() => currentView = 'contacts'}
          class={`w-24 py-2 text-sm font-medium transition-colors duration-200 border-l border-gray-700 ${
            currentView === 'contacts'
              ? 'bg-gray-700 text-white border-l-2 border-orange-500'
              : 'text-gray-400 hover:bg-gray-750 hover:text-gray-300'
          }`}
        >
          CONTACTS
        </button>
        <button
          onclick={() => currentView = 'recon'}
          class={`w-24 py-2 text-sm font-medium transition-colors duration-200 border-l border-gray-700 ${
            currentView === 'recon'
              ? 'bg-gray-700 text-white border-l-2 border-orange-500'
              : 'text-gray-400 hover:bg-gray-750 hover:text-gray-300'
          }`}
        >
          RECON
        </button>
      {/if}
    </div>
    {#if businessCount > 0}
      <div class="flex items-center gap-2 px-3 py-1 bg-gray-800 border border-gray-700">
        <span class="text-xs font-mono text-white">{businessCount}</span>
        <span class="text-xs text-gray-500">BUSINESSES</span>
      </div>
    {/if}
  </div>

  <div class="flex items-center gap-4">
    <div class="relative">
      <button
        onclick={() => showHealthDetails = !showHealthDetails}
        class="flex items-center gap-2 px-3 py-1 bg-gray-800 border border-gray-700 hover:bg-gray-700 transition-colors"
      >
        <div class={`w-2 h-2 rounded-full ${getStatusColor(apiStatus)}`}></div>
        <span class="text-xs font-mono text-gray-400">SOURCES</span>
        {#if disabledSourceCount > 0}
          <span class="px-1 bg-orange-500 text-white text-xs font-mono">{enabledSources?.length === 0 ? '-*' : `-${disabledSourceCount}`}</span>
        {/if}
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          class={`text-gray-400 transition-transform ${showHealthDetails ? 'rotate-180' : ''}`}
        >
          <path d="M2 4 L6 8 L10 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>

      {#if showHealthDetails && Object.keys(healthData.services).length > 0}
        <div class="absolute top-full right-0 mt-1 bg-gray-900 border-2 border-gray-700 shadow-lg min-w-[280px] z-[1100]">
          <div class="px-4 py-2 border-b border-gray-700">
            <div class="text-xs font-bold text-gray-400 tracking-wide">SERVICE STATUS</div>
          </div>
          <div class="p-2">
            {#each Object.entries(healthData.services) as [serviceName, serviceData]}
              {#if serviceData}
                <div class="flex items-center justify-between px-2 py-2 hover:bg-gray-800 transition-colors">
                  <div class="flex items-center gap-2">
                    <div class={`w-2 h-2 rounded-full ${getStatusColor(serviceData?.status || 'unknown')}`}></div>
                    <span class="text-xs font-medium text-gray-300 uppercase">{serviceName}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-gray-500">{serviceData?.message || 'Unknown'}</span>
                    <span class={`text-xs font-mono ${
                      serviceData?.status === 'healthy' ? 'text-green-500' :
                      serviceData?.status === 'degraded' ? 'text-yellow-500' :
                      'text-red-500'
                    }`}>
                      {(serviceData?.status || 'unknown').toUpperCase()}
                    </span>
                  </div>
                </div>
              {/if}
            {/each}
          </div>
          {#if healthData.datasources?.length > 0 || enabledSources !== null}
            <div class="px-4 py-2 border-t border-gray-700 flex items-center justify-between">
              <div class="text-xs font-bold text-gray-400 tracking-wide">DATASOURCES</div>
              <button
                onclick={() => fileInput?.click()}
                class="w-5 h-5 flex items-center justify-center bg-gray-800 hover:bg-gray-700 border border-gray-600 transition-colors"
                title="Upload GeoJSON"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#f97316" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="6" y1="9" x2="6" y2="3"/><polyline points="3 6 6 3 9 6"/>
                </svg>
              </button>
            </div>
            <input
              bind:this={fileInput}
              type="file"
              accept=".geojson,.json"
              class="hidden"
              onchange={(e) => { const f = e.target.files?.[0]; if (f) uploadDatasource(f); e.target.value = '' }}
            />
            <div class="px-3 pb-2 flex flex-col gap-0.5">
              {#each [{key: 'osm', label: 'OSM', sub: 'Overpass'}, {key: 'custom', label: 'Custom POIs', sub: 'local'}] as src}
                <button
                  onclick={() => toggleSource(src.key)}
                  class="flex items-center gap-3 px-2 py-2 hover:bg-gray-800 transition-colors w-full text-left"
                >
                  <div class={`w-9 h-5 rounded-full flex-shrink-0 relative transition-colors ${enabledSources?.includes(src.key) ? 'bg-orange-500' : 'bg-gray-700'}`}>
                    <span class={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${enabledSources?.includes(src.key) ? 'translate-x-[18px]' : 'translate-x-0.5'}`}></span>
                  </div>
                  <div class="w-2.5 h-2.5 rounded-full flex-shrink-0 border border-gray-600" style="background-color: {getSourceColor(src.key)}"></div>
                  <span class="text-xs font-medium text-gray-200">{src.label}</span>
                  <span class="text-xs text-gray-600 ml-auto">{src.sub}</span>
                </button>
              {/each}
              {#each healthData.datasources?.filter(d => d.name !== 'Primary (PostGIS)') ?? [] as ds}
                <div class="flex items-center gap-2 px-2 py-2 hover:bg-gray-800 transition-colors">
                  <button
                    onclick={() => toggleSource(ds.name)}
                    class="flex items-center gap-3 flex-1 text-left"
                  >
                    <div class={`w-9 h-5 rounded-full flex-shrink-0 relative transition-colors ${enabledSources?.includes(ds.name) ? 'bg-orange-500' : 'bg-gray-700'}`}>
                      <span class={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${enabledSources?.includes(ds.name) ? 'translate-x-[18px]' : 'translate-x-0.5'}`}></span>
                    </div>
                    <div class="w-2.5 h-2.5 rounded-full flex-shrink-0 border border-gray-600" style="background-color: {getSourceColor(ds.name)}"></div>
                    <span class="text-xs font-medium text-gray-200">{ds.name}</span>
                    <div class="flex items-center gap-1.5 ml-auto">
                      <div class={`w-1.5 h-1.5 rounded-full ${getStatusColor(ds.status)}`}></div>
                      <span class="text-xs text-gray-500">{(ds.status || '?').toUpperCase()}</span>
                    </div>
                  </button>
                  {#if ds.message?.includes('in-memory')}
                    <button
                      onclick={(e) => { e.stopPropagation(); deleteDatasource(ds.name) }}
                      class="w-5 h-5 flex items-center justify-center hover:bg-gray-700 text-gray-500 hover:text-red-400 transition-colors"
                      title="Delete uploaded source"
                    >
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
                        <line x1="2" y1="2" x2="8" y2="8"/><line x1="8" y1="2" x2="2" y2="8"/>
                      </svg>
                    </button>
                  {/if}
                </div>
              {/each}
              {#each healthData.datasources?.filter(d => d.name === 'Primary (PostGIS)') ?? [] as ds}
                <div class="flex items-center gap-3 px-2 py-2">
                  <div class="w-9 h-5 flex-shrink-0"></div>
                  <span class="text-xs text-gray-600">{ds.name}</span>
                  <div class="flex items-center gap-1.5 ml-auto">
                    <div class={`w-1.5 h-1.5 rounded-full ${getStatusColor(ds.status)}`}></div>
                    <span class="text-xs text-gray-500">{(ds.status || '?').toUpperCase()}</span>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <button
      onclick={() => checkAPI()}
      class="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-medium border border-gray-700 hover:border-gray-600 transition-colors duration-200"
    >
      REFRESH
    </button>

    <a
      href="http://localhost:8000/docs"
      target="_blank"
      rel="noopener"
      class="w-7 h-7 rounded-full bg-gray-800 border border-gray-700 hover:border-gray-500 flex items-center justify-center text-gray-400 hover:text-gray-200 text-xs font-bold transition-colors"
      title="API Docs"
    >?</a>
  </div>
</div>

{#if mappingModal}
  <ColumnMappingModal
    fileName={mappingModal.fileName}
    datasetName={mappingModal.datasetName}
    availableFields={mappingModal.availableFields}
    suggestedMapping={mappingModal.suggestedMapping}
    onCancel={() => mappingModal = null}
    onConfirm={async ({ datasetName, mapping }) => {
      const mapped = applyMappingToGeojson(mappingModal.geojson, mapping)
      const ok = await postDatasource(datasetName, JSON.stringify(mapped))
      if (ok) mappingModal = null
    }}
  />
{/if}

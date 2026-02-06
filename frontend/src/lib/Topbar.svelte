<script>
  let { currentView = $bindable(), businessCount = 0 } = $props()
  let apiStatus = $state('checking...')

  const API_URL = 'http://localhost:8000'

  async function checkAPI() {
    try {
      const response = await fetch(`${API_URL}/api/health`)
      const data = await response.json()
      apiStatus = data.status
    } catch (error) {
      apiStatus = 'offline'
    }
  }

  checkAPI()
</script>

<div class="w-full bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
  <div class="flex items-center gap-6">
    <div class="flex items-center">
      <svg width="120" height="32" viewBox="0 0 120 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <!-- P icon with location pin design -->
        <circle cx="12" cy="12" r="3" fill="#f97316"/>
        <path d="M12 2 C16.4 2 20 5.6 20 10 C20 14 12 22 12 22 C12 22 4 14 4 10 C4 5.6 7.6 2 12 2 Z" stroke="#f97316" stroke-width="2" fill="none"/>
        <!-- Text "POINTR" -->
        <text x="28" y="20" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700" fill="white" letter-spacing="1">POINTR</text>
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
    <div class="flex items-center gap-2 px-3 py-1 bg-gray-800 border border-gray-700">
      <div class={`w-2 h-2 ${apiStatus === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`}></div>
      <span class="text-xs font-mono text-gray-400">API: {apiStatus.toUpperCase()}</span>
    </div>

    <button
      onclick={() => checkAPI()}
      class="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-medium border border-gray-700 hover:border-gray-600 transition-colors duration-200"
    >
      REFRESH
    </button>
  </div>
</div>

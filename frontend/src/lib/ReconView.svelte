<script>
  import DataTable from './components/DataTable/DataTable.svelte'
  import ReconResults from './ReconResults.svelte'
  import { apiFetch } from './api.js'

  let { selectedBusinesses = $bindable([]) } = $props()

  let isRunningRecon = $state(false)
  let reconResults = $state([])
  let reconError = $state(null)
  let reconLogs = $state([])
  let logWidth = $state(350) // Initial width in pixels
  let isResizing = $state(false)
  let reconMode = $state(null) // 'silent' or 'full'
  let showShush = $state(false)

  // Color scheme based on recon mode
  const modeColors = $derived({
    border: reconMode === 'silent' ? 'border-purple-500' : reconMode === 'full' ? 'border-orange-500' : 'border-gray-700',
    bg: reconMode === 'silent' ? 'bg-purple-500' : reconMode === 'full' ? 'bg-orange-500' : 'bg-gray-500',
    bgHover: reconMode === 'silent' ? 'hover:bg-purple-600' : reconMode === 'full' ? 'hover:bg-orange-600' : 'hover:bg-gray-600',
    text: reconMode === 'silent' ? 'text-purple-400' : reconMode === 'full' ? 'text-orange-400' : 'text-gray-400'
  })

  // Common email providers to exclude
  const commonEmailProviders = [
    // Google
    'gmail.com', 'googlemail.com',

    // Microsoft
    'hotmail.com', 'outlook.com', 'live.com', 'msn.com', 'hotmail.co.uk', 'outlook.co.uk',
    'live.co.uk', 'hotmail.fr', 'outlook.fr', 'live.fr', 'hotmail.de', 'outlook.de',

    // Yahoo
    'yahoo.com', 'yahoo.co.uk', 'yahoo.fr', 'yahoo.de', 'yahoo.es', 'yahoo.it',
    'yahoo.se', 'yahoo.no', 'yahoo.dk', 'yahoo.fi', 'ymail.com', 'rocketmail.com',

    // Apple
    'icloud.com', 'me.com', 'mac.com',

    // AOL
    'aol.com', 'aol.co.uk', 'aol.fr', 'aol.de',

    // ProtonMail
    'protonmail.com', 'proton.me', 'pm.me',

    // Russian providers
    'yandex.com', 'yandex.ru', 'ya.ru', 'mail.ru', 'inbox.ru', 'bk.ru', 'list.ru',

    // European providers
    'gmx.com', 'gmx.de', 'gmx.net', 'web.de', 't-online.de', 'freenet.de',
    'orange.fr', 'wanadoo.fr', 'laposte.net', 'free.fr', 'sfr.fr',
    'libero.it', 'virgilio.it', 'alice.it', 'tim.it',
    'tele2.nl', 'ziggo.nl', 'kpnmail.nl', 'planet.nl',

    // Asian providers
    'qq.com', '163.com', '126.com', 'sina.com', 'sohu.com', 'foxmail.com',
    'naver.com', 'daum.net', 'hanmail.net',

    // Other popular providers
    'zoho.com', 'fastmail.com', 'fastmail.fm', 'hushmail.com', 'tutanota.com',
    'mailbox.org', 'posteo.de', 'startmail.com', 'runbox.com',
    'mail.com', 'email.com', 'usa.com', 'myself.com',

    // Disposable/temporary
    'guerrillamail.com', 'temp-mail.org', '10minutemail.com', 'throwaway.email',
    'mailinator.com', 'sharklasers.com', 'guerrillamail.info'
  ]

  function extractDomainFromEmail(email) {
    if (!email) return null
    const parts = email.split('@')
    if (parts.length !== 2) return null
    return parts[1].toLowerCase().trim()
  }

  function normalizeDomain(domain) {
    if (!domain) return null
    // Remove protocol
    let normalized = domain.replace(/^https?:\/\//, '')
    // Remove www.
    normalized = normalized.replace(/^www\./, '')
    // Remove trailing slash and path
    normalized = normalized.split('/')[0]
    // Lowercase
    normalized = normalized.toLowerCase().trim()
    return normalized
  }

  function removeResult(domain) {
    reconResults = reconResults.filter(r => r.domain !== domain)
    if (reconResults.length === 0) {
      reconMode = null
    }
  }

  function clearAllResults() {
    reconResults = []
    reconLogs = []
    reconMode = null
  }

  function removeBusiness(business) {
    selectedBusinesses = selectedBusinesses.filter(b =>
      !(b.name === business.name && b.lat === business.lat && b.lng === business.lng)
    )
  }

  function clearAllBusinesses() {
    selectedBusinesses = []
  }

  function startResize(e) {
    e.preventDefault() // Prevent text selection
    isResizing = true
    const startX = e.clientX
    const startWidth = logWidth

    // Disable text selection during drag
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'ew-resize'

    function onMouseMove(e) {
      e.preventDefault()
      const deltaX = startX - e.clientX // Reversed because we're dragging from left edge
      logWidth = Math.max(250, Math.min(800, startWidth + deltaX))
    }

    function onMouseUp() {
      isResizing = false
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  async function runRecon(silentMode = false) {
    // Show animation for silent mode only
    if (silentMode) {
      showShush = true
      setTimeout(() => {
        showShush = false
      }, 1500)
    }

    isRunningRecon = true
    reconError = null
    reconResults = []
    reconLogs = []
    reconMode = silentMode ? 'silent' : 'full'

    // Extract and normalize domains from websites
    const websiteDomains = selectedBusinesses
      .filter(b => b.website)
      .map(b => normalizeDomain(b.website))
      .filter(d => d)

    // Extract domains from emails (exclude common providers)
    const emailDomains = selectedBusinesses
      .filter(b => b.email)
      .map(b => extractDomainFromEmail(b.email))
      .filter(domain => domain && !commonEmailProviders.includes(domain))

    // Combine and deduplicate (both are already normalized/lowercased)
    const domains = [...new Set([...websiteDomains, ...emailDomains])]

    if (domains.length === 0) {
      reconError = 'No websites or custom email domains found in selected businesses'
      isRunningRecon = false
      return
    }

    try {
      const response = await apiFetch('/api/recon/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domains, silent_mode: silentMode })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'log') {
              reconLogs = [...reconLogs, data.message]
            } else if (data.type === 'result') {
              // Check if we already have this domain to prevent duplicates
              const existingIndex = reconResults.findIndex(r => r.domain === data.result.domain)
              if (existingIndex >= 0) {
                // Replace existing result (in case of retry)
                reconResults[existingIndex] = data.result
                reconResults = [...reconResults]
              } else {
                // Add new result
                reconResults = [...reconResults, data.result]
              }
              reconLogs = [...reconLogs, data.message]
            } else if (data.type === 'complete') {
              reconLogs = [...reconLogs, data.message]
              isRunningRecon = false
            } else if (data.type === 'error') {
              reconError = data.message
              isRunningRecon = false
            }
          }
        }
      }
    } catch (error) {
      reconError = error.message
      console.error('Recon error:', error)
    } finally {
      isRunningRecon = false
    }
  }

</script>

<style>
  @keyframes shush {
    0% {
      opacity: 0;
      transform: scale(0.5) translateY(20px);
    }
    20% {
      opacity: 1;
      transform: scale(1.1) translateY(0);
    }
    80% {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
    100% {
      opacity: 0;
      transform: scale(0.8) translateY(-20px);
    }
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  .animate-shush {
    animation: shush 1.5s ease-in-out;
  }

  .animate-spin {
    animation: spin 1s linear infinite;
  }
</style>

<div class="w-full h-full bg-gray-900 flex flex-col gap-4 p-6 relative">
  <!-- Shush animation -->
  {#if showShush}
    <div class="fixed inset-0 flex items-center justify-center z-50 pointer-events-none">
      <div class="animate-shush">
        <svg width="200" height="180" viewBox="0 0 200 180" fill="none" class="drop-shadow-2xl">
          <!-- Fedora/Detective Hat Silhouette -->
          <!-- Hat brim -->
          <ellipse cx="100" cy="90" rx="80" ry="20" fill="white" opacity="0.95"/>

          <!-- Hat crown -->
          <path d="M 40 90 Q 40 30 100 30 Q 160 30 160 90 Z" fill="white" opacity="0.95"/>

          <!-- Hat band/crease -->
          <rect x="35" y="85" width="130" height="10" fill="white" opacity="0.8" rx="2"/>
          <ellipse cx="100" cy="65" rx="50" ry="8" fill="white" opacity="0.7"/>

          <!-- "Shh..." text -->
          <text x="100" y="150" font-size="36" font-weight="bold" fill="white" text-anchor="middle" font-family="monospace">Shh...</text>
        </svg>
      </div>
    </div>
  {/if}

  <div class="bg-gray-800 border-2 p-4 {reconMode ? modeColors.border : 'border-orange-500'}">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <span class="text-sm font-bold tracking-wide {reconMode ? modeColors.text : 'text-orange-400'}">
          RECON TARGETS: {selectedBusinesses.length}
        </span>
        {#if reconResults.length > 0}
          <span class="text-xs text-gray-500">
            ({reconResults.length} result{reconResults.length !== 1 ? 's' : ''})
          </span>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        {#if reconResults.length > 0 && !isRunningRecon}
          <button
            onclick={clearAllResults}
            class="px-3 py-2 text-xs font-medium bg-gray-600 hover:bg-gray-700 text-white transition-colors"
            title="Clear all results"
          >
            CLEAR ALL RESULTS
          </button>
        {/if}
        <button
          onclick={() => runRecon(true)}
          disabled={isRunningRecon || selectedBusinesses.length === 0}
          class={`px-4 py-2 text-xs font-medium transition-colors ${
            isRunningRecon || selectedBusinesses.length === 0
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-purple-500 hover:bg-purple-600 text-white'
          }`}
          title="DNS, SSL, WHOIS, ASN only - no HTTP requests to target"
        >
          {isRunningRecon ? 'RUNNING...' : 'RUN SILENT RECON'}
        </button>
        <button
          onclick={() => runRecon(false)}
          disabled={isRunningRecon || selectedBusinesses.length === 0}
          class={`px-4 py-2 text-xs font-medium transition-colors ${
            isRunningRecon || selectedBusinesses.length === 0
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-orange-500 hover:bg-orange-600 text-white'
          }`}
          title="Full recon including security headers (makes HTTP request to target)"
        >
          {isRunningRecon ? 'RUNNING...' : 'RUN FULL RECON'}
        </button>
      </div>
    </div>
  </div>

  {#if reconError}
    <div class="bg-red-900 border-2 border-red-700 p-4">
      <p class="text-sm text-red-200">ERROR: {reconError}</p>
    </div>
  {/if}

  <!-- Main content area with log sidebar -->
  <div class="flex-1 flex gap-4 overflow-hidden">
    <!-- Main content -->
    <div class="flex-1 overflow-auto">
      {#if isRunningRecon && reconResults.length === 0}
        <!-- Loading spinner -->
        <div class="flex items-center justify-center h-full">
          <div class="text-center">
            <svg class="animate-spin h-16 w-16 mx-auto mb-4 {reconMode === 'silent' ? 'text-purple-500' : 'text-orange-500'}" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="text-sm tracking-wide {reconMode === 'silent' ? 'text-purple-400' : 'text-orange-400'}">
              {reconMode === 'silent' ? 'RUNNING SILENT RECON...' : 'RUNNING FULL RECON...'}
            </p>
          </div>
        </div>
      {:else if reconResults.length > 0}
        <div class="space-y-4">
          {#each reconResults as result}
            <ReconResults {result} mode={reconMode} onRemove={removeResult} />
          {/each}
        </div>
      {:else if !isRunningRecon && reconLogs.length === 0}
        <div class="bg-gray-800 border-2 border-gray-700 shadow-lg h-full overflow-hidden flex flex-col">
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h4 class="text-sm font-bold text-gray-400 tracking-wide">SELECTED TARGETS</h4>
            {#if selectedBusinesses.length > 0}
              <button
                onclick={clearAllBusinesses}
                class="text-xs text-gray-400 hover:text-gray-200 transition-colors"
              >
                CLEAR ALL
              </button>
            {/if}
          </div>

          {#if selectedBusinesses.length === 0}
            <div class="flex-1 flex items-center justify-center">
              <div class="text-center text-gray-400 border border-gray-700 p-8 bg-gray-900">
                <p class="text-sm font-medium mb-2 tracking-wide">NO TARGETS SELECTED</p>
                <p class="text-xs text-gray-600">Select businesses from LIST or CONTACTS view, then click RUN RECON</p>
              </div>
            </div>
          {:else}
            <div class="flex-1 overflow-auto p-4">
              <div class="space-y-2">
                {#each selectedBusinesses as business}
                  <div class="bg-gray-700 border border-gray-600 p-3 flex items-center justify-between hover:bg-gray-600 transition-colors">
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium text-gray-200 truncate">{business.name}</p>
                      <div class="flex gap-3 mt-1">
                        {#if business.website}
                          <span class="text-xs text-blue-400 truncate">{business.website}</span>
                        {/if}
                        {#if business.email}
                          <span class="text-xs text-orange-400 truncate">{business.email}</span>
                        {/if}
                      </div>
                    </div>
                    <button
                      onclick={() => removeBusiness(business)}
                      class="ml-3 p-1 text-gray-500 hover:text-gray-200 hover:bg-gray-800 transition-colors rounded flex-shrink-0"
                      title="Remove from targets"
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 3 L13 13 M13 3 L3 13" stroke-linecap="round"/>
                      </svg>
                    </button>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Log sidebar (sticky on right) -->
    {#if isRunningRecon || reconLogs.length > 0}
      <div
        class="bg-gray-800 border-2 overflow-hidden flex flex-col relative flex-shrink-0 {modeColors.border}"
        style="width: {logWidth}px;"
      >
        <!-- Resize handle (left edge) -->
        <div
          class="absolute top-0 left-0 bottom-0 w-2 cursor-ew-resize transition-colors z-10 {isResizing ? (reconMode === 'silent' ? 'bg-purple-500/50' : 'bg-orange-500/50') : (reconMode === 'silent' ? 'hover:bg-purple-500/30' : 'hover:bg-orange-500/30')}"
          onmousedown={startResize}
          title="Drag to resize"
        >
          <div class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-12 w-1 bg-gray-600 rounded"></div>
        </div>

        <div class="flex items-center justify-between p-4 border-b border-gray-700">
          <h4 class="text-sm font-bold tracking-wide {modeColors.text}">RECON LOG</h4>
          {#if isRunningRecon}
            <span class="text-xs text-gray-400 animate-pulse">Running...</span>
          {:else}
            <button
              onclick={clearAllResults}
              class="text-xs text-gray-400 hover:text-gray-300"
            >
              CLEAR
            </button>
          {/if}
        </div>

        <div class="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-1">
          {#each reconLogs as log}
            <div class="text-gray-300">{log}</div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

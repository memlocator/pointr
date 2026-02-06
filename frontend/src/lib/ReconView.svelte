<script>
  import DataTable from './components/DataTable/DataTable.svelte'
  import ReconResults from './ReconResults.svelte'

  let { selectedBusinesses = [] } = $props()

  let isRunningRecon = $state(false)
  let reconResults = $state(null)
  let reconError = $state(null)

  async function runRecon() {
    isRunningRecon = true
    reconError = null
    reconResults = null

    // Extract domains from selected businesses
    const domains = selectedBusinesses
      .filter(b => b.website)
      .map(b => b.website)
      .filter((v, i, a) => a.indexOf(v) === i) // unique

    if (domains.length === 0) {
      reconError = 'No websites found in selected businesses'
      isRunningRecon = false
      return
    }

    try {
      const response = await fetch('http://localhost:8000/api/recon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domains })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      reconResults = data.results
    } catch (error) {
      reconError = error.message
      console.error('Recon error:', error)
    } finally {
      isRunningRecon = false
    }
  }

  const columns = [
    { id: 'name', header: 'Name', width: '200px' },
    { id: 'type', header: 'Type', width: '120px' },
    {
      id: 'phone',
      header: 'Phone',
      width: '150px',
      render: (value) => value ? {
        type: 'link',
        value: value,
        href: `tel:${value}`,
        class: 'text-green-400 hover:text-green-300 hover:underline'
      } : { type: 'text', value: '-', class: 'text-gray-600' }
    },
    {
      id: 'email',
      header: 'Email',
      width: '200px',
      render: (value) => value ? {
        type: 'link',
        value: value,
        href: `mailto:${value}`,
        class: 'text-orange-400 hover:text-orange-300 hover:underline'
      } : { type: 'text', value: '-', class: 'text-gray-600' }
    },
    {
      id: 'website',
      header: 'Website',
      width: '200px',
      render: (value) => value ? {
        type: 'link',
        value: value,
        href: value.startsWith('http') ? value : `https://${value}`,
        class: 'text-blue-400 hover:text-blue-300 hover:underline'
      } : { type: 'text', value: '-', class: 'text-gray-600' }
    },
    { id: 'address', header: 'Address', width: '200px' }
  ]
</script>

<div class="w-full h-full bg-gray-900 p-6 flex flex-col gap-4">
  <div class="bg-gray-800 border-2 border-orange-500 p-4">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <span class="text-sm font-bold text-orange-400 tracking-wide">
          RECON TARGETS: {selectedBusinesses.length}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <button
          onclick={runRecon}
          disabled={isRunningRecon || selectedBusinesses.length === 0}
          class={`px-4 py-2 text-xs font-medium transition-colors ${
            isRunningRecon || selectedBusinesses.length === 0
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-orange-500 hover:bg-orange-600 text-white'
          }`}
        >
          {isRunningRecon ? 'RUNNING RECON...' : 'RUN FULL RECON'}
        </button>
      </div>
    </div>
  </div>

  {#if reconError}
    <div class="bg-red-900 border-2 border-red-700 p-4">
      <p class="text-sm text-red-200">ERROR: {reconError}</p>
    </div>
  {/if}

  {#if reconResults}
    <div class="flex-1 overflow-auto space-y-4">
      {#each reconResults as result}
        <ReconResults {result} />
      {/each}
    </div>
  {:else}
    <div class="bg-gray-800 border-2 border-gray-700 shadow-lg flex-1 overflow-hidden">
      <DataTable
        data={selectedBusinesses}
        {columns}
        pageSize={25}
        searchable={true}
        sortable={true}
        selectable={false}
        categoryFilter={{ enabled: false }}
        contactFilter={{ enabled: false }}
        emptyState={{
          title: 'NO TARGETS SELECTED',
          description: 'Select businesses from LIST or CONTACTS view, then click RUN RECON'
        }}
      />
    </div>
  {/if}
</div>

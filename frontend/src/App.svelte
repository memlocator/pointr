<script>
  import Topbar from './lib/Topbar.svelte'
  import Map from './lib/Map.svelte'
  import ListView from './lib/ListView.svelte'
  import ContactsView from './lib/ContactsView.svelte'
  import ReconView from './lib/ReconView.svelte'
  import { loadFromStorage, saveToStorage } from './lib/stores/persistence.js'
  import { BUSINESS_CATEGORIES } from './lib/businessCategories.js'

  // Load persisted state from localStorage or use defaults
  let currentView = $state('map')
  let businesses = $state(loadFromStorage('businesses', []))
  let polygons = $state(loadFromStorage('polygons', []))
  let mapCenter = $state(loadFromStorage('mapCenter', [10.0, 50.0])) // Central Europe
  let mapZoom = $state(loadFromStorage('mapZoom', 4)) // Zoomed out to show Europe
  let selectedBusinesses = $state([])
  let searchQuery = $state('')

  // Category filtering - initialize all as enabled
  let showContactsOnly = $state(loadFromStorage('showContactsOnly', false))

  // Ensure all categories are initialized (create new object for proper reactivity)
  const storedCategories = loadFromStorage('enabledCategories', {})
  const initialCategories = {}
  BUSINESS_CATEGORIES.forEach(cat => {
    initialCategories[cat.name] = storedCategories[cat.name] !== undefined
      ? storedCategories[cat.name]
      : true
  })
  let enabledCategories = $state(initialCategories)

  // Heatmap state
  let heatmapEnabled = $state(loadFromStorage('heatmapEnabled', false))
  let heatmapCategory = $state(loadFromStorage('heatmapCategory', 'Food & Dining'))

  // Routing state (temporary, no persistence)
  let routingEnabled = $state(false)
  let routeStart = $state(null)
  let routeEnd = $state(null)
  let routeData = $state(null)

  // Auto-save to localStorage when state changes
  $effect(() => {
    saveToStorage('businesses', businesses)
  })

  $effect(() => {
    saveToStorage('polygons', polygons)
  })

  $effect(() => {
    saveToStorage('mapCenter', mapCenter)
  })

  $effect(() => {
    saveToStorage('mapZoom', mapZoom)
  })

  $effect(() => {
    saveToStorage('enabledCategories', enabledCategories)
  })

  $effect(() => {
    saveToStorage('showContactsOnly', showContactsOnly)
  })

  $effect(() => {
    saveToStorage('heatmapEnabled', heatmapEnabled)
  })

  $effect(() => {
    saveToStorage('heatmapCategory', heatmapCategory)
  })
</script>

<div class="h-screen w-screen flex flex-col bg-gray-900">
  <Topbar bind:currentView businessCount={businesses.length} />
  <div class="flex-1 overflow-hidden">
    {#if currentView === 'map'}
      <Map bind:businesses bind:polygons bind:mapCenter bind:mapZoom bind:currentView bind:searchQuery bind:enabledCategories bind:showContactsOnly bind:heatmapEnabled bind:heatmapCategory bind:routingEnabled bind:routeStart bind:routeEnd bind:routeData />
    {:else if currentView === 'list'}
      {#key currentView}
        <ListView {businesses} bind:selectedBusinesses bind:currentView bind:searchQuery bind:enabledCategories bind:showContactsOnly />
      {/key}
    {:else if currentView === 'contacts'}
      {#key currentView}
        <ContactsView {businesses} bind:selectedBusinesses bind:currentView bind:enabledCategories bind:showContactsOnly />
      {/key}
    {:else if currentView === 'recon'}
      <ReconView bind:selectedBusinesses />
    {/if}
  </div>
</div>

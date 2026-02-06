<script>
  import Topbar from './lib/Topbar.svelte'
  import Map from './lib/Map.svelte'
  import ListView from './lib/ListView.svelte'
  import ContactsView from './lib/ContactsView.svelte'
  import ReconView from './lib/ReconView.svelte'

  let currentView = $state('map')
  let businesses = $state([])
  let polygons = $state([])
  let mapCenter = $state([18.0686, 59.3293])
  let mapZoom = $state(13)
  let selectedBusinesses = $state([])
  let searchQuery = $state('')
</script>

<div class="h-screen w-screen flex flex-col bg-gray-900">
  <Topbar bind:currentView businessCount={businesses.length} />
  <div class="flex-1 overflow-hidden">
    {#if currentView === 'map'}
      <Map bind:businesses bind:polygons bind:mapCenter bind:mapZoom bind:currentView bind:searchQuery />
    {:else if currentView === 'list'}
      <ListView {businesses} bind:selectedBusinesses bind:currentView bind:searchQuery />
    {:else if currentView === 'contacts'}
      <ContactsView {businesses} bind:selectedBusinesses bind:currentView />
    {:else if currentView === 'recon'}
      <ReconView {selectedBusinesses} />
    {/if}
  </div>
</div>

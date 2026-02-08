<script>
  import { apiUrl } from '../api.js'
  let {
    onLocationSelect = null,
    placeholder = "Search location (min 3 chars)...",
    selectedLocation = $bindable(null),
    inline = false
  } = $props()

  let locationSearch = $state('')
  let searchResults = $state([])
  let isSearching = $state(false)
  let searchTimeout = null

  async function searchLocation() {
    // Clear previous timeout
    if (searchTimeout) {
      clearTimeout(searchTimeout)
    }

    if (!locationSearch || locationSearch.length < 3) {
      searchResults = []
      return
    }

    // Debounce: wait 1000ms after user stops typing
    searchTimeout = setTimeout(async () => {
      isSearching = true
      try {
        const response = await fetch(apiUrl(`/api/search?q=${encodeURIComponent(locationSearch)}`))
        if (response.ok) {
          const data = await response.json()
          searchResults = data.results
        } else {
          searchResults = []
        }
      } catch (error) {
        console.error('Search error:', error)
        searchResults = []
      } finally {
        isSearching = false
      }
    }, 1000)
  }

  function selectResult(result) {
    // Support both callback and bindable prop patterns
    if (onLocationSelect) {
      onLocationSelect(result)
    }
    if (selectedLocation !== null) {
      selectedLocation = {
        lat: result.lat,
        lng: result.lon,
        name: result.display_name
      }
    }
    searchResults = []
    locationSearch = result.display_name
  }

  // Sync locationSearch with selectedLocation
  $effect(() => {
    if (selectedLocation === null) {
      locationSearch = ''
    } else if (selectedLocation && selectedLocation.name) {
      locationSearch = selectedLocation.name
    }
  })
</script>

<div class={inline ? 'relative w-full' : 'absolute top-4 right-16 w-80'} style={inline ? '' : 'z-index: 1000;'}>
  <div class="relative">
    <input
      type="text"
      bind:value={locationSearch}
      oninput={searchLocation}
      placeholder={placeholder}
      class="w-full px-4 py-2 bg-gray-900 border-2 border-gray-700 text-gray-200 placeholder-gray-500 text-sm focus:border-orange-500 focus:outline-none"
    />
    {#if isSearching}
      <div class="absolute right-3 top-2.5">
        <svg class="animate-spin h-5 w-5 text-orange-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
    {/if}
  </div>

  {#if searchResults.length > 0}
    <div class="mt-1 bg-gray-900 border-2 border-gray-700 max-h-64 overflow-y-auto" style={inline ? 'z-index: 10; position: relative;' : ''}>
      {#each searchResults as result}
        <button
          onclick={() => selectResult(result)}
          class="w-full text-left px-4 py-2 hover:bg-gray-800 border-b border-gray-800 last:border-0 transition-colors"
        >
          <p class="text-sm text-gray-200 font-medium">{result.display_name.split(',')[0]}</p>
          <p class="text-xs text-gray-500 truncate">{result.display_name}</p>
        </button>
      {/each}
    </div>
  {/if}
</div>

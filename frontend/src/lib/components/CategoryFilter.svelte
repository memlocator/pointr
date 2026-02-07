<script>
  import { BUSINESS_CATEGORIES } from '../businessCategories.js'

  let {
    businesses = [],
    enabledCategories = $bindable({}),
    businessCounts = $derived.by(() => {
      const counts = {}
      BUSINESS_CATEGORIES.forEach(cat => {
        counts[cat.name] = 0
      })

      businesses.forEach(business => {
        const category = BUSINESS_CATEGORIES.find(cat =>
          cat.types.includes(business.type)
        )
        if (category) {
          counts[category.name]++
        } else {
          counts['Other']++
        }
      })

      return counts
    })
  } = $props()

  let isExpanded = $state(false)

  function toggleCategory(categoryName) {
    enabledCategories[categoryName] = !enabledCategories[categoryName]
  }

  function selectAll() {
    BUSINESS_CATEGORIES.forEach(cat => {
      enabledCategories[cat.name] = true
    })
  }

  function deselectAll() {
    BUSINESS_CATEGORIES.forEach(cat => {
      enabledCategories[cat.name] = false
    })
  }

  let allSelected = $derived(
    BUSINESS_CATEGORIES.every(cat => enabledCategories[cat.name])
  )

  let noneSelected = $derived(
    BUSINESS_CATEGORIES.every(cat => !enabledCategories[cat.name])
  )
</script>

<div class="bg-gray-900 border-2 border-gray-700 shadow-lg" style="z-index: 1000;">
  <!-- Header -->
  <button
    onclick={() => isExpanded = !isExpanded}
    class="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-800 transition-colors"
  >
    <div class="flex items-center gap-2">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class="text-gray-400">
        <path d="M2 4 L6 4 M2 8 L10 8 M2 12 L8 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="12" cy="4" r="2" stroke="currentColor" stroke-width="1.5" fill="none"/>
      </svg>
      <span class="text-xs font-bold text-gray-400 tracking-wide">FILTER CATEGORIES</span>
    </div>
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      class={`text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
    >
      <path d="M2 4 L6 8 L10 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>

  {#if isExpanded}
    <div class="border-t border-gray-700">
      <!-- Select All / Deselect All -->
      <div class="px-3 py-2 border-b border-gray-700 flex gap-2">
        <button
          onclick={selectAll}
          disabled={allSelected}
          class="flex-1 px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-gray-300 transition-colors"
        >
          All
        </button>
        <button
          onclick={deselectAll}
          disabled={noneSelected}
          class="flex-1 px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-gray-300 transition-colors"
        >
          None
        </button>
      </div>

      <!-- Category List -->
      <div class="max-h-80 overflow-y-auto">
        {#each BUSINESS_CATEGORIES as category}
          <button
            onclick={() => toggleCategory(category.name)}
            class="w-full px-3 py-2 flex items-center gap-2 hover:bg-gray-800 transition-colors border-b border-gray-800 last:border-0"
          >
            <!-- Checkbox -->
            <div class={`w-4 h-4 border-2 flex items-center justify-center ${
              enabledCategories[category.name]
                ? 'bg-gray-700 border-gray-500'
                : 'border-gray-600'
            }`}>
              {#if enabledCategories[category.name]}
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                  <path d="M2 5 L4 7 L8 3" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              {/if}
            </div>

            <!-- Color indicator -->
            <div class="w-3 h-3 border border-gray-700" style="background-color: {category.color}"></div>

            <!-- Category name -->
            <span class="text-xs text-gray-300 flex-1 text-left">{category.name}</span>

            <!-- Count badge -->
            {#if businessCounts[category.name] > 0}
              <span class="px-2 py-0.5 bg-gray-800 border border-gray-600 text-gray-400 text-xs font-mono">
                {businessCounts[category.name]}
              </span>
            {/if}
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>

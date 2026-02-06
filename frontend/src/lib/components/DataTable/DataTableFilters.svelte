<script>
  let {
    categoryFilter,
    contactFilter,
    selectedCategories = $bindable([]),
    contactFilters = $bindable({ hasPhone: false, hasEmail: false, hasWebsite: false })
  } = $props()
</script>

<div class="flex flex-col gap-3">
  {#if categoryFilter?.enabled}
    <div class="flex flex-wrap gap-2 items-center">
      <span class="text-xs text-gray-400 font-semibold tracking-wide">CATEGORY:</span>
      {#each categoryFilter.categories as category}
        <label
          class="flex items-center gap-1.5 px-2 py-1 bg-gray-800 border border-gray-700
                 cursor-pointer hover:bg-gray-750 transition-colors text-xs"
        >
          <input
            type="checkbox"
            value={category.name}
            bind:group={selectedCategories}
            class="form-checkbox text-orange-500 w-3 h-3"
          />
          <span class="text-gray-300">{category.name}</span>
        </label>
      {/each}
    </div>
  {/if}

  {#if contactFilter?.enabled}
    <div class="flex flex-wrap gap-2 items-center">
      <span class="text-xs text-gray-400 font-semibold tracking-wide">CONTACT INFO:</span>
      <button
        onclick={() => contactFilters.hasPhone = !contactFilters.hasPhone}
        class={`px-3 py-1 text-xs font-medium border transition-colors ${
          contactFilters.hasPhone
            ? 'bg-orange-500 border-orange-500 text-white'
            : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-750'
        }`}
      >
        Has Phone
      </button>
      <button
        onclick={() => contactFilters.hasEmail = !contactFilters.hasEmail}
        class={`px-3 py-1 text-xs font-medium border transition-colors ${
          contactFilters.hasEmail
            ? 'bg-orange-500 border-orange-500 text-white'
            : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-750'
        }`}
      >
        Has Email
      </button>
      <button
        onclick={() => contactFilters.hasWebsite = !contactFilters.hasWebsite}
        class={`px-3 py-1 text-xs font-medium border transition-colors ${
          contactFilters.hasWebsite
            ? 'bg-orange-500 border-orange-500 text-white'
            : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-750'
        }`}
      >
        Has Website
      </button>
    </div>
  {/if}
</div>

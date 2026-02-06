<script>
  let {
    currentPage = $bindable(1),
    itemsPerPage = $bindable(10),
    totalPages,
    totalItems
  } = $props()

  const startIndex = $derived((currentPage - 1) * itemsPerPage + 1)
  const endIndex = $derived(Math.min(currentPage * itemsPerPage, totalItems))

  // Calculate visible page numbers (show max 7 page buttons)
  const visiblePages = $derived.by(() => {
    const pages = []
    const maxVisible = 7

    if (totalPages <= maxVisible) {
      // Show all pages
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      // Show first, last, current and nearby pages
      if (currentPage <= 4) {
        // Near start
        for (let i = 1; i <= 5; i++) pages.push(i)
        pages.push('...')
        pages.push(totalPages)
      } else if (currentPage >= totalPages - 3) {
        // Near end
        pages.push(1)
        pages.push('...')
        for (let i = totalPages - 4; i <= totalPages; i++) pages.push(i)
      } else {
        // Middle
        pages.push(1)
        pages.push('...')
        for (let i = currentPage - 1; i <= currentPage + 1; i++) pages.push(i)
        pages.push('...')
        pages.push(totalPages)
      }
    }

    return pages
  })
</script>

<div class="flex items-center justify-between px-4 py-3 border-t border-gray-700 bg-gray-800">
  <div class="flex items-center gap-2">
    <span class="text-xs text-gray-400">
      Showing {startIndex}-{endIndex} of {totalItems}
    </span>
  </div>

  <div class="flex items-center gap-2">
    <button
      onclick={() => currentPage--}
      disabled={currentPage === 1}
      class="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 disabled:opacity-50
             disabled:cursor-not-allowed border border-gray-600 text-gray-300
             transition-colors"
    >
      PREV
    </button>

    <div class="flex gap-1">
      {#each visiblePages as page}
        {#if page === '...'}
          <span class="px-2 py-1 text-xs text-gray-500">...</span>
        {:else}
          <button
            onclick={() => currentPage = page}
            class={`px-3 py-1 text-xs border transition-colors ${
              page === currentPage
                ? 'bg-orange-500 border-orange-500 text-white'
                : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {page}
          </button>
        {/if}
      {/each}
    </div>

    <button
      onclick={() => currentPage++}
      disabled={currentPage === totalPages}
      class="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 disabled:opacity-50
             disabled:cursor-not-allowed border border-gray-600 text-gray-300
             transition-colors"
    >
      NEXT
    </button>
  </div>

  <select
    bind:value={itemsPerPage}
    class="px-2 py-1 text-xs bg-gray-700 border border-gray-600 text-gray-300"
  >
    <option value={10}>10 per page</option>
    <option value={25}>25 per page</option>
    <option value={50}>50 per page</option>
    <option value={100}>100 per page</option>
  </select>
</div>

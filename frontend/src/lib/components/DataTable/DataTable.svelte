<script>
  import DataTableSearch from './DataTableSearch.svelte'
  import DataTableFilters from './DataTableFilters.svelte'
  import DataTableHeader from './DataTableHeader.svelte'
  import DataTableCell from './DataTableCell.svelte'
  import DataTablePagination from './DataTablePagination.svelte'
  import {
    searchData,
    sortData,
    filterByCategories,
    filterByContactInfo,
    validateColumns
  } from './dataTableUtils.js'
  import { exportToCSV, exportToJSON } from './exportUtils.js'

  // Props
  let {
    data = [],
    columns = [],
    pageSize = 10,
    searchable = true,
    sortable = true,
    selectable = false,
    selectedRows = $bindable([]),
    initialSearchTerm = '',
    categoryFilter = null,
    contactFilter = null,
    emptyState = { title: 'NO DATA', description: 'No data to display' },
    stickyHeader = true,
    headerClass = '',
    rowClass = ''
  } = $props()

  // Validate columns on mount
  $effect(() => {
    try {
      validateColumns(columns)
    } catch (error) {
      console.error(error.message)
    }
  })

  // Local state
  let searchTerm = $state('')
  let selectedCategories = $state([])
  let contactFilters = $state({ hasPhone: false, hasEmail: false, hasWebsite: false })
  let sortConfig = $state({ column: null, direction: null })
  let currentPage = $state(1)
  let itemsPerPage = $state(10)
  let showExportMenu = $state(false)

  // Sync itemsPerPage with pageSize prop
  $effect(() => {
    itemsPerPage = pageSize
  })

  // Sync initialSearchTerm with searchTerm
  $effect(() => {
    if (initialSearchTerm) {
      searchTerm = initialSearchTerm
    }
  })

  // Data transformation pipeline
  let searchedData = $derived(
    searchable ? searchData(data, searchTerm, columns) : data
  )

  let categoryFilteredData = $derived(
    categoryFilter?.enabled
      ? filterByCategories(searchedData, selectedCategories, categoryFilter)
      : searchedData
  )

  let contactFilteredData = $derived(
    contactFilter?.enabled
      ? filterByContactInfo(categoryFilteredData, contactFilters, contactFilter)
      : categoryFilteredData
  )

  let sortedData = $derived(
    sortable ? sortData(contactFilteredData, sortConfig, columns) : contactFilteredData
  )

  let finalData = $derived(sortedData)

  // Pagination
  let totalPages = $derived(Math.ceil(finalData.length / itemsPerPage))
  let paginatedData = $derived(
    finalData.slice(
      (currentPage - 1) * itemsPerPage,
      currentPage * itemsPerPage
    )
  )

  // Reset to page 1 when filters change
  $effect(() => {
    if (finalData.length > 0 && currentPage > totalPages) {
      currentPage = 1
    }
  })

  function handleSort(columnId) {
    if (!sortable) return

    if (sortConfig.column === columnId) {
      if (sortConfig.direction === 'asc') {
        sortConfig = { column: columnId, direction: 'desc' }
      } else if (sortConfig.direction === 'desc') {
        sortConfig = { column: null, direction: null }
      }
    } else {
      sortConfig = { column: columnId, direction: 'asc' }
    }
  }

  function clearAllFilters() {
    searchTerm = ''
    selectedCategories = []
    contactFilters = { hasPhone: false, hasEmail: false, hasWebsite: false }
    sortConfig = { column: null, direction: null }
  }

  // Selection helpers
  const allSelected = $derived(
    selectable && finalData.length > 0 && finalData.every(row => selectedRows.includes(row))
  )

  const someSelected = $derived(
    selectable && selectedRows.length > 0 && !allSelected
  )

  function toggleSelectAll() {
    if (allSelected) {
      selectedRows = []
    } else {
      selectedRows = [...finalData]
    }
  }

  function toggleRowSelection(row) {
    const index = selectedRows.findIndex(r => r === row)
    if (index >= 0) {
      selectedRows = selectedRows.filter(r => r !== row)
    } else {
      selectedRows = [...selectedRows, row]
    }
  }

  function isRowSelected(row) {
    return selectedRows.some(r => r === row)
  }

  // Export functions
  function handleExportCSV() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)
    exportToCSV(sortedData, columns, `export-${timestamp}.csv`)
    showExportMenu = false
  }

  function handleExportJSON() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)
    exportToJSON(sortedData, columns, `export-${timestamp}.json`)
    showExportMenu = false
  }

  // Close export menu when clicking outside
  $effect(() => {
    if (!showExportMenu) return

    const handleClickOutside = (e) => {
      if (!e.target.closest('.export-container')) {
        showExportMenu = false
      }
    }

    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  })
</script>

<div class="flex flex-col h-full bg-gray-900">
  <!-- Filters bar -->
  {#if searchable || categoryFilter?.enabled || contactFilter?.enabled}
    <div class="border-b border-gray-700 bg-gray-800">
      <div class="flex items-center justify-between gap-4 p-4">
        {#if searchable}
          <div class="flex-1">
            <DataTableSearch bind:searchTerm />
          </div>
        {/if}

        <!-- Export button -->
        <div class="relative export-container">
          <button
            onclick={() => showExportMenu = !showExportMenu}
            class="px-4 py-2 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors flex items-center gap-2 whitespace-nowrap"
            disabled={sortedData.length === 0}
            class:opacity-50={sortedData.length === 0}
            class:cursor-not-allowed={sortedData.length === 0}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            EXPORT ({sortedData.length})
          </button>

          {#if showExportMenu}
            <div class="absolute right-0 mt-1 w-40 bg-gray-800 border border-gray-700 shadow-lg z-20">
              <button
                onclick={handleExportCSV}
                class="w-full px-4 py-2 text-xs text-left text-gray-300 hover:bg-gray-700 transition-colors"
              >
                Export as CSV
              </button>
              <button
                onclick={handleExportJSON}
                class="w-full px-4 py-2 text-xs text-left text-gray-300 hover:bg-gray-700 transition-colors border-t border-gray-700"
              >
                Export as JSON
              </button>
            </div>
          {/if}
        </div>
      </div>

      {#if categoryFilter?.enabled || contactFilter?.enabled}
        <div class="px-4 pb-4">
          <DataTableFilters
            {categoryFilter}
            {contactFilter}
            bind:selectedCategories
            bind:contactFilters
          />
        </div>
      {/if}
    </div>
  {/if}

  <!-- Table -->
  <div class="flex-1 overflow-auto">
    {#if paginatedData.length === 0}
      <div class="flex items-center justify-center h-full">
        <div class="text-center text-gray-400 border border-gray-700 p-8 bg-gray-900">
          {#if data.length === 0}
            <p class="text-sm font-medium mb-2 tracking-wide">{emptyState.title}</p>
            <p class="text-xs text-gray-600">{emptyState.description}</p>
          {:else}
            <p class="text-sm font-medium mb-2 tracking-wide">NO RESULTS</p>
            <p class="text-xs text-gray-600">Try adjusting your search or filters</p>
            <button
              onclick={clearAllFilters}
              class="mt-4 px-4 py-2 text-xs bg-orange-500 hover:bg-orange-600 text-white transition-colors"
            >
              CLEAR ALL FILTERS
            </button>
          {/if}
        </div>
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead class={`${stickyHeader ? 'sticky top-0' : ''} bg-gray-900 border-b-2 border-orange-500 z-10 ${headerClass}`}>
          <tr>
            {#if selectable}
              <th class="w-12 p-3">
                <input
                  type="checkbox"
                  checked={allSelected}
                  indeterminate={someSelected}
                  onchange={toggleSelectAll}
                  class="form-checkbox text-orange-500 w-4 h-4"
                />
              </th>
            {/if}
            <DataTableHeader
              {columns}
              {sortConfig}
              {sortable}
              onSort={handleSort}
            />
          </tr>
        </thead>
        <tbody>
          {#each paginatedData as row, i}
            <tr class="border-b border-gray-700 hover:bg-gray-700 transition-colors {rowClass}">
              {#if selectable}
                <td class="w-12 p-3">
                  <input
                    type="checkbox"
                    checked={isRowSelected(row)}
                    onchange={() => toggleRowSelection(row)}
                    class="form-checkbox text-orange-500 w-4 h-4"
                  />
                </td>
              {/if}
              {#each columns as column}
                <DataTableCell {column} {row} rowIndex={i} />
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <!-- Pagination -->
  {#if finalData.length > 0}
    <DataTablePagination
      bind:currentPage
      bind:itemsPerPage
      {totalPages}
      totalItems={finalData.length}
    />
  {/if}
</div>

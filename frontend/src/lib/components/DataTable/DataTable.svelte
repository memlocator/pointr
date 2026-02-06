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
</script>

<div class="flex flex-col h-full bg-gray-900">
  <!-- Filters bar -->
  {#if searchable || categoryFilter?.enabled || contactFilter?.enabled}
    <div class="border-b border-gray-700 bg-gray-800">
      {#if searchable}
        <div class="p-4">
          <DataTableSearch bind:searchTerm />
        </div>
      {/if}

      {#if categoryFilter?.enabled || contactFilter?.enabled}
        <div class="p-4 pt-0">
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

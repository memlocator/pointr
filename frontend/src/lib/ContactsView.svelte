<script>
  import DataTable from './components/DataTable/DataTable.svelte'
  import { BUSINESS_CATEGORIES } from './businessCategories.js'
  import CategoryFilter from './components/CategoryFilter.svelte'

  let {
    businesses = [],
    selectedBusinesses = $bindable([]),
    currentView = $bindable('contacts'),
    enabledCategories = $bindable({}),
    showContactsOnly = $bindable(false)
  } = $props()

  // Filter by both category and contact info
  let contactBusinesses = $derived.by(() => {
    return businesses.filter(business => {
      // Filter by category
      const category = BUSINESS_CATEGORIES.find(cat =>
        cat.types.includes(business.type)
      )
      const categoryName = category ? category.name : 'Other'
      if (!enabledCategories[categoryName]) {
        return false
      }

      // In contacts view, always show only businesses with contact info
      return business.phone || business.email || business.website
    })
  })

  const columns = [
    { id: 'name', header: 'Name' },
    {
      id: 'phone',
      header: 'Phone',
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
      render: (value) => value ? {
        type: 'link',
        value: value,
        href: value.startsWith('http') ? value : `https://${value}`,
        class: 'text-blue-400 hover:text-blue-300 hover:underline'
      } : { type: 'text', value: '-', class: 'text-gray-600' }
    }
  ]
</script>

<div class="w-full h-full bg-gray-900 p-6 flex flex-col gap-4">
  {#if selectedBusinesses.length > 0}
    <div class="bg-gray-800 border-2 border-orange-500 p-4">
      <div class="flex items-center justify-between">
        <span class="text-sm font-bold text-orange-400 tracking-wide">
          {selectedBusinesses.length} SELECTED
        </span>
        <button
          onclick={() => currentView = 'recon'}
          class="px-4 py-2 text-xs bg-orange-500 hover:bg-orange-600 text-white font-medium transition-colors"
        >
          RUN RECON
        </button>
      </div>
    </div>
  {/if}

  <!-- Category Filter -->
  <CategoryFilter {businesses} bind:enabledCategories bind:showContactsOnly hideContactToggle={true} />

  <div class="bg-gray-800 border-2 border-gray-700 shadow-lg flex-1 overflow-hidden">
    <DataTable
      data={contactBusinesses}
      {columns}
      pageSize={25}
      searchable={true}
      sortable={true}
      selectable={true}
      bind:selectedRows={selectedBusinesses}
      categoryFilter={{ enabled: false }}
      contactFilter={{ enabled: false }}
      emptyState={{
        title: 'NO CONTACTS',
        description: 'Draw a polygon on the map and click ENRICH to find businesses with contact information'
      }}
    />
  </div>
</div>

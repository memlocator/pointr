<script>
  let { columns, sortConfig, sortable, onSort } = $props()
</script>

{#each columns as column}
  <th
    onclick={() => column.sortable !== false && sortable && onSort(column.id)}
    class={`text-left p-3 text-xs font-semibold text-gray-400 tracking-wide uppercase
      ${column.sortable !== false && sortable ? 'cursor-pointer hover:text-gray-200' : ''}`}
    style={column.width ? `width: ${column.width}` : ''}
  >
    <div class="flex items-center gap-2">
      <span>{column.header}</span>
      {#if sortConfig.column === column.id}
        <span class="text-orange-500">
          {sortConfig.direction === 'asc' ? '↑' : '↓'}
        </span>
      {/if}
    </div>
  </th>
{/each}

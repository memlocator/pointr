<script>
  import DataTableCell from './DataTableCell.svelte'

  let { row, columns, rowIndex, class: className = '' } = $props()
</script>

<tr class="border-b border-gray-700 hover:bg-gray-700 transition-colors {className}">
  {#each columns as column}
    <DataTableCell {column} {row} {rowIndex} />
  {/each}
</tr>

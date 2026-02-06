<script>
  let { column, row, rowIndex } = $props()

  const cellValue = $derived.by(() => {
    const rawValue = row[column.id]

    // Handle custom render function
    if (column.render) {
      const renderResult = column.render(rawValue, row, rowIndex)
      return renderResult
    }

    // Handle format function
    if (column.format) {
      return { type: 'text', value: column.format(rawValue, row) }
    }

    // Default: simple text
    return { type: 'text', value: rawValue ?? '-' }
  })
</script>

<td class="p-3 text-gray-300">
  {#if cellValue.type === 'link'}
    <a
      href={cellValue.href}
      class={cellValue.class || 'text-blue-400 hover:text-blue-300 hover:underline'}
    >
      {cellValue.value}
    </a>
  {:else}
    <span class={cellValue.class || 'text-gray-300'}>
      {cellValue.value}
    </span>
  {/if}
</td>

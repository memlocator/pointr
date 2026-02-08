<script>
  let {
    fileName,
    datasetName,
    availableFields = [],
    suggestedMapping = {},
    onCancel,
    onConfirm
  } = $props()

  let nameInput = $state(datasetName || '')
  let mapping = $state({
    name: '',
    category: '',
    phone: '',
    website: '',
    email: '',
    description: '',
    ...suggestedMapping
  })

  const targetFields = [
    { key: 'name', label: 'Name', required: true },
    { key: 'category', label: 'Category' },
    { key: 'phone', label: 'Phone' },
    { key: 'website', label: 'Website' },
    { key: 'email', label: 'Email' },
    { key: 'description', label: 'Description' }
  ]

  function canSubmit() {
    return nameInput.trim().length > 0 && mapping.name
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') onCancel()
  }

  function submit() {
    if (!canSubmit()) return
    onConfirm({ datasetName: nameInput.trim(), mapping })
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="fixed inset-0 bg-black/60 flex items-center justify-center"
  style="z-index: 2100;"
  onclick={(e) => { if (e.target === e.currentTarget) onCancel() }}
  role="dialog"
  aria-modal="true"
>
  <div class="bg-gray-900 border-2 border-gray-700 w-full max-w-xl mx-4">
    <div class="flex items-start justify-between px-5 py-4 border-b border-gray-700">
      <div>
        <div class="text-xs text-gray-500 mb-1">Upload with column mapping</div>
        <h2 class="text-base font-semibold text-gray-100 truncate">{fileName}</h2>
      </div>
      <button onclick={onCancel} class="text-gray-500 hover:text-gray-300">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      </button>
    </div>

    <div class="px-5 py-4">
      <label class="text-xs text-gray-500">Datasource name</label>
      <input
        type="text"
        bind:value={nameInput}
        class="w-full mt-1 px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-sm focus:border-amber-500 focus:outline-none"
        placeholder="Dataset name"
      />

      <div class="mt-4 text-xs text-gray-500">Map fields from your file to expected properties.</div>

      <div class="mt-3 space-y-2">
        {#each targetFields as f}
          <div class="flex items-center gap-3">
            <div class="w-28 text-xs text-gray-400">
              {f.label}{f.required ? ' *' : ''}
            </div>
            <select
              bind:value={mapping[f.key]}
              class="flex-1 px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs focus:border-amber-500 focus:outline-none"
            >
              <option value="">{f.required ? 'Select a source field' : 'None'}</option>
              {#each availableFields as field}
                <option value={field}>{field}</option>
              {/each}
            </select>
          </div>
        {/each}
      </div>

      <div class="mt-4 text-xs text-gray-600">
        Required: name must map to a field in your file's properties.
      </div>
    </div>

    <div class="px-5 py-3 border-t border-gray-700 flex items-center justify-between">
      <button onclick={onCancel} class="text-xs text-gray-400 hover:text-gray-200">Cancel</button>
      <button
        onclick={submit}
        disabled={!canSubmit()}
        class={`text-xs px-3 py-1.5 border ${canSubmit() ? 'border-amber-500 text-amber-400 hover:text-amber-300' : 'border-gray-700 text-gray-600'}`}
      >
        Upload
      </button>
    </div>
  </div>
</div>

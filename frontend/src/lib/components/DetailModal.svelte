<script>
  import { BUSINESS_CATEGORIES } from '../businessCategories.js'

  let {
    entity,        // { type: 'poi'|'area', id, name, category?, description, lat?, lng? }
    onClose,
    onSave         // async (updated) => void
  } = $props()

  let editing = $state(false)
  let inputName = $state('')
  let inputCategory = $state('')
  let inputDescription = $state('')
  let inputPhone = $state('')
  let inputWebsite = $state('')

function startEdit() {
    inputName = entity.name
    inputCategory = entity.category || ''
    inputDescription = entity.description || ''
    inputPhone = entity.phone || ''
    inputWebsite = entity.website || ''
    editing = true
  }

  async function save() {
    await onSave({ name: inputName.trim(), category: inputCategory, description: inputDescription, phone: inputPhone, website: inputWebsite })
    editing = false
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') onClose()
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Backdrop -->
<div
  class="fixed inset-0 bg-black/60 flex items-center justify-center"
  style="z-index: 2000;"
  onclick={(e) => { if (e.target === e.currentTarget) onClose() }}
  role="dialog"
  aria-modal="true"
>
  <div class="bg-gray-900 border-2 border-gray-700 w-full max-w-2xl max-h-[80vh] flex flex-col mx-4">
    <!-- Header -->
    <div class="flex items-start justify-between px-5 py-4 border-b border-gray-700">
      <div class="flex-1 min-w-0">
        {#if editing}
          <input
            type="text"
            bind:value={inputName}
            class="w-full bg-gray-800 border border-gray-600 text-gray-100 text-base px-2 py-1 focus:border-amber-500 focus:outline-none"
            placeholder="Name"
          />
        {:else}
          <h2 class="text-base font-semibold text-gray-100 truncate">{entity.name}</h2>
          {#if entity.category}
            <div class="text-xs text-gray-500 mt-0.5">{entity.category}</div>
          {/if}
          {#if entity.lat != null}
            <div class="text-xs text-gray-600 mt-0.5">{entity.lat.toFixed(5)}, {entity.lng.toFixed(5)}</div>
          {/if}
        {/if}
      </div>
      <div class="flex items-center gap-2 ml-4 shrink-0">
        {#if !editing}
          <button
            onclick={startEdit}
            class="text-xs text-amber-400 hover:text-amber-300 px-2 py-1 border border-gray-700 hover:border-amber-500"
          >Edit</button>
        {/if}
        <button onclick={onClose} class="text-gray-500 hover:text-gray-300">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
      </div>
    </div>

    <!-- Category selector (edit mode, POI only) -->
    {#if editing && entity.type === 'poi'}
      <div class="px-5 pt-3">
        <select
          bind:value={inputCategory}
          class="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 text-gray-200 text-xs focus:border-amber-500 focus:outline-none"
        >
          {#each BUSINESS_CATEGORIES as cat}
            <option value={cat.name}>{cat.name}</option>
          {/each}
        </select>
      </div>
    {/if}

    <!-- Body -->
    <div class="flex-1 overflow-y-auto px-5 py-4">
      {#if editing}
        <textarea
          bind:value={inputDescription}
          placeholder="Description"
          class="w-full h-40 px-3 py-2 bg-gray-800 border border-gray-600 text-gray-200 text-sm placeholder-gray-600 focus:border-amber-500 focus:outline-none resize-none font-mono mb-2"
        ></textarea>
        {#if entity.type === 'poi'}
          <input
            type="tel"
            bind:value={inputPhone}
            placeholder="Phone (optional)"
            class="w-full px-3 py-2 bg-gray-800 border border-gray-600 text-gray-200 text-sm placeholder-gray-600 focus:border-amber-500 focus:outline-none mb-2"
          />
          <input
            type="url"
            bind:value={inputWebsite}
            placeholder="Website (optional)"
            class="w-full px-3 py-2 bg-gray-800 border border-gray-600 text-gray-200 text-sm placeholder-gray-600 focus:border-amber-500 focus:outline-none"
          />
        {/if}
      {:else}
        {#if entity.description}
          <p class="text-gray-300 text-sm whitespace-pre-wrap mb-3">{entity.description}</p>
        {:else}
          <p class="text-gray-600 text-sm italic mb-3">No description.</p>
        {/if}
        {#if entity.type === 'poi' && (entity.phone || entity.website)}
          <div class="flex flex-col gap-1 mt-2">
            {#if entity.phone}
              <a href="tel:{entity.phone}" class="text-sm text-blue-400 hover:text-blue-300">{entity.phone}</a>
            {/if}
            {#if entity.website}
              <a href={entity.website} target="_blank" rel="noopener" class="text-sm text-blue-400 hover:text-blue-300 truncate">{entity.website}</a>
            {/if}
          </div>
        {/if}
      {/if}
    </div>

    <!-- Footer -->
    {#if editing}
      <div class="flex gap-2 px-5 py-3 border-t border-gray-700">
        <button
          onclick={save}
          disabled={!inputName.trim()}
          class="flex-1 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-xs font-medium"
        >Save</button>
        <button
          onclick={() => editing = false}
          class="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs"
        >Cancel</button>
      </div>
    {/if}
  </div>
</div>


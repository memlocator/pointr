<script>
  import { onMount } from 'svelte'
  import { apiUrl } from '../api.js'
  import SwaggerUI from 'swagger-ui-dist/swagger-ui-bundle'
  import 'swagger-ui-dist/swagger-ui.css'

  let { onClose } = $props()
  let container

  onMount(() => {
    const ui = SwaggerUI({
      domNode: container,
      url: apiUrl('/openapi.json'),
      deepLinking: true,
      presets: [SwaggerUI.presets.apis],
      layout: 'BaseLayout'
    })
    return () => {
      if (ui && ui.destroy) ui.destroy()
    }
  })

  function handleKeydown(e) {
    if (e.key === 'Escape') onClose()
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="fixed inset-0 bg-black/70 flex items-center justify-center"
  style="z-index: 2200;"
  onclick={(e) => { if (e.target === e.currentTarget) onClose() }}
  role="dialog"
  aria-modal="true"
>
  <div class="bg-white w-[95vw] h-[90vh] rounded-sm overflow-hidden border border-gray-300 flex flex-col">
    <div class="flex items-center justify-between px-4 py-2 bg-gray-900 text-gray-100">
      <div class="text-sm font-semibold">API Docs</div>
      <button onclick={onClose} class="text-gray-400 hover:text-white">Close</button>
    </div>
    <div class="flex-1 overflow-auto" bind:this={container}></div>
  </div>
</div>

<script>
  let { searchTerm = $bindable('') } = $props()
</script>

<input
  type="text"
  bind:value={searchTerm}
  placeholder="Search all columns..."
  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 text-gray-200
         placeholder-gray-500 focus:border-orange-500 focus:outline-none text-sm"
/>

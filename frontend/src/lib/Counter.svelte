<script>
  let count = $state(0)
  const increment = () => {
    count += 1
  }
</script>

<button
  onclick={increment}
  class="px-6 py-3 bg-gray-800 hover:bg-gray-700 border border-gray-600 hover:border-indigo-500 text-white font-medium rounded-lg transition-all duration-200 cursor-pointer"
>
  count is {count}
</button>

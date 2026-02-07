<script>
  let { asnInfo } = $props()
</script>

{#if asnInfo && asnInfo.asn}
  <div class="bg-gray-900 border border-gray-700 p-4">
    <h4 class="text-sm font-bold text-gray-400 tracking-wide mb-3">ASN / BGP INFORMATION</h4>
    <div class="space-y-2 text-xs">
      {#if asnInfo.asn}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">ASN:</span>
          <span class="text-orange-400 font-mono">{asnInfo.asn}</span>
        </div>
      {/if}
      {#if asnInfo.organization}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Organization:</span>
          <span class="text-gray-300">{asnInfo.organization}</span>
        </div>
      {/if}
      {#if asnInfo.country}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Country:</span>
          <span class="text-gray-300">{asnInfo.country}</span>
        </div>
      {/if}
      {#if asnInfo.rir}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">RIR:</span>
          <span class="text-gray-300">{asnInfo.rir}</span>
        </div>
      {/if}
      {#if asnInfo.network_type}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Network Type:</span>
          <span class="text-gray-300">{asnInfo.network_type}</span>
        </div>
      {/if}
      {#if asnInfo.peering_policy}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Peering Policy:</span>
          <span class="text-gray-300">{asnInfo.peering_policy}</span>
        </div>
      {/if}
      {#if asnInfo.bgp_prefix}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">BGP Prefix:</span>
          <span class="text-purple-400 font-mono">{asnInfo.bgp_prefix}</span>
        </div>
      {/if}

      <!-- BGP Prefixes IPv4 -->
      {#if asnInfo.prefix_count_v4 > 0}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">IPv4 Prefixes:</span>
          <div class="flex-1">
            <div class="text-gray-400 mb-1">
              {asnInfo.prefix_count_v4} total
              {#if asnInfo.prefixes_v4 && asnInfo.prefixes_v4.length > 0}
                (showing first {asnInfo.prefixes_v4.length})
              {/if}
            </div>
            {#if asnInfo.prefixes_v4 && asnInfo.prefixes_v4.length > 0}
              <div class="space-y-1">
                {#each asnInfo.prefixes_v4 as prefix}
                  <div class="text-purple-400 font-mono text-xs">{prefix}</div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- BGP Prefixes IPv6 -->
      {#if asnInfo.prefix_count_v6 > 0}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">IPv6 Prefixes:</span>
          <div class="flex-1">
            <div class="text-gray-400 mb-1">
              {asnInfo.prefix_count_v6} total
              {#if asnInfo.prefixes_v6 && asnInfo.prefixes_v6.length > 0}
                (showing first {asnInfo.prefixes_v6.length})
              {/if}
            </div>
            {#if asnInfo.prefixes_v6 && asnInfo.prefixes_v6.length > 0}
              <div class="space-y-1">
                {#each asnInfo.prefixes_v6 as prefix}
                  <div class="text-purple-400 font-mono text-xs">{prefix}</div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Upstreams (Transit Providers) -->
      {#if asnInfo.upstreams && asnInfo.upstreams.length > 0}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Upstreams:</span>
          <div class="flex-1 flex flex-wrap gap-2">
            {#each asnInfo.upstreams as upstream}
              <span class="px-2 py-1 bg-gray-800 border border-blue-500/30 text-blue-400 font-mono text-xs">{upstream}</span>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Peers -->
      {#if asnInfo.peers && asnInfo.peers.length > 0}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Peers:</span>
          <div class="flex-1">
            <div class="text-gray-400 mb-1">{asnInfo.peers.length} peer ASNs</div>
            <div class="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
              {#each asnInfo.peers as peer}
                <span class="px-2 py-1 bg-gray-800 border border-green-500/30 text-green-400 font-mono text-xs">{peer}</span>
              {/each}
            </div>
          </div>
        </div>
      {/if}

      <!-- Downstreams (Customers) -->
      {#if asnInfo.downstreams && asnInfo.downstreams.length > 0}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Downstreams:</span>
          <div class="flex-1 flex flex-wrap gap-2">
            {#each asnInfo.downstreams as downstream}
              <span class="px-2 py-1 bg-gray-800 border border-yellow-500/30 text-yellow-400 font-mono text-xs">{downstream}</span>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Peering Facilities -->
      {#if asnInfo.peering_facilities && asnInfo.peering_facilities.length > 0}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Peering IXs:</span>
          <div class="flex-1">
            {#each asnInfo.peering_facilities as facility}
              <div class="text-gray-300">{facility}</div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Abuse Contacts -->
      {#if asnInfo.abuse_contacts && asnInfo.abuse_contacts.length > 0}
        <div class="flex gap-2">
          <span class="text-gray-500 w-32">Abuse Contacts:</span>
          <div class="flex-1">
            {#each asnInfo.abuse_contacts as contact}
              <div class="text-gray-300">{contact}</div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

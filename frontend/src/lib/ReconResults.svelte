<script>
  let { result, mode = null, onRemove = null } = $props()

  // Color scheme based on recon mode
  const modeColors = $derived({
    border: mode === 'silent' ? 'border-purple-500' : mode === 'full' ? 'border-orange-500' : 'border-gray-700',
    text: mode === 'silent' ? 'text-purple-400' : mode === 'full' ? 'text-orange-400' : 'text-gray-400'
  })

  // Helper to check if security header exists
  function hasSecurityHeader(value) {
    return value && value.trim().length > 0
  }

  // Count security headers
  const securityScore = $derived(
    (hasSecurityHeader(result.security_headers.strict_transport_security) ? 1 : 0) +
    (hasSecurityHeader(result.security_headers.content_security_policy) ? 1 : 0) +
    (hasSecurityHeader(result.security_headers.x_frame_options) ? 1 : 0) +
    (hasSecurityHeader(result.security_headers.x_content_type_options) ? 1 : 0) +
    (hasSecurityHeader(result.security_headers.referrer_policy) ? 1 : 0) +
    (hasSecurityHeader(result.security_headers.permissions_policy) ? 1 : 0)
  )

  const scoreColor = $derived(
    securityScore >= 5 ? 'text-green-400' :
    securityScore >= 3 ? 'text-yellow-400' :
    'text-red-400'
  )
</script>

<div class="bg-gray-800 border-2 p-6 {modeColors.border} relative">
  <!-- Domain Header -->
  <div class="mb-6 pb-4 border-b border-gray-700 flex items-start justify-between">
    <div class="flex-1">
      <h3 class="text-xl font-bold tracking-wide {modeColors.text}">{result.domain}</h3>
      {#if result.error}
        <p class="text-sm text-red-400 mt-2">ERROR: {result.error}</p>
      {/if}
    </div>
    {#if onRemove}
      <button
        onclick={() => onRemove(result.domain)}
        class="ml-4 p-1 text-gray-500 hover:text-gray-200 hover:bg-gray-700 transition-colors rounded"
        title="Remove this result"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 4 L16 16 M16 4 L4 16" stroke-linecap="round"/>
        </svg>
      </button>
    {/if}
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- DNS Records -->
    {#if result.dns_records && result.dns_records.length > 0}
      <div class="bg-gray-900 border border-gray-700 p-4">
        <h4 class="text-sm font-bold text-gray-400 tracking-wide mb-3">DNS RECORDS</h4>
        <div class="space-y-2">
          {#each result.dns_records as record}
            <div class="flex items-start gap-3 text-xs">
              <span class="px-2 py-0.5 bg-blue-900 text-blue-300 font-mono font-semibold">{record.type}</span>
              <span class="text-gray-300 font-mono flex-1 break-all">{record.value}</span>
              <span class="text-gray-600 font-mono">{record.ttl}s</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Security Headers (only show if data exists) -->
    {#if result.security_headers && (result.security_headers.strict_transport_security || result.security_headers.content_security_policy || result.security_headers.x_frame_options || result.security_headers.x_content_type_options || result.security_headers.referrer_policy || result.security_headers.permissions_policy)}
    <div class="bg-gray-900 border border-gray-700 p-4">
      <div class="flex items-center justify-between mb-3">
        <h4 class="text-sm font-bold text-gray-400 tracking-wide">SECURITY HEADERS</h4>
        <div class="flex items-center gap-2">
          <div class="w-24 h-2 bg-gray-800 border border-gray-700">
            <div
              class={`h-full transition-all ${securityScore >= 5 ? 'bg-green-500' : securityScore >= 3 ? 'bg-yellow-500' : 'bg-red-500'}`}
              style="width: {(securityScore / 6) * 100}%"
            ></div>
          </div>
          <span class={`text-xs font-bold ${scoreColor}`}>{securityScore}/6</span>
        </div>
      </div>
      <div class="space-y-3">
        <!-- HSTS -->
        <div class="bg-gray-800 border border-gray-700 p-2">
          <div class="flex items-center gap-2 mb-1">
            <span class={hasSecurityHeader(result.security_headers.strict_transport_security) ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
              {hasSecurityHeader(result.security_headers.strict_transport_security) ? '✓' : '✗'}
            </span>
            <span class="text-gray-300 font-semibold text-xs">Strict-Transport-Security</span>
          </div>
          <p class="text-xs text-gray-500 ml-6">Forces HTTPS connections</p>
          {#if hasSecurityHeader(result.security_headers.strict_transport_security)}
            <code class="text-xs text-gray-400 font-mono ml-6 block mt-1 truncate">{result.security_headers.strict_transport_security}</code>
          {/if}
        </div>

        <!-- CSP -->
        <div class="bg-gray-800 border border-gray-700 p-2">
          <div class="flex items-center gap-2 mb-1">
            <span class={hasSecurityHeader(result.security_headers.content_security_policy) ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
              {hasSecurityHeader(result.security_headers.content_security_policy) ? '✓' : '✗'}
            </span>
            <span class="text-gray-300 font-semibold text-xs">Content-Security-Policy</span>
          </div>
          <p class="text-xs text-gray-500 ml-6">Prevents XSS attacks</p>
          {#if hasSecurityHeader(result.security_headers.content_security_policy)}
            <code class="text-xs text-gray-400 font-mono ml-6 block mt-1 truncate">{result.security_headers.content_security_policy.substring(0, 60)}...</code>
          {/if}
        </div>

        <!-- X-Frame-Options -->
        <div class="bg-gray-800 border border-gray-700 p-2">
          <div class="flex items-center gap-2 mb-1">
            <span class={hasSecurityHeader(result.security_headers.x_frame_options) ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
              {hasSecurityHeader(result.security_headers.x_frame_options) ? '✓' : '✗'}
            </span>
            <span class="text-gray-300 font-semibold text-xs">X-Frame-Options</span>
          </div>
          <p class="text-xs text-gray-500 ml-6">Prevents clickjacking</p>
          {#if hasSecurityHeader(result.security_headers.x_frame_options)}
            <code class="text-xs text-gray-400 font-mono ml-6 block mt-1">{result.security_headers.x_frame_options}</code>
          {/if}
        </div>

        <!-- X-Content-Type-Options -->
        <div class="bg-gray-800 border border-gray-700 p-2">
          <div class="flex items-center gap-2 mb-1">
            <span class={hasSecurityHeader(result.security_headers.x_content_type_options) ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
              {hasSecurityHeader(result.security_headers.x_content_type_options) ? '✓' : '✗'}
            </span>
            <span class="text-gray-300 font-semibold text-xs">X-Content-Type-Options</span>
          </div>
          <p class="text-xs text-gray-500 ml-6">Prevents MIME-sniffing</p>
          {#if hasSecurityHeader(result.security_headers.x_content_type_options)}
            <code class="text-xs text-gray-400 font-mono ml-6 block mt-1">{result.security_headers.x_content_type_options}</code>
          {/if}
        </div>

        <!-- Referrer-Policy -->
        <div class="bg-gray-800 border border-gray-700 p-2">
          <div class="flex items-center gap-2 mb-1">
            <span class={hasSecurityHeader(result.security_headers.referrer_policy) ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
              {hasSecurityHeader(result.security_headers.referrer_policy) ? '✓' : '✗'}
            </span>
            <span class="text-gray-300 font-semibold text-xs">Referrer-Policy</span>
          </div>
          <p class="text-xs text-gray-500 ml-6">Controls referrer information</p>
          {#if hasSecurityHeader(result.security_headers.referrer_policy)}
            <code class="text-xs text-gray-400 font-mono ml-6 block mt-1">{result.security_headers.referrer_policy}</code>
          {/if}
        </div>

        <!-- Permissions-Policy -->
        <div class="bg-gray-800 border border-gray-700 p-2">
          <div class="flex items-center gap-2 mb-1">
            <span class={hasSecurityHeader(result.security_headers.permissions_policy) ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
              {hasSecurityHeader(result.security_headers.permissions_policy) ? '✓' : '✗'}
            </span>
            <span class="text-gray-300 font-semibold text-xs">Permissions-Policy</span>
          </div>
          <p class="text-xs text-gray-500 ml-6">Controls browser features</p>
          {#if hasSecurityHeader(result.security_headers.permissions_policy)}
            <code class="text-xs text-gray-400 font-mono ml-6 block mt-1 truncate">{result.security_headers.permissions_policy.substring(0, 60)}...</code>
          {/if}
        </div>
      </div>
    </div>
    {/if}

    <!-- SSL Certificates -->
    {#if result.ssl_certificates && result.ssl_certificates.length > 0}
      <div class="bg-gray-900 border border-gray-700 p-4">
        <h4 class="text-sm font-bold text-gray-400 tracking-wide mb-3">SSL CERTIFICATES ({result.ssl_certificates.length})</h4>
        <div class="space-y-3 max-h-60 overflow-y-auto">
          {#each result.ssl_certificates.slice(0, 3) as cert}
            <div class="text-xs space-y-1 pb-3 border-b border-gray-800 last:border-0">
              <div class="text-gray-400">Issuer: <span class="text-gray-300">{cert.issuer.split(',')[0]}</span></div>
              <div class="text-gray-400">Valid: <span class="text-gray-300">{cert.not_before} → {cert.not_after}</span></div>
              {#if cert.san_domains && cert.san_domains.length > 1}
                <div class="text-gray-400">SANs: <span class="text-gray-600">{cert.san_domains.length} domains</span></div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Subdomains -->
    {#if result.subdomains && result.subdomains.length > 0}
      <div class="bg-gray-900 border border-gray-700 p-4">
        <h4 class="text-sm font-bold text-gray-400 tracking-wide mb-3">SUBDOMAINS ({result.subdomains.length})</h4>
        <div class="max-h-60 overflow-y-auto">
          <div class="flex flex-wrap gap-2">
            {#each result.subdomains as subdomain}
              <span class="px-2 py-1 bg-gray-800 text-gray-300 text-xs font-mono border border-gray-700">
                {subdomain}
              </span>
            {/each}
          </div>
        </div>
      </div>
    {/if}

    <!-- WHOIS Data -->
    {#if result.whois && (result.whois.registrar || result.whois.creation_date)}
      <div class="bg-gray-900 border border-gray-700 p-4">
        <h4 class="text-sm font-bold text-gray-400 tracking-wide mb-3">WHOIS</h4>
        <div class="space-y-2 text-xs">
          {#if result.whois.registrar}
            <div class="flex gap-2">
              <span class="text-gray-500 w-24">Registrar:</span>
              <span class="text-gray-300">{result.whois.registrar}</span>
            </div>
          {/if}
          {#if result.whois.registrant_org}
            <div class="flex gap-2">
              <span class="text-gray-500 w-24">Organization:</span>
              <span class="text-gray-300">{result.whois.registrant_org}</span>
            </div>
          {/if}
          {#if result.whois.creation_date}
            <div class="flex gap-2">
              <span class="text-gray-500 w-24">Created:</span>
              <span class="text-gray-300">{result.whois.creation_date}</span>
            </div>
          {/if}
          {#if result.whois.expiration_date}
            <div class="flex gap-2">
              <span class="text-gray-500 w-24">Expires:</span>
              <span class="text-gray-300">{result.whois.expiration_date}</span>
            </div>
          {/if}
          {#if result.whois.name_servers && result.whois.name_servers.length > 0}
            <div class="flex gap-2">
              <span class="text-gray-500 w-24">Name Servers:</span>
              <div class="flex-1">
                {#each result.whois.name_servers as ns}
                  <div class="text-gray-300 font-mono">{ns}</div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- ASN Info -->
    {#if result.asn_info && result.asn_info.asn}
      <div class="bg-gray-900 border border-gray-700 p-4">
        <h4 class="text-sm font-bold text-gray-400 tracking-wide mb-3">ASN / BGP INFORMATION</h4>
        <div class="space-y-2 text-xs">
          {#if result.asn_info.asn}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">ASN:</span>
              <span class="text-orange-400 font-mono">{result.asn_info.asn}</span>
            </div>
          {/if}
          {#if result.asn_info.organization}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Organization:</span>
              <span class="text-gray-300">{result.asn_info.organization}</span>
            </div>
          {/if}
          {#if result.asn_info.country}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Country:</span>
              <span class="text-gray-300">{result.asn_info.country}</span>
            </div>
          {/if}
          {#if result.asn_info.rir}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">RIR:</span>
              <span class="text-gray-300">{result.asn_info.rir}</span>
            </div>
          {/if}
          {#if result.asn_info.network_type}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Network Type:</span>
              <span class="text-gray-300">{result.asn_info.network_type}</span>
            </div>
          {/if}
          {#if result.asn_info.peering_policy}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Peering Policy:</span>
              <span class="text-gray-300">{result.asn_info.peering_policy}</span>
            </div>
          {/if}
          {#if result.asn_info.bgp_prefix}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">BGP Prefix:</span>
              <span class="text-purple-400 font-mono">{result.asn_info.bgp_prefix}</span>
            </div>
          {/if}

          <!-- BGP Prefixes IPv4 -->
          {#if result.asn_info.prefix_count_v4 > 0}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">IPv4 Prefixes:</span>
              <div class="flex-1">
                <div class="text-gray-400 mb-1">
                  {result.asn_info.prefix_count_v4} total
                  {#if result.asn_info.prefixes_v4 && result.asn_info.prefixes_v4.length > 0}
                    (showing first {result.asn_info.prefixes_v4.length})
                  {/if}
                </div>
                {#if result.asn_info.prefixes_v4 && result.asn_info.prefixes_v4.length > 0}
                  <div class="space-y-1">
                    {#each result.asn_info.prefixes_v4 as prefix}
                      <div class="text-purple-400 font-mono text-xs">{prefix}</div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <!-- BGP Prefixes IPv6 -->
          {#if result.asn_info.prefix_count_v6 > 0}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">IPv6 Prefixes:</span>
              <div class="flex-1">
                <div class="text-gray-400 mb-1">
                  {result.asn_info.prefix_count_v6} total
                  {#if result.asn_info.prefixes_v6 && result.asn_info.prefixes_v6.length > 0}
                    (showing first {result.asn_info.prefixes_v6.length})
                  {/if}
                </div>
                {#if result.asn_info.prefixes_v6 && result.asn_info.prefixes_v6.length > 0}
                  <div class="space-y-1">
                    {#each result.asn_info.prefixes_v6 as prefix}
                      <div class="text-purple-400 font-mono text-xs">{prefix}</div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <!-- Upstreams (Transit Providers) -->
          {#if result.asn_info.upstreams && result.asn_info.upstreams.length > 0}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Upstreams:</span>
              <div class="flex-1 flex flex-wrap gap-2">
                {#each result.asn_info.upstreams as upstream}
                  <span class="px-2 py-1 bg-gray-800 border border-blue-500/30 text-blue-400 font-mono text-xs">{upstream}</span>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Peers -->
          {#if result.asn_info.peers && result.asn_info.peers.length > 0}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Peers:</span>
              <div class="flex-1">
                <div class="text-gray-400 mb-1">{result.asn_info.peers.length} peer ASNs</div>
                <div class="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
                  {#each result.asn_info.peers as peer}
                    <span class="px-2 py-1 bg-gray-800 border border-green-500/30 text-green-400 font-mono text-xs">{peer}</span>
                  {/each}
                </div>
              </div>
            </div>
          {/if}

          <!-- Downstreams (Customers) -->
          {#if result.asn_info.downstreams && result.asn_info.downstreams.length > 0}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Downstreams:</span>
              <div class="flex-1 flex flex-wrap gap-2">
                {#each result.asn_info.downstreams as downstream}
                  <span class="px-2 py-1 bg-gray-800 border border-yellow-500/30 text-yellow-400 font-mono text-xs">{downstream}</span>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Peering Facilities -->
          {#if result.asn_info.peering_facilities && result.asn_info.peering_facilities.length > 0}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Peering IXs:</span>
              <div class="flex-1">
                {#each result.asn_info.peering_facilities as facility}
                  <div class="text-gray-300">{facility}</div>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Abuse Contacts -->
          {#if result.asn_info.abuse_contacts && result.asn_info.abuse_contacts.length > 0}
            <div class="flex gap-2">
              <span class="text-gray-500 w-32">Abuse Contacts:</span>
              <div class="flex-1">
                {#each result.asn_info.abuse_contacts as contact}
                  <div class="text-gray-300">{contact}</div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>

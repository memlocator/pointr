// Maximally distinct colors via the golden angle method.
// Each new source index gets hue offset by 137.508° — the most irrational
// fraction of the color wheel, guaranteeing no two close indices share a hue.

const GOLDEN_ANGLE = 137.508

function hslToHex(h, s, l) {
  s /= 100
  l /= 100
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs((h / 60) % 2 - 1))
  const m = l - c / 2
  let r = 0, g = 0, b = 0
  if (h < 60)       { r = c; g = x; b = 0 }
  else if (h < 120) { r = x; g = c; b = 0 }
  else if (h < 180) { r = 0; g = c; b = x }
  else if (h < 240) { r = 0; g = x; b = c }
  else if (h < 300) { r = x; g = 0; b = c }
  else              { r = c; g = 0; b = x }
  const hex = v => Math.round((v + m) * 255).toString(16).padStart(2, '0')
  return `#${hex(r)}${hex(g)}${hex(b)}`
}

// Fixed semantic colors for well-known sources
const FIXED = {
  osm: '#64748b',    // slate — neutral/external
  custom: '#f59e0b'  // amber — user-owned data
}

const _map = {}
let _i = 0

export function getSourceColor(source) {
  if (!source) return FIXED.osm
  if (FIXED[source]) return FIXED[source]
  if (!_map[source]) {
    const hue = (_i * GOLDEN_ANGLE) % 360
    _map[source] = hslToHex(hue, 80, 58)
    _i++
  }
  return _map[source]
}

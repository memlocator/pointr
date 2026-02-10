// Maximally distinct colors via the golden angle method.
// Each new source index gets hue offset by 137.508° — the most irrational
// fraction of the color wheel, guaranteeing no two close indices share a hue.

import { hslToHex } from './colorUtils.js'

const GOLDEN_ANGLE = 137.508

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

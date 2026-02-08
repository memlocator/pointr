// Single source of truth for business categories and colors

// Generate maximally distinct colors using the golden angle method
function generateDistinctColors(count) {
  const goldenAngle = 137.508 // Golden angle in degrees
  const colors = []

  for (let i = 0; i < count; i++) {
    const hue = (i * goldenAngle) % 360

    // Use high saturation and medium-high lightness for vibrant, visible colors
    const saturation = 75
    const lightness = 60

    colors.push(hslToHex(hue, saturation, lightness))
  }

  return colors
}

// Convert HSL to Hex
function hslToHex(h, s, l) {
  s /= 100
  l /= 100

  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs((h / 60) % 2 - 1))
  const m = l - c / 2

  let r = 0, g = 0, b = 0

  if (0 <= h && h < 60) {
    r = c; g = x; b = 0
  } else if (60 <= h && h < 120) {
    r = x; g = c; b = 0
  } else if (120 <= h && h < 180) {
    r = 0; g = c; b = x
  } else if (180 <= h && h < 240) {
    r = 0; g = x; b = c
  } else if (240 <= h && h < 300) {
    r = x; g = 0; b = c
  } else if (300 <= h && h < 360) {
    r = c; g = 0; b = x
  }

  const toHex = (val) => {
    const hex = Math.round((val + m) * 255).toString(16)
    return hex.length === 1 ? '0' + hex : hex
  }

  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

// Generate colors for all categories (excluding 'Other' which gets gray)
const categoryColors = generateDistinctColors(10)

// Simple SVG icon paths (32x32 viewBox, white strokes, centered at 16,16)
const CATEGORY_ICONS = {
  'Food & Dining': `<path d="M10 7v8M8 7v5a2 2 0 004 0V7M20 7v18M22 7v5c0 1.1-.9 2-2 2" stroke="white" stroke-width="2" fill="none" stroke-linecap="round"/>`,
  'Retail': `<path d="M8 12h16l-1.5 11H9.5L8 12zM11 12V9.5a5 5 0 0110 0V12" stroke="white" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`,
  'Healthcare': `<path d="M16 8v16M8 16h16" stroke="white" stroke-width="3.5" stroke-linecap="round"/>`,
  'Services': `<circle cx="12" cy="12" r="3.5" stroke="white" stroke-width="2" fill="none"/><circle cx="20" cy="12" r="3.5" stroke="white" stroke-width="2" fill="none"/><line x1="14" y1="14" x2="22" y2="24" stroke="white" stroke-width="2" stroke-linecap="round"/><line x1="18" y1="14" x2="10" y2="24" stroke="white" stroke-width="2" stroke-linecap="round"/>`,
  'Government': `<path d="M5 25h22M7 25V16M14 25V16M25 25V16M16 6l10 10H6z" stroke="white" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`,
  'Offices': `<rect x="6" y="13" width="20" height="14" rx="2" stroke="white" stroke-width="2" fill="none"/><path d="M12 13V10a4 4 0 018 0v3" stroke="white" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="6" y1="20" x2="26" y2="20" stroke="white" stroke-width="1.5"/>`,
  'Transportation': `<rect x="4" y="10" width="24" height="14" rx="3" stroke="white" stroke-width="2" fill="none"/><line x1="4" y1="16" x2="28" y2="16" stroke="white" stroke-width="1.5"/><rect x="7" y="12" width="6" height="3" rx="1" stroke="white" stroke-width="1.5" fill="none"/><rect x="19" y="12" width="6" height="3" rx="1" stroke="white" stroke-width="1.5" fill="none"/>`,
  'Infrastructure': `<line x1="16" y1="6" x2="16" y2="26" stroke="white" stroke-width="2.5" stroke-linecap="round"/><line x1="9" y1="11" x2="23" y2="11" stroke="white" stroke-width="2" stroke-linecap="round"/><line x1="11" y1="16" x2="21" y2="16" stroke="white" stroke-width="2" stroke-linecap="round"/><line x1="7" y1="26" x2="25" y2="26" stroke="white" stroke-width="2" stroke-linecap="round"/>`,
  'Automotive': `<rect x="4" y="14" width="24" height="9" rx="2" stroke="white" stroke-width="2" fill="none"/><path d="M7 14l3-6h12l3 6" stroke="white" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="10" cy="24" r="2.5" stroke="white" stroke-width="2" fill="none"/><circle cx="22" cy="24" r="2.5" stroke="white" stroke-width="2" fill="none"/>`,
  'Historic & Tourism': `<path d="M16 7l-9 18h18L16 7z" stroke="white" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/><line x1="8" y1="19" x2="24" y2="19" stroke="white" stroke-width="1.5"/>`,
  'Hazard': `<path d="M16 7l-9 18h18L16 7z" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><line x1="16" y1="13" x2="16" y2="19" stroke="white" stroke-width="2.5" stroke-linecap="round"/><circle cx="16" cy="22.5" r="1.5" fill="white"/>`,
  'Note': `<path d="M9 7h14v14l-4 4H9a2 2 0 01-2-2V9a2 2 0 012-2z" stroke="white" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M19 21v-4h4" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/><line x1="12" y1="12" x2="20" y2="12" stroke="white" stroke-width="1.5" stroke-linecap="round"/><line x1="12" y1="16" x2="17" y2="16" stroke="white" stroke-width="1.5" stroke-linecap="round"/>`,
  'Other': `<path d="M12 12a4 4 0 118 0c0 3-4 4-4 7" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round"/><circle cx="16" cy="24" r="2" fill="white"/>`
}

export const BUSINESS_CATEGORIES = [
  {
    name: 'Food & Dining',
    color: categoryColors[0],
    icon: CATEGORY_ICONS['Food & Dining'],
    types: [
      'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'food_court',
      'bakery', 'butcher'
    ]
  },
  {
    name: 'Retail',
    color: categoryColors[1],
    icon: CATEGORY_ICONS['Retail'],
    types: [
      'supermarket', 'convenience', 'clothes', 'fashion', 'shoes',
      'books', 'gift', 'jewelry', 'toys', 'sports',
      'electronics', 'mobile_phone', 'computer',
      'furniture', 'hardware', 'mall', 'department_store', 'marketplace'
    ]
  },
  {
    name: 'Healthcare',
    color: categoryColors[2],
    icon: CATEGORY_ICONS['Healthcare'],
    types: [
      'pharmacy', 'clinic', 'doctors', 'dentist', 'hospital', 'veterinary',
      'greengrocer', 'florist', 'garden_centre', 'chemist', 'optician'
    ]
  },
  {
    name: 'Services',
    color: categoryColors[3],
    icon: CATEGORY_ICONS['Services'],
    types: [
      'bank', 'bureau_de_change', 'hairdresser', 'beauty'
    ]
  },
  {
    name: 'Government',
    color: categoryColors[4],
    icon: CATEGORY_ICONS['Government'],
    types: [
      'townhall', 'courthouse', 'police', 'fire_station', 'post_office',
      'community_centre', 'social_facility', 'public_building', 'government',
      'parliament', 'legislative', 'legislature', 'ministry', 'public_service',
      'administrative', 'regional', 'local', 'national', 'embassy', 'prison',
      'ranger_station', 'public_bath', 'library', 'archive', 'tax',
      'social_security', 'register_office', 'customs', 'bailiff', 'prosecutor',
      'presidency'
    ]
  },
  {
    name: 'Offices',
    color: categoryColors[5],
    icon: CATEGORY_ICONS['Offices'],
    types: [
      'office', 'business'
    ]
  },
  {
    name: 'Transportation',
    color: categoryColors[6],
    icon: CATEGORY_ICONS['Transportation'],
    types: [
      'station', 'bus_station', 'halt', 'ferry_terminal'
    ]
  },
  {
    name: 'Infrastructure',
    color: categoryColors[7],
    icon: CATEGORY_ICONS['Infrastructure'],
    types: [
      // Aviation
      'aerodrome', 'terminal', 'heliport', 'hangar',
      // Telecom
      'telecommunication', 'mast', 'communications_tower',
      // Utilities
      'energy', 'water_utility', 'plant', 'substation', 'generator',
      'water_tower', 'water_works', 'wastewater_plant',
      // Transport companies
      'transport', 'railway', 'airline', 'logistics',
      // Postal
      'post_depot', 'courier', 'delivery',
      // Ports
      'port',
      // Industrial
      'industrial',
      // IT
      'it', 'company'
    ]
  },
  {
    name: 'Automotive',
    color: categoryColors[8],
    icon: CATEGORY_ICONS['Automotive'],
    types: [
      'fuel', 'car_rental', 'car_wash'
    ]
  },
  {
    name: 'Historic & Tourism',
    color: categoryColors[9],
    icon: CATEGORY_ICONS['Historic & Tourism'],
    types: [
      'castle', 'castle:palace', 'palace', 'fort', 'monument', 'memorial',
      'manor', 'citywalls', 'attraction', 'museum',
      'school', 'university', 'college', 'kindergarten'
    ]
  },
  {
    name: 'Hazard',
    color: '#ef4444',
    icon: CATEGORY_ICONS['Hazard'],
    types: ['hazard']
  },
  {
    name: 'Note',
    color: '#eab308',
    icon: CATEGORY_ICONS['Note'],
    types: ['note']
  },
  {
    name: 'Other',
    color: '#9ca3af', // Gray
    icon: CATEGORY_ICONS['Other'],
    types: [] // Default fallback
  }
]

// Generate MapLibre icon-image expression mapping category name → icon image name
export function generateIconExpression() {
  const expr = ['match', ['get', 'type']]
  for (const cat of BUSINESS_CATEGORIES) {
    expr.push(cat.name, `poi-icon-${cat.name}`)
  }
  expr.push('poi-icon-Other')
  return expr
}

// Generate MapLibre GL style expression from categories
export function generateColorExpression() {
  const expression = ['match', ['get', 'type']]

  BUSINESS_CATEGORIES.forEach(category => {
    category.types.forEach(type => {
      expression.push(type, category.color)
    })
  })

  // Default color (Other category)
  expression.push('#ffffff')

  return expression
}

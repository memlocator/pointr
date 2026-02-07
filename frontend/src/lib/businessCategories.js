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

export const BUSINESS_CATEGORIES = [
  {
    name: 'Food & Dining',
    color: categoryColors[0],
    types: [
      'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'food_court',
      'bakery', 'butcher'
    ]
  },
  {
    name: 'Retail',
    color: categoryColors[1],
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
    types: [
      'pharmacy', 'clinic', 'doctors', 'dentist', 'hospital', 'veterinary',
      'greengrocer', 'florist', 'garden_centre', 'chemist', 'optician'
    ]
  },
  {
    name: 'Services',
    color: categoryColors[3],
    types: [
      'bank', 'bureau_de_change', 'hairdresser', 'beauty'
    ]
  },
  {
    name: 'Government',
    color: categoryColors[4],
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
    types: [
      'office', 'business'
    ]
  },
  {
    name: 'Transportation',
    color: categoryColors[6],
    types: [
      'station', 'bus_station', 'halt', 'ferry_terminal'
    ]
  },
  {
    name: 'Infrastructure',
    color: categoryColors[7],
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
    types: [
      'fuel', 'car_rental', 'car_wash'
    ]
  },
  {
    name: 'Historic & Tourism',
    color: categoryColors[9],
    types: [
      'castle', 'castle:palace', 'palace', 'fort', 'monument', 'memorial',
      'manor', 'citywalls', 'attraction', 'museum',
      'school', 'university', 'college', 'kindergarten'
    ]
  },
  {
    name: 'Other',
    color: '#9ca3af', // Gray
    types: [] // Default fallback
  }
]

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

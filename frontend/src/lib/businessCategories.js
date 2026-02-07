// Single source of truth for business categories and colors

export const BUSINESS_CATEGORIES = [
  {
    name: 'Food & Dining',
    color: '#fb923c', // Bright Orange
    types: [
      'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'food_court',
      'bakery', 'butcher'
    ]
  },
  {
    name: 'Retail',
    color: '#3b82f6', // Blue
    types: [
      'supermarket', 'convenience', 'clothes', 'fashion', 'shoes',
      'books', 'gift', 'jewelry', 'toys', 'sports',
      'electronics', 'mobile_phone', 'computer',
      'furniture', 'hardware', 'mall', 'department_store', 'marketplace'
    ]
  },
  {
    name: 'Healthcare',
    color: '#22c55e', // Bright Green
    types: [
      'pharmacy', 'clinic', 'doctors', 'dentist', 'hospital', 'veterinary',
      'greengrocer', 'florist', 'garden_centre', 'chemist', 'optician'
    ]
  },
  {
    name: 'Services',
    color: '#f472b6', // Bright Pink
    types: [
      'bank', 'bureau_de_change', 'hairdresser', 'beauty'
    ]
  },
  {
    name: 'Government',
    color: '#06b6d4', // Cyan
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
    color: '#fde047', // Bright Yellow
    types: [
      'office', 'business'
    ]
  },
  {
    name: 'Transportation',
    color: '#a78bfa', // Light Purple
    types: [
      'station', 'bus_station', 'halt', 'ferry_terminal'
    ]
  },
  {
    name: 'Infrastructure',
    color: '#8b5cf6', // Deep Violet
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
    color: '#ef4444', // Red
    types: [
      'fuel', 'car_rental', 'car_wash'
    ]
  },
  {
    name: 'Historic & Tourism',
    color: '#f59e0b', // Amber/Gold
    types: [
      'castle', 'castle:palace', 'palace', 'fort', 'monument', 'memorial',
      'manor', 'citywalls', 'attraction', 'museum',
      'school', 'university', 'college', 'kindergarten'
    ]
  },
  {
    name: 'Other',
    color: '#d1d5db', // Light Gray
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

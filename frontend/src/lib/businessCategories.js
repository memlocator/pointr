// Single source of truth for business categories and colors

export const BUSINESS_CATEGORIES = [
  {
    name: 'Food & Dining',
    color: '#f97316', // Orange
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
    color: '#10b981', // Green
    types: [
      'pharmacy', 'clinic', 'doctors', 'dentist', 'hospital', 'veterinary',
      'greengrocer', 'florist', 'garden_centre', 'chemist', 'optician'
    ]
  },
  {
    name: 'Services',
    color: '#a855f7', // Purple
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
      'social_security', 'register_office', 'customs', 'bailiff', 'prosecutor'
    ]
  },
  {
    name: 'Offices',
    color: '#eab308', // Yellow
    types: [
      'office', 'business'
    ]
  },
  {
    name: 'Transportation',
    color: '#ec4899', // Pink
    types: [
      'aerodrome', 'terminal', 'heliport', 'station', 'bus_station'
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
    name: 'Other',
    color: '#ffffff', // White
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

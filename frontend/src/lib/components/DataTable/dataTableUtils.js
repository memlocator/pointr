/**
 * Search data across all columns
 * @param {Array} data - Array of data objects
 * @param {string} searchTerm - Search term
 * @param {Array} columns - Column configuration
 * @returns {Array} Filtered data
 */
export function searchData(data, searchTerm, columns) {
  if (!searchTerm?.trim()) return data

  const lowerSearch = searchTerm.toLowerCase().trim()

  return data.filter(row => {
    return columns.some(col => {
      const value = row[col.id]
      if (value == null) return false

      const searchableValue = col.format
        ? col.format(value, row)
        : String(value)

      return searchableValue.toLowerCase().includes(lowerSearch)
    })
  })
}

/**
 * Sort data by column
 * @param {Array} data - Array of data objects
 * @param {Object} sortConfig - Sort configuration { column, direction }
 * @param {Array} columns - Column configuration
 * @returns {Array} Sorted data
 */
export function sortData(data, sortConfig, columns) {
  if (!sortConfig.column || !sortConfig.direction) return data

  const column = columns.find(col => col.id === sortConfig.column)
  if (!column) return data

  return [...data].sort((a, b) => {
    let aVal = column.format ? column.format(a[column.id], a) : a[column.id]
    let bVal = column.format ? column.format(b[column.id], b) : b[column.id]

    // Handle null/undefined
    if (aVal == null && bVal == null) return 0
    if (aVal == null) return 1
    if (bVal == null) return -1

    // String comparison (case-insensitive)
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }

    const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0
    return sortConfig.direction === 'asc' ? comparison : -comparison
  })
}

/**
 * Filter data by business categories
 * @param {Array} data - Array of data objects
 * @param {Array} selectedCategories - Selected category names
 * @param {Object} categoryConfig - Category configuration
 * @returns {Array} Filtered data
 */
export function filterByCategories(data, selectedCategories, categoryConfig) {
  if (!selectedCategories?.length || !categoryConfig) return data

  const { categories, typeField } = categoryConfig

  // Build a map of type -> category name
  const typeToCategory = new Map()
  categories.forEach(cat => {
    cat.types.forEach(type => {
      typeToCategory.set(type, cat.name)
    })
  })

  return data.filter(row => {
    const rowType = row[typeField]
    const rowCategory = typeToCategory.get(rowType) || 'Other'
    return selectedCategories.includes(rowCategory)
  })
}

/**
 * Filter data by contact information availability
 * @param {Array} data - Array of data objects
 * @param {Object} contactFilters - Contact filter state
 * @param {Object} contactConfig - Contact filter configuration
 * @returns {Array} Filtered data
 */
export function filterByContactInfo(data, contactFilters, contactConfig) {
  if (!contactFilters || !contactConfig?.enabled) return data

  const { hasPhone, hasEmail, hasWebsite } = contactFilters

  // If no filters active, show all
  if (!hasPhone && !hasEmail && !hasWebsite) return data

  return data.filter(row => {
    let matches = true

    if (hasPhone) {
      matches = matches && Boolean(row.phone?.trim())
    }
    if (hasEmail) {
      matches = matches && Boolean(row.email?.trim())
    }
    if (hasWebsite) {
      matches = matches && Boolean(row.website?.trim())
    }

    return matches
  })
}

/**
 * Validate column configuration
 * @param {Array} columns - Column configuration
 * @throws {Error} If validation fails
 * @returns {boolean} True if valid
 */
export function validateColumns(columns) {
  if (!Array.isArray(columns) || columns.length === 0) {
    throw new Error('DataTable: columns must be a non-empty array')
  }

  columns.forEach((col, index) => {
    if (!col.id) {
      throw new Error(`DataTable: Column at index ${index} missing required 'id' property`)
    }
    if (!col.header) {
      throw new Error(`DataTable: Column '${col.id}' missing required 'header' property`)
    }
    if (col.render && typeof col.render !== 'function') {
      throw new Error(`DataTable: Column '${col.id}' render must be a function`)
    }
    if (col.format && typeof col.format !== 'function') {
      throw new Error(`DataTable: Column '${col.id}' format must be a function`)
    }
  })

  return true
}

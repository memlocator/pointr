/**
 * Export utilities for DataTable
 */

/**
 * Convert data to CSV format
 */
export function exportToCSV(data, columns, filename = 'export.csv') {
  if (!data || data.length === 0) {
    alert('No data to export')
    return
  }

  // Get column IDs and headers
  const columnIds = columns.map(col => col.id)
  const headers = columns.map(col => col.header)

  // Create CSV content
  const csvRows = []

  // Add header row
  csvRows.push(headers.map(h => `"${h}"`).join(','))

  // Add data rows
  data.forEach(row => {
    const values = columnIds.map(id => {
      let value = row[id]

      // Handle null/undefined
      if (value === null || value === undefined) {
        return '""'
      }

      // Convert to string and escape quotes
      value = String(value).replace(/"/g, '""')
      return `"${value}"`
    })
    csvRows.push(values.join(','))
  })

  // Create blob and download
  const csvContent = csvRows.join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  downloadFile(blob, filename)
}

/**
 * Convert data to JSON format
 */
export function exportToJSON(data, columns, filename = 'export.json') {
  if (!data || data.length === 0) {
    alert('No data to export')
    return
  }

  // Create JSON content (only include columns that are displayed)
  const columnIds = columns.map(col => col.id)
  const exportData = data.map(row => {
    const obj = {}
    columnIds.forEach(id => {
      obj[id] = row[id]
    })
    return obj
  })

  // Create blob and download
  const jsonContent = JSON.stringify(exportData, null, 2)
  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' })
  downloadFile(blob, filename)
}

/**
 * Trigger file download
 */
function downloadFile(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

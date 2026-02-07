/**
 * Simple localStorage utilities for persisting app state
 */

/**
 * Load data from localStorage
 * @param {string} key - localStorage key
 * @param {*} defaultValue - default value if key doesn't exist
 * @returns {*} parsed value or default
 */
export function loadFromStorage(key, defaultValue) {
  try {
    const stored = localStorage.getItem(key)
    return stored ? JSON.parse(stored) : defaultValue
  } catch (error) {
    console.error(`Error loading ${key} from localStorage:`, error)
    return defaultValue
  }
}

/**
 * Save data to localStorage
 * @param {string} key - localStorage key
 * @param {*} value - value to save (will be JSON stringified)
 */
export function saveToStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (error) {
    console.error(`Error saving ${key} to localStorage:`, error)
  }
}

/**
 * Clear specific key from localStorage
 * @param {string} key - localStorage key to remove
 */
export function clearFromStorage(key) {
  try {
    localStorage.removeItem(key)
  } catch (error) {
    console.error(`Error clearing ${key} from localStorage:`, error)
  }
}

/**
 * Clear all app data from localStorage
 */
export function clearAllStorage() {
  const keys = ['polygons', 'businesses', 'mapCenter', 'mapZoom']
  keys.forEach(key => clearFromStorage(key))
}

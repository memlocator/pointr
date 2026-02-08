const RAW = (import.meta.env && import.meta.env.VITE_API_URL) ? import.meta.env.VITE_API_URL : ''
const BASE = RAW.replace(/\/$/, '')

export function apiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${BASE}${p}`
}

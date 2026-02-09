const RAW = (import.meta.env && import.meta.env.VITE_API_URL) ? import.meta.env.VITE_API_URL : ''
const BASE = RAW.replace(/\/$/, '')

export function apiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${BASE}${p}`
}

export function getActiveProjectId() {
  try {
    return localStorage.getItem('activeProjectId') || ''
  } catch {
    return ''
  }
}

export function setActiveProjectId(projectId) {
  try {
    if (!projectId) localStorage.removeItem('activeProjectId')
    else localStorage.setItem('activeProjectId', projectId)
  } catch {}
}

export function getDevImpersonateUser() {
  try {
    return localStorage.getItem('devImpersonateUser') || ''
  } catch {
    return ''
  }
}

export function setDevImpersonateUser(username) {
  try {
    if (!username) localStorage.removeItem('devImpersonateUser')
    else localStorage.setItem('devImpersonateUser', username)
  } catch {}
}

function withProjectQuery(url) {
  const projectId = getActiveProjectId()
  if (!projectId) return url
  try {
    const full = url.startsWith('http') ? url : new URL(url, window.location.origin).toString()
    const u = new URL(full)
    if (!u.searchParams.has('project_id')) {
      u.searchParams.set('project_id', projectId)
    }
    return url.startsWith('http') ? u.toString() : u.toString().replace(window.location.origin, '')
  } catch {
    return url
  }
}

function withProjectBody(body) {
  const projectId = getActiveProjectId()
  if (!projectId) return body
  if (typeof body !== 'string') return body
  try {
    const parsed = JSON.parse(body)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed) && parsed.project_id == null) {
      parsed.project_id = projectId
      return JSON.stringify(parsed)
    }
  } catch {}
  return body
}

export function apiFetch(path, options = {}) {
  const url = withProjectQuery(apiUrl(path))
  const headers = options.headers || {}
  const body = options.body
  const contentType = headers['Content-Type'] || headers['content-type'] || ''
  const patchedBody = contentType.includes('application/json') ? withProjectBody(body) : body
  const devUser = getDevImpersonateUser()
  if (devUser && !headers['X-Dev-Impersonate']) {
    headers['X-Dev-Impersonate'] = devUser
  }
  return fetch(url, { ...options, headers, body: patchedBody })
}

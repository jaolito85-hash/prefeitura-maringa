const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

function buildUrl(path, params) {
  const url = new URL(`${API_URL}${path}`)

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value))
      }
    })
  }

  return url.toString()
}

async function request(path, { method = 'GET', params, body } = {}) {
  const response = await fetch(buildUrl(path, params), {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(`${method} ${path} falhou: ${response.status} ${message}`)
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export function apiGet(path, params) {
  return request(path, { method: 'GET', params })
}

export function apiPatch(path, body) {
  return request(path, { method: 'PATCH', body })
}

export function apiUrl(path, params) {
  return buildUrl(path, params)
}

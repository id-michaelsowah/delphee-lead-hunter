import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach stored password as Basic Auth on every request
api.interceptors.request.use(config => {
  const pw = sessionStorage.getItem('app_password')
  if (pw) {
    config.headers['Authorization'] = 'Basic ' + btoa(':' + pw)
  }
  return config
})

// On 401, clear stored password so the login screen re-appears
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      sessionStorage.removeItem('app_password')
      window.dispatchEvent(new Event('auth:logout'))
    }
    return Promise.reject(err)
  }
)

export const getRegions = () => api.get('/regions').then(r => r.data)
export const startScan = (regions) => api.post('/scans', { regions }).then(r => r.data)
export const listScans = (limit = 20) => api.get('/scans', { params: { limit } }).then(r => r.data)
export const getScan = (id) => api.get(`/scans/${id}`).then(r => r.data)
export const listLeads = (params) => api.get('/leads', { params }).then(r => r.data)
export const updateLead = (id, body) => api.patch(`/leads/${id}`, body).then(r => r.data)
export const cancelScan = (id) => api.post(`/scans/${id}/cancel`).then(r => r.data)
export const findTargets = (leadId) => api.post(`/leads/${leadId}/targets`).then(r => r.data)
export const getTargets = (leadId) => api.get(`/leads/${leadId}/targets`).then(r => r.data)
export const listAllTargets = (params) => api.get('/targets', { params }).then(r => r.data)
export const exportLeadsUrl = (params) => {
  const pw = sessionStorage.getItem('app_password')
  const auth = pw ? '&_auth=' + encodeURIComponent(btoa(':' + pw)) : ''
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '' && v !== 0))
  return `/api/leads/export?${qs}${auth}`
}

export function connectWebSocket(scanId, onMessage) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/scans/${scanId}`)
  ws.onmessage = (e) => onMessage(JSON.parse(e.data))
  return ws
}

export function setPassword(pw) {
  sessionStorage.setItem('app_password', pw)
}

export function getStoredPassword() {
  return sessionStorage.getItem('app_password')
}

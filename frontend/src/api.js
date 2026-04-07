import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const getRegions = () => api.get('/regions').then(r => r.data)
export const startScan = (regions) => api.post('/scans', { regions }).then(r => r.data)
export const listScans = (limit = 20) => api.get('/scans', { params: { limit } }).then(r => r.data)
export const getScan = (id) => api.get(`/scans/${id}`).then(r => r.data)
export const listLeads = (params) => api.get('/leads', { params }).then(r => r.data)
export const updateLead = (id, body) => api.patch(`/leads/${id}`, body).then(r => r.data)
export const cancelScan = (id) => api.post(`/scans/${id}/cancel`).then(r => r.data)
export const exportLeadsUrl = (params) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([,v]) => v != null && v !== '' && v !== 0))
  return `/api/leads/export?${qs}`
}

export function connectWebSocket(scanId, onMessage) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/scans/${scanId}`)
  ws.onmessage = (e) => onMessage(JSON.parse(e.data))
  return ws
}

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getScan, exportLeadsUrl } from '../api'
import LeadCard from '../components/LeadCard'

function fmt(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function ScanDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [scan, setScan] = useState(null)
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [freshness, setFreshness] = useState('')
  const [type, setType] = useState('')
  const [sortBy, setSortBy] = useState('relevance_score')

  useEffect(() => {
    getScan(id)
      .then(s => { setScan(s); setLeads(s.leads || []) })
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="page-content" style={{ color: '#9ca3af' }}>Loading...</div>
  if (!scan) return <div className="page-content" style={{ color: '#ef4444' }}>Scan not found.</div>

  const types = [...new Set(leads.map(l => l.type).filter(Boolean))]

  let filtered = leads
  if (freshness === 'actionable') filtered = filtered.filter(l => ['active','stale'].includes(l.freshness))
  else if (freshness) filtered = filtered.filter(l => l.freshness === freshness)
  if (type) filtered = filtered.filter(l => l.type === type)

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'relevance_score') return (b.relevance_score || 0) - (a.relevance_score || 0)
    if (sortBy === 'urgency') {
      const u = { high: 3, medium: 2, low: 1 }
      return (u[b.urgency] || 0) - (u[a.urgency] || 0)
    }
    return 0
  })

  const exportParams = {
    freshness: freshness || undefined,
    type: type || undefined,
  }

  return (
    <div className="page-content">
      <button
        className="btn btn-secondary btn-sm"
        style={{ marginBottom: 16 }}
        onClick={() => navigate('/history')}
      >
        ← Back to History
      </button>

      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
          {(scan.regions || []).join(', ') || 'Scan'} — {fmt(scan.started_at)}
        </h1>
        <span style={{ fontSize: 13, color: '#6b7280' }}>
          Status: <strong>{scan.status}</strong>
        </span>
      </div>

      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-value">{leads.length}</div>
          <div className="stat-label">Total leads</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#15803d' }}>
            {leads.filter(l => l.freshness === 'active').length}
          </div>
          <div className="stat-label">Active</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#854d0e' }}>
            {leads.filter(l => l.freshness === 'stale').length}
          </div>
          <div className="stat-label">Stale</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#b91c1c' }}>
            {leads.filter(l => ['outdated','expired'].includes(l.freshness)).length}
          </div>
          <div className="stat-label">Outdated/Expired</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#dc2626' }}>
            {leads.filter(l => l.urgency === 'high').length}
          </div>
          <div className="stat-label">Urgent</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#4f46e5' }}>
            {leads.filter(l => (l.relevance_score || 0) >= 70).length}
          </div>
          <div className="stat-label">Score 70+</div>
        </div>
      </div>

      <div className="filter-bar">
        <select value={freshness} onChange={e => setFreshness(e.target.value)}>
          <option value="">All freshness</option>
          <option value="actionable">Actionable only</option>
          <option value="active">Active</option>
          <option value="stale">Stale</option>
          <option value="outdated">Outdated</option>
          <option value="expired">Expired</option>
        </select>
        <select value={type} onChange={e => setType(e.target.value)}>
          <option value="">All types</option>
          {types.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={sortBy} onChange={e => setSortBy(e.target.value)}>
          <option value="relevance_score">Sort: Relevance</option>
          <option value="urgency">Sort: Urgency</option>
        </select>
        <div style={{ marginLeft: 'auto' }}>
          <a
            href={exportLeadsUrl({ ...exportParams, scan_id: id })}
            download="delphee-leads.csv"
            className="btn btn-secondary btn-sm"
          >
            Export CSV
          </a>
        </div>
      </div>

      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 16 }}>
        Showing {sorted.length} of {leads.length} leads
      </div>

      {sorted.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🔍</div>
          <h3>No leads match the filters</h3>
        </div>
      ) : (
        sorted.map(lead => <LeadCard key={lead.id} lead={lead} />)
      )}
    </div>
  )
}

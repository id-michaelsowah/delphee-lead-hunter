import { useState, useEffect, useCallback } from 'react'
import { listLeads, updateLead, exportLeadsUrl } from '../api'
import LeadCard from '../components/LeadCard'

export default function AllLeads() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [freshness, setFreshness] = useState('')
  const [type, setType] = useState('')
  const [minScore, setMinScore] = useState(0)
  const [sortBy, setSortBy] = useState('relevance_score')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const LIMIT = 50

  const fetch = useCallback(async (reset = false) => {
    setLoading(true)
    const params = {
      freshness: freshness || undefined,
      type: type || undefined,
      min_score: minScore || undefined,
      sort_by: sortBy,
      limit: LIMIT,
      offset: reset ? 0 : offset,
    }
    try {
      const data = await listLeads(params)
      if (reset) {
        setLeads(data)
        setOffset(0)
      } else {
        setLeads(prev => [...prev, ...data])
      }
      setHasMore(data.length === LIMIT)
    } finally {
      setLoading(false)
    }
  }, [freshness, type, minScore, sortBy, offset])

  // Re-fetch when filters change
  useEffect(() => {
    setOffset(0)
    setLoading(true)
    const params = {
      freshness: freshness || undefined,
      type: type || undefined,
      min_score: minScore || undefined,
      sort_by: sortBy,
      limit: LIMIT,
      offset: 0,
    }
    listLeads(params).then(data => {
      setLeads(data)
      setHasMore(data.length === LIMIT)
    }).finally(() => setLoading(false))
  }, [freshness, type, minScore, sortBy])

  const handleLoadMore = () => {
    const nextOffset = offset + LIMIT
    setOffset(nextOffset)
    const params = {
      freshness: freshness || undefined,
      type: type || undefined,
      min_score: minScore || undefined,
      sort_by: sortBy,
      limit: LIMIT,
      offset: nextOffset,
    }
    listLeads(params).then(data => {
      setLeads(prev => [...prev, ...data])
      setHasMore(data.length === LIMIT)
    })
  }

  const handleStatusChange = async (leadId, newStatus, notes) => {
    const updates = {}
    if (newStatus !== undefined) updates.lead_status = newStatus
    if (notes !== undefined) updates.notes = notes
    const updated = await updateLead(leadId, updates)
    setLeads(prev => prev.map(l => l.id === leadId ? updated : l))
  }

  const exportParams = {
    freshness: freshness || undefined,
    type: type || undefined,
    min_score: minScore || undefined,
  }

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>All Leads</h1>
          <p style={{ fontSize: 14, color: '#6b7280' }}>
            {leads.length} leads{hasMore ? '+' : ''} across all scans
          </p>
        </div>
        <a
          href={exportLeadsUrl(exportParams)}
          download="delphee-leads.csv"
          className="btn btn-secondary btn-sm"
        >
          Export CSV
        </a>
      </div>

      <div className="filter-bar">
        <select value={freshness} onChange={e => setFreshness(e.target.value)}>
          <option value="">All freshness</option>
          <option value="actionable">Actionable only</option>
          <option value="active">Active</option>
          <option value="stale">Stale</option>
          <option value="outdated">Outdated</option>
          <option value="expired">Expired</option>
          <option value="unknown">Unknown</option>
        </select>
        <select value={type} onChange={e => setType(e.target.value)}>
          <option value="">All types</option>
          <option value="tender">Tender</option>
          <option value="rfq">RFQ</option>
          <option value="news">News</option>
          <option value="regulation">Regulation</option>
          <option value="consulting">Consulting</option>
          <option value="partnership">Partnership</option>
        </select>
        <select value={minScore} onChange={e => setMinScore(Number(e.target.value))}>
          <option value={0}>Any score</option>
          <option value={40}>Score 40+</option>
          <option value={50}>Score 50+</option>
          <option value={65}>Score 65+</option>
          <option value={70}>Score 70+</option>
        </select>
        <select value={sortBy} onChange={e => setSortBy(e.target.value)}>
          <option value="relevance_score">Sort: Relevance</option>
          <option value="urgency">Sort: Urgency</option>
          <option value="first_seen_at">Sort: Newest</option>
        </select>
      </div>

      {loading && leads.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>Loading...</div>
      ) : leads.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🔍</div>
          <h3>No leads found</h3>
          <p>Try adjusting your filters or run a new scan.</p>
        </div>
      ) : (
        <>
          {leads.map(lead => (
            <LeadCard
              key={lead.id}
              lead={lead}
              showScanId
              onStatusChange={(id, status, notes) => handleStatusChange(id, status, notes)}
            />
          ))}
          {hasMore && (
            <button
              className="btn btn-secondary"
              style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
              onClick={handleLoadMore}
            >
              Load more
            </button>
          )}
        </>
      )}
    </div>
  )
}

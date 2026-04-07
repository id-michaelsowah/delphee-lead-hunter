import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const FRESHNESS_DOT = { active: '🟢', stale: '🟡', outdated: '🔴', expired: '⚫', unknown: '⚪' }

function ScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score || 0))
  const cls = pct >= 70 ? 'green' : pct >= 50 ? 'amber' : 'red'
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-bg">
        <div className={`score-bar-fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="score-label">{score ?? '-'}</span>
    </div>
  )
}

export default function LeadCard({ lead, showScanId = false, onStatusChange }) {
  const [expanded, setExpanded] = useState(false)
  const navigate = useNavigate()
  const dim = lead.freshness === 'expired' || lead.freshness === 'outdated'
  const freshKey = lead.freshness || 'unknown'
  const typeKey = (lead.type || 'news').toLowerCase().replace(/\s+/g, '')

  return (
    <div className={`lead-card${dim ? ' dim' : ''}`}>
      <div className="lead-card-header">
        <div style={{ flex: 1 }}>
          <div className="lead-card-badges">
            <span className={`badge badge-${freshKey}`}>
              {FRESHNESS_DOT[freshKey] || '⚪'} {lead.freshness || 'unknown'}
            </span>
            <span className={`badge badge-${typeKey}`}>{lead.type || 'news'}</span>
            {lead.urgency === 'high' && <span className="urgency-high">⚡ Urgent</span>}
            {lead.urgency === 'medium' && <span className="urgency-medium">● Medium</span>}
            {showScanId && lead.scan_run_id && (
              <span
                className="badge badge-unknown"
                style={{ fontFamily: 'monospace', cursor: 'pointer' }}
                onClick={() => navigate(`/history/${lead.scan_run_id}`)}
              >
                {lead.scan_run_id.slice(0, 8)}
              </span>
            )}
          </div>
          <div className="lead-card-meta">{lead.country} · {lead.institution || 'Unknown institution'}</div>
        </div>
        <div style={{ minWidth: 120 }}>
          <ScoreBar score={lead.relevance_score} />
        </div>
      </div>

      <div className="lead-card-title">{lead.title}</div>
      <div className="lead-card-summary">{lead.summary}</div>

      <div className="lead-card-footer">
        {lead.deadline && (
          <span style={{ fontSize: 12, color: '#6b7280' }}>
            📅 Deadline: <strong>{lead.deadline}</strong>
          </span>
        )}
        <button className="expand-btn" onClick={() => setExpanded(e => !e)}>
          {expanded ? '▲ Less' : '▼ More'}
        </button>
        {onStatusChange && (
          <select
            className="status-select"
            value={lead.lead_status || 'new'}
            onChange={e => onStatusChange(lead.id, e.target.value)}
          >
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="closed">Closed</option>
          </select>
        )}
        {lead.source_url && (
          <a
            href={lead.source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, color: '#4f46e5', marginLeft: 'auto' }}
          >
            Source →
          </a>
        )}
      </div>

      {expanded && (
        <div className="lead-card-expand">
          {lead.relevance_reason && (
            <div className="lead-card-expand-row">
              <span className="label">Why relevant:</span>
              <span>{lead.relevance_reason}</span>
            </div>
          )}
          {lead.freshness_reason && (
            <div className="lead-card-expand-row">
              <span className="label">Freshness:</span>
              <span>{lead.freshness_reason}</span>
            </div>
          )}
          {lead.follow_up_action && (
            <div className="lead-card-expand-row">
              <span className="label">Follow-up:</span>
              <span style={{ color: '#4f46e5', fontWeight: 500 }}>{lead.follow_up_action}</span>
            </div>
          )}
          {lead.contact_info && (
            <div className="lead-card-expand-row">
              <span className="label">Contact:</span>
              <span>{lead.contact_info}</span>
            </div>
          )}
          {lead.published_date && (
            <div className="lead-card-expand-row">
              <span className="label">Published:</span>
              <span>{lead.published_date}</span>
            </div>
          )}
          {onStatusChange && (
            <div className="lead-card-expand-row" style={{ marginTop: 8 }}>
              <span className="label">Notes:</span>
              <NotesEditor lead={lead} onSave={onStatusChange} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function NotesEditor({ lead, onSave }) {
  const [notes, setNotes] = useState(lead.notes || '')
  const [saved, setSaved] = useState(true)

  const save = () => {
    onSave(lead.id, lead.lead_status, notes)
    setSaved(true)
  }

  return (
    <div style={{ flex: 1 }}>
      <textarea
        value={notes}
        onChange={e => { setNotes(e.target.value); setSaved(false) }}
        rows={2}
        style={{
          width: '100%', padding: '6px 8px', border: '1px solid #e5e7eb',
          borderRadius: 6, fontSize: 13, resize: 'vertical',
        }}
        placeholder="Add notes..."
      />
      {!saved && (
        <button className="btn btn-sm btn-secondary" style={{ marginTop: 4 }} onClick={save}>
          Save notes
        </button>
      )}
    </div>
  )
}

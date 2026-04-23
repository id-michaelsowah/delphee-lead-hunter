import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { listAllTargets, updateTarget, exportTargetsUrl } from '../api'

const TIERS = ['core', 'expansion', 'greenfield']
const TIER_LABEL = { core: 'Core Markets', expansion: 'Expansion Markets', greenfield: 'Greenfield Markets' }
const TIER_DESC = {
  core: 'Markets where Delphee has strong prior delivery and IFRS 9 reference projects.',
  expansion: 'Markets where Delphee has transferable capabilities but few prior projects.',
  greenfield: 'Markets where Delphee has no prior delivery experience.',
}
const TIER_COLOR = { core: '#15803d', expansion: '#0284c7', greenfield: '#6b7280' }
const TIER_BG = { core: '#f0fdf4', expansion: '#eff6ff', greenfield: '#f9fafb' }

const STATUS_OPTIONS = ['New', 'Contacted', 'Qualified', 'Closed']
const STATUS_COLOR = { New: '#6b7280', Contacted: '#0284c7', Qualified: '#15803d', Closed: '#9333ea' }

function InstitutionRow({ inst, onUpdate }) {
  const [status, setStatus] = useState(inst.status || 'New')
  const [notes, setNotes] = useState(inst.notes || '')
  const [savingNotes, setSavingNotes] = useState(false)

  const handleStatusChange = async (e) => {
    const val = e.target.value
    setStatus(val)
    const updated = await updateTarget(inst.id, { status: val })
    onUpdate(updated)
  }

  const handleNotesSave = async () => {
    if (notes === (inst.notes || '')) return
    setSavingNotes(true)
    const updated = await updateTarget(inst.id, { notes }).finally(() => setSavingNotes(false))
    onUpdate(updated)
  }

  return (
    <div style={{
      border: '1px solid #e5e7eb', borderRadius: 8, padding: '14px 16px',
      marginBottom: 10, background: '#fff',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 3 }}>{inst.institution_name}</div>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>
            {inst.country}
            {inst.type && ` · ${inst.type.replace(/_/g, ' ')}`}
            {inst.estimated_asset_size && ` · ${inst.estimated_asset_size}`}
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
            {inst.dfi_backed && (
              <span style={{ fontSize: 11, background: '#eff6ff', color: '#0284c7', borderRadius: 99, padding: '2px 8px', fontWeight: 500 }}>
                DFI-backed
              </span>
            )}
            {inst.big4_audited && (
              <span style={{ fontSize: 11, background: '#f0fdf4', color: '#15803d', borderRadius: 99, padding: '2px 8px', fontWeight: 500 }}>
                Big 4 audited
              </span>
            )}
            {inst.ifrs9_status && inst.ifrs9_status !== 'unknown' && (
              <span style={{ fontSize: 11, background: '#fef9c3', color: '#92400e', borderRadius: 99, padding: '2px 8px', fontWeight: 500 }}>
                IFRS 9: {inst.ifrs9_status.replace(/_/g, ' ')}
              </span>
            )}
            {(inst.lending_focus || []).map(f => (
              <span key={f} style={{ fontSize: 11, background: '#f3f4f6', color: '#374151', borderRadius: 99, padding: '2px 8px' }}>
                {f}
              </span>
            ))}
          </div>

          {inst.relevance_notes && (
            <div style={{ fontSize: 12, color: '#374151', marginBottom: 4 }}>{inst.relevance_notes}</div>
          )}

          {inst.international_stakeholders?.length > 0 && (
            <div style={{ fontSize: 11, color: '#6b7280' }}>
              Stakeholders: {inst.international_stakeholders.join(', ')}
            </div>
          )}

          {/* Status + Notes */}
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: '#6b7280' }}>Status:</span>
              <select
                value={status}
                onChange={handleStatusChange}
                style={{
                  fontSize: 11, fontWeight: 600, border: '1px solid #e5e7eb',
                  borderRadius: 6, padding: '2px 8px', color: STATUS_COLOR[status],
                  background: '#fff', cursor: 'pointer',
                }}
              >
                {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              onBlur={handleNotesSave}
              placeholder="Add notes..."
              rows={2}
              style={{
                fontSize: 12, border: '1px solid #e5e7eb', borderRadius: 6,
                padding: '6px 8px', resize: 'vertical', width: '100%',
                color: '#374151', fontFamily: 'inherit',
                outline: 'none', boxSizing: 'border-box',
              }}
            />
            {savingNotes && <span style={{ fontSize: 11, color: '#9ca3af' }}>Saving...</span>}
          </div>

          {/* Linked lead */}
          {inst.lead_title && (
            <div style={{
              marginTop: 8, padding: '6px 10px', background: '#f3f4f6',
              borderRadius: 6, fontSize: 11, color: '#6b7280',
            }}>
              From lead:{' '}
              {inst.scan_run_id ? (
                <Link to={`/history/${inst.scan_run_id}`} style={{ color: '#4f46e5', fontWeight: 500 }}>
                  {inst.lead_title}
                </Link>
              ) : (
                <span style={{ color: '#374151', fontWeight: 500 }}>{inst.lead_title}</span>
              )}
              {inst.lead_type && <span style={{ marginLeft: 6 }}>· {inst.lead_type}</span>}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, minWidth: 100 }}>
          {inst.source_url && (
            <a href={inst.source_url} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 11, color: '#4f46e5' }}>
              Source →
            </a>
          )}
          <span style={{ fontSize: 11, color: '#6b7280' }}>Auditor: {inst.auditor || 'unknown'}</span>
        </div>
      </div>
    </div>
  )
}

function TierSection({ tier, institutions, onUpdate }) {
  const [collapsed, setCollapsed] = useState(false)
  if (!institutions.length) return null

  return (
    <div style={{ marginBottom: 32 }}>
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: TIER_BG[tier], border: `1px solid ${TIER_COLOR[tier]}30`,
          borderRadius: 8, padding: '12px 16px', marginBottom: 12, cursor: 'pointer',
        }}
        onClick={() => setCollapsed(c => !c)}
      >
        <div>
          <span style={{ fontWeight: 700, fontSize: 15, color: TIER_COLOR[tier] }}>
            {TIER_LABEL[tier]}
          </span>
          <span style={{ fontSize: 12, color: '#6b7280', marginLeft: 10 }}>
            {institutions.length} institution{institutions.length !== 1 ? 's' : ''}
          </span>
          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>{TIER_DESC[tier]}</div>
        </div>
        <span style={{ fontSize: 16, color: '#6b7280' }}>{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && institutions.map((inst) => (
        <InstitutionRow key={inst.id} inst={inst} onUpdate={onUpdate} />
      ))}
    </div>
  )
}

export default function Targets() {
  const [targets, setTargets] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterCountry, setFilterCountry] = useState('')

  useEffect(() => {
    listAllTargets().then(setTargets).catch(console.error).finally(() => setLoading(false))
  }, [])

  const handleUpdate = (updated) => {
    setTargets(prev => prev.map(t => t.id === updated.id ? updated : t))
  }

  const countries = [...new Set(targets.map(t => t.country).filter(Boolean))].sort()
  const filtered = filterCountry ? targets.filter(t => t.country === filterCountry) : targets

  const byTier = TIERS.reduce((acc, tier) => {
    acc[tier] = filtered.filter(t => t.market_tier === tier)
    return acc
  }, {})

  return (
    <div className="page-content">
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>Target Institutions</h1>
      <p style={{ color: '#6b7280', marginBottom: 24, fontSize: 14 }}>
        Regulated institutions identified as potential Delphee customers, grouped by market tier.
        Use "Find Target Institutions" on any lead card to populate this list.
      </p>

      {loading ? (
        <div style={{ color: '#6b7280', fontSize: 14 }}>Loading...</div>
      ) : targets.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🏦</div>
          <h3>No target institutions yet</h3>
          <p>Open any lead, expand it, and click "Find Target Institutions" to get started.</p>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 12, marginBottom: 24, alignItems: 'center' }}>
            <select
              style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #e5e7eb', fontSize: 13 }}
              value={filterCountry}
              onChange={e => setFilterCountry(e.target.value)}
            >
              <option value="">All countries</option>
              {countries.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            {filterCountry && (
              <button className="btn btn-secondary btn-sm" onClick={() => setFilterCountry('')}>
                Clear
              </button>
            )}
            <span style={{ fontSize: 13, color: '#6b7280' }}>
              {filtered.length} institution{filtered.length !== 1 ? 's' : ''} total
            </span>
            <a
              href={exportTargetsUrl({ country: filterCountry || undefined })}
              download="delphee-targets.csv"
              className="btn btn-secondary btn-sm"
              style={{ marginLeft: 'auto' }}
            >
              Export CSV
            </a>
          </div>

          {TIERS.map(tier => (
            <TierSection key={tier} tier={tier} institutions={byTier[tier]} onUpdate={handleUpdate} />
          ))}
        </>
      )}
    </div>
  )
}

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { listScans, cancelScan, getScan } from '../api'

const STALE_MINUTES = 10

function isStuckRunning(scan) {
  if (scan.status !== 'running') return false
  const ageMinutes = (Date.now() - new Date(scan.started_at)) / 60000
  return ageMinutes > STALE_MINUTES
}

function fmt(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function duration(start, end) {
  if (!start || !end) return ''
  const s = Math.round((new Date(end) - new Date(start)) / 1000)
  return s < 60 ? `${s}s` : `${Math.round(s / 60)}m`
}

function ScanProgressPanel({ scanId, onComplete }) {
  const [progress, setProgress] = useState({ phase: 'discovery', message: 'Running...', pct: 0 })
  const intervalRef = useRef(null)

  useEffect(() => {
    intervalRef.current = setInterval(async () => {
      try {
        const scan = await getScan(scanId)
        if (scan.status === 'completed') {
          setProgress({ phase: 'complete', message: 'Scan complete', pct: 100 })
          clearInterval(intervalRef.current)
          onComplete(scan)
        } else if (scan.status === 'failed') {
          setProgress({ phase: 'error', message: 'Scan failed', pct: 0 })
          clearInterval(intervalRef.current)
          onComplete(scan)
        }
        // still running — progress bar animates via CSS, no message update needed
      } catch {
        // ignore transient fetch errors
      }
    }, 3000)

    return () => clearInterval(intervalRef.current)
  }, [scanId])

  const phaseLabel = { discovery: '🔍 Running', analysis: '🔍 Running', complete: '✅ Complete', error: '❌ Error' }

  return (
    <div style={{
      margin: '0 0 8px 0',
      padding: '10px 16px',
      background: '#f0f9ff',
      border: '1px solid #bae6fd',
      borderRadius: 8,
      fontSize: 13,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <span style={{
          padding: '2px 8px', borderRadius: 12,
          background: progress.phase === 'complete' ? '#dcfce7' : '#e0f2fe',
          color: progress.phase === 'complete' ? '#15803d' : '#0369a1',
          fontWeight: 600, fontSize: 12,
        }}>
          {phaseLabel[progress.phase] || progress.phase}
        </span>
        <span style={{ color: '#6b7280', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {progress.message}
        </span>
        <span style={{ color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{progress.pct}%</span>
      </div>
      <div style={{ height: 4, background: '#e0f2fe', borderRadius: 2, overflow: 'hidden' }}>
        {progress.phase === 'complete' ? (
          <div style={{ height: '100%', width: '100%', background: '#15803d', borderRadius: 2 }} />
        ) : progress.phase === 'error' ? (
          <div style={{ height: '100%', width: '100%', background: '#dc2626', borderRadius: 2 }} />
        ) : (
          <div style={{
            height: '100%', width: '40%', background: '#0284c7', borderRadius: 2,
            animation: 'progress-slide 1.5s ease-in-out infinite',
          }} />
        )}
      </div>
    </div>
  )
}

export default function ScanHistory() {
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    listScans(50)
      .then(setScans)
      .finally(() => setLoading(false))
  }, [])

  function handleScanComplete(updated) {
    setScans(prev => prev.map(s => s.id === updated.id ? { ...s, ...updated } : s))
  }

  async function handleCancel(e, scanId) {
    e.stopPropagation()
    if (!confirm('Mark this scan as failed?')) return
    setCancelling(scanId)
    try {
      const updated = await cancelScan(scanId)
      setScans(prev => prev.map(s => s.id === scanId ? { ...s, ...updated } : s))
    } finally {
      setCancelling(null)
    }
  }

  if (loading) return <div className="page-content" style={{ color: '#9ca3af' }}>Loading...</div>

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Scan History</h1>
          <p style={{ color: '#6b7280', fontSize: 14 }}>{scans.length} scan{scans.length !== 1 ? 's' : ''} total</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/')}>
          + New Scan
        </button>
      </div>

      {scans.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>No scans yet</h3>
          <p>Run your first scan to see results here.</p>
        </div>
      ) : (
        scans.map(scan => (
          <div key={scan.id}>
            <div
              className={`scan-card${scan.status === 'failed' ? ' failed' : ''}`}
              onClick={() => navigate(`/history/${scan.id}`)}
            >
              <div className={`scan-status-dot ${scan.status}`} />
              <div className="scan-card-body">
                <div className="scan-card-title">
                  {(scan.regions || []).join(', ') || 'All regions'}
                </div>
                <div className="scan-card-meta">
                  {fmt(scan.started_at)}
                  {scan.completed_at && ` · ${duration(scan.started_at, scan.completed_at)}`}
                  {' · '}{scan.status}
                </div>
              </div>
              <div className="scan-card-stats">
                <div>
                  <div className="stat-num">{scan.total_found || 0}</div>
                  <div className="stat-lbl">leads</div>
                </div>
                <div>
                  <div className="stat-num" style={{ color: '#15803d' }}>{scan.active_count || 0}</div>
                  <div className="stat-lbl">active</div>
                </div>
              </div>
              {isStuckRunning(scan) && (
                <button
                  className="btn btn-secondary"
                  style={{ marginLeft: 12, fontSize: 12, padding: '4px 10px', color: '#dc2626', borderColor: '#dc2626' }}
                  onClick={(e) => handleCancel(e, scan.id)}
                  disabled={cancelling === scan.id}
                >
                  {cancelling === scan.id ? 'Cancelling...' : 'Cancel'}
                </button>
              )}
            </div>
            {scan.status === 'running' && (
              <ScanProgressPanel
                scanId={scan.id}
                onComplete={handleScanComplete}
              />
            )}
          </div>
        ))
      )}
    </div>
  )
}

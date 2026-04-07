import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRegions, startScan, getScan, cancelScan, connectWebSocket } from '../api'
import LeadCard from '../components/LeadCard'

export default function NewScan() {
  const [regions, setRegions] = useState({})
  const [selected, setSelected] = useState([])
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState(null)   // { phase, current, total, logs, pct }
  const [result, setResult] = useState(null)        // { scan, leads }
  const navigate = useNavigate()
  const wsRef = useRef(null)
  const scanIdRef = useRef(null)
  const logEndRef = useRef(null)

  useEffect(() => {
    getRegions().then(setRegions).catch(console.error)

    // Reconnect to any scan that was running when the user navigated away
    const activeScanId = sessionStorage.getItem('activeScanId')
    if (activeScanId) {
      // Check current status via HTTP first — the scan may have completed while we
      // were on another page (ScanHistory's ScanProgressPanel would have consumed
      // the 'complete' WebSocket message, so we can't rely on WS reconnection alone).
      getScan(activeScanId).then(scan => {
        if (scan.status === 'completed') {
          setResult({ scan, leads: scan.leads || [] })
          sessionStorage.removeItem('activeScanId')
          return
        }
        if (scan.status === 'failed' || scan.status === 'cancelled') {
          sessionStorage.removeItem('activeScanId')
          return
        }

        // Still running — poll via HTTP until complete
        scanIdRef.current = activeScanId
        setScanning(true)
        setProgress({ phase: 'waiting', current: 0, total: 1, logs: ['Scan in progress — results will appear when complete.'], pct: null })
        const pollInterval = setInterval(async () => {
          try {
            const fresh = await getScan(activeScanId)
            if (fresh.status === 'completed') {
              clearInterval(pollInterval)
              setResult({ scan: fresh, leads: fresh.leads || [] })
              setScanning(false)
              setProgress(null)
              sessionStorage.removeItem('activeScanId')
            } else if (fresh.status === 'failed' || fresh.status === 'cancelled') {
              clearInterval(pollInterval)
              setProgress({ phase: 'error', current: 0, total: 1, logs: ['Scan ended without results.'], pct: null })
              setScanning(false)
              sessionStorage.removeItem('activeScanId')
            }
          } catch {
            // ignore transient fetch errors
          }
        }, 3000)
        wsRef.current = { close: () => clearInterval(pollInterval) }
      }).catch(() => {
        // Scan not found or API error — clear stale session entry
        sessionStorage.removeItem('activeScanId')
      })
    }

    return () => wsRef.current?.close()
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [progress?.logs])

  const toggle = (r) =>
    setSelected(s => s.includes(r) ? s.filter(x => x !== r) : [...s, r])

  const handleStart = async () => {
    if (!selected.length) return
    setScanning(true)
    setResult(null)
    setProgress({ phase: 'discovery', current: 0, total: 1, logs: [], pct: 0 })

    const { scan_id } = await startScan(selected)
    scanIdRef.current = scan_id
    sessionStorage.setItem('activeScanId', scan_id)

    const ws = connectWebSocket(scan_id, async (msg) => {
      if (msg.phase === 'ping') return

      if (msg.phase === 'complete') {
        const scan = await getScan(scan_id)
        setResult({ scan, leads: scan.leads || [] })
        setScanning(false)
        setProgress(null)
        sessionStorage.removeItem('activeScanId')
        ws.close()
        return
      }

      if (msg.phase === 'error') {
        setProgress(p => ({ ...p, logs: [...(p?.logs || []), `ERROR: ${msg.message}`] }))
        setScanning(false)
        sessionStorage.removeItem('activeScanId')
        ws.close()
        return
      }

      setProgress(p => {
        const logs = [...(p?.logs || []), `[${msg.phase}] ${msg.message}`]
        const current = msg.current || p?.current || 0
        const total = msg.total || p?.total || 1
        const pct = Math.round((current / total) * 100)
        return { phase: msg.phase, current, total, logs, pct }
      })
    })

    wsRef.current = ws
  }

  const handleCancel = async () => {
    if (!scanIdRef.current) return
    wsRef.current?.close()
    try { await cancelScan(scanIdRef.current) } catch { /* best effort */ }
    sessionStorage.removeItem('activeScanId')
    scanIdRef.current = null
    setScanning(false)
    setProgress(null)
  }

  const phaseState = (ph) => {
    if (!progress && !result) return 'idle'
    if (result) return 'done'
    if (progress?.phase === ph) return 'active'
    if (ph === 'discovery' && progress?.phase === 'analysis') return 'done'
    if (ph === 'discovery' && progress?.phase === 'complete') return 'done'
    if (ph === 'analysis' && progress?.phase === 'complete') return 'done'
    return 'idle'
  }

  return (
    <div className="page-content">
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>New Scan</h1>
      <p style={{ color: '#6b7280', marginBottom: 24, fontSize: 14 }}>
        Select regions to search for IFRS 9 / ECL opportunities.
      </p>

      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Select Regions</h2>
        <div className="region-grid">
          {Object.keys(regions).map(r => (
            <button
              key={r}
              className={`region-btn${selected.includes(r) ? ' selected' : ''}`}
              onClick={() => toggle(r)}
              disabled={scanning}
            >
              {r}
            </button>
          ))}
        </div>
        {selected.length > 0 && (
          <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 16 }}>
            {selected.reduce((acc, r) => acc + (regions[r]?.length || 0), 0)} countries selected
          </p>
        )}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            className="btn btn-primary"
            disabled={!selected.length || scanning}
            onClick={handleStart}
          >
            {scanning ? '⏳ Scanning...' : '🚀 Start Scan'}
          </button>
          {scanning && (
            <button
              className="btn btn-secondary"
              style={{ color: '#dc2626', borderColor: '#dc2626' }}
              onClick={handleCancel}
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {progress && (
        <div className="progress-panel">
          {progress.phase === 'waiting' || progress.phase === 'error' ? (
            <>
              <div className="progress-bar-wrap" style={{ marginBottom: 16 }}>
                {progress.phase === 'waiting' && (
                  <div style={{
                    height: '100%', width: '40%', background: '#0284c7', borderRadius: 99,
                    animation: 'progress-slide 1.5s ease-in-out infinite',
                  }} />
                )}
                {progress.phase === 'error' && (
                  <div style={{ height: '100%', width: '100%', background: '#ef4444', borderRadius: 99 }} />
                )}
              </div>
              <div className="log-list">
                {progress.logs.map((l, i) => (
                  <div key={i} className="log-entry">{l}</div>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="progress-phase">
                {['discovery', 'analysis'].map(ph => (
                  <span key={ph} className={`phase-pill ${phaseState(ph)}`}>
                    {ph === 'discovery' ? '🔍 Discovery' : '🧠 Analysis'}
                  </span>
                ))}
              </div>
              <div className="progress-bar-wrap">
                <div className="progress-bar-fill" style={{ width: `${progress.pct}%` }} />
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 10 }}>
                Batch {progress.current}/{progress.total} · {progress.pct}%
              </div>
              <div className="log-list">
                {progress.logs.map((l, i) => (
                  <div key={i} className="log-entry">{l}</div>
                ))}
                <div ref={logEndRef} />
              </div>
            </>
          )}
        </div>
      )}

      {result && (
        <div>
          <div className="stats-row" style={{ marginTop: 24 }}>
            <div className="stat-card">
              <div className="stat-value">{result.leads.length}</div>
              <div className="stat-label">Total leads</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: '#15803d' }}>
                {result.leads.filter(l => l.freshness === 'active').length}
              </div>
              <div className="stat-label">Active</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: '#4f46e5' }}>
                {result.leads.filter(l => (l.relevance_score || 0) >= 70).length}
              </div>
              <div className="stat-label">Score 70+</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: '#dc2626' }}>
                {result.leads.filter(l => l.urgency === 'high').length}
              </div>
              <div className="stat-label">Urgent</div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700 }}>
              Results — {result.leads.length} leads
            </h2>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/history/${result.scan.id}`)}>
              View full detail →
            </button>
          </div>

          {result.leads.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">🔍</div>
              <h3>No leads found</h3>
              <p>Try different regions or check your API keys.</p>
            </div>
          ) : (
            [...result.leads]
              .sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0))
              .map(lead => <LeadCard key={lead.id} lead={lead} />)
          )}
        </div>
      )}
    </div>
  )
}

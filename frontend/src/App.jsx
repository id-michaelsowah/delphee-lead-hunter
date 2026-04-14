import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import NewScan from './pages/NewScan'
import ScanHistory from './pages/ScanHistory'
import ScanDetail from './pages/ScanDetail'
import AllLeads from './pages/AllLeads'
import Targets from './pages/Targets'
import { setPassword, getStoredPassword, getRegions } from './api'

function LoginScreen({ onSuccess }) {
  const [pw, setPw] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setPassword(pw)
    try {
      await getRegions()
      onSuccess()
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Incorrect password. Please try again.')
        setPassword('')
      } else {
        onSuccess() // non-auth error — let the app load
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#f9fafb',
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, padding: '40px 36px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.08)', width: '100%', maxWidth: 360,
      }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 28, fontWeight: 800, color: '#0f172a', marginBottom: 4 }}>
            Delphee Lead Hunter
          </div>
          <div style={{ fontSize: 13, color: '#6b7280' }}>Enter your password to continue</div>
        </div>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            placeholder="Password"
            value={pw}
            onChange={e => setPw(e.target.value)}
            autoFocus
            style={{
              width: '100%', padding: '10px 12px', borderRadius: 8,
              border: '1px solid #e5e7eb', fontSize: 14, marginBottom: 12,
              boxSizing: 'border-box',
            }}
          />
          {error && (
            <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 10 }}>{error}</div>
          )}
          <button
            type="submit"
            disabled={!pw || loading}
            style={{
              width: '100%', padding: '10px', background: '#0f172a', color: '#fff',
              border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600,
              cursor: pw && !loading ? 'pointer' : 'not-allowed', opacity: pw && !loading ? 1 : 0.5,
            }}
          >
            {loading ? 'Checking...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(!!getStoredPassword())

  useEffect(() => {
    const handleLogout = () => setAuthed(false)
    window.addEventListener('auth:logout', handleLogout)
    return () => window.removeEventListener('auth:logout', handleLogout)
  }, [])

  if (!authed) {
    return <LoginScreen onSuccess={() => setAuthed(true)} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<NewScan />} />
          <Route path="history" element={<ScanHistory />} />
          <Route path="history/:id" element={<ScanDetail />} />
          <Route path="leads" element={<AllLeads />} />
          <Route path="targets" element={<Targets />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

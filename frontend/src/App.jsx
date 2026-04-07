import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import NewScan from './pages/NewScan'
import ScanHistory from './pages/ScanHistory'
import ScanDetail from './pages/ScanDetail'
import AllLeads from './pages/AllLeads'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<NewScan />} />
          <Route path="history" element={<ScanHistory />} />
          <Route path="history/:id" element={<ScanDetail />} />
          <Route path="leads" element={<AllLeads />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

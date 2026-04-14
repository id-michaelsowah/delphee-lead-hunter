import { NavLink, Outlet } from 'react-router-dom'
import logo from '../assets/delpheelogo.jfif'

export default function Layout() {
  return (
    <>
      <header className="app-header">
        <div className="brand">
          <img src={logo} alt="Delphee" className="brand-logo" />
        </div>
        <nav className="app-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
            New Scan
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => isActive ? 'active' : ''}>
            Scan History
          </NavLink>
          <NavLink to="/leads" className={({ isActive }) => isActive ? 'active' : ''}>
            All Leads
          </NavLink>
          <NavLink to="/targets" className={({ isActive }) => isActive ? 'active' : ''}>
            Targets
          </NavLink>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  )
}

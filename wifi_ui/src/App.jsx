import { useState } from 'react'
import Icon from './components/Icons'
import Dashboard from './pages/Dashboard'
import Scanner from './pages/Scanner'
import Connection from './pages/Connection'
import Channels from './pages/Channels'
import Coverage from './pages/Coverage'
import Diagnostics from './pages/Diagnostics'
import SpeedTest from './pages/SpeedTest'

const NAV = [
  { id: 'dashboard',   label: 'Dashboard',        icon: 'dashboard' },
  { id: 'connection',  label: 'Connection',        icon: 'wifi' },
  { id: 'scanner',     label: 'Network Scanner',   icon: 'radar' },
  { id: 'channels',    label: 'Channel Analyzer',  icon: 'bars' },
  { id: 'coverage',    label: 'Coverage Map',      icon: 'map' },
  { id: 'diagnostics', label: 'Diagnostics',       icon: 'activity' },
  { id: 'speedtest',   label: 'Speed Test',        icon: 'speed' },
]

const PAGES = {
  dashboard: Dashboard, connection: Connection, scanner: Scanner,
  channels: Channels, coverage: Coverage, diagnostics: Diagnostics, speedtest: SpeedTest,
}

export default function App() {
  const [active, setActive] = useState('dashboard')
  const Page = PAGES[active] || Dashboard

  return (
    <>
      <nav className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark"><Icon name="wifi" size={18} strokeWidth={2} /></div>
          <div>
            <h1>WiFi Debugger</h1>
            <p>Network Analysis Tool</p>
          </div>
        </div>
        <div className="sidebar-nav">
          <div className="nav-section">Analyze</div>
          {NAV.map(item => (
            <div
              key={item.id}
              className={`nav-item ${active === item.id ? 'active' : ''}`}
              onClick={() => setActive(item.id)}
            >
              <Icon name={item.icon} size={16} />
              {item.label}
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <span className="status-dot" />
          v1.0.0 · Linux
        </div>
      </nav>
      <main className="main">
        <Page key={active} />
      </main>
    </>
  )
}

import { useEffect, useState } from 'react'
import { api } from '../api'
import SignalGauge from '../components/SignalGauge'
import SignalBar from '../components/SignalBar'
import LiveSignalChart from '../components/LiveSignalChart'
import Icon from '../components/Icons'

function StatCard({ label, value, sub, color }) {
  return (
    <div className="card">
      <div className="card-title">{label}</div>
      <div className="stat-value" style={color ? { color } : {}}>{value ?? '—'}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [conn, setConn] = useState(null)
  const [diag, setDiag] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.connection(), api.diagnostics()])
      .then(([c, d]) => { setConn(c); setDiag(d) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ color: 'var(--muted)', padding: 40 }}><span className="spin" /> Loading...</div>

  const pmOn = conn?.power_management
  const criticals = diag?.findings?.filter(f => f.severity === 'critical') ?? []
  const warnings = diag?.findings?.filter(f => f.severity === 'warning') ?? []

  return (
    <div>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Overview of your WiFi connection health</p>
      </div>

      {pmOn && (
        <div className="alert alert-warning" style={{ marginBottom: 20 }}>
          <Icon name="alert" size={16} />
          <span><strong>Power Management is ON</strong> — this is throttling your WiFi speed.
          Go to <strong>Diagnostics</strong> to fix it with one click.</span>
        </div>
      )}

      <div className="grid-4">
        <StatCard label="Connected SSID" value={conn?.ssid ?? 'Not connected'} sub={conn?.bssid} />
        <StatCard label="Band" value={conn?.band ?? '—'}
          color={conn?.band === '5GHz' ? 'var(--accent)' : conn?.band === '2.4GHz' ? '#eab308' : undefined} />
        <StatCard label="TX Rate" value={conn?.tx_rate_mbps ? `${conn.tx_rate_mbps} Mb/s` : '—'} sub={conn?.channel_width ?? 'Channel width N/A'} />
        <StatCard
          label="Issues Found"
          value={diag ? `${diag.critical} critical` : '—'}
          sub={diag ? `${diag.warnings} warnings` : undefined}
          color={diag?.critical > 0 ? '#ef4444' : '#22c55e'}
        />
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-title">Signal Strength</div>
          {conn?.connected ? (
            <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
              <SignalGauge dbm={conn.signal_dbm} quality={conn.quality} size={130} />
              <div style={{ flex: 1 }}>
                <div className="info-row"><span className="key">Channel</span><span className="val">{conn.channel || '—'}</span></div>
                <div className="info-row"><span className="key">Frequency</span><span className="val">{conn.frequency_mhz ? `${conn.frequency_mhz} MHz` : '—'}</span></div>
                <div className="info-row"><span className="key">TX Power</span><span className="val">{conn.tx_power_dbm ? `${conn.tx_power_dbm} dBm` : '—'}</span></div>
                <div className="info-row">
                  <span className="key">Power Mgmt</span>
                  <span className="val" style={{ color: pmOn ? 'var(--red)' : 'var(--green)' }}>{pmOn ? 'ON — throttling' : 'OFF'}</span>
                </div>
                <div className="info-row"><span className="key">TX Retries</span>
                  <span className="val" style={{ color: conn.retry_excessive > 50 ? '#ef4444' : 'var(--text)' }}>{conn.retry_excessive}</span>
                </div>
              </div>
            </div>
          ) : <div style={{ color: 'var(--muted)' }}>Not connected</div>}
        </div>

        <div className="card">
          <LiveSignalChart />
        </div>
      </div>

      {(criticals.length > 0 || warnings.length > 0) && (
        <div className="card">
          <div className="card-title">Top Issues</div>
          {[...criticals, ...warnings].slice(0, 4).map((f, i) => (
            <div key={i} className={`finding-card ${f.severity}`} style={{ animationDelay: `${i * 60}ms` }}>
              <div className="finding-title">
                <span className={`sev-chip ${f.severity}`}>{f.severity}</span> {f.title}
              </div>
              <div className="finding-detail">{f.detail}</div>
              <div className="finding-fix">{f.recommendation}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

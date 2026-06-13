import { useState } from 'react'
import { api } from '../api'
import { signalPct, qualityColor } from '../components/SignalGauge'
import Icon from '../components/Icons'

function BandBadge({ band }) {
  const cls = band === '5GHz' ? 'badge-5ghz' : band === '6GHz' ? 'badge-6ghz' : 'badge-24ghz'
  return <span className={`badge ${cls}`}>{band}</span>
}

function MiniBar({ dbm, quality }) {
  const pct = signalPct(dbm)
  const color = qualityColor(quality)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 60, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 12, color, fontWeight: 600 }}>{dbm} dBm</span>
    </div>
  )
}

export default function Scanner() {
  const [networks, setNetworks] = useState([])
  const [loading, setLoading] = useState(false)
  const [scanned, setScanned] = useState(false)
  const [filter, setFilter] = useState('')

  async function scan() {
    setLoading(true)
    try {
      const data = await api.scan()
      setNetworks(data.networks)
      setScanned(true)
    } finally {
      setLoading(false)
    }
  }

  const filtered = networks.filter(n =>
    n.ssid.toLowerCase().includes(filter.toLowerCase()) ||
    n.bssid.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div>
      <div className="page-header">
        <h2>Network Scanner</h2>
        <p>Scan nearby WiFi access points</p>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={scan} disabled={loading}>
          {loading ? <><span className="spin" /> Scanning...</> : <><Icon name="radar" size={14} /> Scan Now</>}
        </button>
        {scanned && (
          <input
            className="input"
            style={{ width: 220 }}
            placeholder="Filter by SSID or BSSID..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
        )}
        {scanned && <span style={{ color: 'var(--muted)', fontSize: 13 }}>{filtered.length} network(s)</span>}
      </div>

      {!scanned && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--muted)' }}>
          Click "Scan Now" to discover nearby WiFi networks
        </div>
      )}

      {scanned && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="wifi-table">
            <thead>
              <tr>
                <th>SSID</th>
                <th>BSSID</th>
                <th>Band</th>
                <th>CH</th>
                <th>Signal</th>
                <th>Rate</th>
                <th>Security</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((n, i) => (
                <tr key={i}>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: n.is_connected ? 650 : 400, color: n.is_connected ? 'var(--accent)' : 'var(--text)' }}>
                      {n.ssid}
                      {n.is_connected && <span className="badge badge-connected">connected</span>}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--muted)' }}>{n.bssid}</td>
                  <td><BandBadge band={n.band} /></td>
                  <td style={{ color: 'var(--muted)' }}>{n.channel || '—'}</td>
                  <td><MiniBar dbm={n.signal_dbm} quality={n.quality} /></td>
                  <td style={{ color: 'var(--muted)' }}>{n.max_rate_mbps ? `${n.max_rate_mbps} Mb/s` : '—'}</td>
                  <td style={{ fontSize: 12, color: 'var(--muted)' }}>{n.security}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

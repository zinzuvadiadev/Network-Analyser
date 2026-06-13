import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'

function SpeedBar({ label, value, max = 200, color }) {
  const pct = Math.min(100, (value / max) * 100)
  return (
    <div className="speed-bar-row">
      <span className="speed-bar-label">{label}</span>
      <div className="speed-bar-track">
        <div className="speed-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="speed-bar-val" style={{ color }}>{value?.toFixed(1) ?? '—'} Mb/s</span>
    </div>
  )
}

export default function SpeedTest() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  async function run() {
    setLoading(true)
    setResult(null)
    try { setResult(await api.speedtest()) }
    catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const latColor = result ? (result.latency_ms < 30 ? '#22c55e' : result.latency_ms < 80 ? '#eab308' : '#ef4444') : '#64748b'

  return (
    <div>
      <div className="page-header">
        <h2>Speed Test</h2>
        <p>Measure your actual download, upload, and latency</p>
      </div>

      <div style={{ marginBottom: 20 }}>
        <button className="btn btn-primary" onClick={run} disabled={loading}>
          {loading ? <><span className="spin" /> Testing... (this takes ~30s)</> : <><Icon name="play" size={13} fill /> Run Speed Test</>}
        </button>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ marginBottom: 16 }}><span className="spin" style={{ width: 32, height: 32, borderWidth: 3 }} /></div>
          <div style={{ color: 'var(--muted)' }}>Measuring download, upload, and latency...</div>
        </div>
      )}

      {result && !loading && (
        <div className="card">
          <div className="card-title">Results</div>
          <SpeedBar label="Download" value={result.download_mbps} max={200} color="#22c55e" />
          <SpeedBar label="Upload" value={result.upload_mbps} max={50} color="#60a5fa" />
          <div style={{ marginTop: 20, display: 'flex', gap: 20 }}>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: latColor }}>{result.latency_ms} ms</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Latency</div>
            </div>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--muted)' }}>{result.jitter_ms} ms</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>Jitter</div>
            </div>
          </div>
        </div>
      )}

      {!result && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--muted)' }}>
          Click "Run Speed Test" to measure your connection speed
        </div>
      )}
    </div>
  )
}

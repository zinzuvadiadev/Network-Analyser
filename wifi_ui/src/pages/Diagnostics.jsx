import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'

export default function Diagnostics() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [fixing, setFixing] = useState(false)
  const [fixMsg, setFixMsg] = useState(null)

  async function run() {
    setLoading(true)
    setFixMsg(null)
    try { setResult(await api.diagnostics()) }
    finally { setLoading(false) }
  }

  async function fixPower() {
    setFixing(true)
    try {
      const r = await api.fixPower()
      setFixMsg(r.success
        ? { ok: true, text: 'Power management disabled. Re-run diagnostics to confirm.' }
        : { ok: false, text: 'Fix failed. Try running the backend with sudo.' })
      run()
    } finally { setFixing(false) }
  }

  const hasPmIssue = result?.findings?.some(f => f.category === 'power_management' && f.severity === 'critical')

  return (
    <div>
      <div className="page-header">
        <h2>Full Diagnostics</h2>
        <p>Comprehensive analysis of your WiFi setup with actionable fixes</p>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="btn btn-primary" onClick={run} disabled={loading}>
          {loading ? <><span className="spin" /> Running...</> : <><Icon name="refresh" size={14} /> Run Diagnostics</>}
        </button>
        {hasPmIssue && (
          <button className="btn btn-danger" onClick={fixPower} disabled={fixing}>
            {fixing ? <><span className="spin" /> Fixing...</> : <><Icon name="zap" size={14} /> Fix Power Management Now</>}
          </button>
        )}
      </div>

      {fixMsg && (
        <div className={`alert ${fixMsg.ok ? 'alert-success' : 'alert-error'}`} style={{ marginBottom: 20 }}>
          <Icon name={fixMsg.ok ? 'check' : 'x'} size={15} />
          {fixMsg.text}
        </div>
      )}

      {!result && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--muted)' }}>
          Click "Run Diagnostics" to analyze your WiFi
        </div>
      )}

      {result && (
        <>
          <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            {result.critical > 0 && (
              <div className="card" style={{ flex: 1, textAlign: 'center', borderColor: '#ef4444' }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#ef4444' }}>{result.critical}</div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Critical</div>
              </div>
            )}
            {result.warnings > 0 && (
              <div className="card" style={{ flex: 1, textAlign: 'center', borderColor: '#eab308' }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#eab308' }}>{result.warnings}</div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Warnings</div>
              </div>
            )}
            {result.critical === 0 && result.warnings === 0 && (
              <div className="card" style={{ flex: 1, textAlign: 'center', borderColor: 'var(--green)' }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--green)', display: 'flex', justifyContent: 'center' }}>
                  <Icon name="check" size={30} strokeWidth={2.4} />
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>All Clear</div>
              </div>
            )}
          </div>

          <div>
            {result.findings.map((f, i) => (
              <div key={i} className={`finding-card ${f.severity}`} style={{ animationDelay: `${i * 60}ms` }}>
                <div className="finding-title">
                  <span className={`sev-chip ${f.severity}`}>{f.severity}</span> {f.title}
                </div>
                <div className="finding-detail">{f.detail}</div>
                <div className="finding-fix">{f.recommendation}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

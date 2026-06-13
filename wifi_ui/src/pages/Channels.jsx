import { useState } from 'react'
import { api } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import Icon from '../components/Icons'

const GOOD = '#22c55e'
const WARN = '#eab308'
const BAD = '#ef4444'
const CUR = '#00d4ff'

function barColor(d) {
  if (d.is_current) return CUR
  if (d.is_recommended) return GOOD
  if (d.interference_score > 100) return BAD
  if (d.interference_score > 40) return WARN
  return '#2a2a4a'
}

export default function Channels() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  async function analyze() {
    setLoading(true)
    try { setData(await api.channels()) }
    finally { setLoading(false) }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Channel Analyzer</h2>
        <p>Detect congestion and find the best WiFi channel</p>
      </div>

      <div style={{ marginBottom: 20 }}>
        <button className="btn btn-primary" onClick={analyze} disabled={loading}>
          {loading ? <><span className="spin" /> Analyzing...</> : <><Icon name="bars" size={14} /> Analyze Channels</>}
        </button>
      </div>

      {!data && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--muted)' }}>
          Click "Analyze Channels" to see channel occupancy
        </div>
      )}

      {data && (
        <>
          {data.band_24.length > 0 && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-title">2.4 GHz Channels — Interference Score</div>
              <div className="legend-chips" style={{ marginTop: 0, marginBottom: 16 }}>
                <span className="legend-chip"><span className="legend-swatch" style={{ background: CUR }} /> Your channel</span>
                <span className="legend-chip"><span className="legend-swatch" style={{ background: GOOD }} /> Recommended</span>
                <span className="legend-chip"><span className="legend-swatch" style={{ background: WARN }} /> Moderate</span>
                <span className="legend-chip"><span className="legend-swatch" style={{ background: BAD }} /> Congested</span>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data.band_24} margin={{ top: 5, right: 20, left: -20, bottom: 5 }}>
                  <XAxis dataKey="channel" tick={{ fill: '#64748b', fontSize: 12 }} tickLine={false} axisLine={false}
                    tickFormatter={v => `Ch ${v}`} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 8, fontSize: 12 }}
                    formatter={(v, n, p) => [
                      `${v}${n === 'interference_score' ? '' : ' APs'}`,
                      n === 'interference_score' ? 'Interference Score' : 'APs',
                    ]}
                  />
                  <Bar dataKey="interference_score" radius={[4, 4, 0, 0]}>
                    {data.band_24.map((d, i) => <Cell key={i} fill={barColor(d)} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {data.recommended_24 && (
                <div style={{ marginTop: 12, fontSize: 13, color: GOOD, display: 'flex', alignItems: 'center', gap: 7 }}>
                  <Icon name="check" size={14} strokeWidth={2.2} /> Recommended 2.4GHz channel: <strong>{data.recommended_24}</strong>
                </div>
              )}
            </div>
          )}

          {data.band_5.length > 0 && (
            <div className="card">
              <div className="card-title">5 GHz Channels — AP Count</div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data.band_5} margin={{ top: 5, right: 20, left: -20, bottom: 5 }}>
                  <XAxis dataKey="channel" tick={{ fill: '#64748b', fontSize: 12 }} tickLine={false} axisLine={false}
                    tickFormatter={v => `Ch ${v}`} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 8, fontSize: 12 }}
                    formatter={(v) => [`${v} APs`, 'Count']}
                  />
                  <Bar dataKey="ap_count" radius={[4, 4, 0, 0]}>
                    {data.band_5.map((d, i) => (
                      <Cell key={i} fill={d.is_current ? CUR : d.is_recommended ? GOOD : '#2a2a4a'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {data.recommended_5 && (
                <div style={{ marginTop: 12, fontSize: 13, color: GOOD, display: 'flex', alignItems: 'center', gap: 7 }}>
                  <Icon name="check" size={14} strokeWidth={2.2} /> Recommended 5GHz channel: <strong>{data.recommended_5}</strong>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

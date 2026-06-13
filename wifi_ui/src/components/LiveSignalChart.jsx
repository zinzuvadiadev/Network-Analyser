import { useEffect, useRef, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { qualityColor } from './SignalGauge'

export default function LiveSignalChart() {
  const [samples, setSamples] = useState([])
  const [status, setStatus] = useState('connecting')
  const wsRef = useRef(null)

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(`ws://${location.host}/ws/signal`)
      wsRef.current = ws

      ws.onopen = () => setStatus('live')
      ws.onclose = () => { setStatus('disconnected'); setTimeout(connect, 2000) }
      ws.onerror = () => setStatus('error')

      ws.onmessage = (e) => {
        const { signal_dbm, quality, timestamp } = JSON.parse(e.data)
        const color = qualityColor(quality)
        setSamples(prev => {
          const next = [...prev, { t: new Date(timestamp * 1000).toLocaleTimeString(), dbm: signal_dbm, color }]
          return next.slice(-60)
        })
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const last = samples[samples.length - 1]
  const color = last?.color || '#64748b'

  const CustomDot = (props) => {
    if (props.index !== samples.length - 1) return null
    return <circle cx={props.cx} cy={props.cy} r={4} fill={color} stroke="none" />
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span className="card-title" style={{ marginBottom: 0 }}>Live Signal</span>
        <span className="live-pill" style={{ color: status === 'live' ? 'var(--green)' : 'var(--red)' }}>
          {status === 'live' && <span className="dot" />}
          {status.toUpperCase()}
        </span>
      </div>
      {samples.length === 0 ? (
        <div style={{ height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)' }}>
          <span className="spin" style={{ marginRight: 8 }} /> Waiting for signal data...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={samples} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
            <XAxis dataKey="t" tick={false} axisLine={false} tickLine={false} />
            <YAxis domain={[-100, -30]} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: '#64748b' }}
              formatter={(v) => [`${v} dBm`, 'Signal']}
            />
            <ReferenceLine y={-70} stroke="#eab308" strokeDasharray="3 3" strokeWidth={1} />
            <ReferenceLine y={-80} stroke="#ef4444" strokeDasharray="3 3" strokeWidth={1} />
            <Line
              type="monotone"
              dataKey="dbm"
              stroke={color}
              strokeWidth={2}
              dot={<CustomDot />}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

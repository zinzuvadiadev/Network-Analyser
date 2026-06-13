export function qualityColor(q) {
  return { Excellent: '#22c55e', Good: '#86efac', Fair: '#eab308', Poor: '#f97316', 'Very Poor': '#ef4444' }[q] || '#64748b'
}

export function signalPct(dbm) {
  return Math.max(0, Math.min(100, Math.round(((dbm + 100) / 60) * 100)))
}

export default function SignalGauge({ dbm, quality, size = 120 }) {
  const pct = signalPct(dbm)
  const color = qualityColor(quality)
  const r = 46
  const circ = 2 * Math.PI * r
  const strokeDash = (pct / 100) * circ

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={size} height={size} viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#2a2a4a" strokeWidth="8" />
        <circle
          cx="50" cy="50" r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={`${strokeDash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
          style={{ transition: 'stroke-dasharray 0.5s ease' }}
        />
        <text x="50" y="46" textAnchor="middle" fill={color} fontSize="16" fontWeight="700" fontFamily="system-ui">
          {dbm}
        </text>
        <text x="50" y="60" textAnchor="middle" fill="#64748b" fontSize="8" fontFamily="system-ui">
          dBm
        </text>
      </svg>
      <div style={{ fontSize: 12, color, fontWeight: 600, marginTop: 4 }}>{quality}</div>
    </div>
  )
}

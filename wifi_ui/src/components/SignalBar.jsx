import { signalPct, qualityColor } from './SignalGauge'

export default function SignalBar({ dbm, quality, showLabel = true }) {
  const pct = signalPct(dbm)
  const color = qualityColor(quality)
  return (
    <div>
      {showLabel && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
          <span style={{ color }}>{dbm} dBm</span>
          <span style={{ color: 'var(--muted)' }}>{quality}</span>
        </div>
      )}
      <div className="signal-bar-track">
        <div className="signal-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api } from '../api'
import SignalGauge from '../components/SignalGauge'
import LiveSignalChart from '../components/LiveSignalChart'

function Row({ label, value, highlight }) {
  return (
    <div className="info-row">
      <span className="key">{label}</span>
      <span className="val" style={highlight ? { color: highlight } : {}}>{value ?? 'N/A'}</span>
    </div>
  )
}

export default function Connection() {
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.connection().then(setInfo).finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ color: 'var(--muted)', padding: 40 }}><span className="spin" /> Loading...</div>
  if (!info?.connected) return (
    <div>
      <div className="page-header"><h2>Current Connection</h2></div>
      <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--muted)' }}>Not connected to any WiFi network</div>
    </div>
  )

  return (
    <div>
      <div className="page-header">
        <h2>Current Connection</h2>
        <p>Detailed view of your active WiFi link</p>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-title">Connection Details</div>
          <Row label="SSID" value={info.ssid} />
          <Row label="BSSID" value={info.bssid} />
          <Row label="Interface" value={info.interface} />
          <Row label="Band" value={info.band} highlight={info.band === '5GHz' ? 'var(--accent)' : '#eab308'} />
          <Row label="Channel" value={info.channel} />
          <Row label="Frequency" value={info.frequency_mhz ? `${info.frequency_mhz} MHz` : null} />
          <Row label="Channel Width" value={info.channel_width ?? 'N/A (install iw)'} />
          <Row label="MCS Index" value={info.mcs_index} />
          <Row label="TX Rate" value={info.tx_rate_mbps ? `${info.tx_rate_mbps} Mb/s` : null} />
          <Row label="RX Rate" value={info.rx_rate_mbps ? `${info.rx_rate_mbps} Mb/s` : null} />
          <Row label="TX Power" value={info.tx_power_dbm ? `${info.tx_power_dbm} dBm` : null} />
          <Row
            label="Power Management"
            value={info.power_management ? 'ON — throttling speed' : 'OFF (good)'}
            highlight={info.power_management ? '#ef4444' : '#22c55e'}
          />
          <Row
            label="TX Retries"
            value={info.retry_excessive}
            highlight={info.retry_excessive > 50 ? '#ef4444' : undefined}
          />
        </div>

        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">Signal Quality</div>
            <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0' }}>
              <SignalGauge dbm={info.signal_dbm} quality={info.quality} size={150} />
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">Adapter Info</div>
            <Row label="Driver" value={info.driver} />
            <Row label="Driver Version" value={info.driver_version} />
            <Row label="Vendor" value={info.vendor} />
          </div>
        </div>
      </div>

      <div className="card">
        <LiveSignalChart />
      </div>
    </div>
  )
}

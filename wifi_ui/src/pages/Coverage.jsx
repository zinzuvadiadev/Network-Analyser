import { useRef, useState, useEffect } from 'react'
import * as PlotlyModule from 'plotly.js-dist-min'
import { api } from '../api'
import { qualityColor } from '../components/SignalGauge'
import Icon from '../components/Icons'

// CJS interop: Vite may give us either the default or the namespace
const Plotly = PlotlyModule.default ?? PlotlyModule

// Thin React wrapper around Plotly so we never touch react-plotly.js
function Plot({ data, layout, style, config, revision }) {
  const divRef = useRef(null)
  useEffect(() => {
    if (!divRef.current) return
    Plotly.react(divRef.current, data, layout, config ?? {})
  }, [data, layout, config, revision])
  useEffect(() => () => { if (divRef.current) Plotly.purge(divRef.current) }, [])
  useEffect(() => {
    const el = divRef.current
    if (!el) return
    const ro = new ResizeObserver(() => Plotly.Plots?.resize(el))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return <div ref={divRef} style={style} />
}

const WIFI_COLORSCALE = [
  [0, '#d73027'], [0.2, '#f46d43'], [0.4, '#fdae61'],
  [0.6, '#d9ef8b'], [0.8, '#a6d96a'], [1, '#1a9850'],
]

const AP_COLORS = { manual: '#fbbf24', auto: '#a78bfa' }

function dbmToQuality(dbm) {
  if (dbm >= -50) return 'Excellent'
  if (dbm >= -60) return 'Good'
  if (dbm >= -70) return 'Fair'
  if (dbm >= -80) return 'Poor'
  return 'Very Poor'
}

/* Animated floor plan: radar rings emanate from the router, signal pulses
   travel along the rays toward each measurement point. Runs on a single
   requestAnimationFrame loop reading the latest props from a ref. */
function FloorPlan({ roomW, roomH, points, pendingPos, ap, settingAp, onCanvasClick }) {
  const canvasRef = useRef(null)
  const stateRef = useRef({})
  stateRef.current = { roomW, roomH, points, pendingPos, ap, settingAp }

  const CANVAS_W = 520
  const CANVAS_H = Math.max(220, Math.round((roomH / roomW) * CANVAS_W))

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    canvas.width = CANVAS_W * dpr
    canvas.height = CANVAS_H * dpr
    const ctx = canvas.getContext('2d')
    ctx.scale(dpr, dpr)

    let raf
    const draw = (now) => {
      const { roomW, roomH, points, pendingPos, ap, settingAp } = stateRef.current
      const t = now / 1000
      const toC = (x, y) => [(x / roomW) * CANVAS_W, CANVAS_H - (y / roomH) * CANVAS_H]

      ctx.clearRect(0, 0, CANVAS_W, CANVAS_H)
      ctx.fillStyle = '#0b0f1c'
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)

      // Grid (1 m squares)
      ctx.strokeStyle = 'rgba(48,60,90,0.45)'
      ctx.lineWidth = 1
      for (let x = 0; x <= roomW; x++) {
        const [cx] = toC(x, 0)
        ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, CANVAS_H); ctx.stroke()
      }
      for (let y = 0; y <= roomH; y++) {
        const [, cy] = toC(0, y)
        ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(CANVAS_W, cy); ctx.stroke()
      }

      const apColor = ap ? AP_COLORS[ap.source] : null

      if (ap) {
        const [ax, ay] = toC(ap.x, ap.y)

        // Expanding radar rings
        const maxR = Math.hypot(CANVAS_W, CANVAS_H) * 0.45
        for (let i = 0; i < 3; i++) {
          const phase = ((t / 2.8) + i / 3) % 1
          const r = 14 + phase * maxR
          const alpha = 0.32 * (1 - phase)
          if (alpha > 0.01) {
            ctx.beginPath()
            ctx.arc(ax, ay, r, 0, Math.PI * 2)
            ctx.strokeStyle = `${apColor}${Math.round(alpha * 255).toString(16).padStart(2, '0')}`
            ctx.lineWidth = 1.5
            ctx.stroke()
          }
        }

        // Rays with flowing dashes + traveling pulse
        points.forEach((p, idx) => {
          const [px, py] = toC(p.x, p.y)
          const color = qualityColor(dbmToQuality(p.signal_dbm))

          ctx.beginPath()
          ctx.moveTo(ax, ay)
          ctx.lineTo(px, py)
          ctx.strokeStyle = color + '40'
          ctx.lineWidth = 1.5
          ctx.setLineDash([3, 9])
          ctx.lineDashOffset = -((t * 26) % 12)
          ctx.stroke()
          ctx.setLineDash([])

          // Traveling pulse dot (staggered per ray)
          const phase = ((t / 1.7) + idx * 0.21) % 1
          const qx = ax + (px - ax) * phase
          const qy = ay + (py - ay) * phase
          const fade = 1 - phase * 0.55
          ctx.beginPath()
          ctx.arc(qx, qy, 3 + (1 - phase) * 1.5, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(34,211,238,${0.85 * fade})`
          ctx.fill()
        })
      }

      // Measurement points with glow
      points.forEach(p => {
        const [cx, cy] = toC(p.x, p.y)
        const color = qualityColor(dbmToQuality(p.signal_dbm))
        const glow = ctx.createRadialGradient(cx, cy, 2, cx, cy, 18)
        glow.addColorStop(0, color + '50')
        glow.addColorStop(1, color + '00')
        ctx.beginPath(); ctx.arc(cx, cy, 18, 0, Math.PI * 2)
        ctx.fillStyle = glow; ctx.fill()

        ctx.beginPath(); ctx.arc(cx, cy, 10, 0, Math.PI * 2)
        ctx.fillStyle = '#0b0f1c'; ctx.fill()
        ctx.strokeStyle = color; ctx.lineWidth = 1.8; ctx.stroke()
        ctx.fillStyle = color
        ctx.font = '600 9px system-ui'
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
        ctx.fillText(p.signal_dbm, cx, cy)
      })

      // Router marker
      if (ap) {
        const [ax, ay] = toC(ap.x, ap.y)
        const pulse = 1 + 0.08 * Math.sin(t * 3)
        const glow = ctx.createRadialGradient(ax, ay, 2, ax, ay, 26)
        glow.addColorStop(0, apColor + '70')
        glow.addColorStop(1, apColor + '00')
        ctx.beginPath(); ctx.arc(ax, ay, 26, 0, Math.PI * 2)
        ctx.fillStyle = glow; ctx.fill()

        ctx.beginPath(); ctx.arc(ax, ay, 11 * pulse, 0, Math.PI * 2)
        ctx.fillStyle = apColor; ctx.fill()
        ctx.strokeStyle = '#0b0f1c'; ctx.lineWidth = 2; ctx.stroke()
        ctx.fillStyle = '#10141f'
        ctx.font = '700 8.5px system-ui'
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
        ctx.fillText('AP', ax, ay)

        ctx.fillStyle = apColor
        ctx.font = '600 10px system-ui'
        const label = ap.source === 'auto' ? 'Router (estimated)' : 'Router'
        ctx.fillText(label, ax, Math.min(ay + 26, CANVAS_H - 8))
      }

      // Pending position crosshair
      if (pendingPos) {
        const [cx, cy] = toC(pendingPos.x, pendingPos.y)
        ctx.strokeStyle = 'rgba(34,211,238,0.55)'
        ctx.lineWidth = 1
        ctx.setLineDash([4, 5])
        ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, CANVAS_H); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(CANVAS_W, cy); ctx.stroke()
        ctx.setLineDash([])
        const r = 8 + 1.5 * Math.sin(t * 4)
        ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2)
        ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 1.8; ctx.stroke()
        ctx.beginPath(); ctx.arc(cx, cy, 2, 0, Math.PI * 2)
        ctx.fillStyle = '#22d3ee'; ctx.fill()
      }

      // Scale labels
      ctx.fillStyle = 'rgba(123,138,163,0.8)'
      ctx.font = '10px system-ui'
      ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'
      ctx.fillText('0', 5, CANVAS_H - 5)
      ctx.fillText(`${roomW} m`, CANVAS_W - 30, CANVAS_H - 5)
      ctx.textAlign = 'right'
      ctx.fillText(`${roomH} m`, CANVAS_W - 5, 13)

      if (settingAp) {
        ctx.fillStyle = 'rgba(251,191,36,0.9)'
        ctx.font = '600 12px system-ui'
        ctx.textAlign = 'center'
        ctx.fillText('Click where your router is', CANVAS_W / 2, 22)
      }

      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [CANVAS_W, CANVAS_H])

  function handleClick(e) {
    const rect = canvasRef.current.getBoundingClientRect()
    const { roomW, roomH } = stateRef.current
    const x = Math.round(((e.clientX - rect.left) / CANVAS_W) * roomW * 10) / 10
    const y = Math.round((1 - (e.clientY - rect.top) / CANVAS_H) * roomH * 10) / 10
    onCanvasClick({
      x: Math.max(0, Math.min(roomW, x)),
      y: Math.max(0, Math.min(roomH, y)),
    })
  }

  return (
    <div className={`coverage-canvas-wrap ${settingAp ? 'ap-mode' : ''}`} style={{ width: CANVAS_W }}>
      <canvas
        ref={canvasRef}
        style={{ width: CANVAS_W, height: CANVAS_H }}
        onClick={handleClick}
      />
    </div>
  )
}

function Stepper({ points, ap, heatmap }) {
  const steps = [
    { label: <>Set your <strong>room dimensions</strong></>, done: true },
    { label: <>Mark the <strong>router</strong> manually, or auto-detect it later</>, done: !!ap },
    { label: <>Click the map, walk there, <strong>record signal</strong> — {points.length}/4 minimum</>, done: points.length >= 4 },
    { label: <>Generate the <strong>coverage map</strong></>, done: !!heatmap },
  ]
  const currentIdx = steps.findIndex(s => !s.done)
  return (
    <div className="stepper">
      {steps.map((s, i) => (
        <div key={i} className={`step ${s.done ? 'done' : ''} ${i === currentIdx ? 'current' : ''}`}>
          <div className="step-num">{s.done ? <Icon name="check" size={11} strokeWidth={2.5} /> : i + 1}</div>
          <div className="step-body">{s.label}</div>
        </div>
      ))}
    </div>
  )
}

export default function Coverage() {
  const [roomW, setRoomW] = useState(5)
  const [roomH, setRoomH] = useState(4)
  const [points, setPoints] = useState([])
  const [pendingPos, setPendingPos] = useState(null)
  const [ap, setAp] = useState(null)            // { x, y, source: 'manual'|'auto', meta }
  const [settingAp, setSettingAp] = useState(false)
  const [measuring, setMeasuring] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [detectError, setDetectError] = useState(null)
  const [heatmap, setHeatmap] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [tab, setTab] = useState('collect')
  const [pulsePhase, setPulsePhase] = useState(0)

  // Drives the 3D ray pulse animation
  useEffect(() => {
    if (!ap || !heatmap || tab !== '3d') return
    const id = setInterval(() => setPulsePhase(p => (p + 0.05) % 1), 90)
    return () => clearInterval(id)
  }, [ap, heatmap, tab])

  function handleCanvasClick(pos) {
    if (settingAp) {
      setAp({ ...pos, source: 'manual' })
      setSettingAp(false)
    } else {
      setPendingPos(pos)
    }
  }

  async function recordPoint() {
    if (!pendingPos) return
    setMeasuring(true)
    try {
      const sig = await api.signal()
      setPoints(prev => [...prev, { x: pendingPos.x, y: pendingPos.y, signal_dbm: sig.signal_dbm }])
      setPendingPos(null)
    } finally {
      setMeasuring(false)
    }
  }

  async function autoDetect() {
    setDetecting(true)
    setDetectError(null)
    try {
      const r = await api.locateAp({ room_w: roomW, room_h: roomH, points })
      setAp({
        x: r.outside_room ? r.clamped_x : r.x,
        y: r.outside_room ? r.clamped_y : r.y,
        source: 'auto',
        meta: r,
      })
    } catch {
      setDetectError('Detection failed — try adding more spread-out points.')
    } finally {
      setDetecting(false)
    }
  }

  async function generateHeatmap() {
    setGenerating(true)
    try {
      const data = await api.heatmap({ room_w: roomW, room_h: roomH, points, grid_resolution: 80 })
      setHeatmap(data)
      setTab('3d')
    } finally {
      setGenerating(false)
    }
  }

  function reset() {
    setPoints([]); setPendingPos(null); setAp(null)
    setHeatmap(null); setTab('collect'); setDetectError(null)
  }

  function build3DTraces() {
    if (!heatmap) return []
    const traces = [
      {
        type: 'surface',
        x: heatmap.x, y: heatmap.y, z: heatmap.z,
        colorscale: WIFI_COLORSCALE,
        cmin: heatmap.vmin, cmax: heatmap.vmax,
        colorbar: { title: 'dBm', tickfont: { color: '#e6edf6' }, titlefont: { color: '#e6edf6' }, thickness: 14 },
        opacity: 0.85,
        contours: { z: { show: true, usecolormap: true, highlightcolor: '#fff', project: { z: true } } },
        hovertemplate: 'X: %{x:.1f}m<br>Y: %{y:.1f}m<br>Signal: %{z:.0f} dBm<extra></extra>',
      },
      {
        type: 'scatter3d',
        x: heatmap.points.map(p => p.x),
        y: heatmap.points.map(p => p.y),
        z: heatmap.points.map(p => p.signal_dbm),
        mode: 'markers+text',
        marker: {
          size: 5.5,
          color: heatmap.points.map(p => qualityColor(dbmToQuality(p.signal_dbm))),
          line: { color: '#fff', width: 1 },
        },
        text: heatmap.points.map(p => `${p.signal_dbm}`),
        textposition: 'top center',
        textfont: { color: '#fff', size: 10 },
        hovertemplate: 'X: %{x:.1f}m, Y: %{y:.1f}m<br>Signal: %{z:.0f} dBm<extra></extra>',
        showlegend: false,
      },
    ]
    if (!ap) return traces

    const apColor = AP_COLORS[ap.source]
    const apZ = heatmap.vmax + 10

    traces.push({
      type: 'scatter3d',
      x: [ap.x], y: [ap.y], z: [apZ],
      mode: 'markers+text',
      marker: { size: 12, color: apColor, symbol: 'diamond', line: { color: '#fff', width: 2 } },
      text: [ap.source === 'auto' ? 'Router (estimated)' : 'Router'],
      textposition: 'top center',
      textfont: { color: apColor, size: 12 },
      hovertemplate: `Router at (${ap.x}m, ${ap.y}m)<extra></extra>`,
      showlegend: false,
    })

    const rayX = [], rayY = [], rayZ = []
    heatmap.points.forEach(p => {
      rayX.push(ap.x, p.x, null)
      rayY.push(ap.y, p.y, null)
      rayZ.push(apZ, p.signal_dbm, null)
    })
    traces.push({
      type: 'scatter3d',
      x: rayX, y: rayY, z: rayZ,
      mode: 'lines',
      line: { color: '#22d3ee', width: 2 },
      opacity: 0.3,
      showlegend: false, hoverinfo: 'skip',
    })

    // Traveling pulse markers, three wavefronts per ray
    const px = [], py = [], pz = [], sizes = []
    heatmap.points.forEach(p => {
      [0, 1 / 3, 2 / 3].forEach(off => {
        const t = (pulsePhase + off) % 1
        px.push(ap.x + t * (p.x - ap.x))
        py.push(ap.y + t * (p.y - ap.y))
        pz.push(apZ + t * (p.signal_dbm - apZ))
        sizes.push(4.5 + (1 - t) * 4)
      })
    })
    traces.push({
      type: 'scatter3d',
      x: px, y: py, z: pz,
      mode: 'markers',
      marker: { size: sizes, color: '#22d3ee', opacity: 0.75 },
      showlegend: false, hoverinfo: 'skip',
    })
    return traces
  }

  const plotly2D = heatmap ? [
    {
      type: 'heatmap',
      x: heatmap.x, y: heatmap.y, z: heatmap.z,
      colorscale: WIFI_COLORSCALE,
      zmin: heatmap.vmin, zmax: heatmap.vmax,
      colorbar: { title: 'dBm', tickfont: { color: '#e6edf6' }, titlefont: { color: '#e6edf6' }, thickness: 14 },
      hovertemplate: 'X: %{x:.1f}m<br>Y: %{y:.1f}m<br>Signal: %{z:.0f} dBm<extra></extra>',
    },
    {
      type: 'scatter',
      x: heatmap.points.map(p => p.x),
      y: heatmap.points.map(p => p.y),
      mode: 'markers+text',
      marker: { size: 10, color: heatmap.points.map(p => qualityColor(dbmToQuality(p.signal_dbm))), line: { color: '#fff', width: 1.5 } },
      text: heatmap.points.map(p => `${p.signal_dbm}`),
      textposition: 'top center',
      textfont: { color: '#fff', size: 10 },
      hovertemplate: 'X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>',
      showlegend: false,
    },
    ...(ap ? [{
      type: 'scatter',
      x: [ap.x], y: [ap.y],
      mode: 'markers+text',
      marker: { size: 15, color: AP_COLORS[ap.source], symbol: 'diamond', line: { color: '#fff', width: 2 } },
      text: ['Router'],
      textposition: 'top center',
      textfont: { color: AP_COLORS[ap.source], size: 11 },
      showlegend: false,
      hovertemplate: 'Router<extra></extra>',
    }] : []),
  ] : []

  const darkLayout = {
    paper_bgcolor: '#10141f',
    plot_bgcolor: '#0b0f1c',
    font: { color: '#e6edf6', family: 'Inter, system-ui' },
    margin: { t: 40, r: 40, b: 40, l: 40 },
  }

  return (
    <div>
      <div className="page-header">
        <h2>Coverage Visualizer</h2>
        <p>Map signal strength across your room and watch the signal propagate from your router in 3D</p>
      </div>

      <div className="tabs">
        <div className={`tab ${tab === 'collect' ? 'active' : ''}`} onClick={() => setTab('collect')}>
          <Icon name="crosshair" size={13} /> Collect{points.length > 0 ? ` (${points.length})` : ''}
        </div>
        <div
          className={`tab ${tab === '2d' ? 'active' : ''} ${!heatmap ? 'disabled' : ''}`}
          onClick={() => heatmap && setTab('2d')}
        >
          <Icon name="grid" size={13} /> 2D Heatmap
        </div>
        <div
          className={`tab ${tab === '3d' ? 'active' : ''} ${!heatmap ? 'disabled' : ''}`}
          onClick={() => heatmap && setTab('3d')}
        >
          <Icon name="cube" size={13} /> 3D Surface
        </div>
      </div>

      {tab === 'collect' && (
        <div style={{ display: 'grid', gridTemplateColumns: '330px 1fr', gap: 16, alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="card">
              <div className="card-title"><Icon name="map" size={13} /> Setup</div>
              <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <div className="input-group" style={{ flex: 1 }}>
                  <label>Width (m)</label>
                  <input className="input" type="number" min="1" max="50" step="0.5"
                    value={roomW} onChange={e => setRoomW(+e.target.value || 1)} />
                </div>
                <div className="input-group" style={{ flex: 1 }}>
                  <label>Depth (m)</label>
                  <input className="input" type="number" min="1" max="50" step="0.5"
                    value={roomH} onChange={e => setRoomH(+e.target.value || 1)} />
                </div>
              </div>
              <Stepper points={points} ap={ap} heatmap={heatmap} />
            </div>

            <div className="card">
              <div className="card-title"><Icon name="router" size={13} /> Router Position</div>
              {ap ? (
                <div>
                  <div style={{ fontSize: 13, marginBottom: 6 }}>
                    <span style={{ color: AP_COLORS[ap.source], fontWeight: 600 }}>
                      ({ap.x.toFixed(1)}m, {ap.y.toFixed(1)}m)
                    </span>
                    <span style={{ color: 'var(--muted)', marginLeft: 8, fontSize: 12 }}>
                      {ap.source === 'auto' ? 'auto-detected' : 'placed manually'}
                    </span>
                  </div>
                  {ap.meta && (
                    <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 10 }}>
                      Triangulated from {ap.meta.points_used} readings · fit error ±{ap.meta.rmse_db} dB ·{' '}
                      <span style={{
                        color: ap.meta.confidence === 'high' ? 'var(--green)'
                          : ap.meta.confidence === 'medium' ? 'var(--yellow)' : 'var(--red)',
                        fontWeight: 600,
                      }}>{ap.meta.confidence} confidence</span>
                      {ap.meta.outside_room && <div>Estimate falls outside the room — shown at the nearest edge.</div>}
                    </div>
                  )}
                  <button className="btn btn-ghost btn-sm" onClick={() => { setAp(null); setSettingAp(false) }}>
                    <Icon name="x" size={12} /> Remove
                  </button>
                </div>
              ) : (
                <div>
                  <div style={{ fontSize: 12.5, color: 'var(--muted)', marginBottom: 12, lineHeight: 1.55 }}>
                    Place it yourself, or record 4+ points and let the path-loss model triangulate it from your readings.
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button
                      className={`btn btn-amber btn-sm ${settingAp ? 'active' : ''}`}
                      onClick={() => setSettingAp(s => !s)}
                    >
                      <Icon name="crosshair" size={13} /> {settingAp ? 'Click the map…' : 'Place Manually'}
                    </button>
                    <button
                      className="btn btn-violet btn-sm"
                      onClick={autoDetect}
                      disabled={points.length < 4 || detecting}
                      title={points.length < 4 ? `Need ${4 - points.length} more point(s)` : 'Triangulate from signal readings'}
                    >
                      {detecting ? <span className="spin" /> : <Icon name="target" size={13} />}
                      Auto-Detect{points.length < 4 ? ` (${points.length}/4)` : ''}
                    </button>
                  </div>
                  {detectError && <div style={{ fontSize: 12, color: 'var(--red)', marginTop: 10 }}>{detectError}</div>}
                </div>
              )}
            </div>

            {pendingPos && (
              <div className="card" style={{ borderColor: 'rgba(34,211,238,0.45)' }}>
                <div style={{ fontSize: 13, marginBottom: 10 }}>
                  <span style={{ color: 'var(--muted)' }}>Position </span>
                  <strong style={{ color: 'var(--accent)' }}>({pendingPos.x.toFixed(1)}m, {pendingPos.y.toFixed(1)}m)</strong>
                  <span style={{ color: 'var(--muted)' }}> — walk there, then record.</span>
                </div>
                <button className="btn btn-primary" onClick={recordPoint} disabled={measuring} style={{ width: '100%', justifyContent: 'center' }}>
                  {measuring ? <><span className="spin" /> Measuring…</> : <><Icon name="record" size={14} /> Record Signal Here</>}
                </button>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setPoints(p => p.slice(0, -1))} disabled={points.length === 0}>
                <Icon name="undo" size={13} /> Undo
              </button>
              <button className="btn btn-ghost btn-sm" onClick={reset}>
                <Icon name="x" size={13} /> Reset
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={generateHeatmap}
                disabled={points.length < 3 || generating}
              >
                {generating ? <><span className="spin" /> Generating…</> : <><Icon name="cube" size={13} /> Generate Map</>}
              </button>
            </div>

            {points.length > 0 && (
              <div className="card" style={{ padding: 14 }}>
                <div className="card-title" style={{ marginBottom: 8 }}>Readings ({points.length})</div>
                <div className="point-list">
                  {points.map((p, i) => (
                    <div key={i} className="point-row">
                      <span className="point-coords">({p.x.toFixed(1)}, {p.y.toFixed(1)})</span>
                      <span style={{ color: qualityColor(dbmToQuality(p.signal_dbm)), fontWeight: 600, fontSize: 12 }}>
                        {p.signal_dbm} dBm
                      </span>
                      <button className="point-del" onClick={() => setPoints(prev => prev.filter((_, j) => j !== i))}>
                        <Icon name="trash" size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="card" style={{ padding: 14 }}>
            <div className="card-title" style={{ marginBottom: 10 }}>
              Floor Plan
              <span style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 400, color: settingAp ? 'var(--amber)' : 'var(--muted)' }}>
                — {settingAp ? 'click to place the router' : 'click to mark your position'}
              </span>
            </div>
            <FloorPlan
              roomW={roomW} roomH={roomH}
              points={points} pendingPos={pendingPos}
              ap={ap} settingAp={settingAp}
              onCanvasClick={handleCanvasClick}
            />
            <div className="legend-chips">
              <span className="legend-chip"><span className="legend-swatch" style={{ background: '#34d399' }} /> Strong reading</span>
              <span className="legend-chip"><span className="legend-swatch" style={{ background: '#f87171' }} /> Weak reading</span>
              <span className="legend-chip"><span className="legend-swatch" style={{ background: AP_COLORS.manual }} /> Router (manual)</span>
              <span className="legend-chip"><span className="legend-swatch" style={{ background: AP_COLORS.auto }} /> Router (estimated)</span>
            </div>
          </div>
        </div>
      )}

      {tab === '2d' && heatmap && (
        <div className="card" style={{ padding: 14 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>2D Coverage Heatmap</div>
          <Plot
            data={plotly2D}
            layout={{
              ...darkLayout,
              xaxis: { title: 'Width (m)', color: '#e6edf6', gridcolor: '#232b3f', zerolinecolor: '#232b3f' },
              yaxis: { title: 'Depth (m)', color: '#e6edf6', gridcolor: '#232b3f', zerolinecolor: '#232b3f', scaleanchor: 'x' },
            }}
            style={{ width: '100%', height: 520 }}
            config={{ responsive: true, displayModeBar: true, modeBarButtonsToRemove: ['toImage'] }}
            useResizeHandler
          />
        </div>
      )}

      {tab === '3d' && heatmap && (
        <div className="card" style={{ padding: 14 }}>
          <div className="card-title" style={{ marginBottom: 10 }}>
            3D Signal Landscape
            <span style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 400, color: 'var(--muted)' }}>
              — drag to rotate · scroll to zoom{ap ? ' · pulses show signal propagation' : ''}
            </span>
          </div>
          {!ap && (
            <div className="alert alert-warning" style={{ fontSize: 12.5 }}>
              <Icon name="router" size={15} />
              No router position set — go to Collect and place it (or auto-detect) to see animated signal rays.
            </div>
          )}
          <Plot
            data={build3DTraces()}
            layout={{
              ...darkLayout,
              scene: {
                xaxis: { title: 'Width (m)', color: '#e6edf6', gridcolor: '#232b3f', backgroundcolor: '#0b0f1c', showbackground: true },
                yaxis: { title: 'Depth (m)', color: '#e6edf6', gridcolor: '#232b3f', backgroundcolor: '#0b0f1c', showbackground: true },
                zaxis: { title: 'Signal (dBm)', color: '#e6edf6', gridcolor: '#232b3f', backgroundcolor: '#090c14', showbackground: true },
                camera: { eye: { x: 1.4, y: -1.4, z: 0.9 } },
                bgcolor: '#090c14',
              },
            }}
            style={{ width: '100%', height: 600 }}
            config={{ responsive: true, displayModeBar: true }}
            useResizeHandler
            revision={ap ? Math.floor(pulsePhase * 100) : 0}
          />
        </div>
      )}
    </div>
  )
}

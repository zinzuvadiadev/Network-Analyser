const BASE = '/api'

async function get(path) {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

async function post(path, body) {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

export const api = {
  interfaces: () => get('/interfaces'),
  scan: () => get('/scan'),
  connection: () => get('/connection'),
  signal: () => get('/signal'),
  channels: () => get('/channels'),
  adapter: () => get('/adapter'),
  diagnostics: () => get('/diagnostics'),
  speedtest: () => post('/speedtest'),
  heatmap: (body) => post('/coverage/heatmap', body),
  locateAp: (body) => post('/coverage/locate_ap', body),
  fixPower: () => post('/power/fix'),
}

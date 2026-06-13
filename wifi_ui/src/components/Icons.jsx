// Minimal stroke icon set (24x24 viewBox), no emoji anywhere in the UI.

const PATHS = {
  // Navigation
  dashboard: ['M5 13a7 7 0 1 1 14 0', 'M12 13l3.2-3.2', 'M12 13h.01', 'M4 19h16'],
  wifi: ['M5 12.55a11 11 0 0 1 14.08 0', 'M8.53 15.61a6 6 0 0 1 6.95 0', 'M12 19.5h.01'],
  radar: ['M12 3a9 9 0 1 0 9 9', 'M12 7a5 5 0 1 0 5 5', 'M12 12l8.5-8.5', 'M12 12h.01'],
  bars: ['M6 20v-8', 'M12 20V5', 'M18 20v-5'],
  map: ['M9 4 4 6v14l5-2 6 2 5-2V4l-5 2-6-2z', 'M9 4v14', 'M15 6v14'],
  activity: ['M3 12h4l3 7 4-14 3 7h4'],
  speed: ['M13 3 4 14h6l-1 7 9-11h-6l1-7z'],
  // Actions
  refresh: ['M21 12a9 9 0 1 1-2.64-6.36', 'M21 3v6h-6'],
  play: ['M7 4.5v15l13-7.5-13-7.5z'],
  zap: ['M13 3 4 14h6l-1 7 9-11h-6l1-7z'],
  crosshair: ['M12 3v4', 'M12 17v4', 'M3 12h4', 'M17 12h4', 'M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0'],
  target: ['M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0', 'M12 12m-5 0a5 5 0 1 0 10 0a5 5 0 1 0-10 0', 'M12 12h.01'],
  router: ['M4 14h16a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1z', 'M7 17h.01', 'M11 17h.01', 'M17 14v-2', 'M13.5 7.5a5 5 0 0 1 7 0', 'M15.6 9.9a2 2 0 0 1 2.8 0'],
  undo: ['M3 7v6h6', 'M3 13a9 9 0 1 0 2.6-7.4L3 7'],
  x: ['M6 6l12 12', 'M18 6 6 18'],
  record: ['M12 12m-3.5 0a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0', 'M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0'],
  layers: ['M12 3 3 8l9 5 9-5-9-5z', 'M3 13l9 5 9-5', 'M3 18l9 5 9-5'],
  cube: ['M12 3 4 7.5v9L12 21l8-4.5v-9L12 3z', 'M4 7.5l8 4.5 8-4.5', 'M12 12v9'],
  grid: ['M4 4h16v16H4z', 'M4 12h16', 'M12 4v16'],
  check: ['M5 13l4 4 10-10'],
  alert: ['M12 3 2 20h20L12 3z', 'M12 10v4', 'M12 17.5h.01'],
  info: ['M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0', 'M12 11v5', 'M12 8h.01'],
  scan: ['M4 8V5a1 1 0 0 1 1-1h3', 'M16 4h3a1 1 0 0 1 1 1v3', 'M20 16v3a1 1 0 0 1-1 1h-3', 'M8 20H5a1 1 0 0 1-1-1v-3', 'M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0'],
  trash: ['M4 7h16', 'M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2', 'M6 7l1 13h10l1-13', 'M10 11v6', 'M14 11v6'],
}

export default function Icon({ name, size = 16, strokeWidth = 1.8, style, fill = false }) {
  const paths = PATHS[name]
  if (!paths) return null
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={fill ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0, ...style }}
      aria-hidden="true"
    >
      {paths.map((d, i) => <path key={i} d={d} />)}
    </svg>
  )
}

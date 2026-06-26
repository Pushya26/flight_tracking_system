const css = {
  panel: {
    background: 'rgba(5,8,20,0.92)', padding: 16, borderRadius: 10,
    backdropFilter: 'blur(12px)', width: 250, color: 'white',
    fontFamily: '"Courier New", monospace', fontSize: 12,
    border: '1px solid rgba(0,212,255,0.2)',
  },
  row: {
    display: 'flex', justifyContent: 'space-between',
    padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.05)',
  },
  key: { color: '#8899bb' },
  val: { color: '#00d4ff' },
  btn: {
    padding: '5px 12px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
    border: '1px solid rgba(0,212,255,0.4)', background: 'transparent', color: '#00d4ff',
  },
}

export default function FlightInfoPanel({ flight, isTracking, onToggleTrack, onClose, style }) {
  if (!flight) return null

  const alt  = flight.altitude    ?? flight.altitude_m  ?? 0
  const vel  = flight.velocity    ?? flight.velocity_ms ?? 0
  const hdg  = flight.true_track  ?? flight.heading     ?? 0
  const prog = flight.progress    ?? null

  const ft  = m  => `${Math.round(m  / 0.3048).toLocaleString()} ft`
  const kts = ms => `${Math.round(ms * 1.94384)} kts`

  const rows = [
    ['ICAO24',   flight.icao24],
    ['Route',    `${flight.origin_icao ?? '???'} → ${flight.dest_icao ?? '???'}`],
    ['Altitude', ft(alt)],
    ['Speed',    kts(vel)],
    ['Heading',  `${Math.round(hdg)}°`],
    ['Position', `${flight.latitude?.toFixed(3)}, ${flight.longitude?.toFixed(3)}`],
    ...(prog != null ? [['Progress', `${prog}%`]] : []),
  ]

  return (
    <div style={{ ...css.panel, ...style }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10, alignItems: 'center' }}>
        <strong style={{ fontSize: 14, color: '#00d4ff' }}>✈ {flight.callsign}</strong>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#8899bb', cursor: 'pointer', fontSize: 16 }}>✕</button>
      </div>

      {rows.map(([k, v]) => (
        <div key={k} style={css.row}>
          <span style={css.key}>{k}</span>
          <span style={css.val}>{v}</span>
        </div>
      ))}

      {prog != null && (
        <div style={{ marginTop: 10, marginBottom: 10 }}>
          <div style={{ height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2 }}>
            <div style={{
              width: `${prog}%`, height: '100%', borderRadius: 2,
              background: 'linear-gradient(90deg, #0066ff, #00d4ff)',
              transition: 'width 0.5s ease',
            }} />
          </div>
        </div>
      )}

      <button
        onClick={onToggleTrack}
        style={{ ...css.btn, width: '100%', marginTop: prog == null ? 10 : 0, background: isTracking ? 'rgba(0,212,255,0.15)' : 'transparent' }}
      >
        {isTracking ? '📡 Tracking — Click to Release' : '🎯 Lock Camera & Show Trail'}
      </button>
    </div>
  )
}

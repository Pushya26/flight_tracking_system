import { useState, useMemo } from 'react'

const css = {
  panel: {
    background: 'rgba(5,8,20,0.88)', padding: 12, borderRadius: 10,
    backdropFilter: 'blur(12px)', width: 290, color: 'white',
    fontFamily: '"Courier New", monospace', border: '1px solid rgba(0,212,255,0.15)',
  },
  input: {
    width: '100%', padding: '7px 10px', marginTop: 8,
    background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(0,212,255,0.25)',
    borderRadius: 6, color: 'white', outline: 'none', fontSize: 12,
  },
  item: {
    padding: '6px 8px', cursor: 'pointer', borderRadius: 5, fontSize: 12,
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  badge:  { fontSize: 10, padding: '2px 7px', borderRadius: 12, background: 'rgba(0,212,255,0.15)', color: '#00d4ff' },
  label:  { color: '#8899bb', fontSize: 10, marginTop: 6 },
}

export default function SearchPanel({ flights, onSelect, style }) {
  const [query,    setQuery]    = useState('')
  const [showFilt, setShowFilt] = useState(false)
  const [minAlt,   setMinAlt]   = useState(0)
  const [maxAlt,   setMaxAlt]   = useState(15000)

  const toFt = m => `${(Math.round(m / 30.48) * 100).toLocaleString()}ft`

  const altOf = f => f.altitude ?? f.altitude_m ?? 0

  const filtered = useMemo(() => {
    const q = query.toLowerCase()
    return flights
      .filter(f => {
        const alt    = altOf(f)
        const textOk = !q || [f.callsign, f.icao24, f.origin_icao, f.dest_icao].some(v => v?.toLowerCase().includes(q))
        return textOk && alt >= minAlt && alt <= maxAlt
      })
      .slice(0, 60)
  }, [flights, query, minAlt, maxAlt])

  return (
    <div style={{ ...css.panel, ...style }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 18 }}>✈</span>
        <strong style={{ flex: 1, fontSize: 13 }}>Flight Tracker</strong>
        <span style={css.badge}>{flights.length} live</span>
        <button
          onClick={() => setShowFilt(v => !v)}
          style={{ background: 'none', border: 'none', color: '#8899bb', cursor: 'pointer', fontSize: 16 }}
        >⚙</button>
      </div>

      <input
        style={css.input}
        placeholder="Callsign, ICAO, airport…"
        value={query}
        onChange={e => setQuery(e.target.value)}
      />

      {showFilt && (
        <div style={{ marginTop: 8, fontSize: 11 }}>
          <div style={{ color: '#8899bb', marginBottom: 2 }}>Altitude: {toFt(minAlt)} – {toFt(maxAlt)}</div>
          <div style={css.label}>Min</div>
          <input type="range" min={0} max={15000} value={minAlt} style={{ width: '100%' }} onChange={e => setMinAlt(+e.target.value)} />
          <div style={css.label}>Max</div>
          <input type="range" min={0} max={15000} value={maxAlt} style={{ width: '100%' }} onChange={e => setMaxAlt(+e.target.value)} />
        </div>
      )}

      <div style={{ maxHeight: 320, overflowY: 'auto', marginTop: 8 }}>
        {filtered.length === 0 && (
          <div style={{ color: '#445566', fontSize: 11, textAlign: 'center', padding: 12 }}>No flights match</div>
        )}
        {filtered.map(f => (
          <div
            key={f.icao24}
            style={css.item}
            onClick={() => onSelect(f.icao24)}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,212,255,0.08)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div>
              <span style={{ color: '#00d4ff' }}>{f.callsign || f.icao24}</span>
              {f.origin_icao && (
                <span style={{ color: '#556677', marginLeft: 6 }}>{f.origin_icao}→{f.dest_icao}</span>
              )}
            </div>
            <span style={css.badge}>{toFt(altOf(f))}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

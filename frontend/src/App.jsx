import { useState, useCallback, useRef } from 'react'
import * as Cesium         from 'cesium'
import CesiumGlobe         from './globe/CesiumGlobe'
import { FlightLayer }  from './globe/FlightLayer'
import { useFlightWebSocket } from './hooks/useFlightWebSocket'
import SearchPanel      from './components/SearchPanel'
import FlightInfoPanel  from './components/FlightInfoPanel'

export default function App() {
  const layerRef  = useRef(null)
  const viewerRef = useRef(null)

  const [flights,    setFlights]    = useState([])
  const [selected,   setSelected]   = useState(null)
  const [isTracking, setIsTracking] = useState(false)

  const onViewerReady = useCallback(viewer => {
    layerRef.current = new FlightLayer(viewer, icao24 => {
      setSelected(icao24)
      layerRef.current?.flyTo(icao24)
    })
    viewerRef.current = viewer
  }, [])

  const onWsUpdate = useCallback(data => {
    // Broadcaster sends { states: [...] }; each item is an AircraftState dataclass dict
    const list = data.states ?? data.flights ?? (Array.isArray(data) ? data : [])
    setFlights(list)
    layerRef.current?.update(list)
  }, [])

  useFlightWebSocket(onWsUpdate)

  const selectFlight = icao24 => {
    setSelected(icao24)
    layerRef.current?.select(icao24)
    layerRef.current?.flyTo(icao24)
  }

  const toggleTrack = () => {
    if (!selected) return
    if (isTracking) {
      layerRef.current?.untrack()
      setIsTracking(false)
    } else {
      layerRef.current?.track(selected)
      setIsTracking(true)
    }
  }

  const closePanel = () => {
    setSelected(null)
    layerRef.current?.untrack()
    setIsTracking(false)
  }

  const selectedFlight = flights.find(f => f.icao24 === selected)

  return (
    <div style={{ width: '100vw', height: '100vh', position: 'relative', background: '#000' }}>
      <CesiumGlobe onViewerReady={onViewerReady} />

      <SearchPanel
        flights={flights}
        onSelect={selectFlight}
        style={{ position: 'absolute', top: 16, left: 16, zIndex: 10 }}
      />

      <div style={{
        position: 'absolute', top: 16, right: 16, zIndex: 10,
        background: 'rgba(0,0,0,0.7)', color: '#00d4ff',
        padding: '6px 14px', borderRadius: 20, fontFamily: 'monospace', fontSize: 13,
        border: '1px solid rgba(0,212,255,0.3)',
      }}>
        ✈ {flights.length} live
      </div>

      {/* Recentre button — bottom-left */}
      <button
        onClick={() => {
          viewerRef.current?.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(0, 20, 18_000_000),
            duration: 1.5,
          })
        }}
        title="Recentre globe"
        style={{
          position: 'absolute', bottom: 24, left: 16, zIndex: 10,
          background: 'rgba(5,8,20,0.88)', border: '1px solid rgba(0,212,255,0.3)',
          color: '#00d4ff', borderRadius: 8, width: 40, height: 40,
          fontSize: 18, cursor: 'pointer', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >⊕</button>

      {selected && (
        <FlightInfoPanel
          flight={selectedFlight}
          isTracking={isTracking}
          onToggleTrack={toggleTrack}
          onClose={closePanel}
          style={{ position: 'absolute', bottom: 24, right: 16, zIndex: 10 }}
        />
      )}
    </div>
  )
}

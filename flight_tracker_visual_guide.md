# Flight Tracker → Visual Globe Simulator
## Full Implementation Guide

---

## Architecture After This Guide

```
SimulatorSource (Python)          ← replaces OpenSkySource; no API key needed
       │
       │  queue.Queue (existing)
       ▼
StateUpdaterWorker (existing)
       └── AircraftStateStore

FastAPI /ws WebSocket  ─────────────────────────────────────────┐
                                                                │
                                         React + Vite (frontend)│
                                    ┌────────────────────────── ┘
                                    │
                          CesiumJS Viewer
                          ├── ArcGIS satellite imagery  (free, no key)
                          ├── OSM road/label overlay    (free, no key)
                          ├── Cesium World Terrain      (free Ion token)
                          ├── OSM 3-D Buildings         (free Ion token)
                          └── FlightLayer (entity manager)
                               └── SampledPositionProperty ← smooth interpolation
```

**Tokens you need (both free):**

| Service | Where | Notes |
|---------|-------|-------|
| Cesium Ion | [cesium.com/ion](https://cesium.com/ion) → Sign up → Access Tokens | Free: 50K tile req/month |
| Nothing else | ArcGIS imagery + OSM overlays are zero-credential | — |

---

## Phase 1 — Backend Flight Simulator

### File: `src/ingestion/airports.py`

```python
# 50 major airports — extend as needed
# Format: (ICAO_code, display_name, latitude, longitude)
AIRPORTS = [
    ("KJFK", "New York JFK",       40.6413,  -73.7781),
    ("KLAX", "Los Angeles",        33.9425, -118.4081),
    ("KORD", "Chicago O'Hare",     41.9742,  -87.9073),
    ("KDEN", "Denver",             39.8561, -104.6737),
    ("KSFO", "San Francisco",      37.6213, -122.3790),
    ("KATL", "Atlanta",            33.6407,  -84.4277),
    ("KMIA", "Miami",              25.7959,  -80.2870),
    ("KSEA", "Seattle",            47.4502, -122.3088),
    ("CYYZ", "Toronto",            43.6777,  -79.6248),
    ("CYVR", "Vancouver",          49.1967, -123.1815),
    ("EGLL", "London Heathrow",    51.4700,   -0.4543),
    ("EGKK", "London Gatwick",     51.1481,   -0.1903),
    ("LFPG", "Paris CDG",          49.0097,    2.5479),
    ("EDDF", "Frankfurt",          50.0379,    8.5622),
    ("EHAM", "Amsterdam",          52.3086,    4.7639),
    ("LEMD", "Madrid Barajas",     40.4719,   -3.5626),
    ("LIRF", "Rome Fiumicino",     41.8003,   12.2389),
    ("ESSA", "Stockholm Arlanda",  59.6519,   17.9186),
    ("EKCH", "Copenhagen",         55.6180,   12.6561),
    ("EFHK", "Helsinki",           60.3183,   24.9630),
    ("UUEE", "Moscow Sheremetyevo",55.9736,   37.4125),
    ("LTBA", "Istanbul",           40.9769,   28.8146),
    ("LLBG", "Tel Aviv",           32.0114,   34.8867),
    ("OMDB", "Dubai",              25.2528,   55.3644),
    ("OTHH", "Doha",               25.2731,   51.6082),
    ("OERK", "Riyadh",             24.9576,   46.6988),
    ("VABB", "Mumbai",             19.0896,   72.8656),
    ("VIDP", "Delhi",              28.5665,   77.1031),
    ("VHHH", "Hong Kong",          22.3080,  113.9185),
    ("WSSS", "Singapore Changi",    1.3644,  103.9915),
    ("VTBS", "Bangkok Suvarnabhumi",13.6811,  100.7472),
    ("RJTT", "Tokyo Haneda",       35.5494,  139.7798),
    ("RJAA", "Tokyo Narita",       35.7647,  140.3864),
    ("RKSI", "Seoul Incheon",      37.4602,  126.4407),
    ("ZBAA", "Beijing Capital",    40.0799,  116.6031),
    ("ZGSZ", "Shenzhen",           22.6393,  113.8107),
    ("YSSY", "Sydney Kingsford",  -33.9461,  151.1772),
    ("YMML", "Melbourne",         -37.6690,  144.8410),
    ("NZAA", "Auckland",          -37.0082,  174.7850),
    ("FAOR", "Johannesburg OR Tambo",-26.1392,28.2460),
    ("DNMM", "Lagos Murtala",       6.5774,    3.3215),
    ("HAAB", "Addis Ababa Bole",    8.9779,   38.7993),
    ("HECA", "Cairo International",30.1219,   31.4056),
    ("SBGR", "São Paulo Guarulhos",-23.4356,  -46.4731),
    ("SCEL", "Santiago",          -33.3929,  -70.7854),
    ("MMMX", "Mexico City",        19.4363,  -99.0721),
    ("SEQM", "Quito",              -0.1292,  -78.3575),
    ("SPJC", "Lima",               -12.0219, -77.1143),
    ("SAEZ", "Buenos Aires Ezeiza",-34.8222,  -58.5358),
    ("SKBO", "Bogotá El Dorado",    4.7016,  -74.1469),
]
```

### File: `src/ingestion/simulator_source.py`

```python
import math
import time
import random
import threading
import queue
from dataclasses import dataclass
from typing import Tuple, List

from .airports import AIRPORTS

# ─── Math helpers ────────────────────────────────────────────────────────────

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in metres."""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def _gc_point(lat1, lon1, lat2, lon2, f: float) -> Tuple[float, float]:
    """
    Position at fraction f (0→1) along the great-circle arc.
    Returns (lat°, lon°).
    """
    φ1, λ1, φ2, λ2 = map(math.radians, [lat1, lon1, lat2, lon2])
    d = 2*math.asin(math.sqrt(
        math.sin((φ2-φ1)/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin((λ2-λ1)/2)**2
    ))
    if d < 1e-9:
        return lat1, lon1
    A = math.sin((1-f)*d) / math.sin(d)
    B = math.sin(f*d)     / math.sin(d)
    x = A*math.cos(φ1)*math.cos(λ1) + B*math.cos(φ2)*math.cos(λ2)
    y = A*math.cos(φ1)*math.sin(λ1) + B*math.cos(φ2)*math.sin(λ2)
    z = A*math.sin(φ1)               + B*math.sin(φ2)
    lat = math.degrees(math.atan2(z, math.sqrt(x**2+y**2)))
    lon = math.degrees(math.atan2(y, x))
    return lat, lon

def _bearing(lat1, lon1, lat2, lon2) -> float:
    """Forward bearing at origin, degrees clockwise from North."""
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    x = math.sin(Δλ)*math.cos(φ2)
    y = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(Δλ)
    return (math.degrees(math.atan2(x, y)) + 360) % 360

def _altitude_m(f: float, cruise=10_668.0) -> float:
    """
    Altitude profile (metres).
      0–12% : climb from 0 to cruise (~35 000 ft)
     12–88% : cruise
     88–100%: descent back to 0
    """
    if f < 0.12:   return cruise * (f / 0.12)
    if f > 0.88:   return cruise * (1 - (f - 0.88) / 0.12)
    return cruise

def _speed_ms(f: float, cruise=245.0) -> float:
    """Ground speed m/s (~882 km/h at cruise). Slowed at dep/arr."""
    if f < 0.05 or f > 0.95: return cruise * 0.35
    if f < 0.12: return cruise * (0.35 + 0.65*(f-0.05)/0.07)
    if f > 0.88: return cruise * (0.35 + 0.65*(0.95-f)/0.07)
    return cruise


# ─── Simulated flight ────────────────────────────────────────────────────────

_AIRLINE_PREFIXES = [
    "UAL","DAL","BAW","AFR","DLH","UAE","SIA","QFA","AAL","THY",
    "ANA","JAL","KAL","CES","CSN","QTR","ETH","TAM","KLM","AZU",
]

@dataclass
class _SimFlight:
    icao24:       str
    callsign:     str
    origin_icao:  str
    dest_icao:    str
    olat: float; olon: float
    dlat: float; dlon: float
    dist_m:        float
    duration_s:    float   # real-time seconds for full flight at speed_factor
    started_at:    float   # time.time() when spawned
    speed_factor:  float

    def _fraction(self) -> float:
        elapsed = (time.time() - self.started_at) * self.speed_factor
        return min(1.0, elapsed / self.duration_s)

    def is_done(self) -> bool:
        return self._fraction() >= 1.0

    def state(self) -> dict:
        f = self._fraction()
        lat, lon = _gc_point(self.olat, self.olon, self.dlat, self.dlon, f)
        return {
            "icao24":       self.icao24,
            "callsign":     self.callsign,
            "latitude":     round(lat, 5),
            "longitude":    round(lon, 5),
            "altitude":     round(_altitude_m(f), 0),        # metres
            "velocity":     round(_speed_ms(f), 1),          # m/s
            "true_track":   round(_bearing(self.olat, self.olon, self.dlat, self.dlon), 1),
            "vertical_rate":0.0,
            "on_ground":    False,
            "origin_icao":  self.origin_icao,
            "dest_icao":    self.dest_icao,
            "progress":     round(f * 100, 1),
            "last_contact": int(time.time()),
        }


# ─── Source thread ────────────────────────────────────────────────────────────

class SimulatorSource:
    """
    Drop-in replacement for OpenSkySource.

    Parameters
    ----------
    out_queue     : the shared queue.Queue that StateUpdaterWorker reads from
    num_flights   : how many concurrent simulated aircraft to maintain
    speed_factor  : 60 = 1 real second equals 1 simulated minute
                    → a 10-hour flight finishes in ~10 real minutes
    poll_interval : how often (seconds) to push a snapshot to the queue
    """

    def __init__(self,
                 out_queue: queue.Queue,
                 num_flights: int = 200,
                 speed_factor: float = 60.0,
                 poll_interval: float = 2.0):
        self.out_queue     = out_queue
        self.num_flights   = num_flights
        self.speed_factor  = speed_factor
        self.poll_interval = poll_interval
        self._flights: dict[str, _SimFlight] = {}
        self._lock   = threading.Lock()
        self._stop   = threading.Event()

    # ── Internal helpers ──────────────────────────────────────────

    def _spawn(self) -> _SimFlight:
        origin, dest = random.sample(AIRPORTS, 2)
        dist = _haversine_m(origin[2], origin[3], dest[2], dest[3])
        duration_s = dist / 245.0   # sim-seconds at cruise speed
        return _SimFlight(
            icao24      = format(random.randint(0, 0xFFFFFF), '06x'),
            callsign    = random.choice(_AIRLINE_PREFIXES) + str(random.randint(1,9999)).zfill(4),
            origin_icao = origin[0],
            dest_icao   = dest[0],
            olat=origin[2], olon=origin[3],
            dlat=dest[2],   dlon=dest[3],
            dist_m      = dist,
            duration_s  = duration_s,
            # Scatter start times so flights aren't all at 0% when server boots
            started_at  = time.time() - random.uniform(0, duration_s / self.speed_factor),
            speed_factor= self.speed_factor,
        )

    def _refill(self):
        with self._lock:
            done = [k for k, v in self._flights.items() if v.is_done()]
            for k in done:
                del self._flights[k]
            while len(self._flights) < self.num_flights:
                f = self._spawn()
                self._flights[f.icao24] = f

    def _tick(self):
        self._refill()
        with self._lock:
            states = [f.state() for f in self._flights.values()]
        payload = {"states": states, "timestamp": time.time()}
        try:
            self.out_queue.put_nowait(payload)
        except queue.Full:
            pass   # backpressure — drop frame rather than block

    # ── Public ────────────────────────────────────────────────────

    def run(self):
        """Run in its own thread. Blocks until stop() is called."""
        while not self._stop.is_set():
            self._tick()
            time.sleep(self.poll_interval)

    def stop(self):
        self._stop.set()
```

### Wire it in (`src/api/main.py`)

```python
# Replace this:
source = OpenSkySource(data_queue)

# With this:
from src.ingestion.simulator_source import SimulatorSource
_simulator = SimulatorSource(data_queue, num_flights=200, speed_factor=60.0)
threading.Thread(target=_simulator.run, daemon=True).start()

# Optional control endpoints
@app.get("/simulator/status")
def sim_status():
    return {
        "active_flights": len(_simulator._flights),
        "speed_factor":   _simulator.speed_factor,
    }

@app.post("/simulator/speed")
def sim_speed(factor: float = Query(..., ge=1, le=3600)):
    _simulator.speed_factor = factor
    with _simulator._lock:
        for f in _simulator._flights.values():
            f.speed_factor = factor
    return {"speed_factor": factor}
```

> **`speed_factor` cheat-sheet**
> | Value | What it means |
> |-------|--------------|
> | 1 | Real time — flights take 8-12 hours |
> | 60 | 1 real min = 1 sim hour — flights finish in ~10 min |
> | 600 | Demo mode — flights finish in ~1 min |

---

## Phase 2 — Frontend Project Setup

```bash
# Run from the root of your repo
mkdir frontend && cd frontend
npm create vite@latest . -- --template react

# Core dependencies
npm install cesium vite-plugin-cesium

# Optional utilities
npm install axios
```

### `frontend/vite.config.js`

```js
import { defineConfig } from 'vite'
import react   from '@vitejs/plugin-react'
import cesium  from 'vite-plugin-cesium'   // copies Cesium static assets automatically

export default defineConfig({
  plugins: [react(), cesium()],
  server: {
    proxy: {
      '/flights':   'http://localhost:8000',
      '/alerts':    'http://localhost:8000',
      '/simulator': 'http://localhost:8000',
      '/ws': {
        target:    'ws://localhost:8000',
        ws:        true,
        changeOrigin: true,
      },
    },
  },
})
```

### `frontend/index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <!-- Paste your Cesium Ion token here (free at cesium.com/ion) -->
    <meta name="cesium-token" content="YOUR_CESIUM_ION_TOKEN_HERE" />
    <title>Flight Tracker</title>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body, #root { width: 100%; height: 100%; overflow: hidden; }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

---

## Phase 3 — Cesium Globe Component

### `frontend/src/globe/CesiumGlobe.jsx`

```jsx
import { useEffect, useRef } from 'react'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'

// Pull Ion token from the meta tag (never hard-code secrets in JS)
Cesium.Ion.defaultAccessToken =
  document.querySelector('meta[name="cesium-token"]')?.content ?? ''

export default function CesiumGlobe({ onViewerReady }) {
  const containerRef = useRef(null)
  const viewerRef    = useRef(null)

  useEffect(() => {
    if (viewerRef.current) return

    // ── 1. Create the viewer ──────────────────────────────────────
    const viewer = new Cesium.Viewer(containerRef.current, {
      // Satellite imagery — free, no key, excellent quality
      imageryProvider: new Cesium.ArcGisMapServerImageryProvider({
        url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
      }),
      // Real terrain (mountains, valleys) — needs Ion token, free tier
      terrainProvider: Cesium.createWorldTerrain(),

      // Hide chrome we don't need
      baseLayerPicker:      false,
      geocoder:             false,
      homeButton:           false,
      sceneModePicker:      false,
      navigationHelpButton: false,
      animation:            false,
      timeline:             false,
      fullscreenButton:     false,
      infoBox:              false,
      selectionIndicator:   false,
    })

    // ── 2. Add road + label overlay (OSM tiles, 40% opacity) ──────
    //    This gives you the Google-Maps-style street grid on top of satellite.
    viewer.imageryLayers.addImageryProvider(
      new Cesium.OpenStreetMapImageryProvider({
        url:   'https://tile.openstreetmap.org/',
        alpha: 0.4,
      })
    )

    // ── 3. Add 3-D buildings (OSM Buildings via Cesium Ion) ───────
    //    Visible when zoomed in to city level (~500 m altitude)
    Cesium.createOsmBuildingsAsync().then(tileset => {
      viewer.scene.primitives.add(tileset)
    })

    // ── 4. Atmosphere & lighting ──────────────────────────────────
    viewer.scene.globe.enableLighting     = true
    viewer.scene.atmosphere.show          = true
    viewer.scene.globe.depthTestAgainstTerrain = false

    // ── 5. Start camera roughly over the Atlantic ─────────────────
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(0, 20, 18_000_000),
    })

    viewerRef.current = viewer
    onViewerReady?.(viewer)

    return () => { viewer.destroy(); viewerRef.current = null }
  }, [])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}
    />
  )
}
```

**What each imagery layer gives you at different zoom levels:**

| Altitude | What you see |
|----------|-------------|
| > 5 000 km | Blue globe with clouds and atmosphere |
| 500 km – 5 000 km | Continents, country borders, city labels |
| 10 km – 500 km | Satellite imagery + road network overlay |
| < 500 m | Individual streets, building footprints in 3-D |

---

## Phase 4 — Real-Time Flight Layer

### `frontend/src/hooks/useFlightWebSocket.js`

```js
import { useEffect, useRef, useCallback } from 'react'

export function useFlightWebSocket(onUpdate) {
  const wsRef    = useRef(null)
  const timerRef = useRef(null)

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws    = new WebSocket(`${proto}://${location.host}/ws`)

    ws.onopen    = () => console.log('[WS] connected')
    ws.onmessage = e  => onUpdate(JSON.parse(e.data))
    ws.onerror   = ()  => ws.close()
    ws.onclose   = ()  => {
      // Reconnect after 3 s
      timerRef.current = setTimeout(connect, 3000)
    }

    wsRef.current = ws
  }, [onUpdate])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [connect])
}
```

### `frontend/src/globe/FlightLayer.js`

This is the heart of the visualization. Each aircraft gets one Cesium `Entity` with a `SampledPositionProperty` — feed it timestamped positions and Cesium handles all smooth interpolation automatically at 60 fps, even between 2-second WebSocket updates.

```js
import * as Cesium from 'cesium'

// Simple aircraft icon as inline SVG (no external asset dependency)
const PLANE_SVG = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <path d="M16 2 L21 13 L30 16 L21 19 L18 29 L16 27 L14 29 L11 19 L2 16 L11 13 Z"
        fill="#00d4ff" stroke="rgba(0,0,0,0.5)" stroke-width="1.5"/>
</svg>`)}`

export class FlightLayer {
  /**
   * @param {Cesium.Viewer} viewer
   * @param {(icao24: string) => void} onSelect  called when user clicks an aircraft
   */
  constructor(viewer, onSelect) {
    this.viewer   = viewer
    this.onSelect = onSelect
    this._entities = new Map()      // icao24 → { entity, sampled }

    // Click handler
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction(click => {
      const picked = viewer.scene.pick(click.position)
      if (Cesium.defined(picked) && picked.id) {
        onSelect?.(picked.id.id)    // entity.id === icao24
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
  }

  /**
   * Called every time the WebSocket delivers a new snapshot.
   * @param {Array} flights - array of state dicts from your API
   */
  update(flights) {
    const now    = Cesium.JulianDate.now()
    const active = new Set(flights.map(f => f.icao24))

    for (const f of flights) {
      const cartesian = Cesium.Cartesian3.fromDegrees(
        f.longitude, f.latitude, f.altitude
      )

      if (!this._entities.has(f.icao24)) {
        // ── Create entity ──────────────────────────────────────
        const sampled = new Cesium.SampledPositionProperty()
        sampled.setInterpolationOptions({
          interpolationDegree:    1,
          interpolationAlgorithm: Cesium.LinearApproximation,
        })
        sampled.forwardExtrapolationType = Cesium.ExtrapolationType.EXTRAPOLATE
        sampled.addSample(now, cartesian)

        const entity = this.viewer.entities.add({
          id:       f.icao24,          // used for click-to-select
          name:     f.callsign || f.icao24,
          position: sampled,

          billboard: {
            image:     PLANE_SVG,
            width:     26,
            height:    26,
            // Rotate icon to match heading
            rotation:  Cesium.Math.toRadians(-(f.true_track ?? 0)),
            alignedAxis: Cesium.Cartesian3.UNIT_Z,
            // Only show icon when globe altitude < 8 000 km
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8_000_000),
            // Always on top — never clipped by terrain
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            // Subtle size-with-distance scaling
            sizeInMeters: false,
          },

          label: {
            text:       f.callsign || f.icao24,
            font:       '11px "Courier New", monospace',
            fillColor:  Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            style:      Cesium.LabelStyle.FILL_AND_OUTLINE,
            pixelOffset: new Cesium.Cartesian2(0, -24),
            // Only show label when zoomed in < 2 000 km
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2_000_000),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },

          // Show flight trail when camera-tracked (trackedEntity)
          path: {
            show:      false,    // enabled per-flight when selected
            leadTime:  0,
            trailTime: 300,      // 5 minutes of history
            width:     1.5,
            material:  new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.15,
              color:     Cesium.Color.fromCssColorString('#00d4ff').withAlpha(0.6),
            }),
          },

          _sampled: sampled,     // private ref for position updates
        })

        this._entities.set(f.icao24, { entity, sampled })

      } else {
        // ── Update existing entity ─────────────────────────────
        const { entity, sampled } = this._entities.get(f.icao24)
        sampled.addSample(now, cartesian)   // Cesium interpolates automatically

        if (entity.billboard) {
          entity.billboard.rotation =
            Cesium.Math.toRadians(-(f.true_track ?? 0))
        }
        if (entity.label) {
          const ft = Math.round(f.altitude / 0.3048 / 100) * 100
          entity.label.text = `${f.callsign}\n${ft.toLocaleString()} ft`
        }
      }
    }

    // Remove aircraft that disappeared from the feed
    for (const [icao24, { entity }] of this._entities) {
      if (!active.has(icao24)) {
        this.viewer.entities.remove(entity)
        this._entities.delete(icao24)
      }
    }
  }

  /** Lock camera onto this aircraft. Shows trail. */
  track(icao24) {
    const rec = this._entities.get(icao24)
    if (!rec) return
    rec.entity.path.show = true
    this.viewer.trackedEntity = rec.entity
  }

  /** Release camera. */
  untrack() {
    this.viewer.trackedEntity = undefined
    // Hide all trails
    for (const { entity } of this._entities.values()) {
      if (entity.path) entity.path.show = false
    }
  }

  /** Fly camera to a flight without locking. */
  flyTo(icao24) {
    const rec = this._entities.get(icao24)
    if (!rec) return
    this.viewer.flyTo(rec.entity, {
      offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-30), 500_000),
    })
  }
}
```

### `frontend/src/App.jsx`

```jsx
import { useState, useCallback, useRef }  from 'react'
import CesiumGlobe                         from './globe/CesiumGlobe'
import { FlightLayer }                     from './globe/FlightLayer'
import { useFlightWebSocket }              from './hooks/useFlightWebSocket'
import SearchPanel                         from './components/SearchPanel'
import FlightInfoPanel                     from './components/FlightInfoPanel'

export default function App() {
  const layerRef = useRef(null)

  const [flights,      setFlights]      = useState([])
  const [selected,     setSelected]     = useState(null)
  const [isTracking,   setIsTracking]   = useState(false)

  // Called once Cesium viewer is ready
  const onViewerReady = useCallback(viewer => {
    layerRef.current = new FlightLayer(viewer, icao24 => {
      setSelected(icao24)
    })
  }, [])

  // Called on every WebSocket frame
  const onWsUpdate = useCallback(data => {
    // Accept either { states: [...] } or { flights: [...] }
    const list = data.states ?? data.flights ?? []
    setFlights(list)
    layerRef.current?.update(list)
  }, [])

  useFlightWebSocket(onWsUpdate)

  const selectFlight = icao24 => {
    setSelected(icao24)
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

      {/* The globe fills the entire viewport */}
      <CesiumGlobe onViewerReady={onViewerReady} />

      {/* Search panel — top-left overlay */}
      <SearchPanel
        flights={flights}
        onSelect={selectFlight}
        style={{ position: 'absolute', top: 16, left: 16, zIndex: 10 }}
      />

      {/* Live count badge — top-right */}
      <div style={{
        position: 'absolute', top: 16, right: 16, zIndex: 10,
        background: 'rgba(0,0,0,0.7)', color: '#00d4ff',
        padding: '6px 14px', borderRadius: 20, fontFamily: 'monospace', fontSize: 13,
        border: '1px solid rgba(0,212,255,0.3)',
      }}>
        ✈ {flights.length} live
      </div>

      {/* Flight info — bottom-right overlay */}
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
```

---

## Phase 5 — Search & Filter UI

### `frontend/src/components/SearchPanel.jsx`

```jsx
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
    transition: 'background 0.1s',
  },
  badge: {
    fontSize: 10, padding: '2px 7px', borderRadius: 12,
    background: 'rgba(0,212,255,0.15)', color: '#00d4ff',
  },
  label: { color: '#8899bb', fontSize: 11, marginTop: 8, marginBottom: 2 },
}

export default function SearchPanel({ flights, onSelect, style }) {
  const [query,    setQuery]    = useState('')
  const [showFilt, setShowFilt] = useState(false)
  const [minAlt,   setMinAlt]   = useState(0)       // metres
  const [maxAlt,   setMaxAlt]   = useState(15000)

  const filtered = useMemo(() => {
    const q = query.toLowerCase()
    return flights
      .filter(f => {
        const textOk = !q || [f.callsign, f.icao24, f.origin_icao, f.dest_icao]
          .some(v => v?.toLowerCase().includes(q))
        const altOk = f.altitude >= minAlt && f.altitude <= maxAlt
        return textOk && altOk
      })
      .slice(0, 60)
  }, [flights, query, minAlt, maxAlt])

  const toFt = m => `${(Math.round(m / 30.48) * 100).toLocaleString()}ft`

  return (
    <div style={{ ...css.panel, ...style }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 18 }}>✈</span>
        <strong style={{ flex: 1, fontSize: 13 }}>Flight Tracker</strong>
        <span style={css.badge}>{flights.length} live</span>
        <button
          onClick={() => setShowFilt(v => !v)}
          title="Filters"
          style={{ background: 'none', border: 'none', color: '#8899bb', cursor: 'pointer', fontSize: 16 }}
        >⚙</button>
      </div>

      {/* Search box */}
      <input
        style={css.input}
        placeholder="Callsign, ICAO, airport…"
        value={query}
        onChange={e => setQuery(e.target.value)}
      />

      {/* Altitude filter */}
      {showFilt && (
        <div style={{ marginTop: 8, fontSize: 11 }}>
          <div style={css.label}>
            Altitude: {toFt(minAlt)} – {toFt(maxAlt)}
          </div>
          <div style={{ color: '#8899bb', fontSize: 10 }}>Min altitude</div>
          <input type="range" min={0} max={15000} value={minAlt}
                 style={{ width: '100%' }}
                 onChange={e => setMinAlt(+e.target.value)} />
          <div style={{ color: '#8899bb', fontSize: 10 }}>Max altitude</div>
          <input type="range" min={0} max={15000} value={maxAlt}
                 style={{ width: '100%' }}
                 onChange={e => setMaxAlt(+e.target.value)} />
        </div>
      )}

      {/* Results */}
      <div style={{ maxHeight: 320, overflowY: 'auto', marginTop: 8 }}>
        {filtered.length === 0 && (
          <div style={{ color: '#445566', fontSize: 11, textAlign: 'center', padding: 12 }}>
            No flights match
          </div>
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
                <span style={{ color: '#556677', marginLeft: 6 }}>
                  {f.origin_icao}→{f.dest_icao}
                </span>
              )}
            </div>
            <span style={css.badge}>{toFt(f.altitude)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

### `frontend/src/components/FlightInfoPanel.jsx`

```jsx
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
  key:   { color: '#8899bb' },
  val:   { color: '#00d4ff' },
  btn:   {
    padding: '5px 12px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
    border: '1px solid rgba(0,212,255,0.4)', background: 'transparent', color: '#00d4ff',
  },
}

export default function FlightInfoPanel({ flight, isTracking, onToggleTrack, onClose, style }) {
  if (!flight) return null

  const ft  = m  => `${Math.round(m  / 0.3048).toLocaleString()} ft`
  const kts = ms => `${Math.round(ms * 1.94384)} kts`

  const rows = [
    ['ICAO24',   flight.icao24],
    ['Route',    `${flight.origin_icao ?? '???'} → ${flight.dest_icao ?? '???'}`],
    ['Altitude', ft(flight.altitude ?? 0)],
    ['Speed',    kts(flight.velocity ?? 0)],
    ['Heading',  `${Math.round(flight.true_track ?? 0)}°`],
    ['Position', `${flight.latitude?.toFixed(3)}, ${flight.longitude?.toFixed(3)}`],
    ['Progress', `${flight.progress ?? 0}%`],
  ]

  return (
    <div style={{ ...css.panel, ...style }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10, alignItems: 'center' }}>
        <strong style={{ fontSize: 14, color: '#00d4ff' }}>✈ {flight.callsign}</strong>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#8899bb', cursor: 'pointer', fontSize: 16 }}
        >✕</button>
      </div>

      {rows.map(([k, v]) => (
        <div key={k} style={css.row}>
          <span style={css.key}>{k}</span>
          <span style={css.val}>{v}</span>
        </div>
      ))}

      {/* Route progress bar */}
      <div style={{ marginTop: 10, marginBottom: 10 }}>
        <div style={{ height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2 }}>
          <div style={{
            width: `${flight.progress ?? 0}%`,
            height: '100%', borderRadius: 2,
            background: 'linear-gradient(90deg, #0066ff, #00d4ff)',
            transition: 'width 0.5s ease',
          }} />
        </div>
      </div>

      {/* Track toggle */}
      <button
        onClick={onToggleTrack}
        style={{ ...css.btn, width: '100%', background: isTracking ? 'rgba(0,212,255,0.15)' : 'transparent' }}
      >
        {isTracking ? '📡 Tracking — Click to Release' : '🎯 Lock Camera & Show Trail'}
      </button>
    </div>
  )
}
```

---

## Phase 6 — Docker: Serve the Frontend

### `frontend/Dockerfile`

```dockerfile
# ── Build stage ────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build          # outputs to /app/dist

# ── Serve stage ────────────────────────────────────────────────
FROM nginx:1.25-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### `frontend/nginx.conf`

```nginx
server {
  listen 80;
  root   /usr/share/nginx/html;
  index  index.html;

  # SPA fallback
  location / {
    try_files $uri $uri/ /index.html;
  }

  # Proxy WebSocket to FastAPI
  location /ws {
    proxy_pass         http://api:8000;
    proxy_http_version 1.1;
    proxy_set_header   Upgrade    $http_upgrade;
    proxy_set_header   Connection "upgrade";
    proxy_set_header   Host       $host;
  }

  # Proxy REST to FastAPI
  location ~ ^/(flights|alerts|simulator) {
    proxy_pass       http://api:8000;
    proxy_set_header Host $host;
  }
}
```

### Add to `docker/docker-compose.yml`

```yaml
  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - api
    environment:
      # Override if you serve from a different path
      - VITE_API_BASE=/
```

---

## Phase 7 — Cesium Ion Setup (5 minutes)

1. Go to [cesium.com/ion](https://cesium.com/ion) → **Sign Up** (free)
2. Click **Access Tokens** in the left sidebar → copy your **Default Token**
3. Paste it into `frontend/index.html`:
   ```html
   <meta name="cesium-token" content="eyJhbGciOiJI..." />
   ```
4. That's it — World Terrain and OSM Buildings are included in the free tier.

**Free tier limits (as of 2025):** 50 000 terrain tile requests/month. For a private demo this is essentially unlimited. Commercial use requires a paid plan.

---

## Controls Reference

| Action | Control |
|--------|---------|
| Rotate globe | Left-drag |
| Zoom in/out | Scroll wheel |
| Tilt / change pitch | Middle-drag, or Ctrl + left-drag |
| Pan | Right-drag |
| Select aircraft | Click icon or item in list |
| Fly to aircraft | Select from list → camera flies there |
| Lock camera + trail | Click **Lock Camera** in info panel |
| Release camera | Click the button again or ✕ |
| Filter by altitude | ⚙ icon in search panel |
| Street / building view | Scroll in until altitude < 500 m |

---

## Directory Layout After All Changes

```
flight_tracking_system/
├── src/
│   ├── api/
│   │   └── main.py           ← wire in SimulatorSource + 2 control endpoints
│   └── ingestion/
│       ├── airports.py        ← NEW
│       └── simulator_source.py← NEW
├── frontend/                  ← NEW
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── globe/
│       │   ├── CesiumGlobe.jsx
│       │   └── FlightLayer.js
│       ├── hooks/
│       │   └── useFlightWebSocket.js
│       └── components/
│           ├── SearchPanel.jsx
│           └── FlightInfoPanel.jsx
└── docker/
    └── docker-compose.yml    ← add frontend service
```

---

## Common Gotchas

**Cesium assets not loading in dev**
→ Make sure `vite-plugin-cesium` is in `vite.config.js` — it copies Cesium's web workers and WASM into the build output automatically.

**WebSocket 404 in Docker**
→ The nginx proxy block must use `http://api:8000` (service name in docker-compose), not `localhost`.

**Buildings only show at city zoom level**
→ This is by design — OSM Buildings only render below ~5 km altitude. Zoom into any major city to see them.

**Flights all start at 0% when server boots**
→ The `started_at` offset in `_spawn()` scatters them randomly. If you restart the server frequently, increase `num_flights` so the globe always looks busy.

**Heading arrows always point north**
→ `true_track` comes from your store; make sure `StateUpdaterWorker` passes it through from the simulator state dict unchanged.

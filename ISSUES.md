# Development Issues & Challenges

A detailed log of every significant issue encountered during development, why it occurred, how it was diagnosed, the fix applied, and the outcome.

---

## Issue 1 — WebSocket `/ws` Path Conflicting with Vite HMR

### What happened
After wiring up the frontend WebSocket hook to connect to `/ws`, the browser would open a connection and immediately close it. The Vite dev server printed repeated `ECONNREFUSED` errors and the backend logs showed a rapid cycle of `connection open` / `connection closed`.

### Why it occurred
Vite's Hot Module Replacement (HMR) system uses its own internal WebSocket server on the same dev-server port, and it claims the `/ws` path for its own use. When the frontend code opened a `new WebSocket(...)` to `/ws`, Vite's proxy intercepted and routed it to the HMR handler instead of forwarding it to FastAPI. The HMR handler immediately rejected the connection because the upgrade headers didn't match its expected protocol, causing the instant close.

### Fix applied
Renamed the flight tracker WebSocket endpoint from `/ws` to `/ws/flights` in four places simultaneously:
- `src/api/main.py` — the `@app.websocket` decorator
- `frontend/vite.config.js` — the proxy rule key
- `frontend/src/hooks/useFlightWebSocket.js` — the `new WebSocket(...)` URL
- `frontend/nginx.conf` — the nginx proxy `location` block

### Result
WebSocket connections became stable. The backend logs showed persistent `connection open` entries without subsequent closes, and the frontend console printed `[WS] connected` on load and reconnected cleanly after page refreshes.

---

## Issue 2 — Black Globe: Deprecated Cesium Async APIs

### What happened
After getting the Vite dev server running, opening `localhost:5173` showed a completely black canvas where the Cesium globe should have been. No JavaScript errors were thrown in the console — the viewer was created silently but nothing rendered.

### Why it occurred
Cesium 1.116 changed the `ArcGisMapServerImageryProvider` and `createWorldTerrain()` APIs from synchronous constructors to async factory methods. The code was using:
```js
imageryProvider: new Cesium.ArcGisMapServerImageryProvider({ url: '...' })
terrainProvider: Cesium.createWorldTerrain()
```
In Cesium 1.142 (the installed version) both of these return a pending `Promise` object rather than a usable provider. Passing a Promise where Cesium expects a resolved provider causes it to silently fall back to a blank canvas with no error.

### Fix applied
Rewrote `CesiumGlobe.jsx` to use an `async init()` function inside the `useEffect`, replacing both calls with their async equivalents:
```js
const imagery = await Cesium.ArcGisMapServerImageryProvider.fromUrl('...')
const terrain = await Cesium.createWorldTerrainAsync()
```
Also replaced the deprecated `OpenStreetMapImageryProvider` with `UrlTemplateImageryProvider` which uses the same OSM tile URL pattern but is the current supported API.

### Result
The globe rendered correctly with satellite imagery, world terrain, and the OSM road overlay on top.

---

## Issue 3 — Globe Black Without a Cesium Ion Token

### What happened
Even after fixing the async API issue, users without a Cesium Ion token (or with the placeholder `YOUR_CESIUM_ION_TOKEN_HERE` still in `index.html`) saw a completely black globe. The Ion-dependent features — world terrain and ArcGIS satellite imagery — silently failed.

### Why it occurred
`createWorldTerrainAsync()` and `ArcGisMapServerImageryProvider.fromUrl()` both make authenticated requests to Cesium Ion servers. Without a valid token the requests are rejected with a 401. Cesium doesn't throw a catchable error at the viewer level; it simply renders nothing for the affected layer, leaving the canvas black.

### Fix applied
Added a token detection check at the top of `init()`:
```js
const hasToken = Cesium.Ion.defaultAccessToken &&
  Cesium.Ion.defaultAccessToken !== 'YOUR_CESIUM_ION_TOKEN_HERE'
```
When no token is present, the globe falls back to:
- `UrlTemplateImageryProvider` with OSM tiles as the base layer (no auth required)
- `EllipsoidTerrainProvider` for flat terrain (no auth required)

OSM Buildings and the satellite overlay are skipped entirely. When a token is present, all premium layers are loaded as normal.

### Result
The globe renders immediately for anyone without an Ion token, showing a clean OSM map with all flight icons. Users with a token get the full satellite + terrain + 3D buildings experience. A `try/catch` around `createOsmBuildingsAsync()` was also added so a token error in the buildings loader doesn't crash the rest of the globe setup.

---

## Issue 4 — `StateUpdaterWorker` Expecting `AircraftState` Objects, Not Dicts

### What happened
After wiring in `SimulatorSource`, the backend crashed on startup with an `AttributeError` because the worker tried to call `state.icao24` on a plain Python `dict`.

### Why it occurred
The original `StateUpdaterWorker._run()` was written to consume individual `AircraftState` dataclass instances directly from the queue, using attribute access (`state.icao24`, `state.latitude`, etc.). The `SimulatorSource` pushes a completely different shape: a single envelope dict `{"states": [...], "timestamp": ...}` containing a list of plain dicts with different field names — `altitude` instead of `altitude_m`, `velocity` instead of `velocity_ms`, `true_track` instead of `heading`, and extra fields like `origin_icao`, `dest_icao`, `progress` that `AircraftState` didn't have at all.

### Fix applied
Added a static `_to_aircraft_state(d: dict)` converter method to `StateUpdaterWorker` that maps both naming conventions:
```python
altitude_m  = d.get("altitude", d.get("altitude_m", 0.0))
velocity_ms = d.get("velocity", d.get("velocity_ms", 0.0))
heading     = d.get("true_track", d.get("heading", 0.0))
```
The `_run()` loop was updated to detect whether the item off the queue is a dict envelope or a bare `AircraftState`, unpack accordingly, and convert each dict to an `AircraftState` before updating the store. `AircraftState` was also extended with three new optional fields: `origin_icao`, `dest_icao`, and `progress`.

### Result
The backend started cleanly and the store populated with aircraft data from the simulator. Route and progress information was preserved through the full ingestion pipeline all the way to the WebSocket broadcast.

---

## Issue 5 — WebSocket Payload Format Mismatch

### What happened
Flight data was reaching the store correctly (confirmed by hitting `GET /flights/`) but the globe showed zero aircraft. The frontend search panel remained empty.

### Why it occurred
The `WebSocketBroadcaster` sent the payload as a plain JSON array:
```python
json.dumps([asdict(s) for s in self._store.get_all().values()])
```
But `App.jsx` parsed the incoming message as:
```js
const list = data.states ?? data.flights ?? []
```
A plain array has no `.states` or `.flights` property — both are `undefined` — so `list` was always an empty array. The flights existed on the server but were invisible to the frontend.

### Fix applied
Wrapped the broadcast payload in an envelope object:
```python
json.dumps({"states": [asdict(s) for s in self._store.get_all().values()]})
```
This matched the `data.states` key the frontend expected, and the `Array.isArray(data)` fallback in `onWsUpdate` was kept as a safety net.

### Result
The search panel immediately populated with live aircraft on first WebSocket frame. The flight count badge updated every 2 seconds.

---

## Issue 6 — Plane Icons Not Visible on the Globe

### What happened
The search panel showed 230+ live flights, the info panel showed correct data when a flight was selected, but no aircraft icons appeared anywhere on the globe.

### Why it occurred
Two root causes compounded each other:

First, `SampledPositionProperty` requires the Cesium clock to be actively animating and needs at least two time-stamped samples to interpolate between. With a static viewer clock and only one sample added per entity on creation, Cesium had nothing to interpolate and rendered the entity at no position.

Second, when `ConstantPositionProperty` was tried as a replacement, the entity definition included a `path` block. Cesium's `path` visualiser requires a `SampledPositionProperty` (or similar time-dynamic property) — passing it a `ConstantPositionProperty` caused Cesium to silently reject the entire entity definition and render nothing.

### Fix applied
Replaced the position strategy with a `CallbackProperty`:
```js
const state = { pos }  // mutable object
position: new Cesium.CallbackProperty(() => state.pos, false)
```
The `false` argument marks it as non-constant, so Cesium evaluates the callback every render frame. On each WebSocket update `state.pos` is mutated in place — the `CallbackProperty` picks up the new value automatically with zero overhead. The `path` block was removed from entity creation entirely and only added on-demand when the user clicks "Lock Camera & Show Trail".

### Result
All 200+ aircraft icons appeared on the globe immediately after the first WebSocket frame. Icons move smoothly as `state.pos` is updated every 2 seconds.

---

## Issue 7 — `ConstantPositionProperty` Direct Assignment Not Working

### What happened
After switching from `SampledPositionProperty` to `ConstantPositionProperty`, the update path used `entity.position = cartesian` (assigning a raw `Cartesian3` directly). This worked in older Cesium but entities still didn't move on subsequent updates.

### Why it occurred
In Cesium 1.116+, `entity.position` is a typed property slot that only accepts a `PositionProperty` instance. Assigning a raw `Cartesian3` to it is silently ignored — the assignment appears to succeed but the internal property value is not updated. The entity stays frozen at whatever position it was created with.

### Fix applied
The issue was made moot by the `CallbackProperty` approach (Issue 6 fix) — since `state.pos` is a plain mutable JavaScript object reference, updates are done by mutating `state.pos = newCartesian` rather than reassigning `entity.position`. The `CallbackProperty` closure holds a reference to `state`, so it always reads the latest value without any Cesium property assignment at all.

### Result
Aircraft positions update correctly on every WebSocket frame with no Cesium property assignment required in the hot update path.

---

## Issue 8 — `vite-plugin-cesium` Version `^1.3.2` Not Found

### What happened
Running `npm install` after creating `package.json` failed immediately with:
```
npm error notarget No matching version found for vite-plugin-cesium@^1.3.2
```

### Why it occurred
The guide specified `^1.3.2` but this version does not exist on the npm registry. The plugin's published versions jump from `1.2.23` to nothing higher — `1.3.x` was never published.

### Fix applied
Ran `npm show vite-plugin-cesium versions --json` to list all published versions, confirmed `1.2.23` was the latest, and updated `package.json` to `"vite-plugin-cesium": "^1.2.23"`.

### Result
`npm ci` completed successfully, installing all 173 packages. `npm run build` confirmed a clean production build with no errors.

---

## Issue 9 — Route Info (`origin_icao`, `dest_icao`, `progress`) Lost After Ingestion

### What happened
The flight info panel showed `Route: ??? → ???` and no progress bar even though the simulator was generating full route information.

### Why it occurred
`AircraftState` was defined with only the fields needed for tracking — `icao24`, `callsign`, `latitude`, `longitude`, `altitude_m`, `velocity_ms`, `heading`, `vertical_rate`, `on_ground`, `last_seen`. The three simulator-specific fields `origin_icao`, `dest_icao`, and `progress` were not in the dataclass. When `_to_aircraft_state()` converted the simulator dict to an `AircraftState`, those fields were silently discarded. The WebSocket broadcast serialised only what was in the dataclass, so the frontend never received them.

### Fix applied
Added three optional fields to `AircraftState`:
```python
origin_icao: Optional[str] = None
dest_icao:   Optional[str] = None
progress:    Optional[float] = None
```
Updated `_to_aircraft_state()` to populate them:
```python
origin_icao = d.get("origin_icao"),
dest_icao   = d.get("dest_icao"),
progress    = d.get("progress"),
```
`FlightInfoPanel.jsx` was also updated to conditionally show the progress bar only when `progress` is not null, so it degrades gracefully for real ADS-B data that doesn't have a progress value.

### Result
The info panel showed correct `KJFK → EGLL` style routes and an animated progress bar reflecting the flight's position along the great-circle path.

---

## Issue 10 — Plane Icons Invisible at Full Globe Zoom

### What happened
Even after fixing the `CallbackProperty` position issue, icons were not visible when the camera was pulled back to a full-globe view (altitude ~18,000 km).

### Why it occurred
The initial billboard definition included:
```js
distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8_000_000)
```
This hides the billboard when the camera is more than 8,000 km from the entity. At a full-globe overview the camera is roughly 18,000 km away, well beyond the cutoff.

### Fix applied
Removed `distanceDisplayCondition` from the billboard entirely so icons are always visible regardless of zoom level. A `scaleByDistance` was added instead to make icons slightly smaller at extreme zoom-out while remaining readable:
```js
scaleByDistance: new Cesium.NearFarScalar(1e5, 1.2, 2e7, 0.4)
```
Labels retain their `distanceDisplayCondition` capped at 1,500 km so they only appear when zoomed in close enough to be legible.

### Result
All aircraft icons are visible at every zoom level from full-globe view down to city level. Labels appear automatically when the camera descends below 1,500 km altitude.

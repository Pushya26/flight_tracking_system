import * as Cesium from 'cesium'

// ── SVGs ─────────────────────────────────────────────────────────────────────

const svgIcon = (fill) => `data:image/svg+xml,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
    <path d="M16 2 L21 13 L30 16 L21 19 L18 29 L16 27 L14 29 L11 19 L2 16 L11 13 Z"
      fill="${fill}" stroke="rgba(0,0,0,0.6)" stroke-width="1.5"/>
  </svg>`
)}`

const ICON_NORMAL   = svgIcon('#00d4ff')
const ICON_SELECTED = svgIcon('#ffdd00')

// ── Great-circle arc (N points) ───────────────────────────────────────────────

function gcArc(lat1, lon1, lat2, lon2, n = 80) {
  const toR = Math.PI / 180
  const φ1 = lat1*toR, λ1 = lon1*toR
  const φ2 = lat2*toR, λ2 = lon2*toR
  const d = 2*Math.asin(Math.sqrt(
    Math.sin((φ2-φ1)/2)**2 + Math.cos(φ1)*Math.cos(φ2)*Math.sin((λ2-λ1)/2)**2
  ))
  if (d < 1e-6) return [[lat1, lon1]]
  const pts = []
  for (let i = 0; i <= n; i++) {
    const f = i / n
    const A = Math.sin((1-f)*d)/Math.sin(d)
    const B = Math.sin(f*d)/Math.sin(d)
    const x = A*Math.cos(φ1)*Math.cos(λ1) + B*Math.cos(φ2)*Math.cos(λ2)
    const y = A*Math.cos(φ1)*Math.sin(λ1) + B*Math.cos(φ2)*Math.sin(λ2)
    const z = A*Math.sin(φ1) + B*Math.sin(φ2)
    pts.push([Math.atan2(z, Math.sqrt(x*x+y*y))/toR, Math.atan2(y,x)/toR])
  }
  return pts
}

// ── FlightLayer ───────────────────────────────────────────────────────────────

export class FlightLayer {
  constructor(viewer, onSelect) {
    this.viewer       = viewer
    this.onSelect     = onSelect
    this._data        = new Map()   // icao24 → { state:{pos,raw}, entity }
    this._selected    = null        // currently selected icao24
    this._routeEntity = null        // the great-circle arc entity
    this._airports    = {}          // { ICAO: {lat, lon} } loaded once

    fetch('/airports').then(r => r.json()).then(d => { this._airports = d })

    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction(click => {
      const picked = viewer.scene.pick(click.position)
      if (Cesium.defined(picked) && picked.id?.id) {
        this._selectIcon(picked.id.id)
        onSelect?.(picked.id.id)
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
  }

  // ── called every WS frame ─────────────────────────────────────────────────

  update(rawFlights) {
    const active = new Set(rawFlights.map(f => f.icao24))

    for (const raw of rawFlights) {
      const alt = raw.altitude ?? raw.altitude_m ?? 0
      const hdg = raw.true_track ?? raw.heading ?? 0
      const pos = Cesium.Cartesian3.fromDegrees(raw.longitude, raw.latitude, alt)

      if (!this._data.has(raw.icao24)) {
        const state  = { pos, raw }
        const entity = this._addEntity(raw.icao24, raw.callsign, state, hdg)
        this._data.set(raw.icao24, { state, entity })
      } else {
        const rec = this._data.get(raw.icao24)
        rec.state.pos = pos
        rec.state.raw = raw
        rec.entity.billboard.rotation = Cesium.Math.toRadians(-hdg)
        const ft = Math.round(alt / 0.3048 / 100) * 100
        rec.entity.label.text =
          `${raw.callsign || raw.icao24}\n${ft.toLocaleString()} ft`
      }
    }

    // Remove gone aircraft
    for (const [icao24, { entity }] of this._data) {
      if (!active.has(icao24)) {
        if (icao24 === this._selected) this._clearRoute()
        this.viewer.entities.remove(entity)
        this._data.delete(icao24)
      }
    }

    // Keep route arc updated for selected flight
    if (this._selected && this._data.has(this._selected)) {
      this._drawRoute(this._selected)
    }
  }

  // ── public: called from App when user picks from search list ─────────────

  select(icao24) {
    this._selectIcon(icao24)
  }

  flyTo(icao24) {
    const rec = this._data.get(icao24)
    if (!rec) return
    this.viewer.flyTo(rec.entity, {
      offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-40), 3_000_000),
    })
  }

  track(icao24) {
    const rec = this._data.get(icao24)
    if (!rec) return
    this.viewer.trackedEntity = rec.entity
  }

  untrack() {
    this.viewer.trackedEntity = undefined
  }

  // ── internals ─────────────────────────────────────────────────────────────

  _addEntity(icao24, callsign, state, hdg) {
    return this.viewer.entities.add({
      id:   icao24,
      name: callsign || icao24,
      position: new Cesium.CallbackProperty(() => state.pos, false),
      billboard: {
        image:                    ICON_NORMAL,
        width:                    28,
        height:                   28,
        rotation:                 Cesium.Math.toRadians(-hdg),
        alignedAxis:              Cesium.Cartesian3.UNIT_Z,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        scaleByDistance:          new Cesium.NearFarScalar(1e5, 1.2, 2e7, 0.4),
      },
      label: {
        text:         callsign || icao24,
        font:         '11px monospace',
        fillColor:    Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        style:        Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset:  new Cesium.Cartesian2(0, -30),
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 1_500_000),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })
  }

  _selectIcon(icao24) {
    // Reset previous
    if (this._selected && this._data.has(this._selected)) {
      this._data.get(this._selected).entity.billboard.image = ICON_NORMAL
      this._data.get(this._selected).entity.billboard.width  = 28
      this._data.get(this._selected).entity.billboard.height = 28
    }
    this._clearRoute()

    this._selected = icao24
    const rec = this._data.get(icao24)
    if (!rec) return

    // Highlight selected icon
    rec.entity.billboard.image  = ICON_SELECTED
    rec.entity.billboard.width  = 36
    rec.entity.billboard.height = 36

    this._drawRoute(icao24)
  }

  _drawRoute(icao24) {
    const rec = this._data.get(icao24)
    if (!rec) return
    const { raw } = rec.state
    const o = this._airports[raw.origin_icao]
    const d = this._airports[raw.dest_icao]
    if (!o || !d) return

    const progress = (raw.progress ?? 0) / 100
    const arc      = gcArc(o.lat, o.lon, d.lat, d.lon, 80)

    // Split arc at aircraft's progress point
    const splitIdx  = Math.round(progress * arc.length)
    const flownPts  = arc.slice(0, splitIdx + 1)
    const remainPts = arc.slice(splitIdx)

    const toCart = pts =>
      pts.flatMap(([lat, lon]) =>
        Cesium.Cartesian3.fromDegrees(lon, lat, 10000)
      )

    // Remove old route
    this._clearRoute()

    const entities = []

    // Flown segment — dimmed
    if (flownPts.length >= 2) {
      entities.push(this.viewer.entities.add({
        polyline: {
          positions:         toCart(flownPts),
          width:             2,
          material:          Cesium.Color.fromCssColorString('#005577').withAlpha(0.5),
          clampToGround:     false,
          arcType:           Cesium.ArcType.NONE,
        },
      }))
    }

    // Remaining segment — bright
    if (remainPts.length >= 2) {
      entities.push(this.viewer.entities.add({
        polyline: {
          positions:         toCart(remainPts),
          width:             2.5,
          material:          new Cesium.PolylineGlowMaterialProperty({
            glowPower: 0.2,
            color:     Cesium.Color.fromCssColorString('#00d4ff').withAlpha(0.85),
          }),
          clampToGround:     false,
          arcType:           Cesium.ArcType.NONE,
        },
      }))
    }

    // Origin dot
    entities.push(this.viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(o.lon, o.lat, 0),
      point: { pixelSize: 8, color: Cesium.Color.fromCssColorString('#ffdd00'), outlineColor: Cesium.Color.BLACK, outlineWidth: 1 },
      label: {
        text: raw.origin_icao, font: '10px monospace',
        fillColor: Cesium.Color.fromCssColorString('#ffdd00'),
        outlineColor: Cesium.Color.BLACK, outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -14),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    }))

    // Destination dot
    entities.push(this.viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(d.lon, d.lat, 0),
      point: { pixelSize: 8, color: Cesium.Color.fromCssColorString('#ff6644'), outlineColor: Cesium.Color.BLACK, outlineWidth: 1 },
      label: {
        text: raw.dest_icao, font: '10px monospace',
        fillColor: Cesium.Color.fromCssColorString('#ff6644'),
        outlineColor: Cesium.Color.BLACK, outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -14),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    }))

    this._routeEntity = entities
  }

  _clearRoute() {
    if (!this._routeEntity) return
    for (const e of this._routeEntity) this.viewer.entities.remove(e)
    this._routeEntity = null
  }
}

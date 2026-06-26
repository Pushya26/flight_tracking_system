import { useEffect, useRef } from 'react'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'

Cesium.Ion.defaultAccessToken =
  document.querySelector('meta[name="cesium-token"]')?.content ?? ''

export default function CesiumGlobe({ onViewerReady }) {
  const containerRef = useRef(null)
  const viewerRef    = useRef(null)

  useEffect(() => {
    if (viewerRef.current) return

    async function init() {
      const hasToken = Cesium.Ion.defaultAccessToken && Cesium.Ion.defaultAccessToken !== 'YOUR_CESIUM_ION_TOKEN_HERE'

      // Base imagery: satellite if Ion token present, else OSM
      let imageryProvider
      if (hasToken) {
        imageryProvider = await Cesium.ArcGisMapServerImageryProvider.fromUrl(
          'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
        )
      } else {
        imageryProvider = new Cesium.UrlTemplateImageryProvider({
          url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        })
      }

      // Terrain: world terrain if Ion token present, else ellipsoid (flat)
      let terrainProvider
      if (hasToken) {
        try { terrainProvider = await Cesium.createWorldTerrainAsync() }
        catch (e) { terrainProvider = new Cesium.EllipsoidTerrainProvider() }
      } else {
        terrainProvider = new Cesium.EllipsoidTerrainProvider()
      }

      const viewer = new Cesium.Viewer(containerRef.current, {
        imageryProvider,
        terrainProvider,
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

      // OSM road overlay on top of satellite (only when satellite is base)
      if (hasToken) {
        viewer.imageryLayers.addImageryProvider(
          new Cesium.UrlTemplateImageryProvider({
            url:   'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            alpha: 0.4,
          })
        )
      }

      // 3-D buildings (requires Ion token)
      if (hasToken) {
        try {
          const buildings = await Cesium.createOsmBuildingsAsync()
          viewer.scene.primitives.add(buildings)
        } catch (e) {
          console.warn('OSM buildings unavailable:', e)
        }
      }

      viewer.scene.globe.enableLighting          = true
      viewer.scene.atmosphere.show               = true
      viewer.scene.globe.depthTestAgainstTerrain = false

      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(0, 20, 18_000_000),
      })

      viewerRef.current = viewer
      onViewerReady?.(viewer)
    }

    init().catch(console.error)

    return () => {
      viewerRef.current?.destroy()
      viewerRef.current = null
    }
  }, [])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}
    />
  )
}

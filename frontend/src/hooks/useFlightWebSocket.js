import { useEffect, useRef, useCallback } from 'react'

export function useFlightWebSocket(onUpdate) {
  const wsRef    = useRef(null)
  const timerRef = useRef(null)

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws    = new WebSocket(`${proto}://${location.host}/ws/flights`)

    ws.onopen    = () => console.log('[WS] connected')
    ws.onmessage = e  => onUpdate(JSON.parse(e.data))
    ws.onerror   = ()  => ws.close()
    ws.onclose   = ()  => { timerRef.current = setTimeout(connect, 3000) }

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

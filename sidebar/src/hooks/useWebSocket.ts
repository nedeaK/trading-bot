import { useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'
import type { Signal } from '../types'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:7474/ws/signals'
const RECONNECT_MS = 3000

export function useWebSocket() {
  const setWsConnected = useStore((s) => s.setWsConnected)
  const addSignal = useStore((s) => s.addSignal)
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    let active = true

    function connect() {
      if (!active) return
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setWsConnected(true)
        // Keepalive ping every 20s
        const ping = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping')
        }, 20_000)
        ;(ws as unknown as { _ping: ReturnType<typeof setInterval> })._ping = ping
      }

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.event === 'signal') addSignal(msg.data as Signal)
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        timerRef.current = setTimeout(connect, RECONNECT_MS)
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      active = false
      clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [addSignal, setWsConnected])
}

import { create } from 'zustand'
import type { Signal, MarketContext, JournalTrade, JournalSummary, TabId, ScanStatus } from '../types'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:7474'

interface Store {
  // UI state
  symbol: string
  activeTab: TabId
  scanStatus: ScanStatus
  error: string | null
  useClaude: boolean
  wsConnected: boolean

  // Data
  signals: Signal[]
  context: MarketContext | null
  journalTrades: JournalTrade[]
  journalSummary: JournalSummary | null
  lastScanTime: Date | null

  // Actions
  setSymbol: (s: string) => void
  setTab: (t: TabId) => void
  setUseClaude: (v: boolean) => void
  setWsConnected: (v: boolean) => void
  scan: () => Promise<void>
  fetchContext: () => Promise<void>
  fetchJournal: () => Promise<void>
  addSignal: (s: Signal) => void
  clearError: () => void
}

export const useStore = create<Store>((set, get) => ({
  symbol: 'SPY',
  activeTab: 'signals',
  scanStatus: 'idle',
  error: null,
  useClaude: false,
  wsConnected: false,
  signals: [],
  context: null,
  journalTrades: [],
  journalSummary: null,
  lastScanTime: null,

  setSymbol: (symbol) => set({ symbol }),
  setTab: (activeTab) => set({ activeTab }),
  setUseClaude: (useClaude) => set({ useClaude }),
  setWsConnected: (wsConnected) => set({ wsConnected }),
  addSignal: (s) => set((st) => ({ signals: [s, ...st.signals].slice(0, 20) })),
  clearError: () => set({ error: null }),

  scan: async () => {
    const { symbol, useClaude } = get()
    set({ scanStatus: 'loading', error: null })
    try {
      const res = await fetch(
        `${API}/api/signals?symbol=${symbol}&use_claude=${useClaude}`
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail ?? 'Scan failed')
      }
      const data: Signal[] = await res.json()
      set({ signals: data, scanStatus: 'idle', lastScanTime: new Date() })
      // Auto-refresh context after scan
      get().fetchContext()
    } catch (e: unknown) {
      set({ scanStatus: 'error', error: (e as Error).message })
    }
  },

  fetchContext: async () => {
    const { symbol } = get()
    try {
      const res = await fetch(`${API}/api/context?symbol=${symbol}`)
      if (!res.ok) return
      const data: MarketContext = await res.json()
      set({ context: data })
    } catch {
      // Silently ignore context failures
    }
  },

  fetchJournal: async () => {
    try {
      const res = await fetch(`${API}/api/journal?limit=30`)
      if (!res.ok) return
      const data = await res.json()
      set({
        journalTrades: data.trades ?? [],
        journalSummary: data.summary ?? null,
      })
    } catch {
      // Silently ignore
    }
  },
}))

import { useEffect } from 'react'
import { useStore } from './store/useStore'
import { useWebSocket } from './hooks/useWebSocket'
import { Header } from './components/Header'
import { Tabs } from './components/Tabs'
import { SignalCard } from './components/SignalCard'
import { MarketContextPanel } from './components/MarketContextPanel'
import { TradeJournal } from './components/TradeJournal'

function SignalsTab() {
  const { signals, scanStatus, error, clearError } = useStore()

  if (scanStatus === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-3">
        <div className="relative w-10 h-10">
          <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20 border-t-emerald-500 animate-spin" />
        </div>
        <div className="text-xs text-zinc-500 text-center">
          <p>Running AI analysis…</p>
          <p className="text-zinc-700 text-[10px] mt-1">Fetching data, detecting setups, scoring signals</p>
        </div>
      </div>
    )
  }

  if (scanStatus === 'error' && error) {
    return (
      <div className="m-3 p-3 bg-red-950 border border-red-800 rounded-md">
        <p className="text-xs text-red-400 font-semibold mb-1">⚠ Scan Error</p>
        <p className="text-[11px] text-red-300">{error}</p>
        <p className="text-[10px] text-red-500 mt-2">
          Make sure the bot server is running:<br />
          <code className="text-red-400">py -m uvicorn server.main:app --port 7474</code>
        </p>
        <button
          onClick={clearError}
          className="mt-2 text-[10px] text-red-400 underline"
        >
          Dismiss
        </button>
      </div>
    )
  }

  if (signals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-2 text-center px-4">
        <div className="text-2xl">📡</div>
        <p className="text-xs text-zinc-400 font-semibold">No signals yet</p>
        <p className="text-[11px] text-zinc-600">
          Enter a symbol and click <strong className="text-zinc-400">▶ Scan</strong> to run the AI analyst
        </p>
      </div>
    )
  }

  return (
    <div className="p-3 space-y-3 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 130px)' }}>
      {signals.map((s, i) => <SignalCard key={`${s.symbol}-${s.timestamp}-${i}`} signal={s} index={i} />)}
    </div>
  )
}

export default function App() {
  useWebSocket()
  const { activeTab, fetchContext } = useStore()

  useEffect(() => { fetchContext() }, [fetchContext])

  return (
    <div className="flex flex-col h-screen w-full max-w-sm bg-zinc-950 overflow-hidden select-none">
      <Header />
      <Tabs />
      <div className="flex-1 overflow-hidden">
        {activeTab === 'signals' && <SignalsTab />}
        {activeTab === 'context' && <MarketContextPanel />}
        {activeTab === 'journal' && <TradeJournal />}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useStore } from '../store/useStore'

const SYMBOLS = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'BTC-USD', 'ETH-USD', 'AMZN', 'META']

export function Header() {
  const { symbol, setSymbol, scan, scanStatus, useClaude, setUseClaude, wsConnected, lastScanTime } = useStore()
  const [inputVal, setInputVal] = useState(symbol)
  const [showDropdown, setShowDropdown] = useState(false)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const s = inputVal.trim().toUpperCase()
    if (s) { setSymbol(s); setShowDropdown(false); scan() }
  }

  function selectSymbol(s: string) {
    setInputVal(s)
    setSymbol(s)
    setShowDropdown(false)
    scan()
  }

  const isLoading = scanStatus === 'loading'

  return (
    <header className="sticky top-0 z-50 bg-zinc-950 border-b border-zinc-800 px-3 py-2">
      {/* Top row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-emerald-400 font-bold tracking-widest text-xs">◈ AI ANALYST</span>
          <span
            className="pulse-dot"
            style={{ background: wsConnected ? '#22c55e' : '#71717a' }}
            title={wsConnected ? 'Live' : 'Disconnected'}
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 cursor-pointer text-zinc-400 select-none">
            <div
              onClick={() => setUseClaude(!useClaude)}
              className={`w-7 h-4 rounded-full transition-colors cursor-pointer ${useClaude ? 'bg-violet-600' : 'bg-zinc-700'}`}
              style={{ position: 'relative' }}
            >
              <span
                className="absolute top-0.5 rounded-full bg-white transition-transform"
                style={{ width: 12, height: 12, left: useClaude ? 13 : 2, transition: 'left 0.2s' }}
              />
            </div>
            <span className="text-[10px]">{useClaude ? '⚡ Claude' : 'Heuristic'}</span>
          </label>
        </div>
      </div>

      {/* Symbol search + scan */}
      <form onSubmit={handleSubmit} className="flex gap-2 relative">
        <div className="relative flex-1">
          <input
            value={inputVal}
            onChange={(e) => { setInputVal(e.target.value.toUpperCase()); setShowDropdown(true) }}
            onFocus={() => setShowDropdown(true)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
            placeholder="Symbol..."
            className="w-full bg-zinc-900 border border-zinc-700 rounded-md px-2 py-1.5 text-zinc-100 text-xs focus:outline-none focus:border-emerald-500 placeholder-zinc-600"
          />
          {showDropdown && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-zinc-900 border border-zinc-700 rounded-md overflow-hidden z-50 shadow-xl">
              {SYMBOLS.filter(s => s.includes(inputVal) || inputVal === '').map(s => (
                <button
                  key={s}
                  type="button"
                  onMouseDown={() => selectSymbol(s)}
                  className="w-full text-left px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
        <button
          type="submit"
          disabled={isLoading}
          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 disabled:cursor-not-allowed text-white text-xs rounded-md font-semibold transition-colors whitespace-nowrap"
        >
          {isLoading ? (
            <span className="flex items-center gap-1">
              <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
              </svg>
              Scanning
            </span>
          ) : '▶ Scan'}
        </button>
      </form>

      {lastScanTime && (
        <p className="text-[10px] text-zinc-600 mt-1">
          Last scan: {lastScanTime.toLocaleTimeString()}
        </p>
      )}
    </header>
  )
}

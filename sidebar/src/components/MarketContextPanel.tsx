import { useEffect } from 'react'
import { useStore } from '../store/useStore'

const TREND_COLOR: Record<string, string> = {
  BULLISH: 'text-emerald-400',
  BEARISH: 'text-red-400',
  NEUTRAL: 'text-zinc-400',
}

const VOL_STYLES: Record<string, { text: string; bg: string }> = {
  CALM:     { text: 'text-emerald-300', bg: 'bg-emerald-950' },
  NORMAL:   { text: 'text-zinc-300',    bg: 'bg-zinc-800'    },
  ELEVATED: { text: 'text-amber-300',   bg: 'bg-amber-950'   },
  CRISIS:   { text: 'text-red-300',     bg: 'bg-red-950'     },
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-zinc-900 rounded-md p-2">
      <p className="text-[10px] text-zinc-600 uppercase tracking-widest">{label}</p>
      <p className="text-xs font-bold text-zinc-200 mt-0.5">{value}</p>
      {sub && <p className="text-[10px] text-zinc-500">{sub}</p>}
    </div>
  )
}

function TrendChip({ trend, vs20ma }: { trend: string; vs20ma: number }) {
  const color = TREND_COLOR[trend] ?? 'text-zinc-400'
  const sign = vs20ma >= 0 ? '+' : ''
  return (
    <div className="flex items-center justify-between bg-zinc-900 rounded-md p-2">
      <span className={`text-xs font-bold ${color}`}>{trend}</span>
      <span className={`text-[10px] ${vs20ma >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        {sign}{vs20ma.toFixed(1)}% vs 20MA
      </span>
    </div>
  )
}

export function MarketContextPanel() {
  const { context, symbol, fetchContext, scanStatus } = useStore()

  useEffect(() => { fetchContext() }, [symbol, fetchContext])

  if (scanStatus === 'loading') {
    return (
      <div className="p-4 text-center text-zinc-600 text-xs animate-pulse">
        Loading market context…
      </div>
    )
  }

  if (!context) {
    return (
      <div className="p-4 text-center text-zinc-600 text-xs">
        Run a scan to load market context
      </div>
    )
  }

  const volStyle = VOL_STYLES[context.volatility_state] ?? VOL_STYLES.NORMAL

  return (
    <div className="p-3 space-y-3">
      {/* Vol + Regime */}
      <div className="grid grid-cols-2 gap-2">
        <div className={`rounded-md p-2 ${volStyle.bg}`}>
          <p className="text-[10px] text-zinc-500 uppercase tracking-widest">Volatility</p>
          <p className={`text-xs font-bold ${volStyle.text} mt-0.5`}>{context.volatility_state}</p>
          <p className="text-[10px] text-zinc-500">ATR {context.atr_percentile.toFixed(0)}th pct</p>
        </div>
        <Stat
          label="Regime"
          value={context.trend_regime}
          sub={`ATR ${context.atr.toFixed(4)}`}
        />
      </div>

      {/* VIX */}
      <div className="bg-zinc-900 rounded-md p-2 flex items-center justify-between">
        <div>
          <p className="text-[10px] text-zinc-600 uppercase tracking-widest">VIX</p>
          <p className={`text-sm font-bold ${
            context.vix_level === 0 ? 'text-zinc-600'
            : context.vix_level >= 30 ? 'text-red-400'
            : context.vix_level >= 20 ? 'text-amber-400'
            : 'text-emerald-400'
          }`}>
            {context.vix_level === 0 ? 'N/A' : context.vix_level.toFixed(1)}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-zinc-600">ATR Percentile</p>
          <div className="w-24 bg-zinc-800 rounded-full h-1.5 mt-1 overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${context.atr_percentile}%`,
                background: context.atr_percentile > 75 ? '#ef4444'
                  : context.atr_percentile > 50 ? '#f59e0b' : '#22c55e',
              }}
            />
          </div>
          <p className="text-[10px] text-zinc-500 mt-0.5">{context.atr_percentile.toFixed(0)}th</p>
        </div>
      </div>

      {/* Trends */}
      <div className="space-y-1.5">
        <p className="text-[10px] text-zinc-600 uppercase tracking-widest">Trend Alignment</p>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-16">SPY</span>
            <TrendChip trend={context.spy_trend} vs20ma={context.spy_vs_20ma} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-16">{context.sector_etf}</span>
            <TrendChip trend={context.sector_trend} vs20ma={context.sector_vs_20ma} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 w-16">{context.symbol}</span>
            <TrendChip trend={context.instrument_trend} vs20ma={context.instrument_vs_20ma} />
          </div>
        </div>
      </div>
    </div>
  )
}

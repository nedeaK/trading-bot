import type { Signal } from '../types'

interface Props { signal: Signal; index: number }

const VERDICT_STYLES = {
  TRADE: { bg: 'bg-emerald-950', border: 'border-emerald-700', badge: 'bg-emerald-600 text-white', glow: 'glow-green' },
  WAIT:  { bg: 'bg-amber-950',   border: 'border-amber-700',   badge: 'bg-amber-500 text-black',   glow: 'glow-amber' },
  SKIP:  { bg: 'bg-zinc-900',    border: 'border-zinc-700',     badge: 'bg-zinc-600 text-zinc-300', glow: '' },
}

const DIR_COLOR = { BUY: 'text-emerald-400', SELL: 'text-red-400' }

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 75 ? '#22c55e' : value >= 55 ? '#f59e0b' : '#ef4444'
  return (
    <div className="w-full bg-zinc-800 rounded-full h-1 overflow-hidden">
      <div
        className="h-full rounded-full conf-bar"
        style={{ width: `${value}%`, background: color }}
      />
    </div>
  )
}

function PriceLine({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-zinc-500 text-[10px]">{label}</span>
      <span className={`font-bold text-xs ${color}`}>${value.toFixed(4)}</span>
    </div>
  )
}

export function SignalCard({ signal, index }: Props) {
  const styles = VERDICT_STYLES[signal.verdict] ?? VERDICT_STYLES.WAIT
  const isLong = signal.direction === 'BUY'

  return (
    <div
      className={`card ${styles.bg} ${styles.border} ${styles.glow} p-3 space-y-2`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold ${isLong ? DIR_COLOR.BUY : DIR_COLOR.SELL}`}>
            {isLong ? '▲ LONG' : '▼ SHORT'}
          </span>
          <span className="text-zinc-400 text-xs font-bold">{signal.symbol}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`chip ${styles.badge}`}>{signal.verdict}</span>
          {signal.is_extreme && (
            <span className="chip bg-violet-900 text-violet-300">EXTREME</span>
          )}
        </div>
      </div>

      {/* Confidence */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] text-zinc-500">
          <span>AI Confidence</span>
          <span className="font-bold text-zinc-300">{signal.confidence}/100</span>
        </div>
        <ConfidenceBar value={signal.confidence} />
      </div>

      {/* Prices */}
      <div className="bg-zinc-950 rounded-md p-2 space-y-1">
        <PriceLine label="Entry" value={signal.entry_price} color="text-zinc-200" />
        <PriceLine label="Stop Loss" value={signal.stop_loss} color="text-red-400" />
        <PriceLine label="Take Profit" value={signal.take_profit} color="text-emerald-400" />
        <div className="flex justify-between pt-1 border-t border-zinc-800">
          <span className="text-zinc-500 text-[10px]">R:R Ratio</span>
          <span className="text-emerald-300 font-bold text-xs">{signal.rr_ratio.toFixed(1)}:1</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500 text-[10px]">Risk %</span>
          <span className="text-zinc-300 text-xs">{(signal.final_risk_pct * 100).toFixed(1)}%
            <span className="text-zinc-600"> ×{signal.size_adjustment.toFixed(2)}</span>
          </span>
        </div>
      </div>

      {/* AI Thesis */}
      <div className="bg-zinc-900/50 rounded-md p-2">
        <p className="text-[10px] text-zinc-500 font-semibold uppercase tracking-widest mb-1">Analyst Thesis</p>
        <p className="text-[11px] text-zinc-300 leading-relaxed">{signal.thesis}</p>
      </div>

      {/* Concerns */}
      {signal.concerns.length > 0 && (
        <div>
          <p className="text-[10px] text-zinc-500 font-semibold uppercase tracking-widest mb-1">Concerns</p>
          <ul className="space-y-0.5">
            {signal.concerns.map((c, i) => (
              <li key={i} className="text-[10px] text-amber-400 flex gap-1.5">
                <span>⚠</span><span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Analyst notes */}
      {signal.analyst_notes && (
        <p className="text-[10px] text-zinc-500 italic border-t border-zinc-800 pt-2">
          📋 {signal.analyst_notes}
        </p>
      )}

      {/* Footer badges */}
      <div className="flex flex-wrap gap-1 pt-1 border-t border-zinc-800">
        <span className="chip bg-zinc-800 text-zinc-400">
          {signal.zone_type}
          {signal.has_imbalance ? ' + FVG' : ''}
        </span>
        <span className="chip bg-zinc-800 text-zinc-400">ML {signal.ml_score.toFixed(0)}/100</span>
        <span className={`chip ${
          signal.context_volatility === 'CALM' ? 'bg-emerald-950 text-emerald-400'
          : signal.context_volatility === 'ELEVATED' ? 'bg-amber-950 text-amber-400'
          : signal.context_volatility === 'CRISIS' ? 'bg-red-950 text-red-400'
          : 'bg-zinc-800 text-zinc-400'
        }`}>
          {signal.context_volatility}
        </span>
        <span className="chip bg-zinc-800 text-zinc-400 ml-auto">
          {signal.ai_source === 'claude' ? '⚡ Claude' : 'Heuristic'}
        </span>
      </div>
    </div>
  )
}

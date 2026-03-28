import { useEffect } from 'react'
import { useStore } from '../store/useStore'
import type { JournalTrade } from '../types'

function OutcomeBadge({ outcome }: { outcome: string | null }) {
  if (!outcome) return <span className="chip bg-zinc-800 text-zinc-500">PENDING</span>
  const styles: Record<string, string> = {
    WIN: 'bg-emerald-900 text-emerald-300',
    LOSS: 'bg-red-900 text-red-300',
    EXPIRED: 'bg-zinc-800 text-zinc-400',
    CANCELLED: 'bg-zinc-800 text-zinc-500',
  }
  return <span className={`chip ${styles[outcome] ?? 'bg-zinc-800 text-zinc-400'}`}>{outcome}</span>
}

function JournalRow({ trade }: { trade: JournalTrade }) {
  const isLong = trade.direction === 'BUY'
  const date = new Date(trade.timestamp)
  return (
    <div className="p-2 border-b border-zinc-800/50 hover:bg-zinc-900/30 transition-colors">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold ${isLong ? 'text-emerald-400' : 'text-red-400'}`}>
            {isLong ? '▲' : '▼'} {trade.symbol}
          </span>
          <span className={`chip ${trade.verdict === 'TRADE' ? 'bg-emerald-950 text-emerald-400' : 'bg-zinc-800 text-zinc-500'}`}>
            {trade.verdict}
          </span>
        </div>
        <OutcomeBadge outcome={trade.outcome} />
      </div>
      <div className="flex justify-between text-[10px] text-zinc-500">
        <span>@ ${trade.entry_price.toFixed(4)} · R:R {trade.rr_ratio.toFixed(1)}</span>
        <span>
          {trade.pnl_r != null
            ? <span className={trade.pnl_r >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                {trade.pnl_r >= 0 ? '+' : ''}{trade.pnl_r.toFixed(2)}R
              </span>
            : date.toLocaleDateString()}
        </span>
      </div>
      {trade.thesis && (
        <p className="text-[10px] text-zinc-600 mt-1 line-clamp-2">{trade.thesis}</p>
      )}
    </div>
  )
}

export function TradeJournal() {
  const { journalTrades, journalSummary, fetchJournal } = useStore()

  useEffect(() => { fetchJournal() }, [fetchJournal])

  return (
    <div>
      {/* Summary bar */}
      {journalSummary && (
        <div className="p-3 grid grid-cols-4 gap-2 border-b border-zinc-800">
          <div className="text-center">
            <p className="text-[10px] text-zinc-600">Win Rate</p>
            <p className="text-xs font-bold text-emerald-400">
              {(journalSummary.win_rate * 100).toFixed(0)}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-zinc-600">Trades</p>
            <p className="text-xs font-bold text-zinc-300">{journalSummary.total_resolved}</p>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-zinc-600">Avg R</p>
            <p className={`text-xs font-bold ${journalSummary.avg_pnl_r >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {journalSummary.avg_pnl_r >= 0 ? '+' : ''}{journalSummary.avg_pnl_r.toFixed(2)}R
            </p>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-zinc-600">AI Skipped</p>
            <p className="text-xs font-bold text-amber-400">{journalSummary.skipped_by_ai}</p>
          </div>
        </div>
      )}

      {/* Trade list */}
      <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
        {journalTrades.length === 0 ? (
          <div className="p-6 text-center text-zinc-600 text-xs">
            No trades logged yet.<br />
            <span className="text-zinc-700">Trades appear here after your first scan.</span>
          </div>
        ) : (
          journalTrades.map((t) => <JournalRow key={t.trade_id} trade={t} />)
        )}
      </div>
    </div>
  )
}

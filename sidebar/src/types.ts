export interface Signal {
  symbol: string
  direction: 'BUY' | 'SELL'
  entry_price: number
  stop_loss: number
  take_profit: number
  rr_ratio: number
  confidence: number
  verdict: 'TRADE' | 'WAIT' | 'SKIP'
  thesis: string
  concerns: string[]
  size_adjustment: number
  invalidation_level: number
  analyst_notes: string
  ai_source: string
  ml_score: number
  final_risk_pct: number
  context_volatility: string
  context_regime: string
  context_spy_trend: string
  context_vix: number
  timestamp: string
  zone_type: string
  has_imbalance: boolean
  is_extreme: boolean
}

export interface MarketContext {
  symbol: string
  atr: number
  atr_percentile: number
  volatility_state: string
  trend_regime: string
  spy_trend: string
  spy_vs_20ma: number
  vix_level: number
  sector_etf: string
  sector_trend: string
  sector_vs_20ma: number
  instrument_trend: string
  instrument_vs_20ma: number
}

export interface JournalSummary {
  total_logged: number
  total_resolved: number
  win_rate: number
  wins: number
  losses: number
  skipped_by_ai: number
  avg_confidence_on_trades: number
  avg_pnl_r: number
}

export interface JournalTrade {
  trade_id: string
  timestamp: string
  symbol: string
  direction: string
  entry_price: number
  stop_loss: number
  take_profit: number
  rr_ratio: number
  verdict: string
  confidence: number
  thesis: string
  outcome: string | null
  pnl_r: number | null
}

export type TabId = 'signals' | 'context' | 'journal'
export type ScanStatus = 'idle' | 'loading' | 'error'

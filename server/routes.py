"""REST API routes for the trading analyst sidebar."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class ScanRequest(BaseModel):
    symbol: str = "SPY"
    use_claude: bool = False
    start_date: str = ""
    end_date: str = ""
    htf: str = "1d"
    mtf: str = "1h"
    ltf: str = "15m"


class SignalResponse(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    confidence: int
    verdict: str
    thesis: str
    concerns: List[str]
    size_adjustment: float
    invalidation_level: float
    analyst_notes: str
    ai_source: str
    ml_score: float
    final_risk_pct: float
    context_volatility: str
    context_regime: str
    context_spy_trend: str
    context_vix: float
    timestamp: str
    zone_type: str
    has_imbalance: bool
    is_extreme: bool


class ContextResponse(BaseModel):
    symbol: str
    atr: float
    atr_percentile: float
    volatility_state: str
    trend_regime: str
    spy_trend: str
    spy_vs_20ma: float
    vix_level: float
    sector_etf: str
    sector_trend: str
    sector_vs_20ma: float
    instrument_trend: str
    instrument_vs_20ma: float


# ── Helper ────────────────────────────────────────────────────────────────────

def _fetch_candles(symbol: str, period: str, interval: str):
    """Fetch candles via yfinance."""
    try:
        import yfinance as yf
        from data.models import Candle
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if df.empty:
            return []
        candles = []
        for ts, row in df.iterrows():
            candles.append(Candle(
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0)),
            ))
        return candles
    except Exception as exc:
        logger.error("yfinance fetch failed for %s %s %s: %s", symbol, period, interval, exc)
        return []


def _signal_to_response(signal, symbol: str) -> SignalResponse:
    meta = signal.metadata or {}
    return SignalResponse(
        symbol=symbol,
        direction=signal.signal_type.name,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        rr_ratio=round(signal.rr_ratio, 2),
        confidence=int(signal.confidence * 100),
        verdict=meta.get("ai_verdict", "TRADE"),
        thesis=meta.get("ai_thesis", ""),
        concerns=meta.get("ai_concerns", []),
        size_adjustment=meta.get("ai_size_adjustment", 1.0),
        invalidation_level=meta.get("ai_invalidation", signal.stop_loss),
        analyst_notes=meta.get("ai_analyst_notes", ""),
        ai_source=meta.get("ai_source", "heuristic"),
        ml_score=meta.get("ml_score", 50.0),
        final_risk_pct=meta.get("final_risk_pct", 0.02),
        context_volatility=meta.get("context_volatility", "NORMAL"),
        context_regime=meta.get("context_regime", "RANGING"),
        context_spy_trend=meta.get("context_spy_trend", "NEUTRAL"),
        context_vix=meta.get("context_vix", 0.0),
        timestamp=signal.timestamp.isoformat(),
        zone_type=signal.zone.zone_type.name,
        has_imbalance=signal.zone.has_imbalance,
        is_extreme=signal.zone.is_extreme,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "service": "SMC AI Trading Analyst"}


@router.get("/signals", response_model=List[SignalResponse])
def get_signals(
    symbol: str = Query("SPY"),
    use_claude: bool = Query(False),
    htf: str = Query("1d"),
    mtf: str = Query("1h"),
    ltf: str = Query("15m"),
):
    """Run a fresh AI scan and return signals for the given symbol."""
    try:
        from signals.ai_generator import ai_generate_signals
        from config.settings import Config, TimeframeConfig, SMCConfig, RiskConfig
        from config.constants import Timeframe

        logger.info("Scanning %s (htf=%s mtf=%s ltf=%s use_claude=%s)", symbol, htf, mtf, ltf, use_claude)

        htf_period_map = {"1d": "2y", "1wk": "5y"}
        mtf_period_map = {"1h": "60d", "4h": "120d"}
        ltf_period_map = {"15m": "30d", "5m": "10d"}

        htf_candles = _fetch_candles(symbol, htf_period_map.get(htf, "2y"), htf)
        mtf_candles = _fetch_candles(symbol, mtf_period_map.get(mtf, "60d"), mtf)
        ltf_candles = _fetch_candles(symbol, ltf_period_map.get(ltf, "30d"), ltf)

        if not htf_candles or not mtf_candles or not ltf_candles:
            raise HTTPException(status_code=404, detail=f"No data returned for {symbol}")

        signals = ai_generate_signals(
            htf_candles, mtf_candles, ltf_candles,
            symbol=symbol,
            use_claude=use_claude,
            live_mode=True,
        )

        return [_signal_to_response(s, symbol) for s in signals]

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Signal generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/context", response_model=ContextResponse)
def get_context(symbol: str = Query("SPY")):
    """Return current market context for a symbol."""
    try:
        from context.market_context import build_market_context
        htf_candles = _fetch_candles(symbol, "2y", "1d")
        if not htf_candles:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        ctx = build_market_context(symbol=symbol, instrument_candles=htf_candles, live_mode=True)
        return ContextResponse(
            symbol=symbol,
            atr=ctx.atr,
            atr_percentile=ctx.atr_percentile,
            volatility_state=ctx.volatility_state,
            trend_regime=ctx.trend_regime,
            spy_trend=ctx.spy_trend,
            spy_vs_20ma=ctx.spy_vs_20ma,
            vix_level=ctx.vix_level,
            sector_etf=ctx.sector_etf,
            sector_trend=ctx.sector_trend,
            sector_vs_20ma=ctx.sector_vs_20ma,
            instrument_trend=ctx.instrument_trend,
            instrument_vs_20ma=ctx.instrument_vs_20ma,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Context fetch failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/journal")
def get_journal(limit: int = Query(50)):
    """Return recent trade journal entries."""
    try:
        from memory.trade_journal import TradeJournal
        journal = TradeJournal()
        records = journal._load_all()
        recent = sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)[:limit]
        summary = journal.summary()
        return {"summary": summary, "trades": recent}
    except Exception as exc:
        logger.exception("Journal load failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/scan", response_model=List[SignalResponse])
def post_scan(req: ScanRequest):
    """Trigger a scan with custom parameters (same as GET /signals but via POST)."""
    return get_signals(
        symbol=req.symbol,
        use_claude=req.use_claude,
        htf=req.htf,
        mtf=req.mtf,
        ltf=req.ltf,
    )

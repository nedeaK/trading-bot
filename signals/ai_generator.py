"""AI-enhanced signal generator — the new primary entry point.

Wraps the existing rule-based SMC pipeline and adds:
  1. Market context (regime, volatility, SPY, sector)
  2. ML pattern confidence score
  3. Claude AI analyst reasoning (or fast heuristic in backtest mode)
  4. Adaptive risk sizing
  5. Trade journal logging (optional)

Returns the same List[Signal] type as the original generator — the AI
analysis is embedded in signal.metadata so the backtest engine needs
no changes to run.

Usage:
    # Backtesting (fast, heuristic analyst, no API calls):
    signals = ai_generate_signals(htf, mtf, ltf, config, symbol="SPY")

    # Live trading (Claude API, full reasoning):
    signals = ai_generate_signals(
        htf, mtf, ltf, config, symbol="AAPL",
        use_claude=True, live_mode=True,
    )
"""

import logging
from dataclasses import replace
from typing import Dict, List, Optional, Any

from config.settings import Config, SMCConfig, RiskConfig
from data.models import Candle, Signal, MarketContext, AIAnalysis
from signals.generator import generate_signals
from context.market_context import build_market_context
from ml.scorer import SignalScorer
from risk.adaptive_sizer import adaptive_risk_percent, atr_adjusted_stop
from config.constants import SignalType

logger = logging.getLogger(__name__)

# Module-level scorer (loaded once per process)
_scorer: Optional[SignalScorer] = None


def _get_scorer() -> SignalScorer:
    global _scorer
    if _scorer is None:
        _scorer = SignalScorer()
    return _scorer


def ai_generate_signals(
    htf_candles: List[Candle],
    mtf_candles: List[Candle],
    ltf_candles: List[Candle],
    config: Optional[Config] = None,
    symbol: str = "UNKNOWN",
    use_claude: bool = False,
    live_mode: bool = False,
    spy_candles: Optional[List[Candle]] = None,
    vix_candles: Optional[List[Candle]] = None,
    journal=None,
) -> List[Signal]:
    """Generate AI-enhanced trade signals.

    Args:
        htf_candles: Higher timeframe candles (daily/weekly).
        mtf_candles: Medium timeframe candles (1H/4H).
        ltf_candles: Lower timeframe candles (15m/5m).
        config: Full bot configuration.
        symbol: Ticker symbol (used for sector lookup and journal).
        use_claude: If True, call Claude API for final analysis.
        live_mode: If True, fetch live SPY/VIX data via yfinance.
        spy_candles: Pre-fetched SPY candles (avoids redundant fetches in backtest).
        vix_candles: Pre-fetched VIX candles.
        journal: Optional TradeJournal instance for logging.

    Returns:
        List of Signal objects with AI metadata in signal.metadata.
        Empty list if the SMC pipeline produced no candidate or AI said SKIP.
    """
    if config is None:
        config = Config()

    smc_config: SMCConfig = config.smc
    risk_config: RiskConfig = config.risk

    # ── Step 1: Run existing rule-based SMC pipeline ─────────────────────────
    candidate_signals = generate_signals(htf_candles, mtf_candles, ltf_candles, smc_config)
    if not candidate_signals:
        return []

    # ── Step 2: Build market context ─────────────────────────────────────────
    context = build_market_context(
        symbol=symbol,
        instrument_candles=htf_candles,
        spy_candles=spy_candles,
        vix_candles=vix_candles,
        live_mode=live_mode,
    )

    # ── Step 3: Extract setup metadata for scoring ────────────────────────────
    # Reconstruct approximate intermediates from the candles.
    pool_strength, sweep_depth_pct, zone_age_bars, mtf_summary = _extract_setup_metadata(
        mtf_candles, ltf_candles,
    )

    # ── Step 4: ML confidence score ──────────────────────────────────────────
    scorer = _get_scorer()

    # ── Step 5: AI analysis ──────────────────────────────────────────────────
    if use_claude:
        from ai.analyst import ClaudeAnalyst
        analyst = ClaudeAnalyst()
    else:
        from ai.heuristic_analyst import HeuristicAnalyst
        analyst = HeuristicAnalyst()

    enhanced_signals: List[Signal] = []

    for signal in candidate_signals:
        ml_score = scorer.score(
            signal, context, ltf_candles,
            pool_strength, sweep_depth_pct, zone_age_bars,
        )

        ai_analysis: AIAnalysis = analyst.analyze(
            signal=signal,
            context=context,
            ltf_candles=ltf_candles,
            symbol=symbol,
            pool_strength=pool_strength,
            sweep_depth_pct=sweep_depth_pct,
            zone_age_bars=zone_age_bars,
            mtf_structure_summary=mtf_summary,
            ml_score=ml_score,
        )

        logger.info(
            "AI verdict for %s %s @ %.4f: %s (confidence=%d, ML=%.0f)",
            symbol, signal.signal_type.name, signal.entry_price,
            ai_analysis.verdict, ai_analysis.confidence, ml_score,
        )

        # ── Step 6: Adaptive risk sizing ─────────────────────────────────────
        size_result = adaptive_risk_percent(
            base_risk=risk_config.risk_percent,
            context=context,
            ai_analysis=ai_analysis,
            risk_config=risk_config,
        )

        # ── Step 7: Optionally upgrade to ATR-adjusted stop ───────────────────
        is_long = signal.signal_type == SignalType.BUY
        atr_stop = atr_adjusted_stop(
            entry_price=signal.entry_price,
            is_long=is_long,
            atr=context.atr,
            multiplier=1.5,
        )
        # Use whichever stop gives more protection (further from entry)
        if is_long:
            final_stop = min(signal.stop_loss, atr_stop)
        else:
            final_stop = max(signal.stop_loss, atr_stop)

        # ── Step 8: Log to journal ────────────────────────────────────────────
        if journal is not None:
            try:
                journal.log_signal(
                    signal=signal,
                    ai_analysis=ai_analysis,
                    context=context,
                    ltf_candles=ltf_candles,
                    symbol=symbol,
                    pool_strength=pool_strength,
                    sweep_depth_pct=sweep_depth_pct,
                    zone_age_bars=zone_age_bars,
                    final_risk_pct=size_result.risk_percent,
                )
            except Exception as exc:
                logger.warning("Journal logging failed: %s", exc)

        # ── Step 9: Filter — only emit TRADE verdicts ─────────────────────────
        if ai_analysis.verdict != "TRADE":
            logger.info("Signal skipped by AI (%s): %s", ai_analysis.verdict, ai_analysis.thesis[:80])
            continue

        # ── Step 10: Attach AI metadata to signal ────────────────────────────
        metadata: Dict[str, Any] = {
            "ai_verdict": ai_analysis.verdict,
            "ai_confidence": ai_analysis.confidence,
            "ai_thesis": ai_analysis.thesis,
            "ai_concerns": list(ai_analysis.concerns),
            "ai_size_adjustment": ai_analysis.size_adjustment,
            "ai_invalidation": ai_analysis.invalidation_level,
            "ai_analyst_notes": ai_analysis.analyst_notes,
            "ai_source": ai_analysis.source,
            "ml_score": ml_score,
            "final_risk_pct": size_result.risk_percent,
            "risk_reasoning": size_result.reasoning,
            "context_volatility": context.volatility_state,
            "context_regime": context.trend_regime,
            "context_spy_trend": context.spy_trend,
            "context_vix": context.vix_level,
            "pool_strength": pool_strength,
            "sweep_depth_pct": sweep_depth_pct,
            "zone_age_bars": zone_age_bars,
        }

        enhanced = Signal(
            signal_type=signal.signal_type,
            timestamp=signal.timestamp,
            entry_price=signal.entry_price,
            stop_loss=final_stop,
            take_profit=signal.take_profit,
            zone=signal.zone,
            narrative=signal.narrative,
            confidence=ai_analysis.confidence / 100.0,
            metadata=metadata,
        )
        enhanced_signals.append(enhanced)

    return enhanced_signals


def _extract_setup_metadata(
    mtf_candles: List[Candle],
    ltf_candles: List[Candle],
) -> tuple:
    """Derive approximate setup quality metrics from candle data.

    Returns: (pool_strength, sweep_depth_pct, zone_age_bars, mtf_structure_summary)
    """
    # Pool strength: heuristic based on recent swing clustering
    pool_strength = _estimate_pool_strength(ltf_candles)

    # Sweep depth: last candle's wick extension as % of close
    sweep_depth_pct = 0.1
    if ltf_candles:
        last = ltf_candles[-1]
        max_wick = max(last.upper_wick, last.lower_wick)
        if last.close > 0:
            sweep_depth_pct = max_wick / last.close * 100

    # Zone age: approximate from last 20 candles structural activity
    zone_age_bars = min(len(ltf_candles), 10)

    # MTF structure summary
    mtf_summary = _summarize_structure(mtf_candles)

    return pool_strength, round(sweep_depth_pct, 4), zone_age_bars, mtf_summary


def _estimate_pool_strength(candles: List[Candle]) -> int:
    """Estimate liquidity pool strength from recent equal highs/lows clustering."""
    if len(candles) < 10:
        return 2
    recent = candles[-30:]
    highs = [c.high for c in recent]
    lows = [c.low for c in recent]

    def count_clusters(prices, tol=0.001):
        if not prices:
            return 2
        sorted_p = sorted(prices)
        clusters = 1
        for i in range(1, len(sorted_p)):
            if (sorted_p[i] - sorted_p[i - 1]) / (sorted_p[i - 1] + 1e-9) > tol:
                clusters += 1
        touches = len(prices) // max(clusters, 1)
        return max(2, min(touches, 6))

    return max(count_clusters(highs), count_clusters(lows))


def _summarize_structure(candles: List[Candle]) -> str:
    """Create a short readable summary of recent MTF structure."""
    if len(candles) < 8:
        return "Insufficient data"
    tail = candles[-8:]
    closes = [c.close for c in tail]
    highs = [c.high for c in tail]
    lows = [c.low for c in tail]

    hh = highs[-1] > max(highs[:-1])
    ll = lows[-1] < min(lows[:-1])
    hl = lows[-1] > lows[-2]
    lh = highs[-1] < highs[-2]

    if hh and hl:
        return "Bullish (HH+HL)"
    if ll and lh:
        return "Bearish (LL+LH)"
    if hh and lh:
        return "Distribution (HH+LH)"
    if ll and hl:
        return "Accumulation (LL+HL)"
    return "Choppy / No clear structure"

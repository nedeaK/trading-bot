"""Heuristic analyst — fast rule-based scoring that mimics senior analyst judgment.

Used during backtesting to avoid API costs while preserving the same interface
as the Claude analyst. Scores setups the way an experienced trader evaluates
confluence: multiple independent factors each add or subtract conviction.
"""

from typing import List, Optional

from data.models import AIAnalysis, Candle, MarketContext, Signal
from config.constants import SignalType, ZoneType


class HeuristicAnalyst:
    """Score signals using quantitative rules that approximate analyst judgment.

    Each factor contributes ± points to a base score of 50.
    Final score → verdict → thesis is assembled from the scoring breakdown.
    """

    # Minimum confidence to recommend TRADE
    TRADE_THRESHOLD = 65
    # Below this → SKIP
    SKIP_THRESHOLD = 40

    def analyze(
        self,
        signal: Signal,
        context: MarketContext,
        ltf_candles: List[Candle],
        symbol: str,
        pool_strength: int = 2,
        sweep_depth_pct: float = 0.1,
        zone_age_bars: int = 5,
        mtf_structure_summary: str = "",
        ml_score: float = 50.0,
    ) -> AIAnalysis:
        """Score a signal and return an AIAnalysis with a written thesis."""
        score = 50.0
        factors_positive: List[str] = []
        factors_negative: List[str] = []

        # ── R:R quality ──────────────────────────────────────────────────────
        rr = signal.rr_ratio
        if rr >= 5.0:
            score += 15
            factors_positive.append(f"Exceptional R:R of {rr:.1f}:1")
        elif rr >= 3.5:
            score += 8
            factors_positive.append(f"Strong R:R of {rr:.1f}:1")
        elif rr >= 2.5:
            score += 2
        elif rr < 2.0:
            score -= 20
            factors_negative.append(f"Weak R:R of {rr:.1f}:1 — insufficient edge")

        # ── Zone quality ─────────────────────────────────────────────────────
        if signal.zone.has_imbalance:
            score += 10
            factors_positive.append("Zone validated by Fair Value Gap (institutional imbalance)")
        else:
            score -= 8
            factors_negative.append("No FVG imbalance — zone is less reliable")

        if signal.zone.is_extreme:
            score += 10
            factors_positive.append("Extreme zone — furthest from price, highest institutional interest")

        # ── Liquidity pool strength ───────────────────────────────────────────
        if pool_strength >= 4:
            score += 12
            factors_positive.append(f"Strong liquidity pool: {pool_strength} equal-level touches")
        elif pool_strength == 3:
            score += 7
            factors_positive.append(f"Solid liquidity pool: {pool_strength} touches")
        elif pool_strength == 2:
            score += 3
        else:
            score -= 5
            factors_negative.append("Weak liquidity pool — only 1 touch, likely thin stops")

        # ── Sweep conviction ─────────────────────────────────────────────────
        if sweep_depth_pct >= 0.5:
            score += 8
            factors_positive.append(f"Deep liquidity sweep ({sweep_depth_pct:.2f}%) — convincing stop hunt")
        elif sweep_depth_pct >= 0.15:
            score += 3
        else:
            score -= 5
            factors_negative.append(f"Shallow sweep ({sweep_depth_pct:.2f}%) — may be a false break")

        # ── Zone freshness ────────────────────────────────────────────────────
        if zone_age_bars <= 5:
            score += 8
            factors_positive.append("Fresh zone (≤5 bars) — first test, highest probability")
        elif zone_age_bars <= 20:
            score += 3
        elif zone_age_bars > 50:
            score -= 5
            factors_negative.append(f"Stale zone ({zone_age_bars} bars) — may already be absorbed")

        # ── Volatility & regime ───────────────────────────────────────────────
        vol = context.volatility_state
        if vol == "CALM":
            score += 5
            factors_positive.append("Low-volatility environment — tighter spreads, cleaner levels")
        elif vol == "ELEVATED":
            score -= 8
            factors_negative.append("Elevated volatility — widen mental stops, reduce size")
        elif vol == "CRISIS":
            score -= 20
            factors_negative.append("Crisis volatility (VIX spike) — rules break down, avoid directional bets")

        if context.atr_percentile > 80:
            score -= 8
            factors_negative.append(f"ATR at {context.atr_percentile:.0f}th percentile — abnormally wide swings")

        # ── Macro alignment ──────────────────────────────────────────────────
        is_long = signal.signal_type == SignalType.BUY
        spy_bullish = context.spy_trend == "BULLISH"
        spy_bearish = context.spy_trend == "BEARISH"

        if (is_long and spy_bullish) or (not is_long and spy_bearish):
            score += 5
            factors_positive.append(f"SPY trend aligned with trade direction ({context.spy_trend})")
        elif (is_long and spy_bearish) or (not is_long and spy_bullish):
            score -= 10
            factors_negative.append(f"Trading against SPY trend ({context.spy_trend}) — fighting the tape")

        # ── Sector alignment ─────────────────────────────────────────────────
        sec_bullish = context.sector_trend == "BULLISH"
        sec_bearish = context.sector_trend == "BEARISH"
        if (is_long and sec_bullish) or (not is_long and sec_bearish):
            score += 5
            factors_positive.append(f"Sector ({context.sector_etf}) confirming direction")
        elif (is_long and sec_bearish) or (not is_long and sec_bullish):
            score -= 5
            factors_negative.append(f"Sector ({context.sector_etf}) counter-trend")

        # ── ML score ─────────────────────────────────────────────────────────
        if ml_score >= 70:
            score += 5
            factors_positive.append(f"High historical pattern match ({ml_score:.0f}/100)")
        elif ml_score <= 30:
            score -= 5
            factors_negative.append(f"Low historical pattern match ({ml_score:.0f}/100)")

        # ── Instrument trend alignment ────────────────────────────────────────
        instr_aligned = (is_long and context.instrument_trend == "BULLISH") or \
                        (not is_long and context.instrument_trend == "BEARISH")
        if instr_aligned and context.instrument_vs_20ma != 0:
            score += 3
        elif not instr_aligned and context.instrument_trend != "NEUTRAL":
            score -= 5
            factors_negative.append("Instrument's own trend misaligned with trade direction")

        # ── Clamp and classify ────────────────────────────────────────────────
        score = max(0.0, min(100.0, score))
        confidence = int(round(score))

        if confidence >= self.TRADE_THRESHOLD:
            verdict = "TRADE"
        elif confidence >= self.SKIP_THRESHOLD:
            verdict = "WAIT"
        else:
            verdict = "SKIP"

        thesis = self._build_thesis(
            signal, context, symbol, factors_positive, factors_negative,
            rr, pool_strength, is_long,
        )
        concerns = tuple(factors_negative[:3])  # Top 3 concerns
        analyst_notes = self._build_notes(signal, context, verdict)
        size_adj = self._size_adjustment(confidence, context)
        invalidation = self._invalidation_level(signal)

        return AIAnalysis(
            confidence=confidence,
            verdict=verdict,
            thesis=thesis,
            concerns=concerns,
            size_adjustment=size_adj,
            invalidation_level=invalidation,
            analyst_notes=analyst_notes,
            ml_score=ml_score,
            source="heuristic",
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_thesis(
        self,
        signal: Signal,
        context: MarketContext,
        symbol: str,
        positives: List[str],
        negatives: List[str],
        rr: float,
        pool_strength: int,
        is_long: bool,
    ) -> str:
        direction = "long" if is_long else "short"
        zone_label = "demand" if signal.zone.zone_type == ZoneType.DEMAND else "supply"
        bias = signal.narrative.bias.name

        lead = (
            f"{symbol} presents a {direction} opportunity off an {'extreme ' if signal.zone.is_extreme else ''}"
            f"{zone_label} zone at ${signal.zone.low:.4f}–${signal.zone.high:.4f}, "
            f"confirmed by a {pool_strength}-touch liquidity sweep and a {rr:.1f}:1 R:R."
        )

        if positives:
            top_pos = positives[0]
            conf_sent = f"{top_pos}. HTF narrative is {bias}, aligning with the {direction} thesis."
        else:
            conf_sent = f"HTF narrative is {bias}, but confluence is limited."

        if negatives:
            risk_sent = f"Key risk: {negatives[0].lower()}."
        else:
            risk_sent = f"Market conditions are supportive with {context.volatility_state.lower()} volatility."

        return f"{lead} {conf_sent} {risk_sent}"

    def _build_notes(self, signal: Signal, context: MarketContext, verdict: str) -> str:
        if verdict == "SKIP":
            return "Monitor for improved macro conditions before reconsidering this setup."
        if verdict == "WAIT":
            return "Wait for price to close within the zone on LTF before committing capital."
        # TRADE
        is_long = signal.signal_type == SignalType.BUY
        direction_word = "hold above" if is_long else "hold below"
        return (
            f"Watch for LTF {direction_word} zone entry; invalidate if price closes "
            f"beyond stop ${signal.stop_loss:.4f} on a full candle body."
        )

    def _size_adjustment(self, confidence: int, context: MarketContext) -> float:
        if context.volatility_state == "CRISIS":
            return 0.5
        if context.volatility_state == "ELEVATED" or context.atr_percentile > 75:
            if confidence >= 75:
                return 0.75
            return 0.5
        if confidence >= 85:
            return 1.5
        if confidence >= 75:
            return 1.25
        if confidence >= 65:
            return 1.0
        if confidence >= 50:
            return 0.75
        return 0.5

    def _invalidation_level(self, signal: Signal) -> float:
        """Price that structurally invalidates the thesis (beyond stop)."""
        is_long = signal.signal_type == SignalType.BUY
        buffer = signal.risk * 0.5  # Half an R beyond the stop
        if is_long:
            return signal.stop_loss - buffer
        return signal.stop_loss + buffer

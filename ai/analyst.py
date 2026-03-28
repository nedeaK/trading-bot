"""Claude AI analyst — uses the Anthropic API for live trade evaluation.

Calls Claude with a rich context prompt and parses structured JSON back.
Results are cached by signal fingerprint to avoid redundant API calls.

Usage:
    analyst = ClaudeAnalyst(api_key="sk-ant-...")
    analysis = analyst.analyze(signal, context, ltf_candles, symbol="AAPL")
"""

import hashlib
import json
import os
from typing import Dict, List, Optional

from data.models import AIAnalysis, Candle, MarketContext, Signal
from ai.prompts import SYSTEM_PROMPT, ANALYSIS_TEMPLATE
from config.constants import SignalType, ZoneType


class ClaudeAnalyst:
    """Analyst powered by the Claude API (claude-haiku-4-5 for cost efficiency).

    Falls back to HeuristicAnalyst if the API key is missing or the call fails.
    """

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._model = model or os.getenv("CLAUDE_MODEL", self.DEFAULT_MODEL)
        self._cache: Dict[str, AIAnalysis] = {}
        self._client = None  # Lazy init

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
        """Evaluate a signal with Claude. Returns cached result if available."""
        cache_key = self._fingerprint(signal, context, ml_score)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self._api_key:
            return self._fallback(
                signal, context, ltf_candles, symbol,
                pool_strength, sweep_depth_pct, zone_age_bars,
                mtf_structure_summary, ml_score,
                reason="ANTHROPIC_API_KEY not set",
            )

        try:
            result = self._call_api(
                signal, context, ltf_candles, symbol,
                pool_strength, sweep_depth_pct, zone_age_bars,
                mtf_structure_summary, ml_score,
            )
            self._cache[cache_key] = result
            return result
        except Exception as exc:
            return self._fallback(
                signal, context, ltf_candles, symbol,
                pool_strength, sweep_depth_pct, zone_age_bars,
                mtf_structure_summary, ml_score,
                reason=str(exc),
            )

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError as exc:
                raise RuntimeError(
                    "anthropic package not installed. Run: pip install anthropic"
                ) from exc
        return self._client

    def _call_api(
        self,
        signal: Signal,
        context: MarketContext,
        ltf_candles: List[Candle],
        symbol: str,
        pool_strength: int,
        sweep_depth_pct: float,
        zone_age_bars: int,
        mtf_structure_summary: str,
        ml_score: float,
    ) -> AIAnalysis:
        is_long = signal.signal_type == SignalType.BUY
        recent = self._format_candles(ltf_candles[-5:] if ltf_candles else [])
        atr_pct = (context.atr / signal.entry_price * 100) if signal.entry_price else 0

        vix = context.vix_level
        if vix == 0:
            vix_note = "unavailable"
        elif vix < 15:
            vix_note = "very low — complacency zone"
        elif vix < 20:
            vix_note = "low — calm market"
        elif vix < 30:
            vix_note = "elevated — caution warranted"
        else:
            vix_note = "high — fear / risk-off environment"

        prompt = ANALYSIS_TEMPLATE.format(
            symbol=symbol,
            direction="LONG / BUY" if is_long else "SHORT / SELL",
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            rr_ratio=signal.rr_ratio,
            zone_type="DEMAND" if signal.zone.zone_type == ZoneType.DEMAND else "SUPPLY",
            has_imbalance=signal.zone.has_imbalance,
            is_extreme=signal.zone.is_extreme,
            htf_bias=signal.narrative.bias.name,
            trend_regime=context.trend_regime,
            volatility_state=context.volatility_state,
            vix_level=vix,
            vix_note=vix_note,
            atr=context.atr,
            atr_pct=atr_pct,
            atr_percentile=context.atr_percentile,
            spy_trend=context.spy_trend,
            spy_vs_ma=context.spy_vs_20ma,
            sector_etf=context.sector_etf,
            sector_trend=context.sector_trend,
            sector_vs_ma=context.sector_vs_20ma,
            instrument_trend=context.instrument_trend,
            instrument_vs_ma=context.instrument_vs_20ma,
            pool_strength=pool_strength,
            sweep_depth_pct=sweep_depth_pct,
            zone_age_bars=zone_age_bars,
            mtf_structure=mtf_structure_summary or "N/A",
            recent_candles=recent,
            ml_score=ml_score,
        )

        client = self._get_client()
        message = client.messages.create(
            model=self._model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        return self._parse_response(raw, signal, ml_score)

    def _parse_response(self, raw: str, signal: Signal, ml_score: float) -> AIAnalysis:
        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        data = json.loads(raw)

        confidence = max(0, min(100, int(data.get("confidence", 50))))
        verdict = data.get("verdict", "WAIT").upper()
        if verdict not in ("TRADE", "SKIP", "WAIT"):
            verdict = "WAIT"

        concerns_raw = data.get("concerns", [])
        concerns = tuple(str(c) for c in concerns_raw[:5])

        size_adj = float(data.get("size_adjustment", 1.0))
        size_adj = max(0.5, min(1.5, size_adj))

        inv_raw = data.get("invalidation_level")
        if inv_raw is not None:
            try:
                invalidation = float(inv_raw)
            except (TypeError, ValueError):
                invalidation = signal.stop_loss
        else:
            invalidation = signal.stop_loss

        return AIAnalysis(
            confidence=confidence,
            verdict=verdict,
            thesis=str(data.get("thesis", "")),
            concerns=concerns,
            size_adjustment=size_adj,
            invalidation_level=invalidation,
            analyst_notes=str(data.get("analyst_notes", "")),
            ml_score=ml_score,
            source="claude",
        )

    def _fallback(
        self,
        signal: Signal,
        context: MarketContext,
        ltf_candles: List[Candle],
        symbol: str,
        pool_strength: int,
        sweep_depth_pct: float,
        zone_age_bars: int,
        mtf_structure_summary: str,
        ml_score: float,
        reason: str = "",
    ) -> AIAnalysis:
        """Fall back to heuristic analyst on error or missing API key."""
        from ai.heuristic_analyst import HeuristicAnalyst
        result = HeuristicAnalyst().analyze(
            signal, context, ltf_candles, symbol,
            pool_strength, sweep_depth_pct, zone_age_bars,
            mtf_structure_summary, ml_score,
        )
        # Keep source tag to show it was a fallback
        return AIAnalysis(
            confidence=result.confidence,
            verdict=result.verdict,
            thesis=result.thesis,
            concerns=result.concerns,
            size_adjustment=result.size_adjustment,
            invalidation_level=result.invalidation_level,
            analyst_notes=result.analyst_notes,
            ml_score=result.ml_score,
            source=f"heuristic_fallback({reason[:60]})" if reason else "heuristic_fallback",
        )

    @staticmethod
    def _fingerprint(signal: Signal, context: MarketContext, ml_score: float) -> str:
        key = (
            f"{signal.entry_price:.6f}|{signal.stop_loss:.6f}|{signal.take_profit:.6f}"
            f"|{context.volatility_state}|{context.spy_trend}|{ml_score:.1f}"
        )
        return hashlib.md5(key.encode()).hexdigest()

    @staticmethod
    def _format_candles(candles: List[Candle]) -> str:
        if not candles:
            return "  (no candle data)"
        rows = []
        for c in candles:
            direction = "▲" if c.is_bullish else "▼"
            rows.append(
                f"  {c.timestamp.strftime('%Y-%m-%d %H:%M')} "
                f"O:{c.open:.4f} H:{c.high:.4f} L:{c.low:.4f} C:{c.close:.4f} "
                f"Vol:{c.volume:.0f} {direction}"
            )
        return "\n".join(rows)

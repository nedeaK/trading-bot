"""Trade journal — structured JSONL log of every AI trade decision.

Every signal evaluated (TRADE, WAIT, or SKIP) gets a record with:
- The full AI analysis (thesis, confidence, concerns)
- Extracted ML feature vector (for future retraining)
- Outcome field (filled in later: WIN/LOSS/EXPIRED/CANCELLED)

This is the foundation of the bot's self-improvement loop:
once enough trades have outcomes, run `python -m ml.trainer` to
retrain the ML scorer on real results.

File format: newline-delimited JSON (JSONL) — one record per line.
"""

import json
import os
from datetime import datetime
from typing import List, Optional

from data.models import AIAnalysis, Candle, MarketContext, Signal
from ml.features import extract_features


DEFAULT_JOURNAL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "memory", "trades.jsonl"
)


class TradeJournal:
    """Append-only JSONL log for trade signals and outcomes."""

    def __init__(self, path: Optional[str] = None):
        self._path = path or DEFAULT_JOURNAL_PATH
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def log_signal(
        self,
        signal: Signal,
        ai_analysis: AIAnalysis,
        context: MarketContext,
        ltf_candles: List[Candle],
        symbol: str,
        pool_strength: int = 2,
        sweep_depth_pct: float = 0.1,
        zone_age_bars: int = 5,
        final_risk_pct: float = 0.02,
    ) -> str:
        """Write a new signal entry. Returns the trade_id for later update."""
        trade_id = self._make_id(signal, symbol)
        features = extract_features(
            signal, context, ltf_candles,
            pool_strength, sweep_depth_pct, zone_age_bars,
        )

        record = {
            "trade_id": trade_id,
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "direction": signal.signal_type.name,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "rr_ratio": round(signal.rr_ratio, 3),
            "final_risk_pct": final_risk_pct,
            # AI analysis
            "verdict": ai_analysis.verdict,
            "confidence": ai_analysis.confidence,
            "ml_score": ai_analysis.ml_score,
            "thesis": ai_analysis.thesis,
            "concerns": list(ai_analysis.concerns),
            "size_adjustment": ai_analysis.size_adjustment,
            "invalidation_level": ai_analysis.invalidation_level,
            "analyst_notes": ai_analysis.analyst_notes,
            "ai_source": ai_analysis.source,
            # Market context snapshot
            "context": {
                "volatility_state": context.volatility_state,
                "atr": context.atr,
                "atr_percentile": context.atr_percentile,
                "trend_regime": context.trend_regime,
                "spy_trend": context.spy_trend,
                "vix_level": context.vix_level,
                "sector_etf": context.sector_etf,
                "sector_trend": context.sector_trend,
            },
            # ML features (for retraining)
            "features": features,
            # Outcome — filled in later via record_outcome()
            "outcome": None,
            "exit_price": None,
            "exit_timestamp": None,
            "pnl_r": None,
        }

        self._append(record)
        return trade_id

    def record_outcome(
        self,
        trade_id: str,
        outcome: str,         # "WIN" | "LOSS" | "EXPIRED" | "CANCELLED"
        exit_price: float,
        exit_timestamp: Optional[str] = None,
        pnl_r: Optional[float] = None,
    ) -> bool:
        """Update a logged signal with its final outcome.

        Rewrites the matching line in-place (reads full file, updates, rewrites).
        Returns True if the trade_id was found and updated.
        """
        if not os.path.exists(self._path):
            return False

        updated = False
        lines: List[str] = []

        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if record.get("trade_id") == trade_id:
                        record["outcome"] = outcome
                        record["exit_price"] = exit_price
                        record["exit_timestamp"] = exit_timestamp or datetime.utcnow().isoformat()
                        if pnl_r is not None:
                            record["pnl_r"] = round(pnl_r, 3)
                        updated = True
                    lines.append(json.dumps(record))
                except json.JSONDecodeError:
                    lines.append(line)

        if updated:
            with open(self._path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

        return updated

    def summary(self) -> dict:
        """Return aggregate statistics across all logged trades."""
        records = self._load_all()
        total = len(records)
        resolved = [r for r in records if r.get("outcome") in ("WIN", "LOSS")]
        wins = [r for r in resolved if r.get("outcome") == "WIN"]
        skipped = [r for r in records if r.get("verdict") == "SKIP"]

        win_rate = len(wins) / len(resolved) if resolved else 0.0
        avg_confidence_trade = (
            sum(r["confidence"] for r in records if r.get("verdict") == "TRADE") /
            max(1, sum(1 for r in records if r.get("verdict") == "TRADE"))
        )
        pnl_r_values = [r["pnl_r"] for r in resolved if r.get("pnl_r") is not None]
        avg_pnl_r = sum(pnl_r_values) / len(pnl_r_values) if pnl_r_values else 0.0

        return {
            "total_logged": total,
            "total_resolved": len(resolved),
            "win_rate": round(win_rate, 4),
            "wins": len(wins),
            "losses": len(resolved) - len(wins),
            "skipped_by_ai": len(skipped),
            "avg_confidence_on_trades": round(avg_confidence_trade, 1),
            "avg_pnl_r": round(avg_pnl_r, 3),
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _append(self, record: dict) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _load_all(self) -> list:
        if not os.path.exists(self._path):
            return []
        records = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    @staticmethod
    def _make_id(signal: Signal, symbol: str) -> str:
        ts = signal.timestamp.strftime("%Y%m%d%H%M%S")
        price = int(signal.entry_price * 10000)
        return f"{symbol}_{ts}_{price}_{signal.signal_type.name}"

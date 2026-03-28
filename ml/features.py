"""Feature engineering for ML signal scoring.

Extracts a fixed-length numeric feature vector from a Signal + context.
These features capture everything an analyst would look at: setup quality,
zone characteristics, market conditions, and technical pattern properties.

Feature vector is returned as a plain list[float] so it works with any
sklearn-compatible estimator without extra dependencies.
"""

from typing import Dict, List

from data.models import Candle, MarketContext, Signal
from config.constants import SignalType, ZoneType


def extract_features(
    signal: Signal,
    context: MarketContext,
    ltf_candles: List[Candle],
    pool_strength: int = 2,
    sweep_depth_pct: float = 0.1,
    zone_age_bars: int = 5,
) -> List[float]:
    """Extract a 30-feature numeric vector for ML scoring.

    All features are normalized to comparable scales so tree-based
    and distance-based models work without separate scaling.
    """
    c = signal
    z = signal.zone
    n = signal.narrative
    ctx = context

    # ── Signal / R:R features (0-4) ──────────────────────────────────────────
    f0 = min(c.rr_ratio / 10.0, 1.0)                  # R:R capped at 10
    f1 = 1.0 if c.signal_type == SignalType.BUY else 0.0  # direction
    f2 = min(c.risk / (c.entry_price + 1e-9), 0.1) * 10  # risk as % of entry (0-1 range)
    f3 = 1.0 if z.has_imbalance else 0.0               # FVG present
    f4 = 1.0 if z.is_extreme else 0.0                  # zone is extreme

    # ── Zone features (5-9) ──────────────────────────────────────────────────
    f5 = min(z.size / (c.entry_price + 1e-9) * 100, 5.0) / 5.0  # zone width %
    f6 = min(zone_age_bars / 100.0, 1.0)               # zone age (normalised)
    f7 = min(pool_strength / 5.0, 1.0)                 # pool strength
    f8 = min(sweep_depth_pct / 2.0, 1.0)               # sweep depth %
    f9 = 1.0 if z.tap_count == 0 else 0.0              # first tap

    # ── Candle-based features from LTF (10-17) ────────────────────────────────
    recent = ltf_candles[-10:] if ltf_candles else []
    if recent:
        last = recent[-1]
        f10 = last.body_to_range_ratio                          # indecision at entry
        f11 = last.lower_wick / (last.total_range + 1e-9)      # lower wick dominance
        f12 = last.upper_wick / (last.total_range + 1e-9)      # upper wick dominance
        f13 = 1.0 if last.is_bullish else 0.0                  # last candle direction

        # Average body size ratio over recent candles
        avg_btr = sum(c_.body_to_range_ratio for c_ in recent) / len(recent)
        f14 = avg_btr

        # Momentum: close vs open of 5 candles ago
        if len(recent) >= 5:
            start_price = recent[-5].open
            end_price = recent[-1].close
            f15 = min(max((end_price - start_price) / (start_price + 1e-9), -0.1), 0.1) * 10
        else:
            f15 = 0.0

        # Range expansion: last candle range vs 5-candle avg
        if len(recent) >= 2:
            avg_range = sum(c_.total_range for c_ in recent[:-1]) / (len(recent) - 1)
            f16 = min(last.total_range / (avg_range + 1e-9), 3.0) / 3.0
        else:
            f16 = 0.5

        f17 = min(last.volume / (sum(c_.volume for c_ in recent) / len(recent) + 1e-9), 3.0) / 3.0
    else:
        f10 = f11 = f12 = f13 = f14 = f15 = f16 = f17 = 0.5

    # ── Volatility & regime features (18-22) ─────────────────────────────────
    vol_map = {"CALM": 0.0, "NORMAL": 0.33, "ELEVATED": 0.67, "CRISIS": 1.0}
    f18 = vol_map.get(ctx.volatility_state, 0.33)
    f19 = ctx.atr_percentile / 100.0
    regime_map = {"TRENDING": 1.0, "TRANSITIONING": 0.5, "RANGING": 0.0}
    f20 = regime_map.get(ctx.trend_regime, 0.5)
    f21 = min(max(ctx.spy_vs_20ma / 10.0, -1.0), 1.0) * 0.5 + 0.5    # centered 0-1
    f22 = min(max(ctx.sector_vs_20ma / 10.0, -1.0), 1.0) * 0.5 + 0.5

    # ── Trend alignment features (23-26) ─────────────────────────────────────
    is_long = c.signal_type == SignalType.BUY
    trend_val = {"BULLISH": 1.0, "NEUTRAL": 0.5, "BEARISH": 0.0}

    spy_tv = trend_val.get(ctx.spy_trend, 0.5)
    f23 = spy_tv if is_long else (1.0 - spy_tv)             # SPY aligned with trade

    sec_tv = trend_val.get(ctx.sector_trend, 0.5)
    f24 = sec_tv if is_long else (1.0 - sec_tv)             # sector aligned

    instr_tv = trend_val.get(ctx.instrument_trend, 0.5)
    f25 = instr_tv if is_long else (1.0 - instr_tv)         # instrument aligned

    f26 = ctx.vix_level / 80.0 if ctx.vix_level > 0 else 0.2  # VIX (capped at 80)

    # ── Narrative features (27-29) ────────────────────────────────────────────
    from config.constants import BiasDirection
    bias_aligned = (
        (n.bias == BiasDirection.LONG and is_long) or
        (n.bias == BiasDirection.SHORT and not is_long)
    )
    f27 = 1.0 if bias_aligned else 0.0                      # HTF bias aligned
    f28 = 1.0 if n.htf_supply_zone is not None else 0.0     # supply target exists
    f29 = 1.0 if n.htf_demand_zone is not None else 0.0     # demand target exists

    return [
        f0, f1, f2, f3, f4,
        f5, f6, f7, f8, f9,
        f10, f11, f12, f13, f14,
        f15, f16, f17, f18, f19,
        f20, f21, f22, f23, f24,
        f25, f26, f27, f28, f29,
    ]


FEATURE_NAMES = [
    "rr_ratio_norm", "is_long", "risk_pct", "has_fvg", "is_extreme",
    "zone_width_pct", "zone_age_norm", "pool_strength_norm", "sweep_depth_norm", "first_tap",
    "last_candle_btr", "lower_wick_dom", "upper_wick_dom", "last_candle_bullish", "avg_btr",
    "5bar_momentum", "range_expansion", "vol_ratio", "volatility_state", "atr_percentile",
    "regime", "spy_vs_ma_norm", "sector_vs_ma_norm", "spy_aligned", "sector_aligned",
    "instr_aligned", "vix_norm", "htf_bias_aligned", "has_supply_target", "has_demand_target",
]

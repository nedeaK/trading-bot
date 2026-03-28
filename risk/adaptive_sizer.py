"""Adaptive position sizer — regime-aware risk management.

Replaces the fixed 2% / 20%-cap model with a system that:
- Scales risk% with volatility state and ATR percentile
- Applies the AI analyst's size_adjustment multiplier
- Enforces hard caps on individual and total portfolio risk

Senior analyst logic:
  "Bet big when conditions are pristine. Bet small when the environment
   is uncertain or hostile. Never risk the same amount in a VIX-40 crisis
   as in a calm trending market."
"""

from dataclasses import dataclass

from data.models import AIAnalysis, MarketContext
from config.settings import RiskConfig


@dataclass
class SizeResult:
    """Output of the adaptive sizer."""
    risk_percent: float          # Adjusted risk % of equity
    size_adjustment_applied: float
    reasoning: str


def adaptive_risk_percent(
    base_risk: float,
    context: MarketContext,
    ai_analysis: AIAnalysis,
    risk_config: RiskConfig,
) -> SizeResult:
    """Compute the final risk % of equity to use for a trade.

    Adjustment cascade:
    1. Start with base_risk (from RiskConfig, default 2%)
    2. Apply volatility regime scaling
    3. Apply ATR percentile scaling
    4. Apply AI analyst size_adjustment multiplier
    5. Clamp to hard max

    Args:
        base_risk: Configured base risk percent (e.g. 0.02).
        context: Current market context (vol state, ATR percentile).
        ai_analysis: AI analyst output with size_adjustment field.
        risk_config: Risk configuration limits.

    Returns:
        SizeResult with final risk percent and reasoning.
    """
    risk = base_risk
    notes: list[str] = []

    # ── Step 1: Volatility regime scaling ────────────────────────────────────
    vol = context.volatility_state
    if vol == "CALM":
        vol_scalar = 1.0
    elif vol == "NORMAL":
        vol_scalar = 1.0
    elif vol == "ELEVATED":
        vol_scalar = 0.75
        notes.append("Elevated volatility → 75% of base risk")
    else:  # CRISIS
        vol_scalar = 0.40
        notes.append("Crisis volatility → 40% of base risk")
    risk *= vol_scalar

    # ── Step 2: ATR percentile fine-tuning ────────────────────────────────────
    atr_pct = context.atr_percentile
    if atr_pct >= 85:
        atr_scalar = 0.75
        notes.append(f"ATR at {atr_pct:.0f}th percentile → additional 25% reduction")
    elif atr_pct >= 70:
        atr_scalar = 0.90
        notes.append(f"ATR at {atr_pct:.0f}th percentile → 10% reduction")
    else:
        atr_scalar = 1.0
    risk *= atr_scalar

    # ── Step 3: AI analyst judgment ──────────────────────────────────────────
    ai_scalar = ai_analysis.size_adjustment
    if ai_scalar != 1.0:
        direction = "increase" if ai_scalar > 1.0 else "decrease"
        notes.append(f"AI analyst size {direction} (×{ai_scalar:.2f})")
    risk *= ai_scalar

    # ── Step 4: Hard cap ─────────────────────────────────────────────────────
    max_risk = risk_config.max_position_size * 0.10  # Max 10% of max_pos_size
    # Also enforce that risk is not more than 2× base (don't over-leverage)
    absolute_max = base_risk * 1.5
    risk = min(risk, max_risk, absolute_max)

    # Also enforce minimum (0.25% — always some skin in game if verdict is TRADE)
    risk = max(risk, 0.0025)

    reasoning = f"base={base_risk*100:.1f}%"
    if notes:
        reasoning += " → " + " → ".join(notes)
    reasoning += f" → final={risk*100:.2f}%"

    return SizeResult(
        risk_percent=round(risk, 5),
        size_adjustment_applied=ai_scalar,
        reasoning=reasoning,
    )


def atr_adjusted_stop(
    entry_price: float,
    is_long: bool,
    atr: float,
    multiplier: float = 1.5,
) -> float:
    """Compute an ATR-based stop loss.

    More adaptive than a fixed percentage — widens in volatile conditions,
    tightens in calm ones, keeping the trade room to breathe.

    Args:
        entry_price: Limit entry price.
        is_long: True for buy signals.
        atr: Current ATR value.
        multiplier: ATR multiplier (default 1.5×).

    Returns:
        Stop loss price.
    """
    buffer = atr * multiplier
    return entry_price - buffer if is_long else entry_price + buffer

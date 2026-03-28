"""Immutable data models for the SMC Trading Bot.

All models use frozen dataclasses to prevent mutation.
Functions that transform data return new instances.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from config.constants import (
    BiasDirection,
    LiquidityType,
    SignalType,
    StructureType,
    SwingType,
    TrendType,
    ZoneType,
)


class VerdictType(Enum):
    """AI analyst verdict on a trade signal."""
    TRADE = "TRADE"   # High conviction — enter now
    WAIT = "WAIT"     # Setup forming but not ready
    SKIP = "SKIP"     # Red flags — pass on this setup


@dataclass(frozen=True)
class Candle:
    """A single OHLCV candle."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def total_range(self) -> float:
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_to_range_ratio(self) -> float:
        if self.total_range == 0:
            return 0.0
        return self.body_size / self.total_range

    @classmethod
    def from_tuple(cls, data: tuple) -> "Candle":
        """Create a Candle from (timestamp, open, high, low, close, volume)."""
        return cls(
            timestamp=data[0],
            open=data[1],
            high=data[2],
            low=data[3],
            close=data[4],
            volume=data[5] if len(data) > 5 else 0.0,
        )


@dataclass(frozen=True)
class SwingPoint:
    """A detected swing high or swing low."""
    index: int
    timestamp: datetime
    price: float
    swing_type: SwingType


@dataclass(frozen=True)
class StructurePoint:
    """A swing point classified within market structure."""
    swing: SwingPoint
    structure_type: StructureType


@dataclass(frozen=True)
class Zone:
    """A supply or demand zone."""
    zone_type: ZoneType
    high: float
    low: float
    creation_index: int
    creation_timestamp: datetime
    has_imbalance: bool
    is_extreme: bool = False
    tap_count: int = 0

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2

    @property
    def size(self) -> float:
        return self.high - self.low

    @property
    def is_valid(self) -> bool:
        """Zone is valid if it has imbalance and hasn't been tapped."""
        return self.has_imbalance and self.tap_count == 0


def zone_with_tap(zone: Zone) -> Zone:
    """Return a new Zone with tap_count incremented."""
    return Zone(
        zone_type=zone.zone_type,
        high=zone.high,
        low=zone.low,
        creation_index=zone.creation_index,
        creation_timestamp=zone.creation_timestamp,
        has_imbalance=zone.has_imbalance,
        is_extreme=zone.is_extreme,
        tap_count=zone.tap_count + 1,
    )


def zone_as_extreme(zone: Zone) -> Zone:
    """Return a new Zone marked as extreme."""
    return Zone(
        zone_type=zone.zone_type,
        high=zone.high,
        low=zone.low,
        creation_index=zone.creation_index,
        creation_timestamp=zone.creation_timestamp,
        has_imbalance=zone.has_imbalance,
        is_extreme=True,
        tap_count=zone.tap_count,
    )


@dataclass(frozen=True)
class LiquidityPool:
    """A cluster of equal highs or equal lows where liquidity accumulates."""
    pool_type: LiquidityType
    price: float
    swing_indices: Tuple[int, ...]
    swept: bool = False

    @property
    def strength(self) -> int:
        """Number of touches forming this pool."""
        return len(self.swing_indices)


def pool_as_swept(pool: LiquidityPool) -> LiquidityPool:
    """Return a new LiquidityPool marked as swept."""
    return LiquidityPool(
        pool_type=pool.pool_type,
        price=pool.price,
        swing_indices=pool.swing_indices,
        swept=True,
    )


@dataclass(frozen=True)
class Narrative:
    """HTF narrative - the directional bias from weekly/daily analysis."""
    bias: BiasDirection
    htf_demand_zone: Optional[Zone] = None
    htf_supply_zone: Optional[Zone] = None

    @property
    def target_zone(self) -> Optional[Zone]:
        """The zone price is heading toward."""
        if self.bias == BiasDirection.LONG:
            return self.htf_supply_zone
        elif self.bias == BiasDirection.SHORT:
            return self.htf_demand_zone
        return None


@dataclass(frozen=True)
class TrendContext:
    """MTF trend context confirming HTF narrative."""
    trend: TrendType
    structure_points: Tuple[StructurePoint, ...]
    latest_bos_index: Optional[int] = None


@dataclass(frozen=True)
class LiquiditySetup:
    """Equal highs/lows spotted within the trend - liquidity is building."""
    pool: LiquidityPool
    trend_context: TrendContext


@dataclass(frozen=True)
class SweepEvent:
    """A liquidity sweep has occurred."""
    sweep_index: int
    sweep_price: float
    pool: LiquidityPool
    sweep_candle_timestamp: datetime


@dataclass(frozen=True)
class Signal:
    """A trade signal with entry, stop, and target."""
    signal_type: SignalType
    timestamp: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    zone: Zone
    narrative: Narrative
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def risk(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward(self) -> float:
        return abs(self.take_profit - self.entry_price)

    @property
    def rr_ratio(self) -> float:
        if self.risk == 0:
            return 0.0
        return self.reward / self.risk


@dataclass(frozen=True)
class MarketContext:
    """Aggregated market-wide context used by the AI analyst."""
    atr: float                    # Average True Range (14-period)
    atr_percentile: float         # 0-100 vs trailing 252 days
    volatility_state: str         # "CALM" | "NORMAL" | "ELEVATED" | "CRISIS"
    trend_regime: str             # "TRENDING" | "RANGING" | "TRANSITIONING"
    spy_trend: str                # "BULLISH" | "BEARISH" | "NEUTRAL"
    spy_vs_20ma: float            # % price is above/below SPY 20-day MA
    vix_level: float              # VIX close (0.0 if unavailable)
    sector_etf: str               # e.g. "XLK", "XLF"
    sector_trend: str             # "BULLISH" | "BEARISH" | "NEUTRAL"
    sector_vs_20ma: float         # % price is above/below sector 20-day MA
    instrument_trend: str         # Trend of the traded instrument itself
    instrument_vs_20ma: float     # % above/below instrument 20-day MA


@dataclass(frozen=True)
class AIAnalysis:
    """Result of the AI analyst evaluation of a trade signal."""
    confidence: int               # 0-100 composite conviction score
    verdict: str                  # "TRADE" | "SKIP" | "WAIT"
    thesis: str                   # Written rationale (2-3 sentences)
    concerns: Tuple[str, ...]     # List of identified risk factors
    size_adjustment: float        # Multiplier on base risk% (0.5–1.5)
    invalidation_level: float     # Price at which thesis is wrong
    analyst_notes: str            # Post-entry monitoring note
    ml_score: float               # 0-100 from ML pattern scorer
    source: str = "heuristic"     # "claude" | "heuristic" | "ml_only"

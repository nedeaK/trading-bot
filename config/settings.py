"""Configuration for the SMC Trading Bot."""

from dataclasses import dataclass, field
from typing import Optional

from config.constants import (
    DEFAULT_COMMISSION,
    DEFAULT_IMPULSE_MULTIPLIER,
    DEFAULT_INITIAL_BALANCE,
    DEFAULT_LIQUIDITY_TOLERANCE,
    DEFAULT_MAX_POSITION_SIZE,
    DEFAULT_RISK_PERCENT,
    DEFAULT_RR_RATIO,
    DEFAULT_SLIPPAGE,
    DEFAULT_STOP_BUFFER,
    DEFAULT_SWING_WINDOW,
    DEFAULT_ZONE_INDECISION_THRESHOLD,
    Timeframe,
)


@dataclass(frozen=True)
class TimeframeConfig:
    """Configuration for multi-timeframe analysis."""
    htf: Timeframe = Timeframe.D1
    mtf: Timeframe = Timeframe.H1
    ltf: Timeframe = Timeframe.M15


@dataclass(frozen=True)
class SMCConfig:
    """SMC detection parameters."""
    swing_window: int = DEFAULT_SWING_WINDOW
    liquidity_tolerance: float = DEFAULT_LIQUIDITY_TOLERANCE
    zone_indecision_threshold: float = DEFAULT_ZONE_INDECISION_THRESHOLD
    impulse_multiplier: float = DEFAULT_IMPULSE_MULTIPLIER


@dataclass(frozen=True)
class RiskConfig:
    """Risk management parameters."""
    risk_percent: float = DEFAULT_RISK_PERCENT
    default_rr_ratio: float = DEFAULT_RR_RATIO
    stop_buffer: float = DEFAULT_STOP_BUFFER
    max_position_size: float = DEFAULT_MAX_POSITION_SIZE


@dataclass(frozen=True)
class BacktestConfig:
    """Backtesting parameters."""
    initial_balance: float = DEFAULT_INITIAL_BALANCE
    slippage: float = DEFAULT_SLIPPAGE
    commission: float = DEFAULT_COMMISSION


@dataclass(frozen=True)
class Config:
    """Top-level configuration combining all settings."""
    symbol: str = "SPY"
    start_date: str = "2020-01-01"
    end_date: str = "2024-12-31"
    timeframes: TimeframeConfig = field(default_factory=TimeframeConfig)
    smc: SMCConfig = field(default_factory=SMCConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

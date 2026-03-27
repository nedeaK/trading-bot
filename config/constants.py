"""Enums and constants for the SMC Trading Bot."""

from enum import Enum, auto


class SwingType(Enum):
    HIGH = auto()
    LOW = auto()


class StructureType(Enum):
    HH = auto()  # Higher High
    HL = auto()  # Higher Low
    LL = auto()  # Lower Low
    LH = auto()  # Lower High


class TrendType(Enum):
    BULLISH = auto()
    BEARISH = auto()
    CONSOLIDATION = auto()


class ZoneType(Enum):
    SUPPLY = auto()
    DEMAND = auto()


class SignalType(Enum):
    BUY = auto()
    SELL = auto()


class LiquidityType(Enum):
    EQUAL_HIGHS = auto()
    EQUAL_LOWS = auto()


class BiasDirection(Enum):
    """HTF narrative bias direction."""
    LONG = auto()   # Look for buys
    SHORT = auto()  # Look for sells
    NEUTRAL = auto()  # No clear bias


class Timeframe(Enum):
    """Standard timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1wk"
    MN = "1mo"


# Default SMC detection parameters
DEFAULT_SWING_WINDOW = 5
DEFAULT_LIQUIDITY_TOLERANCE = 0.001  # 0.1%
DEFAULT_ZONE_INDECISION_THRESHOLD = 0.5  # body/total ratio
DEFAULT_IMPULSE_MULTIPLIER = 2.0  # impulse vs avg candle size
DEFAULT_IMBALANCE_MIN_GAP = 0.0

# Default risk parameters
DEFAULT_RISK_PERCENT = 0.02  # 2% per trade
DEFAULT_RR_RATIO = 5.0  # 1:5 reward:risk
DEFAULT_STOP_BUFFER = 0.001  # 0.1% buffer beyond zone
DEFAULT_MAX_POSITION_SIZE = 0.2  # 20% max in single position

# Default backtest parameters
DEFAULT_INITIAL_BALANCE = 100_000.0
DEFAULT_SLIPPAGE = 0.0001  # 0.01%
DEFAULT_COMMISSION = 0.0

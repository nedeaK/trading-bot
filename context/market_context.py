"""Market context aggregator.

Builds a MarketContext from available data:
- In backtest mode: derives everything from HTF candles of the instrument +
  optionally pre-fetched SPY/VIX candles.
- In live mode: fetches SPY and VIX via yfinance, caches results for
  the session to avoid redundant network calls.

The sector ETF is inferred from a symbol map; unknown symbols default to SPY.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from data.models import Candle, MarketContext
from context.regime_detector import (
    compute_atr,
    detect_regime,
    detect_trend_from_candles,
    detect_volatility_state,
)

logger = logging.getLogger(__name__)

# ── Sector ETF lookup ─────────────────────────────────────────────────────────

SECTOR_MAP: Dict[str, str] = {
    # Tech
    "AAPL": "XLK", "MSFT": "XLK", "GOOGL": "XLK", "GOOG": "XLK",
    "META": "XLK", "NVDA": "XLK", "AMD": "XLK", "INTC": "XLK",
    "CRM": "XLK", "ADBE": "XLK", "ORCL": "XLK", "QCOM": "XLK",
    # Consumer discretionary
    "AMZN": "XLY", "TSLA": "XLY", "HD": "XLY", "MCD": "XLY",
    # Financials
    "JPM": "XLF", "BAC": "XLF", "GS": "XLF", "MS": "XLF",
    "WFC": "XLF", "BLK": "XLF", "AXP": "XLF",
    # Healthcare
    "JNJ": "XLV", "PFE": "XLV", "UNH": "XLV", "ABBV": "XLV",
    "MRK": "XLV", "LLY": "XLV",
    # Energy
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE", "SLB": "XLE",
    # Industrials
    "BA": "XLI", "CAT": "XLI", "GE": "XLI", "HON": "XLI",
    # Crypto (use own ETF or BTC as benchmark)
    "BTC": "BTC-USD", "ETH": "ETH-USD",
    "BTC-USD": "BTC-USD", "ETH-USD": "ETH-USD",
    # Indices / ETFs (use themselves as sector)
    "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM", "DIA": "DIA",
}


def _infer_sector_etf(symbol: str) -> str:
    base = symbol.upper().split("/")[0]
    return SECTOR_MAP.get(base, "SPY")


# ── Simple candle cache for live data fetches ──────────────────────────────────

_live_cache: Dict[str, List[Candle]] = {}
_live_cache_ts: Dict[str, datetime] = {}
_CACHE_TTL_MINUTES = 60


def _fetch_candles_live(ticker: str, period: str = "1y", interval: str = "1d") -> List[Candle]:
    """Fetch candles via yfinance for live context. Cached for 60 minutes."""
    cache_key = f"{ticker}_{period}_{interval}"
    now = datetime.now()

    if cache_key in _live_cache:
        age = (now - _live_cache_ts.get(cache_key, datetime.min)).total_seconds() / 60
        if age < _CACHE_TTL_MINUTES:
            return _live_cache[cache_key]

    try:
        import yfinance as yf
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty:
            return []
        candles: List[Candle] = []
        for ts, row in df.iterrows():
            candles.append(Candle(
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0)),
            ))
        _live_cache[cache_key] = candles
        _live_cache_ts[cache_key] = now
        return candles
    except Exception as exc:
        logger.warning("Failed to fetch live candles for %s: %s", ticker, exc)
        return []


# ── Public builder ─────────────────────────────────────────────────────────────

def build_market_context(
    symbol: str,
    instrument_candles: List[Candle],
    spy_candles: Optional[List[Candle]] = None,
    vix_candles: Optional[List[Candle]] = None,
    live_mode: bool = False,
) -> MarketContext:
    """Build a MarketContext from available candle data.

    Args:
        symbol: Traded instrument ticker.
        instrument_candles: HTF or daily candles for the instrument itself.
        spy_candles: SPY daily candles. Fetched if live_mode=True and None.
        vix_candles: VIX daily candles. Fetched if live_mode=True and None.
        live_mode: If True, fetch missing SPY/VIX data via yfinance.

    Returns:
        MarketContext with all fields populated.
    """
    sector_etf = _infer_sector_etf(symbol)

    # ── Instrument self-analysis ───────────────────────────────────────────────
    atr = compute_atr(instrument_candles, period=14)
    vol_state, atr_pct = detect_volatility_state(instrument_candles)
    regime = detect_regime(instrument_candles)
    instr_trend, instr_vs_ma = detect_trend_from_candles(instrument_candles, period=20)

    # ── SPY context ───────────────────────────────────────────────────────────
    if spy_candles is None and live_mode:
        spy_candles = _fetch_candles_live("SPY")
    if not spy_candles:
        spy_candles = instrument_candles  # Best-effort fallback

    spy_trend, spy_vs_ma = detect_trend_from_candles(spy_candles, period=20)

    # ── VIX ───────────────────────────────────────────────────────────────────
    if vix_candles is None and live_mode:
        vix_candles = _fetch_candles_live("^VIX")
    vix_level = vix_candles[-1].close if vix_candles else 0.0

    # Upgrade volatility state if VIX is available and signals danger
    if vix_level >= 35 and vol_state != "CRISIS":
        vol_state = "CRISIS"
    elif vix_level >= 25 and vol_state == "CALM":
        vol_state = "ELEVATED"

    # ── Sector context ────────────────────────────────────────────────────────
    sector_candles: Optional[List[Candle]] = None
    if live_mode and sector_etf not in (symbol.upper(), "SPY"):
        sector_candles = _fetch_candles_live(sector_etf)

    if sector_candles:
        sector_trend, sector_vs_ma = detect_trend_from_candles(sector_candles, period=20)
    elif sector_etf == symbol.upper():
        sector_trend, sector_vs_ma = instr_trend, instr_vs_ma
    else:
        sector_trend, sector_vs_ma = spy_trend, spy_vs_ma

    return MarketContext(
        atr=round(atr, 6),
        atr_percentile=atr_pct,
        volatility_state=vol_state,
        trend_regime=regime,
        spy_trend=spy_trend,
        spy_vs_20ma=spy_vs_ma,
        vix_level=round(vix_level, 2),
        sector_etf=sector_etf,
        sector_trend=sector_trend,
        sector_vs_20ma=sector_vs_ma,
        instrument_trend=instr_trend,
        instrument_vs_20ma=instr_vs_ma,
    )

from dataclasses import dataclass
from enum import Enum


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    D1 = "D1"


class TrendSignal(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class SymbolInfo:
    """Native MetaTrader 5 symbol specification fields (mt5.symbol_info)."""
    name: str
    description: str
    currency_base: str
    currency_profit: str
    digits: int
    point: float
    tick_size: float
    volume_min: float
    volume_max: float
    spread: int


@dataclass(frozen=True)
class Tick:
    """Native MetaTrader 5 tick fields (mt5.symbol_info_tick)."""
    symbol: str
    time: int
    time_msc: int
    bid: float
    ask: float
    last: float
    volume: float
    flags: int


@dataclass(frozen=True)
class Candle:
    """Native MetaTrader 5 OHLCV bar fields (mt5.copy_rates_from_pos)."""
    symbol: str
    timeframe: Timeframe
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


@dataclass(frozen=True)
class MarketAnalysis:
    """Domain technical analysis derived strictly from MT5 Candle and Tick data."""
    symbol: str
    timeframe: Timeframe
    reference_time: int
    last_close: float
    bid: float
    ask: float
    spread_points: int
    sma_9: float
    ema_21: float
    rsi_14: float
    atr_14: float
    avg_tick_volume_20: float
    trend: TrendSignal

from typing import Protocol
from src.domain.entities import Candle, MarketAnalysis, SymbolInfo, Tick, Timeframe


class MarketDataProviderPort(Protocol):
    def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        ...

    def get_last_tick(self, symbol: str) -> Tick | None:
        ...

    def get_candles(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle]:
        ...


class MarketRepositoryPort(Protocol):
    def upsert_symbol_info(self, info: SymbolInfo) -> None:
        ...

    def upsert_tick(self, tick: Tick) -> None:
        ...

    def upsert_candles(self, candles: list[Candle]) -> int:
        ...

    def upsert_analysis(self, analysis: MarketAnalysis) -> None:
        ...

    def get_candles(self, symbol: str, timeframe: Timeframe, limit: int) -> list[Candle]:
        ...

    def get_latest_tick(self, symbol: str) -> Tick | None:
        ...

    def get_latest_analysis(self, symbol: str, timeframe: Timeframe) -> MarketAnalysis | None:
        ...

    def count_candles(self, symbol: str, timeframe: Timeframe) -> int:
        ...

    def count_analyses(self, symbol: str, timeframe: Timeframe) -> int:
        ...

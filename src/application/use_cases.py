from dataclasses import dataclass
from src.domain.entities import MarketAnalysis, Timeframe
from src.domain.ports import MarketDataProviderPort, MarketRepositoryPort
from src.domain.services import MarketAnalyzerService


@dataclass(frozen=True)
class SyncAndAnalyzeResult:
    symbol: str
    timeframe: Timeframe
    candles_fetched: int
    total_candles_stored: int
    total_analyses_stored: int
    analysis: MarketAnalysis


class SyncAndAnalyzeMarketUseCase:
    """Orchestrates MT5 data collection, idempotent persistence, and technical analysis."""

    def __init__(
        self,
        provider: MarketDataProviderPort,
        repository: MarketRepositoryPort,
    ) -> None:
        self.provider = provider
        self.repository = repository

    def execute(
        self,
        symbol: str,
        timeframe: Timeframe = Timeframe.M15,
        candle_count: int = 50,
    ) -> SyncAndAnalyzeResult:
        info = self.provider.get_symbol_info(symbol)
        if info is None:
            raise ValueError(f"Symbol not found in MT5 provider: {symbol}")

        self.repository.upsert_symbol_info(info)

        tick = self.provider.get_last_tick(info.name)
        if tick is not None:
            self.repository.upsert_tick(tick)

        candles = self.provider.get_candles(info.name, timeframe, candle_count)
        fetched_count = self.repository.upsert_candles(candles)

        stored_candles = self.repository.get_candles(
            info.name, timeframe, limit=candle_count
        )
        latest_tick = self.repository.get_latest_tick(info.name)

        analysis = MarketAnalyzerService.analyze(
            symbol=info.name,
            timeframe=timeframe,
            candles=stored_candles,
            latest_tick=latest_tick,
        )
        self.repository.upsert_analysis(analysis)

        return SyncAndAnalyzeResult(
            symbol=info.name,
            timeframe=timeframe,
            candles_fetched=fetched_count,
            total_candles_stored=self.repository.count_candles(info.name, timeframe),
            total_analyses_stored=self.repository.count_analyses(info.name, timeframe),
            analysis=analysis,
        )

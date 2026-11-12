import pytest
from src.application.use_cases import SyncAndAnalyzeMarketUseCase
from src.domain.entities import Timeframe
from src.infrastructure.mt5.mt5_provider import MockMT5MarketDataProvider
from src.infrastructure.persistence.sqlite_repository import SQLiteMarketRepository


def test_use_case_idempotency_across_multiple_executions(tmp_path):
    repo = SQLiteMarketRepository(str(tmp_path / "app.db"))
    provider = MockMT5MarketDataProvider()
    use_case = SyncAndAnalyzeMarketUseCase(provider=provider, repository=repo)

    first = use_case.execute("PETR4", Timeframe.M15, candle_count=40)
    second = use_case.execute("PETR4", Timeframe.M15, candle_count=40)
    third = use_case.execute("PETR4", Timeframe.M15, candle_count=40)

    assert first.candles_fetched == 40
    assert first.total_candles_stored == 40
    assert second.total_candles_stored == 40
    assert third.total_candles_stored == 40
    assert first.total_analyses_stored == 1
    assert third.total_analyses_stored == 1
    assert third.analysis.symbol == "PETR4"


def test_use_case_raises_value_error_for_unknown_symbol(tmp_path):
    repo = SQLiteMarketRepository(str(tmp_path / "app.db"))
    provider = MockMT5MarketDataProvider()
    use_case = SyncAndAnalyzeMarketUseCase(provider=provider, repository=repo)

    with pytest.raises(ValueError, match="Symbol not found"):
        use_case.execute("INVALID_TICKER", Timeframe.M15)

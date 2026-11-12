from src.domain.entities import (
    Candle,
    MarketAnalysis,
    SymbolInfo,
    Tick,
    Timeframe,
    TrendSignal,
)
from src.infrastructure.mt5.mt5_provider import MockMT5MarketDataProvider
from src.infrastructure.persistence.sqlite_repository import SQLiteMarketRepository


def test_sqlite_repository_idempotent_upserts(tmp_path):
    db_file = str(tmp_path / "test_market.db")
    repo = SQLiteMarketRepository(db_file)

    info = SymbolInfo(
        "PETR4", "Petrobras PN", "BRL", "BRL", 2, 0.01, 0.01, 100.0, 100000.0, 1
    )
    repo.upsert_symbol_info(info)
    repo.upsert_symbol_info(
        SymbolInfo(
            "PETR4",
            "Petrobras PN Updated",
            "BRL",
            "BRL",
            2,
            0.01,
            0.01,
            100.0,
            100000.0,
            2,
        )
    )

    c1 = Candle(
        "PETR4", Timeframe.M15, 1700000000, 35.0, 35.5, 34.8, 35.2, 1000, 1, 5000
    )
    c2_initial = Candle(
        "PETR4", Timeframe.M15, 1700000900, 35.2, 35.6, 35.1, 35.4, 500, 1, 2500
    )
    repo.upsert_candles([c1, c2_initial])
    assert repo.count_candles("PETR4", Timeframe.M15) == 2

    # Re-inserting same timestamps with updated live candle must NOT duplicate rows
    c2_updated = Candle(
        "PETR4", Timeframe.M15, 1700000900, 35.2, 36.0, 35.0, 35.9, 1200, 1, 6000
    )
    repo.upsert_candles([c1, c2_updated])
    assert repo.count_candles("PETR4", Timeframe.M15) == 2

    stored = repo.get_candles("PETR4", Timeframe.M15, limit=10)
    assert stored[-1].close == 35.9
    assert stored[-1].tick_volume == 1200

    # Tick idempotency
    tick = Tick("PETR4", 1700000900, 1700000900123, 35.89, 35.91, 35.90, 200.0, 6)
    repo.upsert_tick(tick)
    repo.upsert_tick(tick)
    latest_tick = repo.get_latest_tick("PETR4")
    assert latest_tick is not None and latest_tick.last == 35.90

    # Analysis idempotency on (symbol, timeframe, reference_time)
    a1 = MarketAnalysis(
        "PETR4",
        Timeframe.M15,
        1700000900,
        35.4,
        35.39,
        35.41,
        2,
        35.1,
        34.9,
        60.0,
        0.4,
        800.0,
        TrendSignal.BULLISH,
    )
    a2 = MarketAnalysis(
        "PETR4",
        Timeframe.M15,
        1700000900,
        35.9,
        35.89,
        35.91,
        2,
        35.3,
        35.0,
        68.0,
        0.5,
        1100.0,
        TrendSignal.BULLISH,
    )
    repo.upsert_analysis(a1)
    repo.upsert_analysis(a2)
    assert repo.count_analyses("PETR4", Timeframe.M15) == 1
    assert repo.get_latest_analysis("PETR4", Timeframe.M15).last_close == 35.9


def test_mock_mt5_provider_returns_deterministic_mt5_structures():
    provider = MockMT5MarketDataProvider()
    info = provider.get_symbol_info("PETR4")
    tick = provider.get_last_tick("PETR4")
    candles_30 = provider.get_candles("PETR4", Timeframe.M15, count=30)
    candles_10 = provider.get_candles("PETR4", Timeframe.M15, count=10)

    assert info is not None and info.name == "PETR4"
    assert tick is not None and tick.ask >= tick.bid
    assert len(candles_30) == 30
    assert candles_30[0].time < candles_30[-1].time
    # The last candle must be identical regardless of how many historical bars were requested
    assert candles_30[-1] == candles_10[-1]
    assert tick.last == candles_30[-1].close


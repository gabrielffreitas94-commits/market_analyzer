import pytest
from src.domain.entities import Candle, Tick, Timeframe, TrendSignal
from src.domain.services import MarketAnalyzerService


def _make_candles(closes: list[float], symbol: str = "PETR4") -> list[Candle]:
    return [
        Candle(
            symbol=symbol,
            timeframe=Timeframe.M15,
            time=1700000000 + i * 900,
            open=c - 0.1,
            high=c + 0.5,
            low=c - 0.5,
            close=c,
            tick_volume=1000 + i * 10,
            spread=2,
            real_volume=5000,
        )
        for i, c in enumerate(closes)
    ]


def test_analyzer_uptrend_and_indicators():
    closes = [30.0 + i * 0.5 for i in range(30)]
    candles = _make_candles(closes)
    tick = Tick(
        "PETR4",
        1700027000,
        1700027000000,
        bid=44.49,
        ask=44.51,
        last=44.50,
        volume=100.0,
        flags=6,
    )

    analysis = MarketAnalyzerService.analyze("PETR4", Timeframe.M15, candles, tick)

    assert analysis.symbol == "PETR4"
    assert analysis.reference_time == candles[-1].time
    assert analysis.last_close == 44.5
    assert analysis.sma_9 > analysis.ema_21
    assert analysis.rsi_14 == 100.0
    assert analysis.atr_14 == pytest.approx(1.0, rel=1e-2)
    assert analysis.trend == TrendSignal.BULLISH


def test_analyzer_handles_short_and_flat_series():
    candles = _make_candles([10.0, 10.0, 10.0])
    analysis = MarketAnalyzerService.analyze("VALE3", Timeframe.M15, candles, None)

    assert analysis.rsi_14 == 50.0
    assert analysis.trend == TrendSignal.NEUTRAL
    assert analysis.sma_9 == 10.0

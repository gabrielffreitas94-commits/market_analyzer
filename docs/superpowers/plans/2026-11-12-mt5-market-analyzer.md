# MT5 Market Analyzer POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Clean Architecture Python POC that collects MetaTrader 5 market data (SymbolInfo, Tick, OHLCV Candles), persists it idempotently in SQLite, and computes technical analysis indicators.

**Architecture:** Four-layer Clean Architecture (`domain`, `application`, `infrastructure`, `presentation`). The `domain` layer defines pure dataclasses, ports (`Protocol`), and technical indicator math. `infrastructure` implements idempotent SQLite persistence (`ON CONFLICT DO UPDATE`) and an MT5 provider with automatic deterministic fallback when the MT5 terminal is unavailable. `application` orchestrates idempotent sync and analysis use cases, exposed via a `presentation` CLI.

**Tech Stack:** Python 3.10+, `sqlite3` (standard library), `MetaTrader5` (optional runtime dependency with built-in mock fallback), `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-12-mt5-market-analyzer-design.md`

## Global Constraints

- Extract only information available natively via MetaTrader 5: `SymbolInfo`, `Tick`, and `Candle` (OHLCV + tick_volume, real_volume, spread).
- Persist data automatically in a 100% idempotent manner (`UNIQUE` constraints + `ON CONFLICT DO UPDATE`).
- Never couple `domain` or `application` layers directly to `MetaTrader5` or `sqlite3`.

## Review Focus

- Duplicate candle batches synced multiple times must not increase row count, while updating the open candle's `high`/`low`/`close`/`tick_volume` in-place.
- Insufficient candles (e.g., `< 20` candles) passed to `MarketAnalyzerService` must still return a valid `MarketAnalysis` with graceful fallbacks instead of `ZeroDivisionError` or `IndexError`.
- Flat price series (all closes identical, zero losses or zero gains) in RSI calculation must return `100.0` (when losses=0 and gains>0) or `50.0` (when both=0) without dividing by zero.
- Empty or unknown symbol returned by MT5 provider (`None`) must raise a clear domain error or be skipped cleanly in the use case without corrupting SQLite transactions.
- Repeating `AnalyzeMarketUseCase.execute` on the exact same candle reference timestamp must overwrite the existing analysis record idempotently (`UNIQUE(symbol, timeframe, reference_time)`).

---

### Task 1: Domain Layer (Entities, Ports, and MarketAnalyzerService)

**Files:**
- Create: `src/domain/entities.py`
- Create: `src/domain/ports.py`
- Create: `src/domain/services.py`
- Test: `tests/test_domain.py`

**Interfaces:**
- Produces:
  - `Timeframe(str, Enum)`: `M1`, `M5`, `M15`, `H1`, `D1`
  - `SymbolInfo(name: str, description: str, currency_base: str, currency_profit: str, digits: int, point: float, tick_size: float, volume_min: float, volume_max: float, spread: int)`
  - `Tick(symbol: str, time: int, time_msc: int, bid: float, ask: float, last: float, volume: float, flags: int)`
  - `Candle(symbol: str, timeframe: Timeframe, time: int, open: float, high: float, low: float, close: float, tick_volume: int, spread: int, real_volume: int)`
  - `TrendSignal(str, Enum)`: `BULLISH`, `BEARISH`, `NEUTRAL`
  - `MarketAnalysis(symbol: str, timeframe: Timeframe, reference_time: int, last_close: float, bid: float, ask: float, spread_points: int, sma_9: float, ema_21: float, rsi_14: float, atr_14: float, avg_tick_volume_20: float, trend: TrendSignal)`
  - `MarketDataProviderPort(Protocol)`:
    - `get_symbol_info(self, symbol: str) -> SymbolInfo | None`
    - `get_last_tick(self, symbol: str) -> Tick | None`
    - `get_candles(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle]`
  - `MarketRepositoryPort(Protocol)`:
    - `upsert_symbol_info(self, info: SymbolInfo) -> None`
    - `upsert_tick(self, tick: Tick) -> None`
    - `upsert_candles(self, candles: list[Candle]) -> int`
    - `upsert_analysis(self, analysis: MarketAnalysis) -> None`
    - `get_candles(self, symbol: str, timeframe: Timeframe, limit: int) -> list[Candle]`
    - `get_latest_tick(self, symbol: str) -> Tick | None`
    - `get_latest_analysis(self, symbol: str, timeframe: Timeframe) -> MarketAnalysis | None`
    - `count_candles(self, symbol: str, timeframe: Timeframe) -> int`
    - `count_analyses(self, symbol: str, timeframe: Timeframe) -> int`
  - `MarketAnalyzerService.analyze(symbol: str, timeframe: Timeframe, candles: list[Candle], latest_tick: Tick | None) -> MarketAnalysis`

- [ ] **Step 1: Write the failing domain unit tests in `tests/test_domain.py`**

```python
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
    tick = Tick("PETR4", 1700027000, 1700027000000, bid=44.49, ask=44.51, last=44.50, volume=100.0, flags=6)

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 3: Implement `src/domain/entities.py`, `src/domain/ports.py`, and `src/domain/services.py`**

Sort `candles` chronologically by `time` inside `MarketAnalyzerService.analyze`. Compute `sma_9` on up to the last 9 closes, `ema_21` with multiplier $2 / (21 + 1)$, `rsi_14` over the last 14 deltas (`50.0` if both avg gain and loss are 0, `100.0` if avg loss is 0), `atr_14` over up to the last 14 true ranges ($\max(H-L, |H-C_{prev}|, |L-C_{prev}|)$), and `trend` (`BULLISH` if `last_close > sma_9 > ema_21`, `BEARISH` if `last_close < sma_9 < ema_21`, else `NEUTRAL`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_domain.py -v`
Expected: PASS (2 passed)

---

### Task 2: Infrastructure Layer (Idempotent SQLite Repository & MT5 Adapter with Fallback)

**Files:**
- Create: `src/infrastructure/persistence/sqlite_repository.py`
- Create: `src/infrastructure/mt5/mt5_provider.py`
- Test: `tests/test_infrastructure.py`

**Interfaces:**
- Consumes: `src.domain.entities.*`, `src.domain.ports.*`
- Produces:
  - `SQLiteMarketRepository(db_path: str = "market_data.db")` implementing `MarketRepositoryPort`
  - `MT5MarketDataProvider(use_fallback_if_unavailable: bool = True)` implementing `MarketDataProviderPort`
  - `MockMT5MarketDataProvider()` implementing `MarketDataProviderPort`

- [ ] **Step 1: Write the failing infrastructure and idempotency tests in `tests/test_infrastructure.py`**

```python
from src.domain.entities import Candle, SymbolInfo, Tick, Timeframe, TrendSignal, MarketAnalysis
from src.infrastructure.persistence.sqlite_repository import SQLiteMarketRepository
from src.infrastructure.mt5.mt5_provider import MockMT5MarketDataProvider


def test_sqlite_repository_idempotent_upserts(tmp_path):
    db_file = str(tmp_path / "test_market.db")
    repo = SQLiteMarketRepository(db_file)

    info = SymbolInfo("PETR4", "Petrobras PN", "BRL", "BRL", 2, 0.01, 0.01, 100.0, 100000.0, 1)
    repo.upsert_symbol_info(info)
    repo.upsert_symbol_info(SymbolInfo("PETR4", "Petrobras PN Updated", "BRL", "BRL", 2, 0.01, 0.01, 100.0, 100000.0, 2))

    c1 = Candle("PETR4", Timeframe.M15, 1700000000, 35.0, 35.5, 34.8, 35.2, 1000, 1, 5000)
    c2_initial = Candle("PETR4", Timeframe.M15, 1700000900, 35.2, 35.6, 35.1, 35.4, 500, 1, 2500)
    repo.upsert_candles([c1, c2_initial])
    assert repo.count_candles("PETR4", Timeframe.M15) == 2

    # Re-inserting same timestamps with updated live candle must NOT duplicate rows
    c2_updated = Candle("PETR4", Timeframe.M15, 1700000900, 35.2, 36.0, 35.0, 35.9, 1200, 1, 6000)
    repo.upsert_candles([c1, c2_updated])
    assert repo.count_candles("PETR4", Timeframe.M15) == 2

    stored = repo.get_candles("PETR4", Timeframe.M15, limit=10)
    assert stored[-1].close == 35.9
    assert stored[-1].tick_volume == 1200

    # Analysis idempotency on (symbol, timeframe, reference_time)
    a1 = MarketAnalysis("PETR4", Timeframe.M15, 1700000900, 35.4, 35.39, 35.41, 2, 35.1, 34.9, 60.0, 0.4, 800.0, TrendSignal.BULLISH)
    a2 = MarketAnalysis("PETR4", Timeframe.M15, 1700000900, 35.9, 35.89, 35.91, 2, 35.3, 35.0, 68.0, 0.5, 1100.0, TrendSignal.BULLISH)
    repo.upsert_analysis(a1)
    repo.upsert_analysis(a2)
    assert repo.count_analyses("PETR4", Timeframe.M15) == 1
    assert repo.get_latest_analysis("PETR4", Timeframe.M15).last_close == 35.9


def test_mock_mt5_provider_returns_deterministic_mt5_structures():
    provider = MockMT5MarketDataProvider()
    info = provider.get_symbol_info("PETR4")
    tick = provider.get_last_tick("PETR4")
    candles = provider.get_candles("PETR4", Timeframe.M15, count=30)

    assert info is not None and info.name == "PETR4"
    assert tick is not None and tick.ask >= tick.bid
    assert len(candles) == 30
    assert candles[0].time < candles[-1].time
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_infrastructure.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `SQLiteMarketRepository` and `MT5MarketDataProvider` / `MockMT5MarketDataProvider`**

In `SQLiteMarketRepository`:
- Table `symbols` with `PRIMARY KEY (name)` and `ON CONFLICT(name) DO UPDATE`.
- Table `ticks` with `UNIQUE(symbol, time_msc, bid, ask, last, flags)` and `ON CONFLICT DO NOTHING`.
- Table `candles` with `UNIQUE(symbol, timeframe, time)` and `ON CONFLICT(symbol, timeframe, time) DO UPDATE SET open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, tick_volume=excluded.tick_volume, spread=excluded.spread, real_volume=excluded.real_volume`.
- Table `analyses` with `UNIQUE(symbol, timeframe, reference_time)` and `ON CONFLICT(symbol, timeframe, reference_time) DO UPDATE`.

In `MT5MarketDataProvider`:
- Try importing `MetaTrader5 as mt5` and calling `mt5.initialize()`. If unavailable or initialization fails and `use_fallback_if_unavailable=True`, delegate to `MockMT5MarketDataProvider` (which generates deterministic, realistic MT5-structured data anchored to a fixed base timestamp grid so repeated calls within the same timeframe window hit the exact same candle timestamps).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_infrastructure.py -v`
Expected: PASS (2 passed)

---

### Task 3: Application Use Cases & CLI Entrypoint

**Files:**
- Create: `src/application/use_cases.py`
- Create: `src/presentation/cli.py`
- Test: `tests/test_application.py`

**Interfaces:**
- Consumes: `MarketDataProviderPort`, `MarketRepositoryPort`, `MarketAnalyzerService`
- Produces:
  - `SyncAndAnalyzeResult(symbol: str, timeframe: Timeframe, candles_fetched: int, total_candles_stored: int, total_analyses_stored: int, analysis: MarketAnalysis)`
  - `SyncAndAnalyzeMarketUseCase(provider: MarketDataProviderPort, repository: MarketRepositoryPort)`
    - `execute(self, symbol: str, timeframe: Timeframe = Timeframe.M15, candle_count: int = 50) -> SyncAndAnalyzeResult`
  - `src/presentation/cli.py`: `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing application tests in `tests/test_application.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_application.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/application/use_cases.py` and `src/presentation/cli.py`**

In `SyncAndAnalyzeMarketUseCase.execute`:
1. Fetch `SymbolInfo` from `provider.get_symbol_info(symbol)`; if `None`, raise `ValueError(f"Symbol not found in MT5 provider: {symbol}")`.
2. Call `repository.upsert_symbol_info(info)`.
3. Fetch `Tick` and `upsert_tick` if present.
4. Fetch `candles` via `provider.get_candles(symbol, timeframe, candle_count)` and call `repository.upsert_candles(candles)`.
5. Read back ordered candles from `repository.get_candles(symbol, timeframe, limit=candle_count)`, compute `MarketAnalyzerService.analyze`, and call `repository.upsert_analysis(analysis)`.
6. Return `SyncAndAnalyzeResult` including `total_candles_stored` and `total_analyses_stored` so callers can verify idempotency.

In `src/presentation/cli.py`:
- Accept `--symbols` (default `PETR4,VALE3,WIN$N`), `--timeframe` (default `M15`), `--count` (default `50`), `--db` (default `market_data.db`), and `--runs` (default `2` to demonstrate idempotency out of the box) or `--loop-seconds`.
- Print a formatted table showing the MT5 indicators and the database record counts across runs to prove zero duplication.

- [ ] **Step 4: Run full test suite and CLI verification**

Run: `pytest -v && python -m src.presentation.cli --runs 2`
Expected: All tests PASS and CLI shows identical `total_candles_stored` and `total_analyses_stored` across run #1 and run #2.

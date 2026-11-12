import sqlite3
from src.domain.entities import (
    Candle,
    MarketAnalysis,
    SymbolInfo,
    Tick,
    Timeframe,
    TrendSignal,
)


class SQLiteMarketRepository:
    """Idempotent SQLite persistence using UNIQUE constraints and ON CONFLICT DO UPDATE."""

    def __init__(self, db_path: str = "market_data.db") -> None:
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS symbols (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    currency_base TEXT NOT NULL,
                    currency_profit TEXT NOT NULL,
                    digits INTEGER NOT NULL,
                    point REAL NOT NULL,
                    tick_size REAL NOT NULL,
                    volume_min REAL NOT NULL,
                    volume_max REAL NOT NULL,
                    spread INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ticks (
                    symbol TEXT NOT NULL,
                    time INTEGER NOT NULL,
                    time_msc INTEGER NOT NULL,
                    bid REAL NOT NULL,
                    ask REAL NOT NULL,
                    last REAL NOT NULL,
                    volume REAL NOT NULL,
                    flags INTEGER NOT NULL,
                    UNIQUE(symbol, time_msc, bid, ask, last, flags)
                );

                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    time INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    tick_volume INTEGER NOT NULL,
                    spread INTEGER NOT NULL,
                    real_volume INTEGER NOT NULL,
                    UNIQUE(symbol, timeframe, time)
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    reference_time INTEGER NOT NULL,
                    last_close REAL NOT NULL,
                    bid REAL NOT NULL,
                    ask REAL NOT NULL,
                    spread_points INTEGER NOT NULL,
                    sma_9 REAL NOT NULL,
                    ema_21 REAL NOT NULL,
                    rsi_14 REAL NOT NULL,
                    atr_14 REAL NOT NULL,
                    avg_tick_volume_20 REAL NOT NULL,
                    trend TEXT NOT NULL,
                    UNIQUE(symbol, timeframe, reference_time)
                );
                """
            )

    def upsert_symbol_info(self, info: SymbolInfo) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO symbols (
                    name, description, currency_base, currency_profit,
                    digits, point, tick_size, volume_min, volume_max, spread
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    currency_base = excluded.currency_base,
                    currency_profit = excluded.currency_profit,
                    digits = excluded.digits,
                    point = excluded.point,
                    tick_size = excluded.tick_size,
                    volume_min = excluded.volume_min,
                    volume_max = excluded.volume_max,
                    spread = excluded.spread
                """,
                (
                    info.name,
                    info.description,
                    info.currency_base,
                    info.currency_profit,
                    info.digits,
                    info.point,
                    info.tick_size,
                    info.volume_min,
                    info.volume_max,
                    info.spread,
                ),
            )

    def upsert_tick(self, tick: Tick) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ticks (
                    symbol, time, time_msc, bid, ask, last, volume, flags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, time_msc, bid, ask, last, flags) DO NOTHING
                """,
                (
                    tick.symbol,
                    tick.time,
                    tick.time_msc,
                    tick.bid,
                    tick.ask,
                    tick.last,
                    tick.volume,
                    tick.flags,
                ),
            )

    def upsert_candles(self, candles: list[Candle]) -> int:
        if not candles:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO candles (
                    symbol, timeframe, time, open, high, low, close,
                    tick_volume, spread, real_volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, time) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    tick_volume = excluded.tick_volume,
                    spread = excluded.spread,
                    real_volume = excluded.real_volume
                """,
                [
                    (
                        c.symbol,
                        c.timeframe.value,
                        c.time,
                        c.open,
                        c.high,
                        c.low,
                        c.close,
                        c.tick_volume,
                        c.spread,
                        c.real_volume,
                    )
                    for c in candles
                ],
            )
        return len(candles)

    def upsert_analysis(self, analysis: MarketAnalysis) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analyses (
                    symbol, timeframe, reference_time, last_close, bid, ask,
                    spread_points, sma_9, ema_21, rsi_14, atr_14,
                    avg_tick_volume_20, trend
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, reference_time) DO UPDATE SET
                    last_close = excluded.last_close,
                    bid = excluded.bid,
                    ask = excluded.ask,
                    spread_points = excluded.spread_points,
                    sma_9 = excluded.sma_9,
                    ema_21 = excluded.ema_21,
                    rsi_14 = excluded.rsi_14,
                    atr_14 = excluded.atr_14,
                    avg_tick_volume_20 = excluded.avg_tick_volume_20,
                    trend = excluded.trend
                """,
                (
                    analysis.symbol,
                    analysis.timeframe.value,
                    analysis.reference_time,
                    analysis.last_close,
                    analysis.bid,
                    analysis.ask,
                    analysis.spread_points,
                    analysis.sma_9,
                    analysis.ema_21,
                    analysis.rsi_14,
                    analysis.atr_14,
                    analysis.avg_tick_volume_20,
                    analysis.trend.value,
                ),
            )

    def get_candles(
        self, symbol: str, timeframe: Timeframe, limit: int
    ) -> list[Candle]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT symbol, timeframe, time, open, high, low, close,
                           tick_volume, spread, real_volume
                    FROM candles
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY time DESC
                    LIMIT ?
                ) ORDER BY time ASC
                """,
                (symbol, timeframe.value, limit),
            ).fetchall()
        return [
            Candle(
                symbol=r["symbol"],
                timeframe=Timeframe(r["timeframe"]),
                time=r["time"],
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                tick_volume=r["tick_volume"],
                spread=r["spread"],
                real_volume=r["real_volume"],
            )
            for r in rows
        ]

    def get_latest_tick(self, symbol: str) -> Tick | None:
        with self._connect() as conn:
            r = conn.execute(
                """
                SELECT symbol, time, time_msc, bid, ask, last, volume, flags
                FROM ticks
                WHERE symbol = ?
                ORDER BY time_msc DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
        if not r:
            return None
        return Tick(
            symbol=r["symbol"],
            time=r["time"],
            time_msc=r["time_msc"],
            bid=r["bid"],
            ask=r["ask"],
            last=r["last"],
            volume=r["volume"],
            flags=r["flags"],
        )

    def get_latest_analysis(
        self, symbol: str, timeframe: Timeframe
    ) -> MarketAnalysis | None:
        with self._connect() as conn:
            r = conn.execute(
                """
                SELECT symbol, timeframe, reference_time, last_close, bid, ask,
                       spread_points, sma_9, ema_21, rsi_14, atr_14,
                       avg_tick_volume_20, trend
                FROM analyses
                WHERE symbol = ? AND timeframe = ?
                ORDER BY reference_time DESC
                LIMIT 1
                """,
                (symbol, timeframe.value),
            ).fetchone()
        if not r:
            return None
        return MarketAnalysis(
            symbol=r["symbol"],
            timeframe=Timeframe(r["timeframe"]),
            reference_time=r["reference_time"],
            last_close=r["last_close"],
            bid=r["bid"],
            ask=r["ask"],
            spread_points=r["spread_points"],
            sma_9=r["sma_9"],
            ema_21=r["ema_21"],
            rsi_14=r["rsi_14"],
            atr_14=r["atr_14"],
            avg_tick_volume_20=r["avg_tick_volume_20"],
            trend=TrendSignal(r["trend"]),
        )

    def count_candles(self, symbol: str, timeframe: Timeframe) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM candles WHERE symbol = ? AND timeframe = ?",
                (symbol, timeframe.value),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def count_analyses(self, symbol: str, timeframe: Timeframe) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM analyses WHERE symbol = ? AND timeframe = ?",
                (symbol, timeframe.value),
            ).fetchone()
        return int(row["cnt"]) if row else 0

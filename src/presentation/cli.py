import argparse
import time
from datetime import datetime, timezone
from src.application.use_cases import SyncAndAnalyzeMarketUseCase
from src.domain.entities import Timeframe
from src.infrastructure.mt5.mt5_provider import MT5MarketDataProvider
from src.infrastructure.persistence.sqlite_repository import SQLiteMarketRepository


def _format_time(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def run_cycle(
    use_case: SyncAndAnalyzeMarketUseCase,
    symbols: list[str],
    timeframe: Timeframe,
    count: int,
    cycle_num: int,
    using_live_mt5: bool,
) -> None:
    source_label = "MetaTrader 5 Terminal (LIVE)" if using_live_mt5 else "MT5 Structural Fallback (Offline Mode)"
    print(f"\n=== Ciclo #{cycle_num} | Fonte: {source_label} | Timeframe: {timeframe.value} ===")
    header = (
        f"{'ATIVO':<8} | {'REF TIME (UTC)':<16} | {'CLOSE':>10} | {'BID/ASK':<21} | "
        f"{'SMA(9)':>10} | {'EMA(21)':>10} | {'RSI(14)':>7} | {'ATR(14)':>8} | "
        f"{'TENDENCIA':<9} | {'DB CANDLES':>10} | {'DB ANALYSES':>11}"
    )
    print(header)
    print("-" * len(header))

    for sym in symbols:
        res = use_case.execute(sym, timeframe=timeframe, candle_count=count)
        a = res.analysis
        bid_ask = f"{a.bid}/{a.ask}"
        print(
            f"{a.symbol:<8} | {_format_time(a.reference_time):<16} | {a.last_close:>10.5g} | "
            f"{bid_ask:<21} | {a.sma_9:>10.5g} | {a.ema_21:>10.5g} | "
            f"{a.rsi_14:>7.2f} | {a.atr_14:>8.4g} | {a.trend.value:<9} | "
            f"{res.total_candles_stored:>10} | {res.total_analyses_stored:>11}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="POC de Analise de Mercado Financeiro (MT5 + Clean Architecture + Idempotencia)"
    )
    parser.add_argument(
        "--symbols",
        default="PETR4,VALE3,WIN$N,EURUSD",
        help="Lista de ativos separados por virgula",
    )
    parser.add_argument(
        "--timeframe",
        default="M15",
        choices=[tf.value for tf in Timeframe],
        help="Timeframe do MT5 (M1, M5, M15, H1, D1)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Quantidade de candles coletados por sincronizacao",
    )
    parser.add_argument(
        "--db",
        default="market_data.db",
        help="Caminho do arquivo SQLite local",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=2,
        help="Numero de ciclos seguidos (padrao=2 para comprovar idempotencia)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="Intervalo em segundos entre cada ciclo",
    )

    args = parser.parse_args(argv)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    timeframe = Timeframe(args.timeframe)

    provider = MT5MarketDataProvider(use_fallback_if_unavailable=True)
    repository = SQLiteMarketRepository(db_path=args.db)
    use_case = SyncAndAnalyzeMarketUseCase(provider=provider, repository=repository)

    for cycle in range(1, args.runs + 1):
        run_cycle(
            use_case=use_case,
            symbols=symbols,
            timeframe=timeframe,
            count=args.count,
            cycle_num=cycle,
            using_live_mt5=provider.using_live_mt5,
        )
        if cycle < args.runs and args.interval > 0:
            time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

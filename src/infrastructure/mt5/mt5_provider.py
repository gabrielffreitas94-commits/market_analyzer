import math
from src.domain.entities import Candle, SymbolInfo, Tick, Timeframe


_TIMEFRAME_SECONDS = {
    Timeframe.M1: 60,
    Timeframe.M5: 300,
    Timeframe.M15: 900,
    Timeframe.H1: 3600,
    Timeframe.D1: 86400,
}

_MOCK_SYMBOLS: dict[str, SymbolInfo] = {
    "PETR4": SymbolInfo(
        name="PETR4",
        description="PETROBRAS PN",
        currency_base="BRL",
        currency_profit="BRL",
        digits=2,
        point=0.01,
        tick_size=0.01,
        volume_min=100.0,
        volume_max=1000000.0,
        spread=1,
    ),
    "VALE3": SymbolInfo(
        name="VALE3",
        description="VALE ON",
        currency_base="BRL",
        currency_profit="BRL",
        digits=2,
        point=0.01,
        tick_size=0.01,
        volume_min=100.0,
        volume_max=1000000.0,
        spread=2,
    ),
    "WIN$N": SymbolInfo(
        name="WIN$N",
        description="Mini Indice Ibovespa Continuo",
        currency_base="BRL",
        currency_profit="BRL",
        digits=0,
        point=1.0,
        tick_size=5.0,
        volume_min=1.0,
        volume_max=500.0,
        spread=5,
    ),
    "EURUSD": SymbolInfo(
        name="EURUSD",
        description="Euro vs US Dollar",
        currency_base="EUR",
        currency_profit="USD",
        digits=5,
        point=0.00001,
        tick_size=0.00001,
        volume_min=0.01,
        volume_max=100.0,
        spread=8,
    ),
}

_BASE_PRICES: dict[str, float] = {
    "PETR4": 36.50,
    "VALE3": 61.20,
    "WIN$N": 128500.0,
    "EURUSD": 1.08450,
}


class MockMT5MarketDataProvider:
    """Deterministic MT5 fallback provider using exact MT5 data structures."""

    BASE_ANCHOR_TIME = 1730000000

    def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        return _MOCK_SYMBOLS.get(symbol.upper())

    def get_last_tick(self, symbol: str) -> Tick | None:
        info = self.get_symbol_info(symbol)
        if not info:
            return None
        candles = self.get_candles(symbol, Timeframe.M15, count=5)
        last_close = candles[-1].close
        half_spread = (info.spread * info.point) / 2.0
        bid = round(last_close - half_spread, info.digits)
        ask = round(last_close + half_spread, info.digits)
        if ask < bid:
            ask = bid
        return Tick(
            symbol=info.name,
            time=candles[-1].time,
            time_msc=candles[-1].time * 1000,
            bid=bid,
            ask=ask,
            last=last_close,
            volume=info.volume_min * 5,
            flags=6,
        )

    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int
    ) -> list[Candle]:
        info = self.get_symbol_info(symbol)
        if not info:
            return []
        step = _TIMEFRAME_SECONDS[timeframe]
        base_price = _BASE_PRICES.get(info.name, 50.0)
        end_bar_time = (self.BASE_ANCHOR_TIME // step) * step

        # Different symbols get different deterministic trend profiles
        drift_sign = -1.0 if info.name == "VALE3" else 1.0
        unit = info.tick_size if info.tick_size > 0 else info.point

        candles: list[Candle] = []
        for idx in range(count):
            offset = idx - (count - 1)  # ..., -2, -1, 0 (0 is always end_bar_time)
            bar_time = end_bar_time + offset * step
            bar_seq = (bar_time // step) % 1000
            wave = math.sin(bar_seq * 0.35) * (unit * 4)
            drift = drift_sign * (50 + offset) * (unit * 1.5)
            close_p = round(base_price + drift + wave, info.digits)
            open_p = round(close_p - drift_sign * unit, info.digits)
            high_p = round(max(open_p, close_p) + unit * 3, info.digits)
            low_p = round(min(open_p, close_p) - unit * 3, info.digits)

            candles.append(
                Candle(
                    symbol=info.name,
                    timeframe=timeframe,
                    time=bar_time,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    tick_volume=1200 + (bar_seq * 37) % 800,
                    spread=info.spread,
                    real_volume=50000 + (bar_seq * 1500) % 45000,
                )
            )
        return candles


class MT5MarketDataProvider:
    """Official MetaTrader5 adapter with optional fallback to MockMT5MarketDataProvider."""

    def __init__(self, use_fallback_if_unavailable: bool = True) -> None:
        self._mt5 = None
        self._fallback = (
            MockMT5MarketDataProvider() if use_fallback_if_unavailable else None
        )
        self.using_live_mt5 = False

        try:
            import MetaTrader5 as mt5  # type: ignore

            if mt5.initialize():
                self._mt5 = mt5
                self.using_live_mt5 = True
        except Exception:
            self._mt5 = None
            self.using_live_mt5 = False

    def _tf_to_mt5(self, timeframe: Timeframe) -> int:
        assert self._mt5 is not None
        mapping = {
            Timeframe.M1: self._mt5.TIMEFRAME_M1,
            Timeframe.M5: self._mt5.TIMEFRAME_M5,
            Timeframe.M15: self._mt5.TIMEFRAME_M15,
            Timeframe.H1: self._mt5.TIMEFRAME_H1,
            Timeframe.D1: self._mt5.TIMEFRAME_D1,
        }
        return mapping[timeframe]

    def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        if self.using_live_mt5 and self._mt5 is not None:
            self._mt5.symbol_select(symbol, True)
            raw = self._mt5.symbol_info(symbol)
            if raw is None:
                return None
            return SymbolInfo(
                name=raw.name,
                description=raw.description,
                currency_base=raw.currency_base,
                currency_profit=raw.currency_profit,
                digits=int(raw.digits),
                point=float(raw.point),
                tick_size=float(raw.trade_tick_size),
                volume_min=float(raw.volume_min),
                volume_max=float(raw.volume_max),
                spread=int(raw.spread),
            )
        if self._fallback is not None:
            return self._fallback.get_symbol_info(symbol)
        return None

    def get_last_tick(self, symbol: str) -> Tick | None:
        if self.using_live_mt5 and self._mt5 is not None:
            raw = self._mt5.symbol_info_tick(symbol)
            if raw is None:
                return None
            return Tick(
                symbol=symbol,
                time=int(raw.time),
                time_msc=int(raw.time_msc),
                bid=float(raw.bid),
                ask=float(raw.ask),
                last=float(raw.last),
                volume=float(raw.volume_real if hasattr(raw, "volume_real") else raw.volume),
                flags=int(raw.flags),
            )
        if self._fallback is not None:
            return self._fallback.get_last_tick(symbol)
        return None

    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int
    ) -> list[Candle]:
        if self.using_live_mt5 and self._mt5 is not None:
            rates = self._mt5.copy_rates_from_pos(
                symbol, self._tf_to_mt5(timeframe), 0, count
            )
            if rates is None:
                return []
            return [
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    time=int(r["time"]),
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                    tick_volume=int(r["tick_volume"]),
                    spread=int(r["spread"]),
                    real_volume=int(r["real_volume"]),
                )
                for r in rates
            ]
        if self._fallback is not None:
            return self._fallback.get_candles(symbol, timeframe, count)
        return []

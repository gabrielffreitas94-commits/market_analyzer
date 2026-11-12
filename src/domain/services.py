from src.domain.entities import Candle, MarketAnalysis, Tick, Timeframe, TrendSignal


class MarketAnalyzerService:
    """Pure domain service calculating indicators from MT5 candles and ticks."""

    @staticmethod
    def analyze(
        symbol: str,
        timeframe: Timeframe,
        candles: list[Candle],
        latest_tick: Tick | None,
    ) -> MarketAnalysis:
        if not candles:
            raise ValueError(f"Cannot analyze {symbol}: candle list is empty.")

        ordered = sorted(candles, key=lambda c: c.time)
        closes = [c.close for c in ordered]
        last_candle = ordered[-1]

        sma_9 = MarketAnalyzerService._sma(closes, 9)
        ema_21 = MarketAnalyzerService._ema(closes, 21)
        rsi_14 = MarketAnalyzerService._rsi(closes, 14)
        atr_14 = MarketAnalyzerService._atr(ordered, 14)

        recent_vols = [c.tick_volume for c in ordered[-20:]]
        avg_vol_20 = sum(recent_vols) / len(recent_vols)

        last_close = last_candle.close
        if last_close > sma_9 > ema_21:
            trend = TrendSignal.BULLISH
        elif last_close < sma_9 < ema_21:
            trend = TrendSignal.BEARISH
        else:
            trend = TrendSignal.NEUTRAL

        bid = latest_tick.bid if latest_tick else last_close
        ask = latest_tick.ask if latest_tick else last_close
        spread_points = last_candle.spread

        return MarketAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            reference_time=last_candle.time,
            last_close=round(last_close, 5),
            bid=round(bid, 5),
            ask=round(ask, 5),
            spread_points=spread_points,
            sma_9=round(sma_9, 5),
            ema_21=round(ema_21, 5),
            rsi_14=round(rsi_14, 2),
            atr_14=round(atr_14, 5),
            avg_tick_volume_20=round(avg_vol_20, 2),
            trend=trend,
        )

    @staticmethod
    def _sma(values: list[float], period: int) -> float:
        window = values[-period:]
        return sum(window) / len(window)

    @staticmethod
    def _ema(values: list[float], period: int) -> float:
        multiplier = 2.0 / (period + 1)
        ema_val = values[0]
        for price in values[1:]:
            ema_val = (price - ema_val) * multiplier + ema_val
        return ema_val

    @staticmethod
    def _rsi(closes: list[float], period: int) -> float:
        if len(closes) < 2:
            return 50.0
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        window = deltas[-period:]
        gains = [d if d > 0 else 0.0 for d in window]
        losses = [-d if d < 0 else 0.0 for d in window]

        avg_gain = sum(gains) / len(window)
        avg_loss = sum(losses) / len(window)

        if avg_loss == 0.0 and avg_gain == 0.0:
            return 50.0
        if avg_loss == 0.0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _atr(candles: list[Candle], period: int) -> float:
        if len(candles) == 1:
            return candles[0].high - candles[0].low

        trs: list[float] = []
        for i in range(1, len(candles)):
            curr = candles[i]
            prev_close = candles[i - 1].close
            tr = max(
                curr.high - curr.low,
                abs(curr.high - prev_close),
                abs(curr.low - prev_close),
            )
            trs.append(tr)

        window = trs[-period:]
        return sum(window) / len(window)

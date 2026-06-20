# region imports
from AlgorithmImports import *
from collections import deque
# endregion


class ORBVolumeBreakout(QCAlgorithm):
    """
    QuantConnect/LEAN port of a MultiCharts Opening-Range-Breakout (ORB)
    strategy that filters entries by:
      - daily ATR (stopbuffer = Nstop * ATRDaily)
      - daily average volume (minShares)
      - minimum daily ATR (minATR)
      - relative opening-range volume vs. its own lookback average (minRelVolumeX)

    Entries are stop orders placed off the opening-range bar (the bar that
    closes at MarketOpen + BarIntervalMinutes), direction set by whether
    that bar closed up or down. Exits are a fixed protective stop
    (EntryPrice -/+ stopbuffer) plus a hard end-of-day liquidation.

    ATRType cases 2-5 (Bekker-Parkinson, Garman-Klass, Yang-Zhang,
    Parkinson volatility) are placeholders pending the MultiCharts source
    for those functions -- they currently fall back to standard ATR with a
    one-time warning. Case 1 (AvgTrueRange) is fully implemented.
    """

    def Initialize(self) -> None:
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2023, 1, 1)
        self.SetCash(100000)

        # ---- Inputs (MultiCharts "Inputs:" block) ----
        self.n_stop = self.GetParameter("Nstop", 0.1)
        self.atr_type = int(self.GetParameter("ATRType", 1))
        self.lookback_days = int(self.GetParameter("LookbackDays", 20))
        self.min_price = self.GetParameter("minPrice", 5)
        self.min_shares = self.GetParameter("minShares", 1_000_000)
        self.min_atr = self.GetParameter("minATR", 0.50)
        self.min_rel_volume_x = self.GetParameter("minRelVolumeX", 1)
        self.risk_fraction = self.GetParameter("Risk", 5) / 100.0  # 1% used at sizing time below, per the MultiCharts code
        self.print_log = False

        # MultiCharts "barinterval" -- length of the opening range in minutes.
        self.bar_interval_minutes = 5
        if self.bar_interval_minutes >= 30:
            raise ValueError("Bar interval >= 30 doesn't work for the '930+barinterval' opening-range condition")

        self._atr_type_warned = False

        # ---- Symbols ----
        # MultiCharts ran this per-symbol; list your universe here.
        tickers = ["AAPL", "MSFT", "SPY"]
        self.symbol_states = {}
        for ticker in tickers:
            equity = self.AddEquity(ticker, Resolution.Minute)
            equity.SetDataNormalizationMode(DataNormalizationMode.Raw)
            self.symbol_states[equity.Symbol] = SymbolState(self, equity.Symbol, self.lookback_days)

        self.SetWarmUp(timedelta(days=self.lookback_days * 2))

    def OnData(self, data: Slice) -> None:
        for symbol, state in self.symbol_states.items():
            if symbol not in data.Bars:
                continue
            bar = data.Bars[symbol]
            state.on_minute_bar(self, bar)

    # ---- ATR / volatility dispatch (MultiCharts "Switch(ATRType)") ----
    def compute_daily_atr(self, state: "SymbolState") -> float:
        if self.atr_type == 1:
            return state.atr_indicator.Current.Value

        if not self._atr_type_warned:
            self.Log(
                f"ATRType={self.atr_type} (Bekker-Parkinson/Garman-Klass/Yang-Zhang/Parkinson) "
                "is not yet implemented -- falling back to standard ATR. "
                "Provide the source formulas to fill in compute_* below."
            )
            self._atr_type_warned = True

        # TODO: implement once source is provided.
        if self.atr_type == 2:
            return self._compute_bekker_parkinson_vol(state)
        if self.atr_type == 3:
            return self._compute_garman_klass_vol(state)
        if self.atr_type == 4:
            return self._compute_yang_zhang_vol(state)
        if self.atr_type == 5:
            return self._compute_parkinson_vol(state)

        return state.atr_indicator.Current.Value

    def _compute_bekker_parkinson_vol(self, state: "SymbolState") -> float:
        # TODO: port get_bekker_parkinson_vol(lookbackdays)data2 * close_data2
        return state.atr_indicator.Current.Value

    def _compute_garman_klass_vol(self, state: "SymbolState") -> float:
        # TODO: port get_garman_class_vol(lookbackdays)data2 * close_data2
        return state.atr_indicator.Current.Value

    def _compute_yang_zhang_vol(self, state: "SymbolState") -> float:
        # TODO: port get_yang_zhang_vol(lookbackdays)data2 * close_data2
        return state.atr_indicator.Current.Value

    def _compute_parkinson_vol(self, state: "SymbolState") -> float:
        # TODO: port get_parkinson_vol(lookbackdays)data2 * close_data2
        return state.atr_indicator.Current.Value


class SymbolState:
    """Per-symbol state mirroring the MultiCharts per-symbol Vars/Arrays."""

    def __init__(self, algorithm: QCAlgorithm, symbol: Symbol, lookback_days: int) -> None:
        self.symbol = symbol
        self.lookback_days = lookback_days

        # ---- Daily series (MultiCharts "data2") via a daily consolidator ----
        self.atr_indicator = AverageTrueRange(lookback_days)
        self.avg_volume_indicator = SimpleMovingAverage(lookback_days)

        self.daily_consolidator = TradeBarConsolidator(timedelta(days=1))
        self.daily_consolidator.DataConsolidated += self._on_daily_bar
        algorithm.SubscriptionManager.AddConsolidator(symbol, self.daily_consolidator)
        algorithm.RegisterIndicator(symbol, self.atr_indicator, self.daily_consolidator)

        # ---- Opening-range volume bookkeeping (MultiCharts array + n/j/jj) ----
        self.opening_range_volume_history = deque(maxlen=lookback_days)  # prior days only, excludes today
        self.days_seen = 0  # MultiCharts "n"
        self.prev_session_date = None  # MultiCharts "prevdatetime" (date portion)

        self.opening_range_bar_today = None  # (open, high, low, close, volume) captured at MarketOpen+barInterval
        self.rel_volume_pct_today = 0.0

        # ---- Position management ----
        self.stop_buffer = 0.0
        self.entry_order_ticket: OrderTicket = None
        self.protective_stop_ticket: OrderTicket = None

        self.market_open_time = time(9, 30)  # NYSE open; adjust per exchange if needed
        self.eod_liquidate_time = time(15, 55)

    def _on_daily_bar(self, sender, bar: TradeBar) -> None:
        self.avg_volume_indicator.Update(bar.EndTime, bar.Volume)

    @property
    def avg_volume(self) -> float:
        return self.avg_volume_indicator.Current.Value

    def on_minute_bar(self, algorithm: QCAlgorithm, bar: TradeBar) -> None:
        current_date = algorithm.Time.date()
        bar_close_time = bar.EndTime.time()
        opening_range_close_time = (
            datetime.combine(date.min, self.market_open_time) + timedelta(minutes=algorithm.bar_interval_minutes)
        ).time()

        # ---- Capture the opening-range bar once per day ----
        if bar_close_time == opening_range_close_time and current_date != self.prev_session_date:
            self._on_opening_range_bar(algorithm, bar, current_date)

        # ---- Manage exits every bar ----
        self._manage_exits(algorithm, bar)

    def _on_opening_range_bar(self, algorithm: QCAlgorithm, bar: TradeBar, current_date) -> None:
        self.opening_range_bar_today = bar
        self.prev_session_date = current_date
        self.days_seen += 1

        warmed_up = self.days_seen > self.lookback_days + 1  # MultiCharts "condition5"

        if warmed_up and len(self.opening_range_volume_history) == self.lookback_days:
            or_volume_avg = sum(self.opening_range_volume_history) / self.lookback_days
            self.rel_volume_pct_today = (
                100.0 * bar.Volume / or_volume_avg if or_volume_avg != 0 else 0.0
            )
        else:
            self.rel_volume_pct_today = 0.0

        self.opening_range_volume_history.append(bar.Volume)

        if not warmed_up:
            return

        self._evaluate_entry(algorithm, bar)

    def _evaluate_entry(self, algorithm: QCAlgorithm, bar: TradeBar) -> None:
        daily_atr = algorithm.compute_daily_atr(self)
        self.stop_buffer = algorithm.n_stop * daily_atr

        condition1 = bar.Open > algorithm.min_price
        condition2 = self.avg_volume >= algorithm.min_shares
        condition3 = daily_atr > algorithm.min_atr
        condition4 = self.rel_volume_pct_today > algorithm.min_rel_volume_x * 100

        if algorithm.print_log:
            algorithm.Log(
                f"{self.symbol.Value} stopbuffer:{self.stop_buffer:.4f} ATRDaily:{daily_atr:.4f} "
                f"AvgVolume:{self.avg_volume:.0f} RelVolumePct:{self.rel_volume_pct_today:.2f}"
            )

        if not (condition1 and condition2 and condition3 and condition4):
            return
        if self.stop_buffer == 0:
            return

        point_value = 1.0  # MultiCharts "bigpointvalue" -- 1 for equities
        risk_per_share = self.stop_buffer * point_value
        shares = round((algorithm.Portfolio.TotalPortfolioValue * 0.01) / risk_per_share)
        if shares <= 0:
            return

        tick_offset = 0.02  # MultiCharts "2 point" stop offset

        if bar.Close > bar.Open:
            stop_price = bar.High + tick_offset
            self.entry_order_ticket = algorithm.StopMarketOrder(self.symbol, shares, stop_price)
        elif bar.Close < bar.Open:
            stop_price = bar.Low - tick_offset
            self.entry_order_ticket = algorithm.StopMarketOrder(self.symbol, -shares, stop_price)

    def _manage_exits(self, algorithm: QCAlgorithm, bar: TradeBar) -> None:
        holding = algorithm.Portfolio[self.symbol]

        if not holding.Invested:
            return

        # Place/refresh the protective stop once per position.
        if self.protective_stop_ticket is None and self.stop_buffer > 0:
            entry_price = holding.AveragePrice
            if holding.IsLong:
                stop_price = entry_price - self.stop_buffer
                self.protective_stop_ticket = algorithm.StopMarketOrder(self.symbol, -holding.Quantity, stop_price)
            elif holding.IsShort:
                stop_price = entry_price + self.stop_buffer
                self.protective_stop_ticket = algorithm.StopMarketOrder(self.symbol, -holding.Quantity, stop_price)

        # Hard end-of-day liquidation (MultiCharts "time>1555").
        if bar.EndTime.time() > self.eod_liquidate_time:
            algorithm.Liquidate(self.symbol)
            if self.protective_stop_ticket is not None:
                self.protective_stop_ticket.Cancel()
            self.protective_stop_ticket = None
            self.entry_order_ticket = None

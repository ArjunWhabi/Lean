# region imports
from AlgorithmImports import *
# endregion


class SP500UniverseLogger(QCAlgorithm):
    """
    Live/backtest algorithm that tracks the daily S&P 500 constituent list
    (via the ETF Constituents Universe on SPY) and appends it to a CSV file
    in the Object Store. Runs bar-by-bar on OnData; universe membership
    changes are captured in OnSecuritiesChanged and a snapshot is written
    once per trading day.
    """

    def Initialize(self) -> None:
        self.SetStartDate(2023, 1, 1)
        self.SetEndDate(2023, 12, 31)
        self.SetCash(100000)

        self.UniverseSettings.Resolution = Resolution.Daily

        # ETF Constituents Universe on SPY -> proxy for daily S&P 500 membership.
        self.spy_universe = self.AddUniverse(
            self.Universe.ETF("SPY", self.UniverseSettings, lambda constituents: [c.Symbol for c in constituents])
        )

        self.csv_key = "sp500_constituents.csv"
        self._current_symbols = set()
        self._last_saved_date = None

        # Write the header row once if the file doesn't already exist.
        if not self.ObjectStore.ContainsKey(self.csv_key):
            self.ObjectStore.Save(self.csv_key, "date,ticker\n")

    def OnSecuritiesChanged(self, changes: SecurityChanges) -> None:
        for security in changes.AddedSecurities:
            self._current_symbols.add(security.Symbol)
        for security in changes.RemovedSecurities:
            self._current_symbols.discard(security.Symbol)

    def OnData(self, data: Slice) -> None:
        # Bar-by-bar entry point. Snapshot constituents once per new trading day.
        today = self.Time.date()
        if today == self._last_saved_date:
            return

        if not self._current_symbols:
            return

        self._last_saved_date = today
        self._append_constituents_to_csv(today)

    def _append_constituents_to_csv(self, as_of_date) -> None:
        existing = self.ObjectStore.Read(self.csv_key) if self.ObjectStore.ContainsKey(self.csv_key) else "date,ticker\n"

        rows = [f"{as_of_date.isoformat()},{symbol.Value}" for symbol in sorted(self._current_symbols, key=lambda s: s.Value)]
        new_content = existing + "\n".join(rows) + "\n"

        self.ObjectStore.Save(self.csv_key, new_content)
        self.Debug(f"{as_of_date}: saved {len(rows)} S&P 500 constituents to {self.csv_key}")

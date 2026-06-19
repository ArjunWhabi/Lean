# QuantConnect Research environment notebook/script
# Pulls the daily historical S&P 500 constituent list (Index Constituents
# Universe, CBOE "SPX" data) and saves it to a CSV.

from AlgorithmImports import *
import pandas as pd

qb = QuantBook()

universe_settings = UniverseSettings
universe_settings.Resolution = Resolution.Daily

spx_universe = qb.AddUniverse(qb.Universe.Index("SPX", universe_settings))

start = datetime(2015, 1, 1)
end = datetime(2024, 1, 1)

# Returns a pandas Series indexed by date; each value is the list of
# constituent data objects (one per symbol) for that date.
history = qb.UniverseHistory(spx_universe, start, end)

rows = []
for as_of_date, constituents in history.items():
    for c in constituents:
        rows.append({"date": as_of_date.date().isoformat(), "ticker": c.Symbol.Value})

df = pd.DataFrame(rows).sort_values(["date", "ticker"]).reset_index(drop=True)

output_path = "sp500_constituents.csv"
df.to_csv(output_path, index=False)

print(f"Saved {len(df)} rows covering {df['date'].nunique()} trading days to {output_path}")
df.head(20)

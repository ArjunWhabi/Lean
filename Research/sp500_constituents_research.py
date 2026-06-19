# QuantConnect Research environment notebook/script
# Pulls the daily historical S&P 500 constituent list (Index Constituents
# Universe, CBOE "SPX" data) and saves it to a CSV.

from AlgorithmImports import *
import pandas as pd

qb = QuantBook()

qb.UniverseSettings.Resolution = Resolution.Daily

spx_universe = qb.AddUniverse(qb.Universe.Index("SPX", qb.UniverseSettings))

start = datetime(2015, 1, 1)
end = datetime(2024, 1, 1)

# Returns a pandas Series indexed by date; each value is the list of
# constituent data objects (one per symbol) for that date.
history = qb.UniverseHistory(spx_universe, start, end)

print(f"history type: {type(history)}")
print(f"history length: {len(history)}")

rows = []
for as_of_date, constituents in history.items():
    constituents = list(constituents)
    if not constituents:
        continue
    for c in constituents:
        rows.append({"date": as_of_date.date().isoformat(), "ticker": c.Symbol.Value})

if not rows:
    raise RuntimeError(
        "No constituent rows were returned by UniverseHistory. "
        "This usually means the SPX Index Constituents dataset isn't available "
        "in the current environment (e.g. running the local Lean CLI research "
        "container instead of QuantConnect's cloud Research environment, or no "
        "data subscription for this dataset). Verify by running this in "
        "QuantConnect cloud Research, and confirm the date range overlaps "
        "available data."
    )

df = pd.DataFrame(rows).sort_values(["date", "ticker"]).reset_index(drop=True)

output_path = "sp500_constituents.csv"
df.to_csv(output_path, index=False)

print(f"Saved {len(df)} rows covering {df['date'].nunique()} trading days to {output_path}")
df.head(20)

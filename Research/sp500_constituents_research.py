# QuantConnect Research environment notebook/script
# Pulls the daily historical S&P 500 constituent list via the ETF
# Constituents Universe on SPY (the S&P 500 ETF) and saves it to a CSV.

from AlgorithmImports import *
import pandas as pd

qb = QuantBook()

qb.UniverseSettings.Resolution = Resolution.Daily

# ETF Constituents Universe: returns, for each date, the list of constituent
# securities (with weights) underlying the SPY ETF, i.e. the S&P 500.
spy_universe = qb.AddUniverse(
    qb.Universe.ETF("SPY", qb.UniverseSettings, lambda constituents: [c.Symbol for c in constituents])
)

start = datetime(2020, 1, 1)
end = datetime(2024, 1, 1)

history = qb.UniverseHistory(spy_universe, start, end)

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
        "No constituent rows were returned by UniverseHistory. Check that the "
        "date range overlaps the ETF Constituents dataset's coverage, and that "
        "qb.Universe.ETF('SPY', ...) is the correct universe accessor for your "
        "Lean/QC API version (it may have moved or been renamed)."
    )

df = pd.DataFrame(rows).sort_values(["date", "ticker"]).reset_index(drop=True)

output_path = "sp500_constituents.csv"
df.to_csv(output_path, index=False)

print(f"Saved {len(df)} rows covering {df['date'].nunique()} trading days to {output_path}")
df.head(20)

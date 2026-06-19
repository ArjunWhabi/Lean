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
print(f"sample index: {history.index[0]!r}")

def _extract_date(index_key):
    # The index key is a (Symbol, Timestamp) tuple for this universe's
    # UniverseHistory; the Timestamp is the second element.
    if isinstance(index_key, tuple):
        for part in index_key:
            if isinstance(part, (pd.Timestamp, datetime)):
                return pd.Timestamp(part).date().isoformat()
        raise ValueError(f"No Timestamp found in index tuple: {index_key!r}")
    return pd.Timestamp(index_key).date().isoformat()

def _extract_ticker(constituent):
    # constituent may already be a Symbol, or an object exposing .Symbol.
    symbol_obj = getattr(constituent, "Symbol", constituent)
    return getattr(symbol_obj, "Value", str(symbol_obj))

rows = []
for index_key, constituents in history.items():
    as_of_date = _extract_date(index_key)
    if not isinstance(constituents, (list, tuple, set)):
        try:
            constituents = list(constituents)
        except TypeError:
            constituents = [constituents]
    for c in constituents:
        rows.append({"date": as_of_date, "ticker": _extract_ticker(c)})

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

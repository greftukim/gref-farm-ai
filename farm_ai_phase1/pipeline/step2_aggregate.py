"""Step 2: 5분 → 1시간 → 주간 집계."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from utils.time_aggregation import aggregate_to_hourly, aggregate_to_weekly

BASE = Path(__file__).parent.parent


def run(input_csv: str = None,
        hourly_csv: str = None,
        weekly_csv: str = None):
    inp  = input_csv or str(BASE / 'processed' / 'priva_with_internal.csv')
    outH = hourly_csv or str(BASE / 'processed' / 'priva_hourly.csv')
    outW = weekly_csv or str(BASE / 'processed' / 'priva_weekly.csv')
    Path(outH).parent.mkdir(exist_ok=True)

    priva = pd.read_csv(inp, parse_dates=['datetime']).set_index('datetime')
    hourly = aggregate_to_hourly(priva)
    hourly.to_csv(outH)

    weekly_cols = [c for c in ['radiation_internal', 'meas grh temp', 'meas CO2 conc'] if c in hourly.columns]
    weekly = aggregate_to_weekly(hourly[weekly_cols])
    weekly.to_csv(outW)

    print(f"[Step 2] Hourly: {len(hourly):,} rows | Weekly: {len(weekly)} rows")
    return hourly, weekly


if __name__ == '__main__':
    run()

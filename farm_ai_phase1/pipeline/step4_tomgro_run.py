"""Step 4: 전 작기 TOMGRO 주간 시뮬레이션."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from models.tomgro_week import run_tomgro_week

BASE = Path(__file__).parent.parent


def run(lai_csv: str = None, output_csv: str = None) -> pd.DataFrame:
    inp = lai_csv or str(BASE / 'processed' / 'weekly_with_lai.csv')
    out = output_csv or str(BASE / 'processed' / 'tomgro_predictions.csv')
    Path(out).parent.mkdir(exist_ok=True)

    weekly = pd.read_csv(inp, parse_dates=['week_end'])
    results = []

    for _, row in weekly.iterrows():
        week_end   = row['week_end']
        week_start = week_end - pd.Timedelta(days=6)
        result = run_tomgro_week(
            start=str(week_start.date()),
            end=str(week_end.date()),
            lai=row['lai'],
        )
        results.append({
            'week_end':          week_end,
            'tomgro_prediction': result['fruit_fw_kg_m2'],
            'dli_internal':      result['dli_internal'],
            'gross_photo':       result['gross_photo_g_m2'],
            'net_dm':            result['net_dm_g_m2'],
            'lai':               row['lai'],
        })

    df = pd.DataFrame(results)
    df.to_csv(out, index=False)
    print(f"[Step 4] TOMGRO: {len(df)} weeks, "
          f"mean prediction={df['tomgro_prediction'].mean():.3f} kg/m²/week")
    return df


if __name__ == '__main__':
    run()

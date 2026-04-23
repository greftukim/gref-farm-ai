"""Step 3: 주간 생육 조사 → LAI 계산 (SHAPE 0.5 적용)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from models.lai import estimate_lai

BASE = Path(__file__).parent.parent


def run(input_csv: str = None, output_csv: str = None) -> pd.DataFrame:
    inp = input_csv or str(BASE / 'data' / 'weekly_combined.csv')
    out = output_csv or str(BASE / 'processed' / 'weekly_with_lai.csv')
    Path(out).parent.mkdir(exist_ok=True)

    weekly = pd.read_csv(inp, parse_dates=['week_end'])
    weekly['lai'] = weekly.apply(
        lambda r: estimate_lai(r['leaf_length_cm'], r['leaf_width_cm'], r['n_leaves']),
        axis=1
    )
    weekly.to_csv(out, index=False)

    print(f"[Step 3] LAI computed for {len(weekly)} weeks. "
          f"mean={weekly['lai'].mean():.2f}, range={weekly['lai'].min():.2f}~{weekly['lai'].max():.2f}")
    return weekly


if __name__ == '__main__':
    run()

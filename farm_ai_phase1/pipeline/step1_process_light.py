"""Step 1: 외부 일사 → 내부 광량 변환 (투과율 50%)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from config import LIGHT_TRANSMISSION

BASE = Path(__file__).parent.parent


def run(input_csv: str = None, output_csv: str = None) -> pd.DataFrame:
    inp = input_csv or str(BASE / 'data' / 'priva_clean.csv')
    out = output_csv or str(BASE / 'processed' / 'priva_with_internal.csv')
    Path(out).parent.mkdir(exist_ok=True)

    priva = pd.read_csv(inp, parse_dates=['datetime'])
    priva['radiation_internal'] = priva['radiation'] * LIGHT_TRANSMISSION
    priva.to_csv(out, index=False)
    print(f"[Step 1] {len(priva):,} rows → {out}")
    return priva


if __name__ == '__main__':
    run()

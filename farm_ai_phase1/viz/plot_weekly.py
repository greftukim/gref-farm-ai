"""주차별 예측 vs 실측 그래프."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

BASE = Path(__file__).parent.parent


def plot(csv_path: str = None, out_path: str = None):
    inp = csv_path or str(BASE / 'outputs' / 'weekly_predictions.csv')
    out = out_path or str(BASE / 'outputs' / 'plot_weekly.png')

    df = pd.read_csv(inp, parse_dates=['week_end'])
    df = df.sort_values('week_end')

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df['week_end'], df['actual_harvest'],      'k-o', ms=5, lw=1.5, label='Actual')
    ax.plot(df['week_end'], df['xgb_cv_prediction'],   'b-s', ms=4, lw=1.5, label='Full Chain (5-fold CV)')
    ax.plot(df['week_end'], df['tomgro_sv_prediction'],'g--', lw=1.0, label='TOMGRO + S&V')
    ax.plot(df['week_end'], df['tomgro_prediction'],   'r:',  lw=1.0, label='TOMGRO only')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=4))
    plt.xticks(rotation=45, ha='right')
    ax.set_ylabel('Yield (kg/m²/week)')
    ax.set_title('GREF Phase 1 — Weekly Prediction vs Actual')
    ax.legend(loc='upper left')
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"[viz] saved: {out}")
    return fig


if __name__ == '__main__':
    plot()

"""월별 WMAPE 막대 그래프 (XGBoost CV 기준)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BASE = Path(__file__).parent.parent
MONTH_LABELS = {7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov',
                12:'Dec', 1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr'}


def _wmape(pred, actual):
    mask = actual > 0
    return np.sum(np.abs(pred[mask] - actual[mask])) / np.sum(actual[mask]) * 100


def plot(csv_path: str = None, out_path: str = None):
    inp = csv_path or str(BASE / 'outputs' / 'weekly_predictions.csv')
    out = out_path or str(BASE / 'outputs' / 'plot_monthly.png')

    df = pd.read_csv(inp, parse_dates=['week_end'])
    df['month'] = df['week_end'].dt.month
    monthly = (
        df.groupby('month')
          .apply(lambda g: _wmape(g['xgb_cv_prediction'].values, g['actual_harvest'].values))
          .rename('wmape')
          .reset_index()
    )
    monthly['label'] = monthly['month'].map(MONTH_LABELS)

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ['#e07b54' if v > 30 else '#5490e0' for v in monthly['wmape']]
    bars = ax.bar(monthly['label'], monthly['wmape'], color=colors, edgecolor='white')

    for bar, v in zip(bars, monthly['wmape']):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.5, f'{v:.1f}%',
                ha='center', va='bottom', fontsize=9)

    ax.axhline(25.2, color='green', ls='--', lw=1.5, label='Overall 25.2%')
    ax.set_ylabel('WMAPE (%)')
    ax.set_title('GREF Phase 1 — Monthly WMAPE (Full Chain CV)')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"[viz] saved: {out}")
    return fig


if __name__ == '__main__':
    plot()

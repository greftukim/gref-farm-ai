"""3단계 오차율 체인 그래프 (TOMGRO → S&V → Full Chain)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import matplotlib.pyplot as plt

BASE = Path(__file__).parent.parent


def plot(mape_tomgro: float = None,
         mape_sv: float = None,
         mape_final: float = None,
         out_path: str = None):
    """mape_* 값이 없으면 validation_report.txt 에서 파싱."""
    out = out_path or str(BASE / 'outputs' / 'plot_mape_chain.png')

    if mape_tomgro is None:
        rep = Path(BASE / 'outputs' / 'validation_report.txt').read_text(encoding='utf-8')
        import re
        vals = re.findall(r'(\d+\.\d+)%', rep)
        mape_tomgro, mape_sv, mape_final = float(vals[0]), float(vals[1]), float(vals[2])

    stages  = ['TOMGRO\nonly', 'TOMGRO\n+ S&V', 'Full Chain\n(5-fold CV)']
    values  = [mape_tomgro, mape_sv, mape_final]
    colors  = ['#e07b54', '#e0c454', '#5490e0']

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(stages, values, color=colors, width=0.5, edgecolor='white', linewidth=1.5)

    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.5, f'{v:.1f}%',
                ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax.axhline(25.2, color='green', ls='--', lw=1.5, label='Target 25.2%')
    ax.set_ylabel('WMAPE (%)')
    ax.set_ylim(0, max(values) * 1.25)
    ax.set_title('GREF Phase 1 — MAPE Reduction Chain')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"[viz] saved: {out}")
    return fig


if __name__ == '__main__':
    plot()

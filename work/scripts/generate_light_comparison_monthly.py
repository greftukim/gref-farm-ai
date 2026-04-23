"""
월별 외부 DLI vs 내부 DLI 및 투과율 차트 생성.

입력: 원본_데이터/export.csv (Priva 5분 간격 수집)
출력: site_images/light_comparison_monthly.png

계산:
- 외부 DLI: radiation(W/m²) → 시간당 MJ/m² → 월 평균 일일 DLI
- 투과율: 유리 기본 투과율 0.70에 커튼 3장의 shading 효과 합성
  effective = 0.70 × ∏_i (1 - curtain_i/100 × α_i)
  (α_1=0.50, α_2=0.55, α_3=0.45) — 경험적 추정치
- 내부 DLI = 외부 × effective transmittance (시점별)
- 월 투과율 = 내부 DLI / 외부 DLI × 100 (월합 기준)
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

BASE = Path(__file__).parent.parent.parent
DATA = BASE / '원본_데이터' / 'export.csv'
OUT  = BASE / 'site_images' / 'light_comparison_monthly.png'

GLASS_T = 0.70
ALPHA1, ALPHA2, ALPHA3 = 0.50, 0.55, 0.45  # shading coefficients per curtain
INTERVAL_SEC = 300  # 5 min

MONTH_LABELS = {6:'Jun',7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',
                12:'Dec',1:'Jan',2:'Feb',3:'Mar',4:'Apr'}


def main():
    df = pd.read_csv(DATA, sep=';', header=0, skiprows=[1,2])
    df = df.rename(columns={'Unnamed: 0': 'datetime'})
    df['datetime'] = pd.to_datetime(df['datetime'], format='%d-%m-%Y %H:%M:%S', errors='coerce')
    df = df.dropna(subset=['datetime']).copy()

    # 작기 기간 (2025-07-09 ~ 2026-04-03 — 4월 말 철거 전까지 데이터)
    df = df[(df['datetime'] >= '2025-07-01') & (df['datetime'] < '2026-05-01')].copy()

    # 투과율 (시점별)
    c1 = df['meas curtain 1'].clip(0,100).fillna(0)
    c2 = df['meas curtain 2'].clip(0,100).fillna(0)
    c3 = df['meas curtain 3'].clip(0,100).fillna(0)
    trans = GLASS_T * (1 - c1/100*ALPHA1) * (1 - c2/100*ALPHA2) * (1 - c3/100*ALPHA3)
    df['trans'] = trans

    # 외부·내부 에너지(MJ/m²)
    rad = df['radiation'].clip(lower=0).fillna(0)
    df['ext_MJ'] = rad * INTERVAL_SEC / 1e6
    df['int_MJ'] = rad * trans * INTERVAL_SEC / 1e6

    # 월별 집계
    df['ym'] = df['datetime'].dt.to_period('M')
    g = df.groupby('ym').agg(
        ext_sum=('ext_MJ','sum'),
        int_sum=('int_MJ','sum'),
        days=('datetime', lambda s: s.dt.date.nunique()),
    ).reset_index()
    g['ext_dli'] = g['ext_sum'] / g['days']    # MJ/m²/day
    g['int_dli'] = g['int_sum'] / g['days']
    g['trans_pct'] = g['int_sum'] / g['ext_sum'] * 100
    g['label'] = g['ym'].dt.month.map(MONTH_LABELS)

    print(g[['ym','days','ext_dli','int_dli','trans_pct']].to_string(index=False))

    # 전 작기 평균 투과율
    overall_trans = g['int_sum'].sum() / g['ext_sum'].sum() * 100
    print(f"\n전 작기 평균 투과율: {overall_trans:.1f}%")

    # ═══ 차트 ═══
    mpl.rcParams['font.family'] = 'DejaVu Sans'
    fig, ax1 = plt.subplots(figsize=(11, 5.2))

    x = range(len(g))
    width = 0.38

    b1 = ax1.bar([i-width/2 for i in x], g['ext_dli'], width, label='External DLI',
                 color='#6EA8DB', edgecolor='white')
    b2 = ax1.bar([i+width/2 for i in x], g['int_dli'], width, label='Internal DLI (est.)',
                 color='#1F4E79', edgecolor='white')

    ax1.set_ylabel('DLI (MJ/m²/day)', fontsize=11)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(g['label'])
    ax1.grid(axis='y', alpha=0.25)
    ax1.set_axisbelow(True)

    # 투과율 — 오른쪽 축
    ax2 = ax1.twinx()
    ln = ax2.plot(list(x), g['trans_pct'], color='#C0392B', marker='o',
                  linewidth=2, markersize=7, label='Transmittance (%)')
    for xi, v in zip(x, g['trans_pct']):
        ax2.text(xi, v + 1.2, f'{v:.0f}%', ha='center', va='bottom',
                 fontsize=9, color='#C0392B', fontweight='bold')
    ax2.set_ylabel('Transmittance (%)', fontsize=11, color='#C0392B')
    ax2.tick_params(axis='y', labelcolor='#C0392B')
    ax2.set_ylim(0, max(45, g['trans_pct'].max()+5))

    # 저온기 음영 (11/12 ~ 1/7 = Nov-Dec-Jan 대략)
    lowtemp_months = ['Nov', 'Dec', 'Jan']
    lowtemp_idx = [i for i, lbl in enumerate(g['label']) if lbl in lowtemp_months]
    if lowtemp_idx:
        left = min(lowtemp_idx) - 0.5
        right = max(lowtemp_idx) + 0.5
        ax1.axvspan(left, right, color='#F2C080', alpha=0.18, zorder=0)
        ax1.text((left+right)/2, ax1.get_ylim()[1]*0.92, 'Low-temp period',
                 ha='center', fontsize=9, color='#8A5A0A', fontweight='bold')

    # 전체 작기 평균 투과율 라인
    ax2.axhline(overall_trans, color='#8B4513', linestyle='--', linewidth=1.2, alpha=0.6)
    ax2.text(len(g)-0.5, overall_trans+0.5, f'Avg {overall_trans:.1f}%',
             ha='right', va='bottom', fontsize=9, color='#8B4513')

    # 범례 합치기
    lines = [b1, b2, ln[0]]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper right', fontsize=10, framealpha=0.95)

    ax1.set_title('Monthly Light Transmittance — Full Crop Period (2025.07 ~ 2026.04)',
                  fontsize=12, fontweight='bold', pad=12)

    OUT.parent.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n✅ saved: {OUT}")


if __name__ == '__main__':
    main()

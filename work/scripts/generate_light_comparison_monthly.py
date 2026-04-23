"""
월별 광 투과율 차트 — 실측 Priva 데이터 기반 (한국어).

입력:
  - 원본_데이터/export.csv         : 외부 radiation sum (J/cm² 누적)
  - 원본_데이터/export(cal).csv    : 내부 cal radiation sum (J/cm² 누적, daehan221223:Cmp 1)

출력: site_images/light_comparison_monthly.png

계산:
- 일별 DLI = 해당 일자의 cumulative sum 최댓값 (Priva가 매일 00:00 리셋)
- 월별 합산·평균 (일평균 DLI = 월합 / 일수)
- 투과율 = 내부 월합 / 외부 월합 × 100
- 단위 환산: 1 J/cm² = 0.01 MJ/m²
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import font_manager

BASE = Path(__file__).parent.parent.parent
EXT_CSV = BASE / '원본_데이터' / 'export.csv'
INT_CSV = BASE / '원본_데이터' / 'export(cal).csv'
OUT     = BASE / 'site_images' / 'light_comparison_monthly.png'

MONTH_LABELS_KO = {6:'6월',7:'7월',8:'8월',9:'9월',10:'10월',11:'11월',
                   12:'12월',1:'1월',2:'2월',3:'3월',4:'4월'}


def _setup_korean_font():
    for fp in ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
               '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf'):
        if Path(fp).exists():
            font_manager.fontManager.addfont(fp)
    mpl.rcParams['font.family'] = 'NanumGothic'
    mpl.rcParams['axes.unicode_minus'] = False


def load_external():
    df = pd.read_csv(EXT_CSV, sep=';', header=0, skiprows=[1,2])
    df = df.rename(columns={'Unnamed: 0':'datetime'})
    df['datetime'] = pd.to_datetime(df['datetime'], format='%d-%m-%Y %H:%M:%S', errors='coerce')
    df = df.dropna(subset=['datetime']).copy()
    df['ext_sum_jcm2'] = pd.to_numeric(df['radiation sum'], errors='coerce')
    return df[['datetime','ext_sum_jcm2']]


def load_internal():
    df = pd.read_csv(INT_CSV, sep=';', header=0, skiprows=[1,2])
    df = df.rename(columns={'Unnamed: 0':'datetime', 'M102N1R6.1V2':'int_sum_jcm2'})
    df['datetime'] = pd.to_datetime(df['datetime'], format='%d-%m-%Y %H:%M:%S', errors='coerce')
    df = df.dropna(subset=['datetime']).copy()
    df['int_sum_jcm2'] = pd.to_numeric(df['int_sum_jcm2'], errors='coerce')
    return df[['datetime','int_sum_jcm2']]


def main():
    _setup_korean_font()

    ext = load_external()
    intn = load_internal()
    df = pd.merge(ext, intn, on='datetime', how='inner')

    # 작기 기간 (2025-07-01 ~ 2026-04-30)
    df = df[(df['datetime'] >= '2025-07-01') & (df['datetime'] < '2026-05-01')].copy()

    # 일별 최댓값 = 그 날의 누적 DLI (Priva 리셋 가정)
    df['date'] = df['datetime'].dt.date
    daily = df.groupby('date').agg(
        ext_day_jcm2=('ext_sum_jcm2', 'max'),
        int_day_jcm2=('int_sum_jcm2', 'max'),
    ).reset_index()

    # J/cm² → MJ/m² (× 0.01)
    daily['ext_day_MJ'] = daily['ext_day_jcm2'] * 0.01
    daily['int_day_MJ'] = daily['int_day_jcm2'] * 0.01
    daily['date'] = pd.to_datetime(daily['date'])

    # 월별 집계
    daily['ym'] = daily['date'].dt.to_period('M')
    g = daily.groupby('ym').agg(
        ext_sum=('ext_day_MJ', 'sum'),
        int_sum=('int_day_MJ', 'sum'),
        days=('date', 'count'),
    ).reset_index()
    g['ext_dli'] = g['ext_sum'] / g['days']
    g['int_dli'] = g['int_sum'] / g['days']
    g['trans_pct'] = g['int_sum'] / g['ext_sum'] * 100
    g['label'] = g['ym'].dt.month.map(MONTH_LABELS_KO)

    print(g[['ym','days','ext_dli','int_dli','trans_pct']].to_string(index=False))
    overall_trans = g['int_sum'].sum() / g['ext_sum'].sum() * 100
    print(f"\n전 작기 평균 투과율 (실측): {overall_trans:.1f}%")

    # ═══ 차트 ═══
    fig, ax1 = plt.subplots(figsize=(11, 5.4))

    x = range(len(g))
    width = 0.38

    b1 = ax1.bar([i-width/2 for i in x], g['ext_dli'], width, label='외부 DLI (실측)',
                 color='#6EA8DB', edgecolor='white')
    b2 = ax1.bar([i+width/2 for i in x], g['int_dli'], width, label='내부 DLI (Priva 실측)',
                 color='#1F4E79', edgecolor='white')

    ax1.set_ylabel('일일 적산광량 DLI (MJ/m²/일)', fontsize=11)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(g['label'])
    ax1.grid(axis='y', alpha=0.25)
    ax1.set_axisbelow(True)

    ax2 = ax1.twinx()
    ln = ax2.plot(list(x), g['trans_pct'], color='#C0392B', marker='o',
                  linewidth=2, markersize=7, label='투과율 (%)')
    for xi, v in zip(x, g['trans_pct']):
        ax2.text(xi, v + 1.0, f'{v:.0f}%', ha='center', va='bottom',
                 fontsize=9, color='#C0392B', fontweight='bold')
    ax2.set_ylabel('투과율 (%)', fontsize=11, color='#C0392B')
    ax2.tick_params(axis='y', labelcolor='#C0392B')
    ax2.set_ylim(0, max(45, g['trans_pct'].max()+8))

    # 저온기 음영
    lowtemp = ['11월','12월','1월']
    idx = [i for i,l in enumerate(g['label']) if l in lowtemp]
    if idx:
        left, right = min(idx)-0.5, max(idx)+0.5
        ax1.axvspan(left, right, color='#F2C080', alpha=0.18, zorder=0)
        # 라벨을 저온기 구간 하단(x축 바로 위)에 배치해 투과율 라인과 겹치지 않게
        ax1.text((left+right)/2, ax1.get_ylim()[1]*0.08, '저온기 구간',
                 ha='center', fontsize=10, color='#8A5A0A', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF4DE',
                           edgecolor='#D4A050', alpha=0.95))

    ax2.axhline(overall_trans, color='#8B4513', linestyle='--', linewidth=1.2, alpha=0.6)
    ax2.text(len(g)-0.5, overall_trans+0.5, f'전 작기 평균 {overall_trans:.1f}%',
             ha='right', va='bottom', fontsize=9, color='#8B4513')

    lines = [b1, b2, ln[0]]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper right', fontsize=10, framealpha=0.95)

    ax1.set_title('월별 광 투과율 — 전 작기 (2025.07 ~ 2026.04)  ·  Priva 실측',
                  fontsize=13, fontweight='bold', pad=12)

    OUT.parent.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n✅ saved: {OUT}")


if __name__ == '__main__':
    main()

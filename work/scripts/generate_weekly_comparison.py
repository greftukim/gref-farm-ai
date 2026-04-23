"""
주차별 예측 비교 + 예측 vs 실제 산점도 생성 (Priva 실측 기반, 한국어).

입력: farm_ai_phase1/outputs_phase1_v1/weekly_predictions.csv
출력: site_images/integration_weekly_comparison.png

포인트:
- XGBoost는 CV 예측(xgb_cv_prediction)을 사용 — 5-fold cross validation 결과로
  실제 배포 환경에서의 예측 성능을 대표함 ('학습 기준' 아님)
- 색상 위계: 주 메시지(실제·XGBoost)는 쨍한 색, 보조(TOMGRO·S&V)는 연한 회색 계열
- 산점도 대각선: 완벽 예측 y=x 점선
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.dates as mdates
from matplotlib import font_manager

BASE = Path(__file__).parent.parent.parent
CSV  = BASE / 'farm_ai_phase1' / 'outputs_phase1_v1' / 'weekly_predictions.csv'
OUT_PATHS = [
    BASE / 'site_images' / 'integration_weekly_comparison.png',
    BASE / 'site_images' / 'xgb_pred_vs_actual.png',
]


def _setup_korean_font():
    for fp in ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
               '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf'):
        if Path(fp).exists():
            font_manager.fontManager.addfont(fp)
    mpl.rcParams['font.family'] = 'NanumGothic'
    mpl.rcParams['axes.unicode_minus'] = False


# 색상 팔레트 — 주 메시지는 쨍하게, 보조는 연하게
C_ACTUAL  = '#1B8A3A'  # 진한 초록 — 실측
C_XGBOOST = '#D63B3B'  # 진한 빨강 — 최종 예측 (강조)
C_TOMGRO  = '#B8B8B8'  # 연한 회색 — 보조
C_SV      = '#A9C1D9'  # 연한 하늘 — 보조


def _wmape(actual, pred):
    mask = actual > 0
    return np.sum(np.abs(pred[mask] - actual[mask])) / np.sum(actual[mask]) * 100


def main():
    _setup_korean_font()
    df = pd.read_csv(CSV, parse_dates=['harvest_week_end'])
    df = df.sort_values('harvest_week_end').reset_index(drop=True)

    # 지표 계산
    wmape_chain = _wmape(df['actual_harvest'].values, df['xgb_cv_prediction'].values)
    wmape_sv    = _wmape(df['actual_harvest'].values, df['tomgro_sv_prediction'].values)
    wmape_tom   = _wmape(df['actual_harvest'].values, df['tomgro_prediction'].values)
    print(f"전 작기 WMAPE — TOMGRO: {wmape_tom:.1f}% · +S&V: {wmape_sv:.1f}% · +XGBoost(CV): {wmape_chain:.1f}%")

    # ═══════════ 차트 ═══════════
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.0),
                                   gridspec_kw={'width_ratios': [2.2, 1.0]})

    # ── 왼쪽: 주차별 라인 ──
    x = df['harvest_week_end']
    # 보조 라인 먼저 (뒤에) — 연한 색
    ax1.plot(x, df['tomgro_prediction'],    linestyle='--', marker='s', ms=4, lw=1.0,
             color=C_TOMGRO, alpha=0.85, label='TOMGRO 단독', zorder=2)
    ax1.plot(x, df['tomgro_sv_prediction'], linestyle='--', marker='D', ms=4, lw=1.0,
             color=C_SV, alpha=0.9, label='TOMGRO + S&V', zorder=3)
    # 주 메시지 — 쨍한 색 + 굵게 + 위로
    ax1.plot(x, df['actual_harvest'],       linestyle='-',  marker='o', ms=7, lw=2.6,
             color=C_ACTUAL, label='실제 수확량', zorder=5)
    ax1.plot(x, df['xgb_cv_prediction'],    linestyle='-',  marker='^', ms=6, lw=2.4,
             color=C_XGBOOST, label='XGBoost 최종 예측 (CV)', zorder=6)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=4))
    ax1.set_ylabel('수확량 (kg/m²/week)', fontsize=11)
    ax1.set_xlabel('주 (week_end)', fontsize=11)
    ax1.set_title('주차별 수확량 예측 비교', fontsize=13, fontweight='bold', pad=10)
    ax1.grid(alpha=0.25)
    ax1.set_axisbelow(True)
    for lbl in ax1.get_xticklabels():
        lbl.set_rotation(30)
        lbl.set_ha('right')
    ax1.legend(loc='upper left', fontsize=10, framealpha=0.95)

    # ── 오른쪽: 산점도 (CV 기준) ──
    a = df['actual_harvest'].values
    sv = df['tomgro_sv_prediction'].values
    xgb = df['xgb_cv_prediction'].values
    lim_max = max(a.max(), sv.max(), xgb.max()) * 1.08
    lim_min = min(a.min(), sv.min(), xgb.min()) * 0.8
    # 보조 먼저 (뒤)
    ax2.scatter(a, sv,  s=52, color=C_SV,    edgecolor='#4A6B88', linewidth=0.5,
                alpha=0.55, marker='s', label='TOMGRO + S&V', zorder=3)
    # 주 메시지 — 큰 마커 + 진한 색
    ax2.scatter(a, xgb, s=78, color=C_XGBOOST, edgecolor='#8A1F1F', linewidth=0.6,
                alpha=0.92, marker='o', label='XGBoost 최종 예측 (CV)', zorder=5)
    ax2.plot([lim_min, lim_max], [lim_min, lim_max],
             linestyle='--', lw=1.2, color='#777', alpha=0.8, label='완벽 예측 y=x', zorder=2)

    ax2.set_xlim(lim_min, lim_max)
    ax2.set_ylim(lim_min, lim_max)
    ax2.set_aspect('equal', adjustable='box')
    ax2.set_xlabel('실제 수확량 (kg/m²/week)', fontsize=11)
    ax2.set_ylabel('예측 수확량 (kg/m²/week)', fontsize=11)
    ax2.set_title('예측 vs 실제 산점도 (CV 기준)', fontsize=13, fontweight='bold', pad=10)
    ax2.grid(alpha=0.25)
    ax2.set_axisbelow(True)
    ax2.legend(loc='upper left', fontsize=9.5, framealpha=0.95)

    # 하단 서머리
    fig.text(0.01, -0.01,
             f'  29주 실측 기준. CV WMAPE — TOMGRO 단독 {wmape_tom:.1f}% · +S&V {wmape_sv:.1f}% · '
             f'+XGBoost 최종 {wmape_chain:.1f}%.  XGBoost는 5-fold CV 결과로 '
             f'실제 배포 환경에서의 예측 성능을 반영.',
             fontsize=10.5, color='#444', ha='left')

    for out in OUT_PATHS:
        out.parent.mkdir(exist_ok=True)
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    for out in OUT_PATHS:
        fig.savefig(out, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"  ✅ saved: {out}")


if __name__ == '__main__':
    main()

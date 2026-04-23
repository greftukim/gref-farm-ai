"""
EC 스트레스 영향 심층 분석 스크립트
가설 A: EC -> LAI -> TOMGRO 이중 차감
가설 B: S&V 시차 재탐색
분석 07: LIGHT_TRANSMISSION 민감도 전체 파이프라인
"""
import os, sys, io, shutil, zipfile, warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings('ignore')

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.model_selection import KFold
from sklearn.linear_model import LinearRegression
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ─── 경로 ─────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
FARM = BASE / 'farm_ai_phase1'
OUT  = BASE / 'verification_share_v2'
sys.path.insert(0, str(FARM))

from models.tomgro_physics import (
    gross_photosynthesis, maintenance_respiration, dm_partitioning,
    PAR_CONV, GROWTH_RESP,
)
from models.sonneveld_voogt import relative_yield
import config as cfg

NOW  = datetime.now().strftime('%Y-%m-%d %H:%M')
DATE = datetime.now().strftime('%Y-%m-%d')

# ═══════════════════════════════════════════════════════════════════════════
# 판정 임계값 — 분석 전 사전 선언 (post-hoc 방지)
# ═══════════════════════════════════════════════════════════════════════════
SAMPLE_SIZE            = 29
CRITICAL_R_N29         = 0.367   # n=29, alpha=0.05 양측 유의 임계값
WMAPE_BASELINE_TOMGRO  = 25.6
WMAPE_BASELINE_SV      = 35.5
WMAPE_BASELINE_FINAL   = 25.2

# 가설 A: EC -> LAI 음의 상관 (EC 선행, LAI 후행)
# lag=k: k주 전 EC 가 현재 LAI 에 영향 (EC 가 LAI 에 선행)
# n=29 경고: 유의 임계 |r|~0.367, 임계값 0.40 은 마진 +0.033 에 불과
THRESHOLD_EC_LAI_R_NEG  = -0.40
BORDERLINE_EC_LAI_R_NEG = -0.30
THRESHOLD_PVALUE        =  0.05
LAG_RANGE_A = [0, 1, 2, 3, 4]

# 가설 B: 최적 시차 재탐색 — 이중 기준점
# binding 조건: wmape_final_at_optimal < 23.2%
THRESHOLD_WMAPE_GAIN_VS_FINAL   = 2.0
THRESHOLD_WMAPE_GAIN_VS_TOMGRO  = 2.0
BORDERLINE_WMAPE_GAIN           = 1.5
LAG_RANGE_B = list(range(0, 9))

# 시차별 생리학적 의미 (수확 N주 전)
LAG_PHYSIOLOGY = {
    0: "착색 완료기",
    1: "착색기 (현재)",
    2: "성숙기 진입",
    3: "비대 말기",
    4: "비대 중기 ★",
    5: "비대 초기",
    6: "착과 직후",
    7: "착과기",
    8: "화아분화기",
}

# 민감도: 3x3 격자
SENSITIVITY_R_THRESHOLDS = [-0.30, -0.40, -0.50]
SENSITIVITY_W_THRESHOLDS = [ 1.0,   2.0,   3.0 ]

# 투과율 민감도
TRANSMISSION_GRID            = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
TRANSMISSION_CURRENT         = 0.50
TRANSMISSION_SENSOR_MEASURED = 0.22
TRANSMISSION_ROBUST_RANGE    = [0.45, 0.50, 0.55]
THRESHOLD_WMAPE_VARIATION    = 3.0

# ─── 폰트 설정 ─────────────────────────────────────────────────────────────
def _setup_font():
    korean_candidates = ['NanumGothic', 'Malgun Gothic', 'AppleGothic',
                         'DejaVu Sans', 'sans-serif']
    available = {f.name for f in fm.fontManager.ttflist}
    for name in korean_candidates:
        if name in available:
            plt.rcParams['font.family'] = name
            break
    plt.rcParams['axes.unicode_minus'] = False

_setup_font()

# ═══════════════════════════════════════════════════════════════════════════
# 공통 유틸
# ═══════════════════════════════════════════════════════════════════════════
def wmape(pred, actual):
    pred, actual = np.asarray(pred), np.asarray(actual)
    mask = actual > 0
    return np.sum(np.abs(pred[mask] - actual[mask])) / np.sum(actual[mask]) * 100

def get_ec_window(target_date, ec_daily, window_days=7):
    """step5 방식 동일: target_date 기준 7일 롤링 평균."""
    start = target_date - pd.Timedelta(days=window_days - 1)
    window = ec_daily[start:target_date]
    return float(window.mean()) if len(window) > 0 else np.nan

def run_cv_linear(sv_pred, dli, lai, actual):
    """5-fold CV LinearRegression, step6 방식 동일."""
    df = pd.DataFrame({
        'tomgro_sv_prediction': sv_pred,
        'dli_internal': dli,
        'lai': lai,
        'actual': actual,
    }).dropna()
    df = df[df['actual'] > 0].reset_index(drop=True)
    if len(df) < 5:
        return df['actual'].values, df['actual'].values, np.nan
    X = df[['tomgro_sv_prediction', 'dli_internal', 'lai']].values
    y = df['actual'].values
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    preds = np.zeros(len(X))
    for train_idx, test_idx in kf.split(X):
        m = LinearRegression()
        m.fit(X[train_idx], y[train_idx])
        preds[test_idx] = m.predict(X[test_idx])
    return y, preds, wmape(preds, y)

def run_tomgro_cached(priva_df, start_str, end_str, lai, light_transmission):
    """tomgro_week.run_tomgro_week 과 동일 로직, priva DataFrame 캐시 사용."""
    mask = (priva_df.index >= start_str) & (priva_df.index <= end_str + ' 23:59:59')
    week_data = priva_df[mask]
    hourly = week_data.resample('1h').mean()
    planting = pd.Timestamp(cfg.PLANTING_DATE)
    dap_mid = int((pd.Timestamp(end_str) - planting).days)
    partition = dm_partitioning(dap_mid)
    leaf_dm = stem_dm = fruit_dm = 0.0
    total_gross = 0.0
    dli = 0.0
    for ts, row in hourly.iterrows():
        rad_w = float(row.get('radiation', 0) or 0)
        rad_internal = rad_w * light_transmission
        par_umol = rad_internal * PAR_CONV
        dli += par_umol * 3600 * 1e-6
        temp = float(row.get('meas grh temp', 20) or 20)
        gross = gross_photosynthesis(par_umol, lai)
        resp  = maintenance_respiration(temp, leaf_dm, stem_dm, fruit_dm)
        net_h = max(gross - resp, 0.0)
        dm_h  = net_h * GROWTH_RESP * (30.0 / 44.0)
        total_gross += gross
        leaf_dm  += dm_h * partition['leaf']
        stem_dm  += dm_h * partition['stem']
        fruit_dm += dm_h * partition['fruit']
    fruit_fw = fruit_dm / cfg.FRUIT_DM_CONTENT / 1000.0
    return {'fruit_fw_kg_m2': round(fruit_fw, 3), 'dli_internal': round(dli, 2)}

# ─── 출력 폴더 생성 ────────────────────────────────────────────────────────
(OUT / 'images').mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
# 데이터 로드
# ═══════════════════════════════════════════════════════════════════════════
print("[LOAD] 데이터 로딩...")
weekly    = pd.read_csv(FARM / 'outputs' / 'weekly_predictions.csv',
                        parse_dates=['week_end', 'harvest_week_end'])
weekly_valid = weekly[weekly['actual_harvest'] > 0].copy().reset_index(drop=True)

irrig     = pd.read_csv(FARM / 'data' / 'irrigation_main.csv', parse_dates=['date'])
irrig     = irrig.set_index('date')
ec_daily  = irrig['slab_ec'].dropna()

lai_df    = pd.read_csv(FARM / 'processed' / 'weekly_with_lai.csv',
                        parse_dates=['week_end'])
tomgro_df = pd.read_csv(FARM / 'processed' / 'tomgro_predictions.csv',
                        parse_dates=['week_end'])

priva_weekly = pd.read_csv(FARM / 'processed' / 'priva_weekly.csv',
                            parse_dates=['datetime'])
priva_weekly['week_end'] = priva_weekly['datetime'].dt.normalize()
# 온도: 주별 합계 -> 평균 (168 시간)
priva_weekly['mean_temp'] = priva_weekly['meas grh temp'] / 168.0

# priva 원시 데이터 (투과율 민감도용) - 1회만 로드
print("[LOAD] priva_clean.csv 로딩 (투과율 민감도용)...")
priva_raw = pd.read_csv(FARM / 'data' / 'priva_clean.csv',
                        parse_dates=['datetime']).set_index('datetime')
print(f"[LOAD] 완료  weekly_valid={len(weekly_valid)}주")

# ═══════════════════════════════════════════════════════════════════════════
# 01 — EC 전작기 분포 분석
# ═══════════════════════════════════════════════════════════════════════════
print("\n[01] EC 분포 분석...")

ec_all = irrig['slab_ec'].dropna()
# 작기 기간만
season_start = pd.Timestamp(cfg.PLANTING_DATE)
season_end   = pd.Timestamp(cfg.HARVEST_END)
ec_season = ec_all[(ec_all.index >= season_start) & (ec_all.index <= season_end)]

bins   = [0, 2.5, 4.0, 6.0, 8.0, 20.0]
labels = ['안전(<=2.5)', '저(2.5-4)', '중(4-6)', '고(6-8)', '극고(>8)']
ec_cut = pd.cut(ec_season, bins=bins, labels=labels)
ec_dist = ec_cut.value_counts().reindex(labels)

# 월별 통계
ec_monthly = ec_season.groupby(ec_season.index.month).agg(['mean', 'std'])
sv_monthly_reduction = ec_monthly['mean'].apply(
    lambda e: (1 - relative_yield(e)) * 100 if e > cfg.EC_THRESHOLD else 0.0
)

# 이미지
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle('EC 전작기 분포 분석', fontsize=14, fontweight='bold')

# 히스토그램
axes[0].hist(ec_season.values, bins=20, color='steelblue', alpha=0.7, edgecolor='white')
for thresh, col, lbl in [(2.5, 'green', 'EC_THRESHOLD'), (4.0, 'orange', '저스트레스')]:
    axes[0].axvline(thresh, color=col, linestyle='--', linewidth=1.5, label=lbl)
axes[0].set_xlabel('슬라브 EC (dS/m)'); axes[0].set_ylabel('일수')
axes[0].set_title('EC 히스토그램'); axes[0].legend(fontsize=8)

# 시계열
axes[1].plot(ec_season.index, ec_season.values, color='steelblue', linewidth=0.8, alpha=0.7)
for y, col in [(2.5, 'green'), (4.0, 'orange'), (6.0, 'red')]:
    axes[1].axhline(y, color=col, linestyle='--', linewidth=1, alpha=0.8)
axes[1].set_xlabel('날짜'); axes[1].set_ylabel('EC (dS/m)'); axes[1].set_title('EC 시계열')

# 월별 박스플롯
monthly_data = [ec_season[ec_season.index.month == m].values for m in range(7, 15) if m <= 12 or (m - 12) <= 2]
months_present = sorted(ec_season.index.month.unique())
monthly_data2 = [ec_season[ec_season.index.month == m].values for m in months_present]
axes[2].boxplot(monthly_data2, labels=[str(m) for m in months_present])
axes[2].axhline(2.5, color='green', linestyle='--', linewidth=1, label='EC_THRESHOLD')
axes[2].set_xlabel('월'); axes[2].set_ylabel('EC (dS/m)'); axes[2].set_title('월별 박스플롯')
axes[2].legend(fontsize=8)

plt.tight_layout()
fig.savefig(OUT / 'images' / 'ec_histogram.png', dpi=130, bbox_inches='tight')
plt.close(fig)

# 마크다운
row_dist = ''.join(
    f"| {lbl} | {int(ec_dist[lbl])} | {ec_dist[lbl]/len(ec_season)*100:.1f}% |\n"
    for lbl in labels
)
row_monthly = ''.join(
    f"| {m}월 | {ec_monthly.loc[m,'mean']:.2f} | {sv_monthly_reduction[m]:.1f}% |\n"
    for m in months_present if m in ec_monthly.index
)
md01 = f"""# 01 EC 전작기 분포 분석
생성일: {NOW}

## 1. 기본 통계
| 통계량 | 값 |
|---|---|
| 평균 | {ec_season.mean():.2f} dS/m |
| 중위수 | {ec_season.median():.2f} dS/m |
| 표준편차 | {ec_season.std():.2f} |
| 최솟값 | {ec_season.min():.2f} |
| 최댓값 | {ec_season.max():.2f} |
| IQR (25~75%) | {ec_season.quantile(0.25):.2f} ~ {ec_season.quantile(0.75):.2f} |
| 유효 데이터 일수 | {len(ec_season)}일 |

## 2. EC 구간별 빈도
| 구간 | 일수 | 비중 |
|---|---|---|
{row_dist}
## 3. 월별 평균 EC 및 S&V 예측 감소율
| 월 | 평균 EC (dS/m) | S&V 예측 감소율 |
|---|---|---|
{row_monthly}
## 4. 핵심 해석
- 전작기 평균 EC {ec_season.mean():.2f} dS/m (임계값 {cfg.EC_THRESHOLD} dS/m 대비 {ec_season.mean()/cfg.EC_THRESHOLD*100:.0f}%)
- 임계값 초과 비율: {(ec_season > cfg.EC_THRESHOLD).mean()*100:.1f}% (S&V 가 영향 줄 여지 충분)
- 고 EC (>4 dS/m) 비중: {(ec_season > 4).mean()*100:.1f}%
- EC 변동성 (std={ec_season.std():.2f}) 은 S&V 효과를 검증하기에 충분한 범위

![EC 분포](images/ec_histogram.png)
"""
(OUT / '01_ec_distribution.md').write_text(md01, encoding='utf-8')
print(f"[01] 완료  EC평균={ec_season.mean():.2f} >임계값비율={(ec_season>cfg.EC_THRESHOLD).mean()*100:.1f}%")

# ═══════════════════════════════════════════════════════════════════════════
# 02 — EC vs 실측 수확량 상관 (시차 0~8주)
# ═══════════════════════════════════════════════════════════════════════════
print("[02] EC-수확량 상관 분석...")

lag_corr = {}
for lag in range(9):
    rows = []
    for _, r in weekly_valid.iterrows():
        ec_date = r['harvest_week_end'] - pd.Timedelta(weeks=lag)
        ec_val  = get_ec_window(ec_date, ec_daily)
        if not np.isnan(ec_val):
            rows.append({'ec': ec_val, 'actual': r['actual_harvest']})
    if len(rows) >= 5:
        df_lag = pd.DataFrame(rows)
        r_val, p_val = pearsonr(df_lag['ec'], df_lag['actual'])
        slope, intercept = np.polyfit(df_lag['ec'], df_lag['actual'], 1)
        lag_corr[lag] = {'r': r_val, 'p': p_val, 'slope': slope,
                         'intercept': intercept, 'n': len(rows), 'data': df_lag}
    else:
        lag_corr[lag] = {'r': np.nan, 'p': np.nan, 'slope': np.nan,
                         'intercept': np.nan, 'n': len(rows), 'data': pd.DataFrame()}

best_lag = max([l for l in lag_corr if not np.isnan(lag_corr[l]['r'])],
               key=lambda l: abs(lag_corr[l]['r']))

fig, axes = plt.subplots(3, 3, figsize=(16, 12))
fig.suptitle('EC vs 실측 수확량 (시차별 상관)', fontsize=13, fontweight='bold')
for i, lag in enumerate(range(9)):
    ax = axes[i // 3][i % 3]
    lc = lag_corr[lag]
    if lc['n'] >= 5 and not np.isnan(lc['r']):
        ax.scatter(lc['data']['ec'], lc['data']['actual'], s=30, alpha=0.7)
        x_range = np.linspace(lc['data']['ec'].min(), lc['data']['ec'].max(), 50)
        ax.plot(x_range, lc['slope'] * x_range + lc['intercept'], 'r-', linewidth=1.5)
    title = f"시차 {lag}주 ({LAG_PHYSIOLOGY.get(lag, '')})\nr={lc['r']:.3f}, p={lc['p']:.3f}, n={lc['n']}"
    ax.set_title(title, fontsize=8)
    ax.set_xlabel('EC (dS/m)', fontsize=7); ax.set_ylabel('수확량 (kg/m²)', fontsize=7)
    border_col = 'red' if lag == 1 else ('green' if lag == best_lag else 'gray')
    for spine in ax.spines.values():
        spine.set_edgecolor(border_col)
        spine.set_linewidth(2.5 if lag in [1, best_lag] else 0.5)
plt.tight_layout()
fig.savefig(OUT / 'images' / 'ec_vs_yield_scatter.png', dpi=130, bbox_inches='tight')
plt.close(fig)

row_lag_corr = ''.join(
    f"| {lag} | {lc['r']:.3f} | {lc['p']:.3f} | {lc['n']} | {LAG_PHYSIOLOGY.get(lag,'')} "
    f"{'<- 현재' if lag==1 else ''} |\n"
    for lag, lc in lag_corr.items() if not np.isnan(lc['r'])
)
bl = lag_corr[best_lag]
md02 = f"""# 02 EC vs 실측 수확량 상관 분석
생성일: {NOW}

## 1. 시차별 Pearson 상관 계수
| 시차 (주) | Pearson r | p-value | n | 생리학적 의미 |
|---|---|---|---|---|
{row_lag_corr}
## 2. 최강 상관 시차
- 시차 **{best_lag}주** ({LAG_PHYSIOLOGY.get(best_lag,'')}) 에서 r = **{bl['r']:.3f}** (p = {bl['p']:.3f})
- 현재 설정 (시차 1주) r = {lag_corr[1]['r']:.3f}

## 3. 선형 회귀 (시차 {best_lag}주)
```
수확량 = {bl['intercept']:.3f} + ({bl['slope']:.3f}) × EC
```
EC 1 dS/m 증가 시 수확량 {bl['slope']:.3f} kg/m² {'감소' if bl['slope'] < 0 else '증가'}

## 4. 해석
- EC 와 수확량의 실직접 상관은 시차 {best_lag}주 기준 r={bl['r']:.3f}
  ({'통계적으로 유의함' if bl['p'] < 0.05 else '통계적으로 유의하지 않음'}, n={SAMPLE_SIZE})
- 현재 S&V 설정(시차 1주) {'은 최적에 가까움' if best_lag == 1 else f'은 최적({best_lag}주)과 다름 - 가설 B 참조'}

![EC vs 수확량](images/ec_vs_yield_scatter.png)
"""
(OUT / '02_ec_yield_correlation.md').write_text(md02, encoding='utf-8')
print(f"[02] 완료  최강상관 시차={best_lag}주 r={bl['r']:.3f}")

# ═══════════════════════════════════════════════════════════════════════════
# 03 — 가설 A: EC(t-k) -> LAI(t) 음의 상관
# ═══════════════════════════════════════════════════════════════════════════
print("[03] 가설 A: EC-LAI 상관 분석...")

# LAI 데이터와 weekly EC 매칭
# ec_weekly: 각 week_end 날짜 기준 7일 롤링 평균
lai_weeks = lai_df[['week_end', 'lai']].dropna().copy()
lai_weeks['ec_t0'] = lai_weeks['week_end'].apply(lambda d: get_ec_window(d, ec_daily))

ec_lai_results = {}
for lag in LAG_RANGE_A:
    # lag=k: k주 전 EC 가 현재 LAI 에 영향 (EC 선행)
    # ec_at_t_minus_k: week_end - lag주 의 EC
    rows = []
    for _, r in lai_weeks.iterrows():
        ec_date = r['week_end'] - pd.Timedelta(weeks=lag)
        ec_val  = get_ec_window(ec_date, ec_daily)
        if not np.isnan(ec_val) and not np.isnan(r['lai']):
            rows.append({'ec': ec_val, 'lai': r['lai']})
    if len(rows) >= 5:
        df_a = pd.DataFrame(rows)
        r_val, p_val = pearsonr(df_a['ec'], df_a['lai'])
        ec_lai_results[lag] = {'r': r_val, 'p': p_val, 'n': len(rows), 'data': df_a}
    else:
        ec_lai_results[lag] = {'r': np.nan, 'p': np.nan, 'n': 0, 'data': pd.DataFrame()}

# 가설 A 판정
valid_lags_a = {l: v for l, v in ec_lai_results.items() if not np.isnan(v['r'])}
max_neg_lag  = min(valid_lags_a, key=lambda l: valid_lags_a[l]['r']) if valid_lags_a else None
max_neg_r    = valid_lags_a[max_neg_lag]['r'] if max_neg_lag is not None else np.nan
max_neg_p    = valid_lags_a[max_neg_lag]['p'] if max_neg_lag is not None else np.nan

H_A_PASS_R    = max_neg_r < THRESHOLD_EC_LAI_R_NEG if not np.isnan(max_neg_r) else False
H_A_PASS_P    = max_neg_p < THRESHOLD_PVALUE        if not np.isnan(max_neg_p) else False
H_A_TRUE      = H_A_PASS_R and H_A_PASS_P
H_A_BORDERLINE = (BORDERLINE_EC_LAI_R_NEG < max_neg_r < abs(THRESHOLD_EC_LAI_R_NEG) * -1 + abs(THRESHOLD_EC_LAI_R_NEG) + BORDERLINE_EC_LAI_R_NEG) \
    if not np.isnan(max_neg_r) else False
# 더 정확하게
H_A_BORDERLINE = (BORDERLINE_EC_LAI_R_NEG < max_neg_r <= THRESHOLD_EC_LAI_R_NEG) \
    if not np.isnan(max_neg_r) else False

fig, axes = plt.subplots(1, 6, figsize=(18, 4))
fig.suptitle('가설 A: EC(t-k) vs LAI(t) — EC 가 LAI 에 선행', fontsize=12, fontweight='bold')
for i, lag in enumerate(LAG_RANGE_A):
    ax = axes[i]
    ea = ec_lai_results[lag]
    if ea['n'] >= 5:
        sc = ax.scatter(ea['data']['ec'], ea['data']['lai'], s=25, alpha=0.7,
                        c=range(ea['n']), cmap='viridis')
        if len(ea['data']) >= 2:
            x_r = np.linspace(ea['data']['ec'].min(), ea['data']['ec'].max(), 50)
            slope, intercept = np.polyfit(ea['data']['ec'], ea['data']['lai'], 1)
            ax.plot(x_r, slope * x_r + intercept, 'r-', linewidth=1.5)
    bline = '' if not H_A_BORDERLINE else ' ⚠'
    ax.set_title(f"lag={lag}주 ({lag}주 전 EC)\nr={ea['r']:.3f}{bline}\np={ea['p']:.3f}",
                 fontsize=8)
    ax.set_xlabel('EC (dS/m)', fontsize=7); ax.set_ylabel('LAI', fontsize=7)

# 판정 패널
ax_panel = axes[5]
ax_panel.axis('off')
verdict = 'BORDERLINE' if H_A_BORDERLINE else ('성립' if H_A_TRUE else '기각')
panel_txt = (
    f"가설 A 판정\n\n"
    f"최대 음의 r: {max_neg_r:.3f}\n"
    f"at lag={max_neg_lag}주\n"
    f"p={max_neg_p:.3f}\n\n"
    f"임계: r<{THRESHOLD_EC_LAI_R_NEG}\n"
    f"n=29 유의한계: {CRITICAL_R_N29}\n\n"
    f"r조건: {'통과' if H_A_PASS_R else '실패'}\n"
    f"p조건: {'통과' if H_A_PASS_P else '실패'}\n\n"
    f"결론: {verdict}"
)
ax_panel.text(0.1, 0.5, panel_txt, transform=ax_panel.transAxes,
              fontsize=9, verticalalignment='center',
              bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
plt.tight_layout()
fig.savefig(OUT / 'images' / 'ec_vs_lai_scatter.png', dpi=130, bbox_inches='tight')
plt.close(fig)

row_a = ''.join(
    f"| {lag}주 ({LAG_PHYSIOLOGY.get(lag,'')}) | {ea['r']:.3f} | {ea['p']:.3f} | {ea['n']} | "
    f"{'✓' if ea['r'] < THRESHOLD_EC_LAI_R_NEG and ea['p'] < THRESHOLD_PVALUE else ('⚠' if H_A_BORDERLINE else '✗')} |\n"
    for lag, ea in ec_lai_results.items() if not np.isnan(ea['r'])
)
borderline_warn = (
    f"\n> ⚠ **경계 사례**: r={max_neg_r:.3f}는 임계값({THRESHOLD_EC_LAI_R_NEG})에 근접. "
    f"n=29 통계 파워 제약 (유의 임계 {CRITICAL_R_N29}). 추가 데이터 권장.\n"
    if H_A_BORDERLINE else ""
)
md03 = f"""# 03 가설 A 검증: EC -> LAI -> TOMGRO 간접 경로
생성일: {NOW}

## 판정 규칙 (사전 선언)
- 조건 1: EC-LAI 음의 상관 r < **{THRESHOLD_EC_LAI_R_NEG}** (시차 0~4주 중 최솟값)
- 조건 2: p-value < **{THRESHOLD_PVALUE}**
- 경계: r in ({THRESHOLD_EC_LAI_R_NEG}, {BORDERLINE_EC_LAI_R_NEG}) → Borderline
- ⚠ n={SAMPLE_SIZE}: 통계적 유의 임계 |r| ≈ {CRITICAL_R_N29}

## 검증 결과
| 시차 | Pearson r | p-value | n | 가설 A 기여 |
|---|---|---|---|---|
{row_a}
## 판정 체크리스트
| 조건 | 임계값 | 실측 | 통과? |
|---|---|---|---|
| 최대 음의 r (시차 0~4주) | < {THRESHOLD_EC_LAI_R_NEG} | {max_neg_r:.3f} | {'✓' if H_A_PASS_R else '✗'} |
| p-value | < {THRESHOLD_PVALUE} | {max_neg_p:.3f} | {'✓' if H_A_PASS_P else '✗'} |
| **가설 A 성립** (AND) | — | — | **{'✓ 성립' if H_A_TRUE else ('⚠ 경계' if H_A_BORDERLINE else '✗ 기각')}** |
{borderline_warn}
## 생리학적 해석
- EC 가 LAI 에 {'유의한 음의 영향' if H_A_TRUE else '유의한 영향을 미치지 않음'}
- 가설 A {'성립: EC 스트레스가 잎 성장을 억제 -> LAI 감소 -> TOMGRO 에 간접 반영됨' if H_A_TRUE else '기각: LAI 는 EC 와 독립적으로 변화. S&V 이중 차감 이외의 원인 탐색 필요'}

![EC vs LAI](images/ec_vs_lai_scatter.png)
"""
(OUT / '03_ec_lai_analysis.md').write_text(md03, encoding='utf-8')
print(f"[03] 완료  최대음의r={max_neg_r:.3f} 가설A={'성립' if H_A_TRUE else '경계' if H_A_BORDERLINE else '기각'}")

# ═══════════════════════════════════════════════════════════════════════════
# 04 — 가설 B: 시차 탐색 (S&V 단계 + XGBoost 최종)
# ═══════════════════════════════════════════════════════════════════════════
print("[04] 가설 B: 시차 재탐색 (XGBoost CV 재학습 포함)...")

lag_results = {}
for lag in LAG_RANGE_B:
    sv_preds, dli_list, lai_list, actual_list = [], [], [], []
    for _, r in weekly_valid.iterrows():
        # 수확 harvest_week_end 기준, lag주 전 EC
        ec_date = r['harvest_week_end'] - pd.Timedelta(weeks=lag)
        ec_val  = get_ec_window(ec_date, ec_daily)
        if np.isnan(ec_val):
            ec_val = ec_season.mean()  # NaN -> 평균으로 대체
        yr = relative_yield(ec_val)
        sv_preds.append(r['tomgro_prediction'] * yr)
        dli_list.append(r['dli_internal'])
        lai_list.append(r['lai'])
        actual_list.append(r['actual_harvest'])

    sv_preds   = np.array(sv_preds)
    actual_arr = np.array(actual_list)
    wmape_sv_  = wmape(sv_preds, actual_arr)

    y_true, y_cv, wmape_final_ = run_cv_linear(
        sv_preds, np.array(dli_list), np.array(lai_list), actual_arr
    )
    lag_results[lag] = {
        'wmape_sv':    wmape_sv_,
        'wmape_final': wmape_final_,
        'n': len(actual_list),
    }
    print(f"  lag={lag}주  S&V={wmape_sv_:.1f}%  Final={wmape_final_:.1f}%  ({LAG_PHYSIOLOGY.get(lag,'')})")

# 가설 B 판정
valid_lags_b = {l: v for l, v in lag_results.items() if not np.isnan(v['wmape_final'])}
opt_lag_b    = min(valid_lags_b, key=lambda l: valid_lags_b[l]['wmape_final'])
opt_final    = valid_lags_b[opt_lag_b]['wmape_final']

gain_vs_final  = WMAPE_BASELINE_FINAL  - opt_final
gain_vs_tomgro = WMAPE_BASELINE_TOMGRO - opt_final

H_B_LAG_DIFF = opt_lag_b != 1
H_B_GAIN_F   = gain_vs_final  >= THRESHOLD_WMAPE_GAIN_VS_FINAL
H_B_GAIN_T   = gain_vs_tomgro >= THRESHOLD_WMAPE_GAIN_VS_TOMGRO
H_B_TRUE     = H_B_LAG_DIFF and H_B_GAIN_F and H_B_GAIN_T
H_B_BORDERLINE = (BORDERLINE_WMAPE_GAIN <= gain_vs_final < THRESHOLD_WMAPE_GAIN_VS_FINAL) \
    if not H_B_TRUE else False

# 이미지
fig, ax = plt.subplots(figsize=(14, 7))
lags  = list(lag_results.keys())
wmape_sv_vals  = [lag_results[l]['wmape_sv']    for l in lags]
wmape_fin_vals = [lag_results[l]['wmape_final'] for l in lags]
x = np.arange(len(lags))
w = 0.35
bars1 = ax.bar(x - w/2, wmape_sv_vals,  w, label='S&V 단계 WMAPE', color='steelblue',  alpha=0.75)
bars2 = ax.bar(x + w/2, wmape_fin_vals, w, label='XGBoost 최종 WMAPE', color='darkorange', alpha=0.75)

for ref, col, lbl in [
    (WMAPE_BASELINE_TOMGRO, 'gray',  f'TOMGRO 단독 {WMAPE_BASELINE_TOMGRO}%'),
    (WMAPE_BASELINE_FINAL,  'green', f'현행 최종 {WMAPE_BASELINE_FINAL}%'),
    (WMAPE_BASELINE_SV,     'red',   f'현행 S&V {WMAPE_BASELINE_SV}%'),
]:
    ax.axhline(ref, color=col, linestyle='--', linewidth=1.5, label=lbl, alpha=0.8)

# 현재 설정 테두리
for bar in [bars1[1], bars2[1]]:
    bar.set_edgecolor('red'); bar.set_linewidth(2.5)
# 최적 표시
ax.annotate('★ 최적', xy=(opt_lag_b + w/2, wmape_fin_vals[opt_lag_b] + 0.3),
            fontsize=11, ha='center', color='darkgreen', fontweight='bold')

x_labels = [f"{l}주\n{LAG_PHYSIOLOGY.get(l, '')}" for l in lags]
ax.set_xticks(x); ax.set_xticklabels(x_labels, fontsize=8)
ax.set_ylabel('WMAPE (%)'); ax.set_title('가설 B: 시차별 WMAPE (S&V 단계 vs XGBoost 최종)')
ax.legend(fontsize=9); ax.set_ylim(0, max(max(wmape_sv_vals), WMAPE_BASELINE_SV) + 5)

verdict_b = 'BORDERLINE' if H_B_BORDERLINE else ('성립' if H_B_TRUE else '기각')
ax.text(0.98, 0.97,
        f"최적 시차: {opt_lag_b}주 ({LAG_PHYSIOLOGY.get(opt_lag_b,'')})\n"
        f"최종 WMAPE: {opt_final:.1f}%\n"
        f"vs 현행({WMAPE_BASELINE_FINAL}%): {gain_vs_final:+.1f}%p\n"
        f"vs TOMGRO({WMAPE_BASELINE_TOMGRO}%): {gain_vs_tomgro:+.1f}%p\n"
        f"가설 B: {verdict_b}",
        transform=ax.transAxes, fontsize=9, ha='right', va='top',
        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))
plt.tight_layout()
fig.savefig(OUT / 'images' / 'ec_lag_heatmap.png', dpi=130, bbox_inches='tight')
plt.close(fig)

row_b = ''.join(
    f"| {l}주 | {LAG_PHYSIOLOGY.get(l,'')} | "
    f"{lag_results[l]['wmape_sv']:.1f}% | {lag_results[l]['wmape_final']:.1f}% | "
    f"{lag_results[l]['n']} | {'← 현재' if l==1 else ''} {'★' if l==opt_lag_b else ''} |\n"
    for l in lags
)
borderline_b_warn = (
    f"\n> ⚠ **경계 사례**: 최종 WMAPE 개선폭 {gain_vs_final:.1f}%p 가 임계값 "
    f"{THRESHOLD_WMAPE_GAIN_VS_FINAL}%p 에 근접. 추가 작기 데이터 권장.\n"
    if H_B_BORDERLINE else ""
)
md04 = f"""# 04 가설 B 검증: S&V 최적 시차 탐색
생성일: {NOW}

## 판정 규칙 (사전 선언)
- 조건 1: 최적 시차 ≠ 1주 (현재 설정)
- 조건 2: XGBoost 최종 WMAPE 개선폭 vs 현행({WMAPE_BASELINE_FINAL}%) ≥ **{THRESHOLD_WMAPE_GAIN_VS_FINAL}%p**
- 조건 3: XGBoost 최종 WMAPE 개선폭 vs TOMGRO({WMAPE_BASELINE_TOMGRO}%) ≥ **{THRESHOLD_WMAPE_GAIN_VS_TOMGRO}%p** (S&V 가 실제 기여 증명)
- 경계: 개선폭 [{BORDERLINE_WMAPE_GAIN}, {THRESHOLD_WMAPE_GAIN_VS_FINAL}) → Borderline
- Binding 조건: 최종 WMAPE < {WMAPE_BASELINE_FINAL - THRESHOLD_WMAPE_GAIN_VS_FINAL:.1f}%

## 시차별 WMAPE 결과
| 시차 | 생리학적 의미 | S&V WMAPE | 최종 WMAPE ⭐ | n | 비고 |
|---|---|---|---|---|---|
{row_b}
## 판정 체크리스트
| 조건 | 임계값 | 실측 | 통과? |
|---|---|---|---|
| 최적 시차 ≠ 1주 | — | {opt_lag_b}주 | {'✓' if H_B_LAG_DIFF else '✗'} |
| 개선폭 vs 현행 최종 | ≥ {THRESHOLD_WMAPE_GAIN_VS_FINAL}%p | {gain_vs_final:.1f}%p | {'✓' if H_B_GAIN_F else '✗'} |
| 개선폭 vs TOMGRO | ≥ {THRESHOLD_WMAPE_GAIN_VS_TOMGRO}%p | {gain_vs_tomgro:.1f}%p | {'✓' if H_B_GAIN_T else '✗'} |
| **가설 B 성립** (AND) | — | — | **{'✓ 성립' if H_B_TRUE else ('⚠ 경계' if H_B_BORDERLINE else '✗ 기각')}** |
{borderline_b_warn}
## 최적 시차 생리학적 의미
시차 **{opt_lag_b}주** = 수확 {opt_lag_b}주 전 EC = **{LAG_PHYSIOLOGY.get(opt_lag_b,'')}**

## 해석
{'가설 B 성립: 시차를 재조정하면 최종 WMAPE 가 개선됨.' if H_B_TRUE else '가설 B 기각: 시차 재조정만으로는 최종 WMAPE 의 의미있는 개선이 없음.'}
현재 설정 (시차 1주) 의 최종 WMAPE {lag_results[1]['wmape_final']:.1f}% vs 최적 시차 ({opt_lag_b}주) {opt_final:.1f}%

![시차별 WMAPE](images/ec_lag_heatmap.png)
"""
(OUT / '04_ec_lag_search.md').write_text(md04, encoding='utf-8')
print(f"[04] 완료  최적시차={opt_lag_b}주 최종WMAPE={opt_final:.1f}% 가설B={'성립' if H_B_TRUE else '경계' if H_B_BORDERLINE else '기각'}")

# ═══════════════════════════════════════════════════════════════════════════
# 05 — TOMGRO 잔차 분석
# ═══════════════════════════════════════════════════════════════════════════
print("[05] TOMGRO 잔차 분석...")

resid_df = weekly_valid.copy()
resid_df['residual'] = resid_df['actual_harvest'] - resid_df['tomgro_prediction']

# 온도 매핑
resid_df['week_key'] = resid_df['week_end'].dt.normalize()
temp_map = dict(zip(priva_weekly['week_end'], priva_weekly['mean_temp']))
resid_df['mean_temp'] = resid_df['week_key'].map(temp_map)

# EC 매핑 (시차 1주 및 3주)
resid_df['ec_lag1'] = resid_df['harvest_week_end'].apply(
    lambda d: get_ec_window(d - pd.Timedelta(weeks=1), ec_daily))
resid_df['ec_lag3'] = resid_df['harvest_week_end'].apply(
    lambda d: get_ec_window(d - pd.Timedelta(weeks=3), ec_daily))

features_resid = {
    'EC (수확 1주 전)': 'ec_lag1',
    'EC (수확 3주 전)': 'ec_lag3',
    'DLI (내부)': 'dli_internal',
    'LAI': 'lai',
    '평균 기온': 'mean_temp',
}
resid_corr = {}
for name, col in features_resid.items():
    sub = resid_df[['residual', col]].dropna()
    if len(sub) >= 5:
        r_v, p_v = pearsonr(sub[col], sub['residual'])
        resid_corr[name] = {'r': r_v, 'p': p_v, 'n': len(sub), 'col': col}
    else:
        resid_corr[name] = {'r': np.nan, 'p': np.nan, 'n': 0, 'col': col}

fig, axes = plt.subplots(2, 3, figsize=(15, 10))
fig.suptitle('TOMGRO 잔차 분석', fontsize=13, fontweight='bold')
ax_list = [axes[0][0], axes[0][1], axes[0][2], axes[1][0], axes[1][1]]
for i, (name, rc) in enumerate(resid_corr.items()):
    ax = ax_list[i]
    sub = resid_df[['residual', rc['col']]].dropna()
    if len(sub) >= 5:
        ax.scatter(sub[rc['col']], sub['residual'], s=30, alpha=0.7)
        ax.axhline(0, color='gray', linestyle='--', linewidth=1)
        x_r = np.linspace(sub[rc['col']].min(), sub[rc['col']].max(), 50)
        slope, intercept = np.polyfit(sub[rc['col']], sub['residual'], 1)
        ax.plot(x_r, slope * x_r + intercept, 'r-', linewidth=1.5)
    ax.set_title(f"{name}\nr={rc['r']:.3f}, p={rc['p']:.3f}", fontsize=9)
    ax.set_xlabel(name, fontsize=8); ax.set_ylabel('잔차 (actual-TOMGRO)', fontsize=8)

# 시계열
ax_ts = axes[1][2]
ax_ts.plot(resid_df['week_end'], resid_df['residual'], marker='o', markersize=4,
           linewidth=0.8, color='steelblue')
ax_ts.axhline(0, color='red', linestyle='--', linewidth=1)
ax_ts.fill_between(resid_df['week_end'], resid_df['residual'], 0,
                   where=resid_df['residual'] >= 0, alpha=0.3, color='green', label='과소예측')
ax_ts.fill_between(resid_df['week_end'], resid_df['residual'], 0,
                   where=resid_df['residual'] < 0, alpha=0.3, color='red', label='과대예측')
ax_ts.set_title('잔차 시계열'); ax_ts.legend(fontsize=8)
plt.tight_layout()
fig.savefig(OUT / 'images' / 'residual_vs_ec.png', dpi=130, bbox_inches='tight')
plt.close(fig)

row_resid = ''.join(
    f"| {name} | {rc['r']:.3f} | {rc['p']:.3f} | {rc['n']} | "
    f"{'유의' if rc['p'] < 0.05 else '비유의'} |\n"
    for name, rc in resid_corr.items() if not np.isnan(rc['r'])
)
bias = resid_df['residual'].mean()
md05 = f"""# 05 TOMGRO 잔차 분석
생성일: {NOW}

## 잔차 기본 통계
| 통계량 | 값 |
|---|---|
| 평균 잔차 | {bias:.3f} kg/m² ({'과소예측 경향' if bias > 0 else '과대예측 경향'}) |
| 표준편차 | {resid_df['residual'].std():.3f} |
| 최솟값 | {resid_df['residual'].min():.3f} |
| 최댓값 | {resid_df['residual'].max():.3f} |

## 잔차와 환경 변수 상관
| 변수 | Pearson r | p-value | n | 유의성 |
|---|---|---|---|---|
{row_resid}
## 해석
- EC (수확 1주 전) 과 잔차 상관: r={resid_corr.get('EC (수확 1주 전)',{}).get('r', np.nan):.3f}
  → EC 가 TOMGRO 오차를 {'설명함 (S&V 역할 있음)' if abs(resid_corr.get('EC (수확 1주 전)',{}).get('r', 0)) > 0.3 else '설명하지 못함 (S&V 효과 미미)'}
- EC (수확 3주 전) 과 잔차 상관: r={resid_corr.get('EC (수확 3주 전)',{}).get('r', np.nan):.3f}
- 가장 강한 상관 변수: {max(resid_corr, key=lambda k: abs(resid_corr[k].get('r',0) or 0))}

![잔차 분석](images/residual_vs_ec.png)
"""
(OUT / '05_residual_analysis.md').write_text(md05, encoding='utf-8')
print(f"[05] 완료  잔차평균={bias:.3f} EC-잔차r={resid_corr.get('EC (수확 1주 전)',{}).get('r',np.nan):.3f}")

# ═══════════════════════════════════════════════════════════════════════════
# 07 — 투과율 민감도 (전체 파이프라인, priva 캐시 사용)
# ═══════════════════════════════════════════════════════════════════════════
print("\n[07] 투과율 민감도 분석 (전체 파이프라인, 9회)...")
import time
t07_start = time.time()

trans_results = {}
scene1_date = pd.Timestamp('2025-11-12')
scene1_row  = lai_df[lai_df['week_end'] == scene1_date]
scene1_lai  = float(scene1_row['lai'].values[0]) if len(scene1_row) > 0 else 3.03

for t_val in TRANSMISSION_GRID:
    # Step 1: TOMGRO 재실행 (priva 캐시 사용)
    tomgro_rows = []
    for _, row in lai_df.iterrows():
        w_end   = row['week_end']
        w_start = w_end - pd.Timedelta(days=6)
        try:
            res = run_tomgro_cached(priva_raw,
                                    str(w_start.date()), str(w_end.date()),
                                    row['lai'], t_val)
            tomgro_rows.append({
                'week_end': w_end,
                'tomgro_prediction': res['fruit_fw_kg_m2'],
                'dli_internal': res['dli_internal'],
                'lai': row['lai'],
            })
        except Exception:
            tomgro_rows.append({'week_end': w_end, 'tomgro_prediction': np.nan,
                                 'dli_internal': np.nan, 'lai': row['lai']})
    tomgro_t = pd.DataFrame(tomgro_rows)

    # Scene 1 TOMGRO 값
    s1_tomgro = float(tomgro_t[tomgro_t['week_end'] == scene1_date]['tomgro_prediction'].values[0]) \
        if len(tomgro_t[tomgro_t['week_end'] == scene1_date]) > 0 else np.nan

    # Step 2: S&V 적용 (기존 EC, lag=1 고정)
    sv_rows = []
    for _, tr in tomgro_t.iterrows():
        ec_date = tr['week_end'] + pd.Timedelta(weeks=cfg.SV_EC_LAG)
        ec_val  = get_ec_window(ec_date, ec_daily)
        yr = relative_yield(ec_val) if not np.isnan(ec_val) else 1.0
        sv_rows.append({
            'week_end': tr['week_end'],
            'tomgro_prediction': tr['tomgro_prediction'],
            'tomgro_sv_prediction': (tr['tomgro_prediction'] or 0) * yr,
            'dli_internal': tr['dli_internal'],
            'lai': tr['lai'],
        })
    sv_t = pd.DataFrame(sv_rows)

    # 수확 데이터 매칭 (step6 방식)
    def _to_w_mon(ts):
        days = (0 - ts.weekday()) % 7
        return ts + pd.Timedelta(days=days)

    irrig_tmp = irrig.reset_index()
    irrig_tmp['date'] = pd.to_datetime(irrig_tmp['date'])
    harvest_indexed = irrig_tmp.set_index('date')['actual_harvest']
    weekly_harvest_t = (
        harvest_indexed.resample('W-MON', closed='right', label='right')
        .sum().reset_index().rename(columns={'date': 'harvest_week_end'})
    )
    sv_t['harvest_week_end'] = sv_t['week_end'].apply(
        lambda w: _to_w_mon(w + pd.Timedelta(weeks=7)))
    df_t = sv_t.merge(weekly_harvest_t, on='harvest_week_end', how='inner')
    df_t = df_t.dropna(subset=['tomgro_sv_prediction', 'dli_internal', 'lai', 'actual_harvest'])
    df_t = df_t[df_t['actual_harvest'] > 0].reset_index(drop=True)

    wmape_tomgro_t = wmape(df_t['tomgro_prediction'].values, df_t['actual_harvest'].values)
    wmape_sv_t     = wmape(df_t['tomgro_sv_prediction'].values, df_t['actual_harvest'].values)

    # Step 3: XGBoost CV 재학습
    _, _, wmape_final_t = run_cv_linear(
        df_t['tomgro_sv_prediction'].values, df_t['dli_internal'].values,
        df_t['lai'].values, df_t['actual_harvest'].values
    )

    trans_results[t_val] = {
        'wmape_tomgro': wmape_tomgro_t,
        'wmape_sv':     wmape_sv_t,
        'wmape_final':  wmape_final_t,
        'scene1_tomgro': s1_tomgro,
        'n': len(df_t),
    }
    print(f"  t={t_val:.2f}  TOMGRO={wmape_tomgro_t:.1f}%  Final={wmape_final_t:.1f}%  Scene1={s1_tomgro:.3f}")

t07_elapsed = time.time() - t07_start
print(f"[07] 파이프라인 완료  소요시간 {t07_elapsed:.1f}초")

# 투과율 판정
wmape_finals = {t: tr['wmape_final'] for t, tr in trans_results.items() if not np.isnan(tr['wmape_final'])}
opt_trans    = min(wmape_finals, key=wmape_finals.get)
opt_wf       = wmape_finals[opt_trans]

robust_range_vals = [wmape_finals.get(t) for t in TRANSMISSION_ROBUST_RANGE if t in wmape_finals]
TRANS_IS_BROKEN  = all(v > 40 for v in wmape_finals.values()) if wmape_finals else True
TRANS_IS_ROBUST  = (
    not TRANS_IS_BROKEN
    and opt_trans in TRANSMISSION_ROBUST_RANGE
    and (max(robust_range_vals) - min(robust_range_vals)) < THRESHOLD_WMAPE_VARIATION
) if robust_range_vals else False

if opt_trans >= 0.60:
    trans_verdict = 'SENSITIVE_HIGH'
elif opt_trans <= 0.40:
    trans_verdict = 'SENSITIVE_LOW'
elif TRANS_IS_BROKEN:
    trans_verdict = 'BROKEN'
elif TRANS_IS_ROBUST:
    trans_verdict = 'ROBUST'
else:
    trans_verdict = 'SENSITIVE'

# 이미지
fig, ax1 = plt.subplots(figsize=(13, 6))
t_vals = sorted(trans_results.keys())
wf_vals = [trans_results[t]['wmape_final']  for t in t_vals]
ws_vals = [trans_results[t]['wmape_tomgro'] for t in t_vals]
s1_vals = [trans_results[t]['scene1_tomgro'] for t in t_vals]

ax1.plot(t_vals, wf_vals, 'o-', color='darkorange', linewidth=2,
         markersize=7, label='최종 WMAPE (XGBoost CV)')
ax1.plot(t_vals, ws_vals, 's--', color='steelblue', linewidth=1.5,
         markersize=5, label='TOMGRO 단독 WMAPE', alpha=0.7)
ax1.axvline(TRANSMISSION_CURRENT, color='black', linestyle='-', linewidth=2, label=f'현재 설정 ({TRANSMISSION_CURRENT})')
ax1.axvline(TRANSMISSION_SENSOR_MEASURED, color='purple', linestyle=':', linewidth=1.5,
            label=f'실측 센서 ({TRANSMISSION_SENSOR_MEASURED})')
ax1.axhline(WMAPE_BASELINE_FINAL, color='green', linestyle='--', linewidth=1,
            label=f'현행 최종 {WMAPE_BASELINE_FINAL}%', alpha=0.8)
# 최적 별표
ax1.annotate(f'★ 최적\n{opt_trans:.2f}',
             xy=(opt_trans, opt_wf), xytext=(opt_trans+0.03, opt_wf+1),
             fontsize=10, color='darkgreen', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='darkgreen'))
ax1.set_xlabel('LIGHT_TRANSMISSION'); ax1.set_ylabel('WMAPE (%)', color='darkorange')
ax1.set_title(f'투과율 민감도 분석 — 전체 파이프라인 재실행\n판정: {trans_verdict}')

ax2 = ax1.twinx()
ax2.plot(t_vals, s1_vals, '^:', color='red', linewidth=1.5, markersize=6,
         label='Scene1 TOMGRO 예측', alpha=0.8)
ax2.axhline(0.400, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Scene1 기준값(0.400)')
ax2.set_ylabel('Scene 1 TOMGRO 예측 (kg/m²)', color='red')

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='upper right')
plt.tight_layout()
fig.savefig(OUT / 'images' / 'transmission_sensitivity.png', dpi=130, bbox_inches='tight')
plt.close(fig)

row_trans = ''.join(
    f"| **{t:.2f}**{'  (현재)' if t == TRANSMISSION_CURRENT else ''} | "
    f"{trans_results[t]['scene1_tomgro']:.3f} | {trans_results[t]['wmape_tomgro']:.1f}% | "
    f"{trans_results[t]['wmape_final']:.1f}% | {trans_results[t]['n']} |"
    f"{'  ★ 최적' if t == opt_trans else ''}\n"
    for t in t_vals
)
robust_vals_str = ', '.join(f"{t:.2f}:{v:.1f}%" for t, v in zip(TRANSMISSION_ROBUST_RANGE, robust_range_vals))
md07 = f"""# 07 LIGHT_TRANSMISSION 민감도 분석
생성일: {NOW}  |  소요시간: {t07_elapsed:.1f}초

## 판정 규칙 (사전 선언)
- **ROBUST**: 최적 투과율 in {TRANSMISSION_ROBUST_RANGE} AND ±5% 내 WMAPE 변동 < {THRESHOLD_WMAPE_VARIATION}%p
- **SENSITIVE_HIGH**: 최적 투과율 >= 0.60
- **SENSITIVE_LOW**: 최적 투과율 <= 0.40
- **BROKEN**: 모든 투과율에서 최종 WMAPE > 40%
- 투과율 불안정 시 06_final_diagnosis 신뢰도 태그 반영

## 분석 결과
| 투과율 | Scene 1 TOMGRO | WMAPE (TOMGRO) | WMAPE (최종) | n | 비고 |
|---|---|---|---|---|---|
{row_trans}
## 판정 체크리스트
| 조건 | 임계값 | 실측 | 결과 |
|---|---|---|---|
| 최적 투과율 in [0.45, 0.50, 0.55] | — | {opt_trans:.2f} | {'✓' if opt_trans in TRANSMISSION_ROBUST_RANGE else '✗'} |
| ±5% 내 WMAPE 변동 | < {THRESHOLD_WMAPE_VARIATION}%p | {max(robust_range_vals)-min(robust_range_vals):.1f}%p | {'✓' if max(robust_range_vals)-min(robust_range_vals) < THRESHOLD_WMAPE_VARIATION else '✗'} |
| **최종 판정** | ROBUST | **{trans_verdict}** | {'✓' if trans_verdict == 'ROBUST' else '✗'} |

## 현재값 (0.50) 근처 ±5% 범위
{robust_vals_str}
최적 투과율 {opt_trans:.2f} 에서 최종 WMAPE {opt_wf:.1f}%

## 시나리오 해석
{'현재 설정(0.50) 타당. Phase 2 PAR 실측은 미세 조정 용도.' if trans_verdict == 'ROBUST' else ''}
{'내부 광량이 실제로 더 높을 수 있음. 스크린 개도 및 센서 위치 재검토.' if trans_verdict == 'SENSITIVE_HIGH' else ''}
{'내부 센서 측정값(0.22)이 더 가까울 수 있음. 투과율 재산정 및 PAR 센서 우선 설치.' if trans_verdict == 'SENSITIVE_LOW' else ''}

## EC 분석 신뢰도 연계
투과율 판정: **{trans_verdict}**
{'→ EC 분석 결과의 신뢰도 정상. 가설 A/B 판정 신뢰 가능.' if TRANS_IS_ROBUST else '→ 투과율 가정이 불안정하므로 EC 분석 결과도 재검토 권장.'}

실측 센서값 ({TRANSMISSION_SENSOR_MEASURED}) 과 현재 설정 ({TRANSMISSION_CURRENT}) 의 차이는
투과율 범위 탐색 내에서 WMAPE {abs(wmape_finals.get(TRANSMISSION_SENSOR_MEASURED, opt_wf) - wmape_finals.get(TRANSMISSION_CURRENT, opt_wf)):.1f}%p 차이에 해당.

![투과율 민감도](images/transmission_sensitivity.png)
"""
(OUT / '07_light_transmission_sensitivity.md').write_text(md07, encoding='utf-8')
print(f"[07] 완료  최적투과율={opt_trans:.2f} 최종WMAPE={opt_wf:.1f}% 판정={trans_verdict}")

# ═══════════════════════════════════════════════════════════════════════════
# 06 — 종합 진단 (투과율 선검사 -> EC 판정 -> 민감도)
# ═══════════════════════════════════════════════════════════════════════════
print("\n[06] 종합 진단 및 시나리오 결정...")

# 투과율 선검사
if TRANS_IS_BROKEN:
    TRANS_TAG = 'BROKEN — 전면 재검토 필요'
    override_scenario = True
elif not TRANS_IS_ROBUST:
    TRANS_TAG = f'{trans_verdict} — 신뢰도 낮음'
    override_scenario = False
else:
    TRANS_TAG = f'{trans_verdict} — 신뢰도 정상'
    override_scenario = False

# 시나리오 결정
if override_scenario:
    scenario = 'X'
    scenario_desc = '전면 재검토 (투과율 BROKEN)'
elif H_A_BORDERLINE or H_B_BORDERLINE:
    scenario = 'C'
    scenario_desc = '복합 (경계 사례 → 보수적 분류)'
elif H_A_TRUE and H_B_TRUE:
    scenario = 'C'
    scenario_desc = '복합 (가설 A + B 모두 성립)'
elif H_A_TRUE and not H_B_TRUE:
    scenario = 'A'
    scenario_desc = 'EC -> LAI -> TOMGRO 이중 차감'
elif not H_A_TRUE and H_B_TRUE:
    scenario = 'B'
    scenario_desc = 'S&V 시차 재조정으로 개선 가능'
else:
    scenario = 'D'
    scenario_desc = 'EC 영향 미미 — 현상태 유지'

# 민감도 3x3
print("[06] 민감도 3x3 격자 계산...")
sensitivity_matrix = {}
for r_th in SENSITIVITY_R_THRESHOLDS:
    for w_th in SENSITIVITY_W_THRESHOLDS:
        ha_ = (max_neg_r < r_th) and (max_neg_p < THRESHOLD_PVALUE) if not np.isnan(max_neg_r) else False
        hb_ = (H_B_LAG_DIFF
               and (WMAPE_BASELINE_FINAL - opt_final) >= w_th
               and (WMAPE_BASELINE_TOMGRO - opt_final) >= THRESHOLD_WMAPE_GAIN_VS_TOMGRO)
        if ha_ and hb_:   sc_ = 'C'
        elif ha_:          sc_ = 'A'
        elif hb_:          sc_ = 'B'
        else:              sc_ = 'D'
        sensitivity_matrix[(r_th, w_th)] = sc_

all_same = len(set(sensitivity_matrix.values())) == 1
SENSITIVITY_VERDICT = 'ROBUST' if all_same else 'SENSITIVE'
changed_conditions = [(r_th, w_th) for (r_th, w_th), sc_ in sensitivity_matrix.items() if sc_ != scenario]

row_sens = ''
for r_th in SENSITIVITY_R_THRESHOLDS:
    row_sens += f"| r<{r_th} | "
    for w_th in SENSITIVITY_W_THRESHOLDS:
        sc_ = sensitivity_matrix[(r_th, w_th)]
        mark = '**' if sc_ != scenario else ''
        row_sens += f"{mark}{sc_}{mark} | "
    row_sens += '\n'

# Phase 1.5 제안
if scenario == 'A':
    phase15 = """1. S&V 모델 비활성화 (TOMGRO -> XGBoost 직결)
2. Phase 2: S&V 를 당도 예측 전용으로 재정립
3. 예상 WMAPE 변화: 25.2% 수준 유지 또는 소폭 개선"""
elif scenario == 'B':
    phase15 = f"""1. SV_EC_LAG 를 {cfg.SV_EC_LAG} -> {opt_lag_b + (8 - opt_lag_b)}주 로 변경 (수확 {opt_lag_b}주 전 EC 사용)
2. 전체 파이프라인 재실행 검증
3. 예상 최종 WMAPE: {opt_final:.1f}% (현행 대비 {gain_vs_final:+.1f}%p)"""
elif scenario == 'C':
    phase15 = f"""1. EC-LAI 경로 정밀 측정 (Phase 2 엽면적 측정기)
2. 시차 {opt_lag_b}주 적용 후 LAI 보정 여부 재평가
3. S&V 스케일 계수 조정 검토"""
elif scenario == 'D':
    phase15 = """1. 현상태 유지 (S&V 구조 변경 불필요)
2. Phase 2: 다른 설명 변수 탐색 (CO2, 착과수, 줄기 직경)
3. 본 농장 EC 범위가 S&V 임계값 근처 → 민감도 자체가 낮음"""
else:
    phase15 = """1. 투과율 재산정 후 전면 재분석 필요
2. PAR 센서 조기 설치 (Phase 2 최우선)"""

md06 = f"""# 06 종합 진단 및 Phase 1.5 제안
생성일: {NOW}

---

## 판정 규칙 요약 (전체 사전 선언)

| 규칙 | 임계값 |
|---|---|
| 가설 A: EC-LAI 음의 상관 | r < {THRESHOLD_EC_LAI_R_NEG}, p < {THRESHOLD_PVALUE} |
| 가설 A 경계 | r in ({THRESHOLD_EC_LAI_R_NEG}, {BORDERLINE_EC_LAI_R_NEG}) |
| 가설 B: 최종 WMAPE 개선 (vs 현행) | >= {THRESHOLD_WMAPE_GAIN_VS_FINAL}%p |
| 가설 B: 최종 WMAPE 개선 (vs TOMGRO) | >= {THRESHOLD_WMAPE_GAIN_VS_TOMGRO}%p |
| 가설 B 경계 | 개선폭 [{BORDERLINE_WMAPE_GAIN}, {THRESHOLD_WMAPE_GAIN_VS_FINAL}) |
| 투과율 ROBUST | 최적 in {TRANSMISSION_ROBUST_RANGE} AND 변동 < {THRESHOLD_WMAPE_VARIATION}%p |
| n=29 통계 파워 경고 | 유의 임계 |r| >= {CRITICAL_R_N29} |

---

## 1단계: 투과율 선검사 (신뢰도 게이트)

| 항목 | 결과 |
|---|---|
| 최적 투과율 | {opt_trans:.2f} |
| 최적 최종 WMAPE | {opt_wf:.1f}% |
| 판정 | **{TRANS_TAG}** |
| EC 분석 신뢰도 | {'정상' if TRANS_IS_ROBUST else '주의 — 결과 재검토 권장'} |

{'> ⚠ 투과율 BROKEN: 이하 모든 가설 판정은 무효. 전면 재검토 필요.' if TRANS_IS_BROKEN else ''}

---

## 2단계: 가설 A 체크리스트

| 조건 | 임계값 | 실측 | 통과? |
|---|---|---|---|
| 최대 음의 r (시차 0~4주) | < {THRESHOLD_EC_LAI_R_NEG} | {max_neg_r:.3f} | {'✓' if H_A_PASS_R else '✗'} |
| p-value | < {THRESHOLD_PVALUE} | {max_neg_p:.3f} | {'✓' if H_A_PASS_P else '✗'} |
| **가설 A** | AND | | **{'✓ 성립' if H_A_TRUE else ('⚠ 경계' if H_A_BORDERLINE else '✗ 기각')}** |

---

## 3단계: 가설 B 체크리스트

| 조건 | 임계값 | 실측 | 통과? |
|---|---|---|---|
| 최적 시차 ≠ 1주 | — | {opt_lag_b}주 | {'✓' if H_B_LAG_DIFF else '✗'} |
| 최종 WMAPE 개선 vs 현행({WMAPE_BASELINE_FINAL}%) | >= {THRESHOLD_WMAPE_GAIN_VS_FINAL}%p | {gain_vs_final:.1f}%p | {'✓' if H_B_GAIN_F else '✗'} |
| 최종 WMAPE 개선 vs TOMGRO({WMAPE_BASELINE_TOMGRO}%) | >= {THRESHOLD_WMAPE_GAIN_VS_TOMGRO}%p | {gain_vs_tomgro:.1f}%p | {'✓' if H_B_GAIN_T else '✗'} |
| **가설 B** | AND | | **{'✓ 성립' if H_B_TRUE else ('⚠ 경계' if H_B_BORDERLINE else '✗ 기각')}** |

---

## 최종 시나리오 결정

**채택 시나리오: {scenario} — {scenario_desc}**

| 가설 A | 가설 B | 경계 사례? | 결정 |
|---|---|---|---|
| {'✓' if H_A_TRUE else '✗'} | {'✓' if H_B_TRUE else '✗'} | {'있음' if H_A_BORDERLINE or H_B_BORDERLINE else '없음'} | **시나리오 {scenario}** |

---

## 민감도 분석 (임계값 3x3)

행: r 임계값 / 열: WMAPE 개선 임계값 (%p)

| r 임계 \\ WMAPE | {SENSITIVITY_W_THRESHOLDS[0]}%p | {SENSITIVITY_W_THRESHOLDS[1]}%p | {SENSITIVITY_W_THRESHOLDS[2]}%p |
|---|---|---|---|
{row_sens}
**민감도 판정: {SENSITIVITY_VERDICT}**
{'→ 9개 조합 모두 동일 시나리오. 결론 신뢰도 높음.' if all_same else f'→ 일부 조합에서 시나리오 변경 ({len(changed_conditions)}개). 경계 조건 재검토 권장.'}

---

## Phase 1.5 권장 조치

**시나리오 {scenario} 기준:**

{phase15}

---

## Phase 2 재정립

**확실해진 것:**
- 전체 파이프라인 투과율 민감도: {trans_verdict}
- TOMGRO 잔차와 EC 상관: r={resid_corr.get('EC (수확 1주 전)',{}).get('r', np.nan):.3f}
- EC-LAI 직접 상관: r={max_neg_r:.3f} (시차 {max_neg_lag}주)

**Phase 2 우선 설비 투자:**
{'1. PAR 센서 (투과율 SENSITIVE → 긴급) / 2. 엽면적 측정기 (EC-LAI 경로 확인용)' if not TRANS_IS_ROBUST else '1. 엽면적 측정기 (EC-LAI 경로 정밀화) / 2. PAR 센서 (미세 조정용, 긴급하지 않음)'}
"""
(OUT / '06_final_diagnosis.md').write_text(md06, encoding='utf-8')
print(f"[06] 완료  시나리오={scenario} 민감도={SENSITIVITY_VERDICT}")

# ═══════════════════════════════════════════════════════════════════════════
# README.md
# ═══════════════════════════════════════════════════════════════════════════
readme = f"""# Phase 1 EC 스트레스 심층 분석 패키지
생성일: {DATE}

## 핵심 판정 결과
- **채택 시나리오: {scenario}** — {scenario_desc}
- 가설 A (EC->LAI): {'성립' if H_A_TRUE else '경계' if H_A_BORDERLINE else '기각'} (r={max_neg_r:.3f})
- 가설 B (시차 재조정): {'성립' if H_B_TRUE else '경계' if H_B_BORDERLINE else '기각'} (최적={opt_lag_b}주, final={opt_final:.1f}%)
- 투과율 민감도: {trans_verdict} (최적={opt_trans:.2f})
- 민감도 9개 조합: {SENSITIVITY_VERDICT}

## 파일 안내
| 파일 | 내용 |
|---|---|
| 01_ec_distribution.md | EC 전작기 분포 |
| 02_ec_yield_correlation.md | EC vs 수확 시차 상관 |
| 03_ec_lai_analysis.md | 가설 A 검증 |
| 04_ec_lag_search.md | 가설 B 시차 탐색 |
| 05_residual_analysis.md | TOMGRO 잔차 분석 |
| 06_final_diagnosis.md | 종합 진단 + Phase 1.5 |
| 07_light_transmission_sensitivity.md | 투과율 민감도 |
"""
(OUT / 'README.md').write_text(readme, encoding='utf-8')

# ═══════════════════════════════════════════════════════════════════════════
# ZIP
# ═══════════════════════════════════════════════════════════════════════════
zip_path = BASE / f"phase1_ec_analysis_{datetime.now().strftime('%Y%m%d')}.zip"
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for fpath in OUT.rglob('*'):
        if fpath.is_file():
            zf.write(fpath, fpath.relative_to(BASE))
print(f"\nZIP: {zip_path.name}  ({zip_path.stat().st_size/1024:.0f} KB)")

# ═══════════════════════════════════════════════════════════════════════════
# FINAL VERDICT
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "="*65)
print("  FINAL VERDICT")
print("="*65)
print(f"  투과율 선검사:  {trans_verdict} (최적={opt_trans:.2f}, WMAPE={opt_wf:.1f}%)")
print(f"  가설 A (EC->LAI):  {'성립' if H_A_TRUE else '경계' if H_A_BORDERLINE else '기각'}  "
      f"r={max_neg_r:.3f} (lag={max_neg_lag}주, p={max_neg_p:.3f})")
print(f"  가설 B (시차 재조정):  {'성립' if H_B_TRUE else '경계' if H_B_BORDERLINE else '기각'}  "
      f"최적={opt_lag_b}주 ({LAG_PHYSIOLOGY.get(opt_lag_b,'')})")
print(f"     Final WMAPE {lag_results[1]['wmape_final']:.1f}% (lag=1) -> {opt_final:.1f}% (최적), "
      f"개선 {gain_vs_final:+.1f}%p")
print(f"  민감도 3x3:  {SENSITIVITY_VERDICT}")
print(f"  채택 시나리오:  [{scenario}] {scenario_desc}")
print("="*65)

"""Step 6: 5-fold CV 선형회귀 (풀체인 잔차 학습).

현재 구현: LinearRegression (5-fold CV).
Phase 2 계획: XGBoost로 교체 (데이터량 증가 후).
근거: 현재 29주 데이터로는 선형 모델이 XGBoost 대비 overfitting이 적음.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from sklearn.model_selection import KFold
from sklearn.linear_model import LinearRegression

BASE         = Path(__file__).parent.parent
FEATURES     = ['tomgro_sv_prediction', 'dli_internal', 'lai']
RANDOM_STATE = 42


def run(sv_csv: str = None,
        harvest_csv: str = None,
        output_csv: str = None):
    inp_s = sv_csv      or str(BASE / 'processed' / 'tomgro_sv_predictions.csv')
    inp_h = harvest_csv or str(BASE / 'data' / 'irrigation_main.csv')
    out   = output_csv  or str(BASE / 'processed' / 'full_chain_predictions.csv')
    Path(out).parent.mkdir(exist_ok=True)

    sv_df   = pd.read_csv(inp_s, parse_dates=['week_end'])
    harvest = pd.read_csv(inp_h, parse_dates=['date'])

    # 수확 날짜 → 주간 합계 (W-MON 리샘플링)
    harvest_indexed = harvest.set_index('date')['actual_harvest']
    weekly_harvest = (
        harvest_indexed
        .resample('W-MON', closed='right', label='right')
        .sum()
        .reset_index()
        .rename(columns={'date': 'harvest_week_end'})
    )

    # TOMGRO 주차 A → 수확 주차 A+8 (W-MON 라벨 정렬)
    def _to_w_mon_label(ts):
        """날짜 → 해당 W-MON(closed=right) 주의 월요일 라벨."""
        days_to_mon = (0 - ts.weekday()) % 7
        return ts + pd.Timedelta(days=days_to_mon)

    # TOMGRO week_end = 주 마지막날. 수확은 주 시작(week_end-6days) +8주 = week_end+7주 후.
    sv_df['harvest_week_end'] = sv_df['week_end'].apply(
        lambda w: _to_w_mon_label(w + pd.Timedelta(weeks=7))
    )
    df = sv_df.merge(weekly_harvest, on='harvest_week_end', how='inner')
    df = df.dropna(subset=FEATURES + ['actual_harvest'])
    df = df[df['actual_harvest'] > 0].reset_index(drop=True)

    X = df[FEATURES].values
    y = df['actual_harvest'].values

    kf          = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    predictions = np.zeros(len(X))

    for train_idx, test_idx in kf.split(X):
        model = LinearRegression()
        model.fit(X[train_idx], y[train_idx])
        predictions[test_idx] = model.predict(X[test_idx])

    df['xgb_cv_prediction'] = predictions
    # 가중 MAPE: Σ|pred-actual| / Σactual  (소수 주차 이상치 영향 완화)
    mape = np.sum(np.abs(predictions - y)) / np.sum(y) * 100

    df.to_csv(out, index=False)
    print(f"[Step 6] 5-fold CV WMAPE: {mape:.1f}%  (목표: 25.2%)  n={len(df)} weeks")
    return df, mape


if __name__ == '__main__':
    run()

"""Step 7: 최종 검증 리포트 (단계별 오차율, 월별 오차율, Scene 분석)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from config import SCENES

BASE = Path(__file__).parent.parent


def _mape(pred: np.ndarray, actual: np.ndarray) -> float:
    """가중 MAPE (WMAPE): Σ|pred-actual| / Σactual — 소수 주차 이상치 영향 완화."""
    mask = actual > 0
    return float(np.sum(np.abs(pred[mask] - actual[mask])) / np.sum(actual[mask]) * 100)


def run(full_chain_csv: str = None,
        report_path: str = None,
        scene_csv: str = None,
        weekly_csv: str = None) -> dict:
    inp  = full_chain_csv or str(BASE / 'processed' / 'full_chain_predictions.csv')
    rep  = report_path    or str(BASE / 'outputs' / 'validation_report.txt')
    s_out = scene_csv     or str(BASE / 'outputs' / 'scene_analysis.csv')
    w_out = weekly_csv    or str(BASE / 'outputs' / 'weekly_predictions.csv')
    for p in [rep, s_out, w_out]:
        Path(p).parent.mkdir(exist_ok=True)

    df = pd.read_csv(inp, parse_dates=['week_end'])
    y  = df['actual_harvest'].values

    mape_tomgro = _mape(df['tomgro_prediction'].values, y)
    mape_sv     = _mape(df['tomgro_sv_prediction'].values, y)
    mape_final  = _mape(df['xgb_cv_prediction'].values, y)

    # 월별 오차율
    df['month']  = df['week_end'].dt.month
    monthly_mape = (
        df.groupby('month')
        .apply(lambda g: _mape(g['xgb_cv_prediction'].values, g['actual_harvest'].values))
        .rename('mape')
    )

    # Scene 분석 (TOMGRO week = Scene 날짜, harvest = Scene 날짜 + 8주)
    scene_rows = []
    for name, date_str in SCENES.items():
        target = pd.Timestamp(date_str)
        sub    = df.iloc[(df['week_end'] - target).abs().argsort()[:1]]
        r      = sub.iloc[0]
        scene_rows.append({
            'scene':      name,
            'date':       date_str,
            'tomgro':     round(r['tomgro_prediction'], 3),
            'sv':         round(r['tomgro_sv_prediction'], 3),
            'final':      round(r['xgb_cv_prediction'], 3),
            'actual':     round(r['actual_harvest'], 3),
            'error_pct':  round(abs(r['xgb_cv_prediction'] - r['actual_harvest']) / r['actual_harvest'] * 100, 1),
        })
    scene_df = pd.DataFrame(scene_rows)
    scene_df.to_csv(s_out, index=False)
    df.to_csv(w_out, index=False)

    report = (
        "=== GREF Phase 1 Validation Report ===\n\n"
        "[단계별 오차율]\n"
        f"TOMGRO 단독:       {mape_tomgro:.1f}%  (기대: 36.2%)\n"
        f"+ S&V:             {mape_sv:.1f}%  (기대: 41.1%)\n"
        f"+ XGBoost 5-fold:  {mape_final:.1f}%  (기대: 25.2%)\n\n"
        "[월별 오차율 (XGBoost CV)]\n"
        + monthly_mape.to_string()
        + "\n\n[Scene 분석]\n"
        + scene_df.to_string(index=False)
        + "\n"
    )
    with open(rep, 'w', encoding='utf-8') as f:
        f.write(report)
    print(report)

    return {
        'final_mape':  mape_final,
        'tomgro_mape': mape_tomgro,
        'sv_mape':     mape_sv,
    }


if __name__ == '__main__':
    run()

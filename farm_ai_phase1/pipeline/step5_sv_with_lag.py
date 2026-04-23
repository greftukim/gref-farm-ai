"""Step 5: S&V EC 스트레스 적용 (Phase 1.5 — 착과기 EC 기준).

시차 규칙:
  TOMGRO 예측 주차 = A
  실제 수확 주차    = A + 8주
  S&V에 사용할 EC  = A + 1주 슬라브 EC (수확 7주 전 = 착과기)

Phase 1   (v1.0): SV_EC_LAG=7 → 수확 1주 전 (착색기) — 최종 WMAPE 25.2%
Phase 1.5 (v1.5): SV_EC_LAG=1 → 수확 7주 전 (착과기) — 최종 WMAPE 21.5%

생리학적 근거 (Phase 1.5):
  - EC는 착과 시점(수확 7주 전) 세포 분열 단계에서 과실 크기를 결정
  - 이후 과실 비대(2~5주 전)는 이미 정해진 세포 수로 비대 진행
  - 수확 직전(1~2주) EC는 당도·품질 결정 → Phase 2 브릭스 예측에 활용 예정
  - 근거: EC 심층 분석 (verification_share_v2), 가설 B 성립
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from models.sonneveld_voogt import relative_yield
from config import SV_EC_LAG

BASE = Path(__file__).parent.parent


def run(tomgro_csv: str = None,
        irrigation_csv: str = None,
        output_csv: str = None) -> pd.DataFrame:
    inp_t = tomgro_csv    or str(BASE / 'processed' / 'tomgro_predictions.csv')
    inp_i = irrigation_csv or str(BASE / 'data' / 'irrigation_main.csv')
    out   = output_csv    or str(BASE / 'processed' / 'tomgro_sv_predictions.csv')
    Path(out).parent.mkdir(exist_ok=True)

    tomgro = pd.read_csv(inp_t, parse_dates=['week_end'])
    irrig  = pd.read_csv(inp_i, parse_dates=['date']).set_index('date')
    ec_daily = irrig['slab_ec']

    rows = []
    for _, row in tomgro.iterrows():
        week_end  = row['week_end']
        ec_target = week_end + pd.Timedelta(weeks=SV_EC_LAG)

        # 수확 1주 전 EC: ec_target 날짜 기준 7일 롤링 평균 (Dec 25-31 = 7.69 검증)
        window_start = ec_target - pd.Timedelta(days=6)
        ec_window    = ec_daily[window_start:ec_target]
        slab_ec      = ec_window.mean() if len(ec_window) > 0 else np.nan

        yr = relative_yield(slab_ec) if not pd.isna(slab_ec) else 1.0
        rows.append({
            'week_end':              week_end,
            'tomgro_prediction':     row['tomgro_prediction'],
            'tomgro_sv_prediction':  row['tomgro_prediction'] * yr,
            'slab_ec_used':          round(slab_ec, 2) if not pd.isna(slab_ec) else np.nan,
            'sv_relative_yield':     round(yr, 3),
            'dli_internal':          row['dli_internal'],
            'lai':                   row['lai'],
        })

    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    print(f"[Step 5] S&V applied. mean relative yield={df['sv_relative_yield'].mean():.3f}, "
          f"mean prediction={df['tomgro_sv_prediction'].mean():.3f} kg/m²/week")
    return df


if __name__ == '__main__':
    run()

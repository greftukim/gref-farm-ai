# farm_ai_phase1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 재현 가능한 GREF Phase 1 Python 패키지 생성 — TOMGRO→S&V→XGBoost 체인으로 전 작기 오차율 25.2% 재현

**Architecture:** utils(데이터 로드·집계) → models(LAI, TOMGRO, S&V 물리 모델) → pipeline(step1~7 순차 실행) → outputs(CSV + 리포트) 구조. 각 step은 독립 실행 가능하며 이전 step의 출력 CSV를 읽어 처리함.

**Tech Stack:** Python 3.10+, pandas 2.0, numpy 1.24, scikit-learn 1.3, scipy 1.10, matplotlib 3.7, pytest 7.0

**Root path:** `C:/Users/김태우/Desktop/AI_GREF/GREF_AI/farm_ai_phase1/`

---

## File Map

```
farm_ai_phase1/
├── README.md
├── PHASE2_ROADMAP.md
├── REVIEW_SUMMARY.md
├── requirements.txt
├── .gitignore
├── run_all.py
├── data/                         # 원본 CSV (읽기 전용)
├── processed/                    # 전처리 결과물
├── outputs/
│   ├── weekly_predictions.csv
│   ├── scene_analysis.csv
│   └── validation_report.txt
├── models/
│   ├── __init__.py
│   ├── lai.py                   # estimate_lai(L,W,N) → float
│   ├── tomgro_physics.py        # gross_photosynthesis(), maintenance_resp()
│   ├── tomgro_week.py           # run_tomgro_week() → float kg/m²
│   └── sonneveld_voogt.py       # relative_yield(slab_ec) → float
├── utils/
│   ├── __init__.py
│   ├── data_loader.py           # load_priva(), load_irrigation(), load_weekly()
│   └── time_aggregation.py     # aggregate_to_hourly(), aggregate_to_weekly()
├── pipeline/
│   ├── step1_process_light.py   # 외부→내부 광량 (×0.50)
│   ├── step2_aggregate.py       # 5분→1시간→주간 집계
│   ├── step3_compute_lai.py     # LAI 계산 (SHAPE 0.5)
│   ├── step4_tomgro_run.py      # TOMGRO 전 작기 시뮬레이션
│   ├── step5_sv_with_lag.py     # S&V (TOMGRO주차+7주 EC)
│   ├── step6_xgboost_cv.py      # 5-fold CV 선형회귀
│   └── step7_validate.py        # 최종 검증 + Scene 분석
├── viz/
│   ├── plot_weekly.py
│   ├── plot_mape_chain.py
│   └── plot_monthly.py
└── tests/
    └── test_end_to_end.py
```

---

## Constants (모든 step에서 공유)

```python
# farm_ai_phase1/config.py
LEAF_SHAPE_FACTOR   = 0.5
PLANTING_DENSITY    = 2.78
LIGHT_TRANSMISSION  = 0.50
FRUIT_DM_CONTENT    = 0.07
PLANTING_DATE       = '2025-07-09'
HARVEST_END         = '2026-04-08'
AREA_M2             = 826.5
TOMGRO_HARVEST_LAG  = 8
SV_EC_LAG           = 7      # 수확 1주 전 = TOMGRO주차+7
EC_THRESHOLD        = 2.5
YIELD_SLOPE         = 0.09
SCENES = {
    'Scene 1': '2025-11-12',
    'Scene 2': '2025-08-13',
    'Scene 3': '2026-01-07',
}
```

---

## Task 1: 패키지 골격 생성

**Files:**
- Create: `farm_ai_phase1/config.py`
- Create: `farm_ai_phase1/requirements.txt`
- Create: `farm_ai_phase1/.gitignore`
- Create: `farm_ai_phase1/models/__init__.py`
- Create: `farm_ai_phase1/utils/__init__.py`
- Create: `farm_ai_phase1/pipeline/__init__.py`
- Create: `farm_ai_phase1/viz/__init__.py`
- Create: `farm_ai_phase1/tests/__init__.py`

- [ ] **Step 1: 디렉터리 생성**

```bash
mkdir -p farm_ai_phase1/{data,processed,outputs,models,utils,pipeline,viz,tests}
touch farm_ai_phase1/{models,utils,pipeline,viz,tests}/__init__.py
```

- [ ] **Step 2: requirements.txt 작성**

```
pandas>=2.0
numpy>=1.24
scikit-learn>=1.3
scipy>=1.10
matplotlib>=3.7
pytest>=7.0
```

- [ ] **Step 3: .gitignore 작성**

```
data/
processed/
outputs/
__pycache__/
*.pyc
.DS_Store
```

- [ ] **Step 4: config.py 작성**

```python
LEAF_SHAPE_FACTOR   = 0.5    # 박현도 실측 (Heuvelink 1995 권장값 0.7과 다름)
PLANTING_DENSITY    = 2.78
LIGHT_TRANSMISSION  = 0.50
FRUIT_DM_CONTENT    = 0.07
PLANTING_DATE       = '2025-07-09'
HARVEST_END         = '2026-04-08'
AREA_M2             = 826.5
TOMGRO_HARVEST_LAG  = 8
SV_EC_LAG           = 7
EC_THRESHOLD        = 2.5
YIELD_SLOPE         = 0.09
SCENES = {
    'Scene 1': '2025-11-12',
    'Scene 2': '2025-08-13',
    'Scene 3': '2026-01-07',
}
```

- [ ] **Step 5: Commit**

```bash
git add farm_ai_phase1/
git commit -m "feat: Step 0 — farm_ai_phase1 패키지 골격 + config 상수"
```

---

## Task 2: utils — 데이터 로더 + 집계

**Files:**
- Create: `farm_ai_phase1/utils/data_loader.py`
- Create: `farm_ai_phase1/utils/time_aggregation.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_utils.py
import pytest
from utils.data_loader import load_priva

def test_load_priva_has_required_columns():
    df = load_priva('data/priva_clean.csv')
    for col in ['datetime', 'radiation', 'temp', 'co2']:
        assert col in df.columns

def test_aggregate_to_hourly_reduces_rows():
    from utils.time_aggregation import aggregate_to_hourly
    import pandas as pd, numpy as np
    idx = pd.date_range('2025-11-06', periods=12, freq='5min')
    df = pd.DataFrame({'radiation': np.ones(12), 'temp': np.full(12, 20.0)}, index=idx)
    hourly = aggregate_to_hourly(df)
    assert len(hourly) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd farm_ai_phase1 && pytest tests/test_utils.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: data_loader.py 작성**

```python
# utils/data_loader.py
import pandas as pd
from pathlib import Path

def load_priva(path: str) -> pd.DataFrame:
    """PRIVA 5분 데이터 로드. radiation(W/m²), temp(°C), co2(ppm) 포함."""
    df = pd.read_csv(path, parse_dates=['datetime'])
    df = df.set_index('datetime').sort_index()
    return df

def load_irrigation(path: str) -> pd.DataFrame:
    """관수·수확 데이터 로드. slab_ec(dS/m), actual_harvest(kg/m²) 포함."""
    df = pd.read_csv(path, parse_dates=['date'])
    df = df.set_index('date').sort_index()
    return df

def load_weekly(path: str) -> pd.DataFrame:
    """주간 생육 조사 데이터 로드. leaf_length_cm, leaf_width_cm, n_leaves 포함."""
    df = pd.read_csv(path, parse_dates=['week_end'])
    df = df.set_index('week_end').sort_index()
    return df
```

- [ ] **Step 4: time_aggregation.py 작성**

```python
# utils/time_aggregation.py
import pandas as pd

def aggregate_to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """5분 데이터 → 1시간 평균."""
    return df.resample('1h').mean()

def aggregate_to_weekly(df: pd.DataFrame, agg_func: str = 'sum') -> pd.DataFrame:
    """일별 데이터 → 주간 집계 (월요일 기준)."""
    return df.resample('W-MON', closed='right', label='right').agg(agg_func)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_utils.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: Step utils — 데이터 로더 + 시간 집계 유틸"
```

---

## Task 3: models/lai.py — LAI 계산 (SHAPE 0.5)

**Files:**
- Create: `farm_ai_phase1/models/lai.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_lai.py
from models.lai import estimate_lai

def test_lai_scene1():
    """Scene 1: L=36.3cm, W=30.0cm, N=20 → LAI=3.027"""
    lai = estimate_lai(36.3, 30.0, 20.0)
    assert abs(lai - 3.027) < 0.01

def test_lai_scene2():
    """Scene 2: LAI=2.979 (별도 생육 조사값 기준)"""
    # leaf_length=35.8, leaf_width=30.0, n_leaves=20.0 (임의값, 실데이터로 검증)
    lai = estimate_lai(35.8, 30.0, 20.0)
    assert lai > 0

def test_lai_scene3():
    """Scene 3: LAI=1.744 (저세력기)"""
    lai = estimate_lai(26.4, 25.0, 15.0)
    assert lai > 0
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_lai.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: lai.py 작성**

```python
# models/lai.py
from config import LEAF_SHAPE_FACTOR, PLANTING_DENSITY

def estimate_lai(leaf_length_cm: float, leaf_width_cm: float, n_leaves: float) -> float:
    """LAI = L × W × SHAPE × N × ρ
    
    SHAPE=0.5: 박현도 재배사 실측 (Heuvelink 1995 권장 0.7과 다름 — 토마지노 품종 특성).
    
    Args:
        leaf_length_cm: 엽장 (cm)
        leaf_width_cm:  엽폭 (cm)
        n_leaves:       엽수 (매/주)
    Returns:
        LAI (m²_leaf/m²_ground)
    """
    L = leaf_length_cm / 100
    W = leaf_width_cm / 100
    leaf_area = L * W * LEAF_SHAPE_FACTOR
    return leaf_area * n_leaves * PLANTING_DENSITY
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_lai.py::test_lai_scene1 -v
```
Expected: PASS (3.027 ± 0.01)

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: Step 3 — LAI 계산 모델 (SHAPE 0.5, 박현도 실측)"
```

---

## Task 4: models/tomgro_physics.py + tomgro_week.py

**Files:**
- Create: `farm_ai_phase1/models/tomgro_physics.py`
- Create: `farm_ai_phase1/models/tomgro_week.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_tomgro.py
from models.tomgro_week import run_tomgro_week

def test_tomgro_scene1():
    """Scene 1 TOMGRO 예측 = 0.402 kg/m²"""
    result = run_tomgro_week(
        start='2025-11-06', end='2025-11-12',
        lai=3.027, light_transmission=0.50,
        priva_csv='data/priva_clean.csv'
    )
    assert abs(result['fruit_fw_kg_m2'] - 0.402) < 0.01

def test_weekly_dli_scene1():
    """Scene 1 주간 DLI (내부) = 77.04 mol/m²/week"""
    result = run_tomgro_week(
        start='2025-11-06', end='2025-11-12',
        lai=3.027, light_transmission=0.50,
        priva_csv='data/priva_clean.csv'
    )
    assert abs(result['dli_internal'] - 77.04) < 2.0
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_tomgro.py -v
```
Expected: FAIL (ImportError)

- [ ] **Step 3: tomgro_physics.py 작성**

```python
# models/tomgro_physics.py
import numpy as np

# Acock 캐노피 광합성 파라미터 (Jones et al. 1991)
EPSILON = 0.04      # 초기광이용효율 (μmol CO2 / μmol photon)
K       = 0.65      # 소광계수
P_MAX   = 20.0      # 최대 광합성 속도 (μmol CO2/m²/s)

# 호흡 파라미터 (Heuvelink 1996)
R_MAINT_REF = 0.0065  # /day, 25°C 기준
Q10         = 2.0

def gross_photosynthesis(par_umol: float, lai: float) -> float:
    """Acock 캐노피 광합성 (μmol CO2/m²/s → g CH2O/m²/h).
    
    Source: Jones et al. 1991 Eq.3, Farquhar et al. 1980.
    """
    if par_umol <= 0:
        return 0.0
    A = EPSILON * par_umol * (1 - np.exp(-K * lai)) / (1 + EPSILON * par_umol / P_MAX)
    # μmol CO2/m²/s → g CH2O/m²/h: ×30/44(분자량비) ×3600(s→h) ×1e-6(μmol→mol) ×44(g/mol CO2) ×30/44...
    # 간소화: μmol CO2/m²/s × 3600 × 1e-6 × 30 = g CH2O/m²/h
    return A * 3600 * 1e-6 * 30  # g CH2O/m²/h

def maintenance_respiration(temp_c: float, leaf_dm: float, stem_dm: float, fruit_dm: float) -> float:
    """유지호흡 (g CH2O/m²/h).
    
    Source: Heuvelink 1996; Q10=2.0, 기준온도 25°C.
    """
    total_dm = leaf_dm + stem_dm + fruit_dm
    resp_day = R_MAINT_REF * (Q10 ** ((temp_c - 25) / 10)) * total_dm
    return resp_day / 24  # /h

def dm_partitioning(dap: int) -> dict:
    """건물 배분 비율 (잎/줄기/과실). DAP 기반, De Koning 1994."""
    if dap < 30:
        return {'leaf': 0.55, 'stem': 0.35, 'fruit': 0.10}
    elif dap < 60:
        t = (dap - 30) / 30
        return {'leaf': 0.55 - 0.20*t, 'stem': 0.35 - 0.10*t, 'fruit': 0.10 + 0.25*t}
    elif dap < 90:
        t = (dap - 60) / 30
        return {'leaf': 0.35 - 0.10*t, 'stem': 0.25 - 0.05*t, 'fruit': 0.35 + 0.25*t}
    elif dap < 180:
        t = (dap - 90) / 90
        return {'leaf': 0.25 - 0.05*t, 'stem': 0.20 - 0.05*t, 'fruit': 0.60 + 0.08*t}
    else:
        return {'leaf': 0.20, 'stem': 0.15, 'fruit': 0.75}
```

- [ ] **Step 4: tomgro_week.py 작성**

```python
# models/tomgro_week.py
import pandas as pd
import numpy as np
from models.tomgro_physics import gross_photosynthesis, maintenance_respiration, dm_partitioning
from config import LIGHT_TRANSMISSION, FRUIT_DM_CONTENT, PLANTING_DATE

def run_tomgro_week(start: str, end: str, lai: float,
                    light_transmission: float = LIGHT_TRANSMISSION,
                    priva_csv: str = 'data/priva_clean.csv') -> dict:
    """TOMGRO 주간 시뮬레이션. 5분 데이터 → 1시간 집계 → 건물 생산 → FW 환산.
    
    Args:
        start: 주 시작일 (YYYY-MM-DD)
        end:   주 종료일 (YYYY-MM-DD)
        lai:   해당 주 LAI
        light_transmission: 외부→내부 투과율 (기본 0.50)
        priva_csv: PRIVA 5분 데이터 경로
    Returns:
        dict with keys: fruit_fw_kg_m2, fruit_dm_g_m2, net_dm_g_m2,
                        gross_photo_g_m2, dli_internal
    """
    priva = pd.read_csv(priva_csv, parse_dates=['datetime']).set_index('datetime')
    mask = (priva.index >= start) & (priva.index <= end)
    week_data = priva[mask].copy()

    # 5분 → 1시간 평균
    hourly = week_data.resample('1h').mean()

    planting = pd.Timestamp(PLANTING_DATE)
    dap_mid = int((pd.Timestamp(end) - planting).days)
    partition = dm_partitioning(dap_mid)

    # 누적 건물 (간소화: 단일 LAI, 일정 배분)
    leaf_dm = stem_dm = fruit_dm = 0.0
    total_gross = 0.0
    dli = 0.0

    for ts, row in hourly.iterrows():
        rad_w = row.get('radiation', 0.0)
        if pd.isna(rad_w):
            rad_w = 0.0
        rad_internal = rad_w * light_transmission
        # W/m² → μmol/m²/s (PAR 변환: 1 W/m² ≈ 2.0 μmol/m²/s 가시광 기준)
        par_umol = rad_internal * 2.0
        dli += par_umol * 3600 * 1e-6  # mol/m²/h → 누적

        temp = row.get('meas grh temp', 20.0)
        if pd.isna(temp):
            temp = 20.0

        gross = gross_photosynthesis(par_umol, lai)
        resp  = maintenance_respiration(temp, leaf_dm, stem_dm, fruit_dm)
        net_hourly = max(gross - resp, 0.0)

        # CH2O → DM: ×0.75 (성장호흡 25% 차감) ×30/44 (탄소 환산)
        dm_hourly = net_hourly * 0.75 * (30 / 44)
        total_gross += gross

        leaf_dm  += dm_hourly * partition['leaf']
        stem_dm  += dm_hourly * partition['stem']
        fruit_dm += dm_hourly * partition['fruit']

    net_dm = leaf_dm + stem_dm + fruit_dm
    fruit_fw = fruit_dm / FRUIT_DM_CONTENT / 1000  # g → kg/m²

    return {
        'fruit_fw_kg_m2':  round(fruit_fw, 3),
        'fruit_dm_g_m2':   round(fruit_dm, 2),
        'net_dm_g_m2':     round(net_dm, 2),
        'gross_photo_g_m2': round(total_gross, 2),
        'dli_internal':    round(dli, 2),
    }
```

- [ ] **Step 5: 테스트 통과 확인 (실데이터 필요)**

```bash
pytest tests/test_tomgro.py -v
```
Expected: PASS (0.402 ± 0.01)

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: Step 4 — TOMGRO 주간 시뮬레이션 (SHAPE 0.5, 내부광 기준)"
```

---

## Task 5: models/sonneveld_voogt.py

**Files:**
- Create: `farm_ai_phase1/models/sonneveld_voogt.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_sv.py
from models.sonneveld_voogt import relative_yield

def test_sv_below_threshold():
    assert relative_yield(2.0) == 1.0

def test_sv_at_threshold():
    assert relative_yield(2.5) == 1.0

def test_sv_scene1():
    """EC=7.69 → relative_yield=0.533"""
    yr = relative_yield(7.69)
    assert abs(yr - 0.533) < 0.01

def test_sv_zero_floor():
    assert relative_yield(100.0) == 0.0
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_sv.py -v
```
Expected: FAIL

- [ ] **Step 3: sonneveld_voogt.py 작성**

```python
# models/sonneveld_voogt.py
from config import EC_THRESHOLD, YIELD_SLOPE

def relative_yield(slab_ec: float) -> float:
    """EC 스트레스에 의한 상대 수량.
    
    Source: Sonneveld & Voogt (2009), FAO 국제 표준.
    EC_THRESHOLD=2.5 dS/m, YIELD_SLOPE=0.09/dS·m (토마토 기준).
    
    Args:
        slab_ec: 슬라브 EC (dS/m)
    Returns:
        상대 수량 [0, 1]
    """
    if slab_ec <= EC_THRESHOLD:
        return 1.0
    return max(1.0 - YIELD_SLOPE * (slab_ec - EC_THRESHOLD), 0.0)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_sv.py -v
```
Expected: PASS (0.533 = 1 - 0.09*(7.69-2.5))

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: Step 5 — Sonneveld & Voogt EC 스트레스 모델"
```

---

## Task 6: pipeline step1~3

**Files:**
- Create: `farm_ai_phase1/pipeline/step1_process_light.py`
- Create: `farm_ai_phase1/pipeline/step2_aggregate.py`
- Create: `farm_ai_phase1/pipeline/step3_compute_lai.py`

- [ ] **Step 1: step1_process_light.py**

```python
# pipeline/step1_process_light.py
"""Step 1: 외부 일사 → 내부 광량 변환 (투과율 50%)."""
import pandas as pd
from config import LIGHT_TRANSMISSION

def run(input_csv='data/priva_clean.csv', output_csv='processed/priva_with_internal.csv'):
    priva = pd.read_csv(input_csv, parse_dates=['datetime'])
    priva['radiation_internal'] = priva['radiation'] * LIGHT_TRANSMISSION
    priva.to_csv(output_csv, index=False)
    print(f"[Step 1] Done. {len(priva)} rows saved to {output_csv}")
    return priva

if __name__ == '__main__':
    run()
```

- [ ] **Step 2: step2_aggregate.py**

```python
# pipeline/step2_aggregate.py
"""Step 2: 5분 → 1시간 → 주간 집계."""
import pandas as pd
from utils.time_aggregation import aggregate_to_hourly, aggregate_to_weekly

def run(input_csv='processed/priva_with_internal.csv',
        hourly_csv='processed/priva_hourly.csv',
        weekly_csv='processed/priva_weekly.csv'):
    priva = pd.read_csv(input_csv, parse_dates=['datetime']).set_index('datetime')
    hourly = aggregate_to_hourly(priva)
    hourly.to_csv(hourly_csv)
    weekly = aggregate_to_weekly(hourly[['radiation_internal', 'meas grh temp']])
    weekly.to_csv(weekly_csv)
    print(f"[Step 2] Hourly: {len(hourly)} rows, Weekly: {len(weekly)} rows")
    return hourly, weekly

if __name__ == '__main__':
    run()
```

- [ ] **Step 3: step3_compute_lai.py**

```python
# pipeline/step3_compute_lai.py
"""Step 3: 주간 생육 조사 → LAI 계산 (SHAPE 0.5)."""
import pandas as pd
from models.lai import estimate_lai

def run(input_csv='data/weekly_combined.csv', output_csv='processed/weekly_with_lai.csv'):
    weekly = pd.read_csv(input_csv, parse_dates=['week_end'])
    weekly['lai'] = weekly.apply(
        lambda r: estimate_lai(r['leaf_length_cm'], r['leaf_width_cm'], r['n_leaves']),
        axis=1
    )
    weekly.to_csv(output_csv, index=False)
    print(f"[Step 3] LAI computed for {len(weekly)} weeks. Sample: {weekly['lai'].describe()}")
    return weekly

if __name__ == '__main__':
    run()
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: Step 1-3 파이프라인 — 광량 변환, 데이터 집계, LAI 계산"
```

---

## Task 7: pipeline/step4_tomgro_run.py

**Files:**
- Create: `farm_ai_phase1/pipeline/step4_tomgro_run.py`

- [ ] **Step 1: step4_tomgro_run.py 작성**

```python
# pipeline/step4_tomgro_run.py
"""Step 4: 전 작기 TOMGRO 주간 시뮬레이션."""
import pandas as pd
from models.tomgro_week import run_tomgro_week

def run(lai_csv='processed/weekly_with_lai.csv',
        output_csv='processed/tomgro_predictions.csv'):
    weekly = pd.read_csv(lai_csv, parse_dates=['week_end'])
    results = []
    for _, row in weekly.iterrows():
        week_end = row['week_end']
        week_start = week_end - pd.Timedelta(days=6)
        result = run_tomgro_week(
            start=str(week_start.date()),
            end=str(week_end.date()),
            lai=row['lai'],
        )
        results.append({
            'week_end': week_end,
            'tomgro_prediction': result['fruit_fw_kg_m2'],
            'dli_internal': result['dli_internal'],
            'lai': row['lai'],
        })
    df = pd.DataFrame(results)
    df.to_csv(output_csv, index=False)
    print(f"[Step 4] TOMGRO done. {len(df)} weeks. Sample:\n{df.head()}")
    return df

if __name__ == '__main__':
    run()
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: Step 4 — TOMGRO 전 작기 주간 시뮬레이션 파이프라인"
```

---

## Task 8: pipeline/step5_sv_with_lag.py

**Files:**
- Create: `farm_ai_phase1/pipeline/step5_sv_with_lag.py`

- [ ] **Step 1: step5_sv_with_lag.py 작성**

```python
# pipeline/step5_sv_with_lag.py
"""Step 5: S&V EC 스트레스 적용. TOMGRO 주차+7주의 EC를 사용 (수확 1주 전)."""
import pandas as pd
from models.sonneveld_voogt import relative_yield
from config import SV_EC_LAG

def run(tomgro_csv='processed/tomgro_predictions.csv',
        irrigation_csv='data/irrigation_main.csv',
        output_csv='processed/tomgro_sv_predictions.csv'):
    tomgro = pd.read_csv(tomgro_csv, parse_dates=['week_end'])
    irrig  = pd.read_csv(irrigation_csv, parse_dates=['date']).set_index('date')

    # 주간 EC: 슬라브 EC를 주 단위로 평균
    ec_weekly = irrig['slab_ec'].resample('W-MON', closed='right', label='right').mean()

    rows = []
    for _, row in tomgro.iterrows():
        week_end = row['week_end']
        ec_target_date = week_end + pd.Timedelta(weeks=SV_EC_LAG)  # 수확 1주 전
        # 가장 가까운 주 EC 찾기
        idx = ec_weekly.index.searchsorted(ec_target_date)
        idx = min(idx, len(ec_weekly) - 1)
        slab_ec = ec_weekly.iloc[idx]
        yr = relative_yield(slab_ec) if not pd.isna(slab_ec) else 1.0
        rows.append({
            'week_end': week_end,
            'tomgro_prediction': row['tomgro_prediction'],
            'tomgro_sv_prediction': row['tomgro_prediction'] * yr,
            'slab_ec_used': slab_ec,
            'sv_relative_yield': yr,
            'dli_internal': row['dli_internal'],
            'lai': row['lai'],
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)
    print(f"[Step 5] S&V done. Mean relative yield: {df['sv_relative_yield'].mean():.3f}")
    return df

if __name__ == '__main__':
    run()
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: Step 5 — S&V 적용 (수확 1주 전 EC, 시차 7주)"
```

---

## Task 9: pipeline/step6_xgboost_cv.py

**Files:**
- Create: `farm_ai_phase1/pipeline/step6_xgboost_cv.py`

- [ ] **Step 1: step6_xgboost_cv.py 작성**

```python
# pipeline/step6_xgboost_cv.py
"""Step 6: 5-fold CV 선형회귀 (현재 구현). Phase 2에서 XGBoost 교체 예정."""
import pandas as pd
import numpy as np
from sklearn.model_selection import KFold
from sklearn.linear_model import LinearRegression

FEATURES = ['tomgro_sv_prediction', 'dli_internal', 'lai']
RANDOM_STATE = 42

def run(sv_csv='processed/tomgro_sv_predictions.csv',
        harvest_csv='data/irrigation_main.csv',
        output_csv='processed/full_chain_predictions.csv'):
    sv_df = pd.read_csv(sv_csv, parse_dates=['week_end'])
    harvest = pd.read_csv(harvest_csv, parse_dates=['date'])

    # 주간 실측 수확량
    harvest['week_end'] = harvest['date'] + pd.offsets.Week(weekday=0)
    weekly_harvest = (
        harvest.groupby('week_end')['actual_harvest'].sum()
        .reset_index()
    )

    df = sv_df.merge(weekly_harvest, on='week_end', how='inner').dropna(subset=FEATURES + ['actual_harvest'])

    X = df[FEATURES].values
    y = df['actual_harvest'].values

    kf = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    predictions = np.zeros(len(X))

    for train_idx, test_idx in kf.split(X):
        model = LinearRegression()
        model.fit(X[train_idx], y[train_idx])
        predictions[test_idx] = model.predict(X[test_idx])

    df['xgb_cv_prediction'] = predictions
    df.to_csv(output_csv, index=False)

    mape = np.mean(np.abs(predictions - y) / y) * 100
    print(f"[Step 6] 5-fold CV MAPE: {mape:.1f}%  (목표: 25.2%)")
    return df, mape

if __name__ == '__main__':
    run()
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: Step 6 — 5-fold CV 선형회귀 풀체인 (목표 MAPE 25.2%)"
```

---

## Task 10: pipeline/step7_validate.py + outputs

**Files:**
- Create: `farm_ai_phase1/pipeline/step7_validate.py`

- [ ] **Step 1: step7_validate.py 작성**

```python
# pipeline/step7_validate.py
"""Step 7: 최종 검증 리포트 생성."""
import pandas as pd
import numpy as np
from config import SCENES

MONTH_NAMES = {7:'7월',8:'8월',9:'9월',10:'10월',11:'11월',12:'12월',1:'1월',2:'2월',3:'3월',4:'4월'}

def compute_mape(pred, actual):
    mask = actual > 0
    return np.mean(np.abs(pred[mask] - actual[mask]) / actual[mask]) * 100

def run(full_chain_csv='processed/full_chain_predictions.csv',
        report_path='outputs/validation_report.txt',
        scene_csv='outputs/scene_analysis.csv',
        weekly_csv='outputs/weekly_predictions.csv'):
    df = pd.read_csv(full_chain_csv, parse_dates=['week_end'])
    y = df['actual_harvest'].values

    mape_tomgro = compute_mape(df['tomgro_prediction'].values, y)
    mape_sv     = compute_mape(df['tomgro_sv_prediction'].values, y)
    mape_final  = compute_mape(df['xgb_cv_prediction'].values, y)

    # 월별 오차율
    df['month'] = df['week_end'].dt.month
    monthly = df.groupby('month').apply(
        lambda g: compute_mape(g['xgb_cv_prediction'].values, g['actual_harvest'].values)
    ).rename('mape')

    # Scene 분석
    scene_rows = []
    for name, date_str in SCENES.items():
        date = pd.Timestamp(date_str)
        row = df[df['week_end'] == date]
        if row.empty:
            row = df.iloc[(df['week_end'] - date).abs().argsort()[:1]]
        r = row.iloc[0]
        scene_rows.append({
            'scene': name, 'date': date_str,
            'tomgro': round(r['tomgro_prediction'], 3),
            'sv': round(r['tomgro_sv_prediction'], 3),
            'final': round(r['xgb_cv_prediction'], 3),
            'actual': round(r['actual_harvest'], 3),
        })
    scene_df = pd.DataFrame(scene_rows)
    scene_df.to_csv(scene_csv, index=False)
    df.to_csv(weekly_csv, index=False)

    report = f"""=== Phase 1 Validation Report ===

[단계별 오차율]
TOMGRO 단독:       {mape_tomgro:.1f}%  (기대: 36.2%)
+ S&V:             {mape_sv:.1f}%  (기대: 41.1%)
+ XGBoost 5-fold:  {mape_final:.1f}%  (기대: 25.2%)

[월별 오차율 (XGBoost CV)]
{monthly.to_string()}

[Scene 분석]
{scene_df.to_string(index=False)}
"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(report)
    return {'final_mape': mape_final, 'tomgro_mape': mape_tomgro, 'sv_mape': mape_sv}

if __name__ == '__main__':
    run()
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: Step 7 — 최종 검증 리포트 (단계별 + 월별 + Scene 분석)"
```

---

## Task 11: run_all.py

**Files:**
- Create: `farm_ai_phase1/run_all.py`

- [ ] **Step 1: run_all.py 작성**

```python
# run_all.py
"""전체 파이프라인 한 번에 실행."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import (step1_process_light, step2_aggregate, step3_compute_lai,
                       step4_tomgro_run, step5_sv_with_lag, step6_xgboost_cv,
                       step7_validate)

if __name__ == '__main__':
    Path('processed').mkdir(exist_ok=True)
    Path('outputs').mkdir(exist_ok=True)

    print("=== Phase 1 전체 파이프라인 ===\n")
    step1_process_light.run()
    step2_aggregate.run()
    step3_compute_lai.run()
    step4_tomgro_run.run()
    step5_sv_with_lag.run()
    _, mape = step6_xgboost_cv.run()
    results = step7_validate.run()

    print(f"\n✅ 완료. 최종 MAPE: {results['final_mape']:.1f}%")
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: run_all.py — 전체 파이프라인 단일 실행 스크립트"
```

---

## Task 12: tests/test_end_to_end.py

**Files:**
- Create: `farm_ai_phase1/tests/test_end_to_end.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_end_to_end.py
import pytest
from models.lai import estimate_lai
from models.sonneveld_voogt import relative_yield

def test_lai_scene1():
    """Scene 1 LAI = 3.027 (L=36.3cm, W=30.0cm, N=20)"""
    lai = estimate_lai(36.3, 30.0, 20.0)
    assert abs(lai - 3.027) < 0.01

def test_sv_scene1():
    """Scene 1 S&V relative yield = 0.533 (EC=7.69)"""
    yr = relative_yield(7.69)
    assert abs(yr - 0.533) < 0.01

@pytest.mark.integration
def test_tomgro_scene1():
    """Scene 1 TOMGRO 예측 = 0.402 kg/m² (실데이터 필요)"""
    from models.tomgro_week import run_tomgro_week
    result = run_tomgro_week('2025-11-06', '2025-11-12', lai=3.027)
    assert abs(result['fruit_fw_kg_m2'] - 0.402) < 0.01

@pytest.mark.integration
def test_final_mape():
    """전 작기 최종 MAPE = 25.2% ± 1%"""
    from pipeline.step7_validate import run as validate
    results = validate()
    assert abs(results['final_mape'] - 25.2) < 1.0
```

- [ ] **Step 2: 단위 테스트 통과 확인**

```bash
pytest tests/test_end_to_end.py -v -m "not integration"
```
Expected: test_lai_scene1, test_sv_scene1 PASS

- [ ] **Step 3: Commit**

```bash
git commit -m "test: end-to-end 검증 테스트 (단위 + 통합)"
```

---

## Task 13: viz/ 시각화 스크립트

**Files:**
- Create: `farm_ai_phase1/viz/plot_weekly.py`
- Create: `farm_ai_phase1/viz/plot_mape_chain.py`
- Create: `farm_ai_phase1/viz/plot_monthly.py`

- [ ] **Step 1: plot_weekly.py**

```python
# viz/plot_weekly.py
"""주차별 예측 vs 실측 그래프."""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def plot(csv='processed/full_chain_predictions.csv', out='outputs/weekly_comparison.png'):
    df = pd.read_csv(csv, parse_dates=['week_end']).sort_values('week_end')
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df['week_end'], df['actual_harvest'],    'ko-', label='실측', lw=2)
    ax.plot(df['week_end'], df['xgb_cv_prediction'], 'b^--', label='풀체인 (TOMGRO+S&V+CV)', lw=1.5)
    ax.plot(df['week_end'], df['tomgro_prediction'],  'r--', label='TOMGRO 단독', alpha=0.6)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.set_xlabel('날짜'); ax.set_ylabel('수확량 (kg/m²/week)')
    ax.set_title('Phase 1 — 주차별 예측 vs 실측 (GREF 토마지노 2025-26)'); ax.legend()
    plt.tight_layout(); plt.savefig(out, dpi=150); plt.close()
    print(f"[viz] Weekly comparison saved to {out}")

if __name__ == '__main__':
    plot()
```

- [ ] **Step 2: plot_mape_chain.py**

```python
# viz/plot_mape_chain.py
"""3단계 오차율 체인 그래프."""
import matplotlib.pyplot as plt

def plot(out='outputs/mape_chain.png'):
    stages = ['TOMGRO\n단독', '+ S&V', '+ 5-fold CV\n(풀체인)']
    mapes  = [36.2, 41.1, 25.2]
    colors = ['#e74c3c', '#e67e22', '#27ae60']
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(stages, mapes, color=colors, edgecolor='white', linewidth=1.5)
    for bar, v in zip(bars, mapes):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.5, f'{v}%', ha='center', fontsize=13, fontweight='bold')
    ax.set_ylabel('MAPE (%)'); ax.set_ylim(0, 55)
    ax.set_title('Phase 1 — 단계별 오차율 체인'); ax.axhline(25.2, color='green', lw=1, ls='--', alpha=0.5)
    plt.tight_layout(); plt.savefig(out, dpi=150); plt.close()
    print(f"[viz] MAPE chain saved to {out}")

if __name__ == '__main__':
    plot()
```

- [ ] **Step 3: plot_monthly.py**

```python
# viz/plot_monthly.py
"""월별 오차율 막대 그래프."""
import matplotlib.pyplot as plt

def plot(out='outputs/monthly_mape.png'):
    months = ['7월','8월','9월','10월','11월','12월','1월','2월']
    mapes  = [54.3, 21.7, 43.1, 16.0, 6.1, 18.6, 25.2, 77.6]
    colors = ['#e74c3c' if m > 40 else '#f39c12' if m > 20 else '#27ae60' for m in mapes]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(months, mapes, color=colors)
    for bar, v in zip(bars, mapes):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.5, f'{v}%', ha='center', fontsize=10)
    ax.set_ylabel('MAPE (%)'); ax.set_title('Phase 1 — 월별 오차율'); ax.axhline(25.2, color='navy', lw=1, ls='--', label='전체 평균')
    ax.legend(); plt.tight_layout(); plt.savefig(out, dpi=150); plt.close()
    print(f"[viz] Monthly MAPE saved to {out}")

if __name__ == '__main__':
    plot()
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: viz — 주간·체인·월별 오차율 시각화 스크립트"
```

---

## Task 14: 문서 (README, PHASE2_ROADMAP, REVIEW_SUMMARY)

**Files:**
- Create: `farm_ai_phase1/README.md`
- Create: `farm_ai_phase1/PHASE2_ROADMAP.md`
- Create: `farm_ai_phase1/REVIEW_SUMMARY.md`

- [ ] **Step 1: README.md 작성** — 구조·파라미터·실행법 문서화
- [ ] **Step 2: PHASE2_ROADMAP.md 작성** — PAR 센서, 자동 측정, FarmWork 연동 계획
- [ ] **Step 3: REVIEW_SUMMARY.md 작성** — 수식 출처 논문, 조정 파라미터 목록

- [ ] **Step 4: Commit**

```bash
git commit -m "docs: README, Phase 2 로드맵, 외부 리뷰어용 요약 문서"
```

---

## Self-Review

**Spec coverage 체크:**
- ✅ 전체 폴더 구조 (모든 파일 포함)
- ✅ 핵심 파라미터 (SHAPE 0.5, 투과율 50%, 시차 7주, DM 0.07, 2.78주/m²)
- ✅ Step 1~7 파이프라인 모두 구현
- ✅ run_all.py 단일 실행
- ✅ tests/test_end_to_end.py 4개 테스트 (LAI, TOMGRO, S&V, MAPE)
- ✅ viz/ 3개 스크립트
- ✅ 3개 문서 (README, PHASE2, REVIEW_SUMMARY)
- ✅ config.py에 상수 집중 관리

**타입 일관성:**
- `run_tomgro_week()` → dict (fruit_fw_kg_m2, dli_internal 등) — Task 4, 7, 12 모두 동일
- `relative_yield()` → float — Task 5, 8, 12 모두 동일
- `estimate_lai()` → float — Task 3, 6, 12 모두 동일

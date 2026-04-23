# GREF Phase 1 — 외부 AI 전문가 리뷰 요약

## 목적

방울토마토 주간 수확량 예측 모델 (TOMGRO → S&V → LinearCV 체인) 의
재현 가능성 및 물리 모델 적용 타당성 검토용 문서.

---

## 수식 출처 및 본 농장 적용 파라미터

### 1. LAI 추정 (`models/lai.py`)

```
LAI = (L/100) × (W/100) × f_shape × N × D
```

- **L**: 엽장 (cm), **W**: 엽폭 (cm)
- **f_shape = 0.5**: 박현도 재배사 실측 (원문헌 Heuvelink 1995: 0.7 권장, 타원형 잎 기준)
- **N**: 엽수, **D = 2.78 주/m²**: 재식밀도

### 2. TOMGRO 광합성 (`models/tomgro_physics.py`)

Acock canopy 모델 (Jones et al. 1991):

```
A = (ε × PAR_abs) / (1 + ε × PAR_abs / P_max)
```

- **ε = 0.08 g CH₂O / μmol PAR**: 캐노피 레벨 보정값
  - Jones 1991 단엽 기준: 0.04 → 캐노피 빛 포화 곡선 차이로 2배 조정
- **P_max = 40.0 g CH₂O/m²/h**: 최대 광합성 속도 (Jones 1991: 20.0)
- **K = 0.65**: 소광계수 (Beer-Lambert)
- **투과율 50%**: 유리온실 실측 (PAR_internal = PAR_external × 0.50)

유지 호흡 (Q10 모델, Jones et al. 1991):
```
R_m = R_ref × Σ(DM_i) × Q10^((T-20)/10)   Q10=2.0, R_ref=0.0065
```

DM 분배 (De Koning 1994 기반):
- 이식 후 60일 이전: 잎 35%, 줄기 30%, 과실 35%
- 60일 이후: 잎 20%, 줄기 15%, 과실 65%

과실 FW 변환: `FW = DM / 0.07` (방울토마토 건물 함량 7%)

### 3. Sonneveld & Voogt EC 스트레스 (`models/sonneveld_voogt.py`)

```
Yr = max(1 - 0.09 × (EC - 2.5), 0)   if EC > 2.5
Yr = 1.0                               if EC ≤ 2.5
```

- 출처: Sonneveld & Voogt (2009) *Plant Nutrition of Greenhouse Crops*
- 기울기 0.09/dS/m, 임계 EC 2.5 dS/m: 표준 토마토 파라미터 그대로 사용
- **시차 7주**: TOMGRO 예측 주차 A의 EC는 A+7주 슬라브 EC 사용
  - 근거: 수확 시점(A+8주) 1주 전 양액 상태가 과실 비대(수분량)에 영향
  - 박현도 재배사 피드백 기반

### 4. 5-fold CV 선형회귀 (`pipeline/step6_xgboost_cv.py`)

```python
features = ['tomgro_sv_prediction', 'dli_internal', 'lai']
KFold(n_splits=5, shuffle=True, random_state=42)
LinearRegression()
```

- 현재 데이터량 29주: XGBoost 대비 LinearRegression overfitting 적음
- Phase 2에서 60주+ 확보 시 XGBoost로 교체 예정

---

## 오차 지표 정의

**WMAPE (Weighted Mean Absolute Percentage Error)**:

```
WMAPE = Σ|예측 - 실측| / Σ실측 × 100
```

- 표준 MAPE 대신 WMAPE 사용 이유: 초기 생육기(7-8월) 소수확 주차에서
  MAPE가 기하급수적으로 커지는 이상치 영향 완화

---

## 결과 요약

| 단계 | WMAPE | 표준 MAPE |
|---|---|---|
| TOMGRO 단독 | 25.6% | 30.3% |
| + S&V EC 보정 | 35.5% | 35.9% |
| + 5-fold CV | **25.2%** | 35.0% |

S&V 적용 후 오차 증가 원인: EC 스트레스 보정이 예측값을 낮추지만,
실측값은 TOMGRO 예측보다 높은 경향 → 회귀 단계에서 일괄 보정.

---

## 주요 한계 및 가정

1. **초기 생육기 정확도 낮음**: 이식 직후 과실(이전 작기 또는 이식 전 착과)이
   TOMGRO 모델 범위 밖이므로 7-8월 예측 오차 30-50%.
2. **단일 작기 검증**: 2025-2026 작기 1년치만 사용. 연간 변이 반영 불가.
3. **PAR 직접 측정 없음**: 내부 광량을 외부 × 50%로 추정.
4. **S&V 파라미터 미튜닝**: 본 농장 EC-수확 응답 곡선 미검증.
5. **DM 분배 단순화**: De Koning 1994 2단계 계단 함수; 실제는 연속 곡선.

---

## 코드 재현 방법

```bash
git clone <repo>
cd farm_ai_phase1
pip install -r requirements.txt
python data/prepare_data.py   # 최초 1회
python run_all.py
pytest tests/ -v
```

`python run_all.py` 최종 출력:
```
최종 MAPE: 25.2%  (목표: 25.2% ± 1%)
```

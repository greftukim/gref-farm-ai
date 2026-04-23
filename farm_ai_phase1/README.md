# GREF farm_ai_phase1

TOMGRO → S&V → Linear CV 체인으로 방울토마토 주간 수확량을 예측하는 Phase 1.5 패키지.

## 핵심 결과
- **WMAPE 21.7%** (Phase 1.5 공식, 2026-04-20 업데이트)
- Phase 1 원본 25.2%에서 **-3.5%p 개선**
- 개선 근거: EC 심층 분석으로 착과기(수확 7주 전) EC가 수확량 결정 발견

## 버전 이력
- Phase 1 (v1.0): S&V 시차 1주 (착색기, SV_EC_LAG=7), WMAPE **25.2%**
- Phase 1.5 (v1.5): S&V 시차 7주 (착과기, SV_EC_LAG=1), WMAPE **21.7%** ⭐ 현재

---

## 디렉토리 구조

```
farm_ai_phase1/
├── config.py               # 전역 상수 (SV_EC_LAG=1, PROJECT_VERSION="1.5")
├── run_all.py              # 전체 파이프라인 단일 실행
├── requirements.txt
├── PHASE_1.5_UPDATE.md     # Phase 1 → 1.5 변경 상세 리포트
│
├── data/
│   ├── prepare_data.py     # 원본 CSV → 정제 CSV 변환
│   ├── priva_clean.csv     # 5분 간격 내부 환경 (PRIVA)
│   ├── irrigation_main.csv # 일별 급액 EC + 수확량
│   └── weekly_combined.csv # 주간 생육 조사 (엽수·엽장·엽폭)
│
├── models/
│   ├── lai.py              # LAI 추정 (Heuvelink 형태계수)
│   ├── tomgro_physics.py   # Acock 광합성 + 호흡 + DM 분배
│   ├── tomgro_week.py      # 주간 TOMGRO 시뮬레이션
│   └── sonneveld_voogt.py  # S&V EC 스트레스 상대수율
│
├── pipeline/
│   ├── step1_process_light.py   # 외부광 → 내부광 (×0.50)
│   ├── step2_aggregate.py       # 5분 → 시간 → 주간 집계
│   ├── step3_compute_lai.py     # 주간 LAI 계산
│   ├── step4_tomgro_run.py      # 전 작기 TOMGRO 시뮬레이션
│   ├── step5_sv_with_lag.py     # S&V EC 스트레스 적용 (착과기, 수확 7주 전)
│   ├── step6_xgboost_cv.py      # 5-fold CV 선형회귀
│   └── step7_validate.py        # 검증 리포트 + Scene 분석
│
├── utils/
│   ├── data_loader.py      # CSV 로더
│   └── time_aggregation.py # 리샘플링 헬퍼
│
├── viz/
│   ├── plot_weekly.py      # 주간 예측 vs 실측
│   ├── plot_mape_chain.py  # 3단계 오차율 체인
│   └── plot_monthly.py     # 월별 오차율
│
├── tests/
│   └── test_end_to_end.py  # 단위 + 통합 테스트 (7개, Phase 1.5 기준)
│
├── outputs/                # Phase 1.5 기준 최신 결과
│   ├── validation_report.txt
│   ├── scene_analysis.csv
│   ├── weekly_predictions.csv
│   ├── plot_weekly.png
│   ├── plot_mape_chain.png
│   └── plot_monthly.png
│
└── outputs_phase1_v1/      # Phase 1 원본 백업 (SV_EC_LAG=7, WMAPE 25.2%)
    └── ...
```

---

## 핵심 파라미터

| 파라미터 | 값 | 근거 |
|---|---|---|
| `LEAF_SHAPE_FACTOR` | 0.5 | 박현도 재배사 실측 (Heuvelink 1995: 0.7) |
| `LIGHT_TRANSMISSION` | 0.50 | 유리온실 50% 투과율 실측 |
| `SV_EC_LAG` | **1** | 착과기 기준: TOMGRO 주차 A, S&V EC = A+1주 = 수확 7주 전 |
| `TOMGRO_HARVEST_LAG` | 8주 | 수정~수확 약 8주 (박현도 피드백) |
| `PLANTING_DENSITY` | 2.78 주/m² | 본 농장 실측 |
| `FRUIT_DM_CONTENT` | 0.07 | 방울토마토 건물 함량 7% |
| TOMGRO `EPSILON` | 0.08 | 캐노피 레벨 보정 (Jones 1991: 0.04) |
| TOMGRO `P_MAX` | 40.0 g CH₂O/m²/h | 캐노피 레벨 보정 (Jones 1991: 20.0) |

> SV_EC_LAG 의미: 코드 내부 변수 (TOMGRO week_end 이후 몇 주).
> SV_EC_LAG=1 → ec_target = week_end+1주 = 수확 7주 전 (HARVEST_LAG 8 - SV_EC_LAG 1 = 7)

---

## 오차율 (WMAPE) — Phase 1.5 기준

| 단계 | Phase 1 WMAPE | Phase 1.5 WMAPE | 변화 |
|---|---|---|---|
| TOMGRO 단독 | 25.6% | 25.6% | — |
| + S&V EC 보정 | 35.5% | 34.1% | -1.4%p |
| + 5-fold CV | 25.2% | **21.7%** | **-3.5%p** |

> WMAPE = sigma-abs(예측-실측) / sigma(실측) × 100 (소수 주차 이상치 영향 완화)

---

## 검증값 (Scene 분석)

| Scene | 날짜 | TOMGRO | Phase 1 최종 | Phase 1.5 최종 | 실측 | Phase 1.5 오차 |
|---|---|---|---|---|---|---|
| Scene 1 | 2025-11-12 | 0.400 | 0.314 | **0.378** | 0.393 | **3.9%** |
| Scene 2 | 2025-08-13 | 0.103 | 0.253 | **0.233** | 0.103 | 125.7% |
| Scene 3 | 2026-01-07 | 0.394 | 0.343 | **0.388** | 0.377 | **2.8%** |

Scene 2 오차가 큰 이유: 초기 생육기(8월) 이식 전 수확량 포함으로 TOMGRO 예측 불가 (구조적 한계).

---

## 실행 방법

```bash
# 1. 환경 설정
pip install -r requirements.txt

# 2. 원본 데이터 정제 (최초 1회)
python data/prepare_data.py

# 3. 전체 파이프라인 실행
python run_all.py

# 4. 단위 테스트
pytest tests/ -v
```

---

## Phase 2 예정

`PHASE2_ROADMAP.md` 참조.

Phase 1.5 이후 우선순위:
1. **FarmWork 착과 기록** 확보 (착과 시점 EC 정확 추적)
2. S&V 브릭스 예측 (수확 직전 EC → 당도 예측)
3. PAR 센서 캐노피 위 설치 (2순위로 하향 조정)
4. 2월 말기 별도 처리 로직 개발

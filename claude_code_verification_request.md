# Claude Code 지시문 — Phase 1 검증 결과 공유 패키지 생성

## 📋 작업 목적

완성된 `farm_ai_phase1/` 패키지의 **검증 결과** 를 외부 공유 가능한 형태로 정리
전체 코드를 다시 실행할 필요 없고, 기존 실행 결과를 **구조화된 리포트 파일** 로 출력하면 됨

## 🎯 최종 결과물

단일 폴더 `verification_share/` 를 생성하고 그 안에 다음 파일들 포함:

```
verification_share/
├── 01_validation_report.md       # 모든 수치 검증 리포트 (마크다운)
├── 02_folder_structure.txt       # 프로젝트 폴더 트리
├── 03_test_results.txt           # pytest 출력 전문
├── 04_scene_analysis.md          # Scene 1/2/3 상세 비교표
├── 05_monthly_breakdown.md       # 월별 오차율 상세
├── 06_metric_comparison.md       # WMAPE vs MAPE 비교 분석
├── 07_code_snapshots/             # 핵심 코드 스냅샷 (읽기 전용)
│   ├── lai.py
│   ├── tomgro_week.py
│   ├── sonneveld_voogt.py
│   └── step6_xgboost_cv.py
├── images/
│   ├── weekly_comparison.png
│   ├── mape_chain.png
│   └── monthly_mape.png
└── README.md                      # 이 패키지 설명
```

---

## 📝 각 파일 상세 요구사항

### 01_validation_report.md

다음 형식의 마크다운 파일 작성:

```markdown
# Phase 1 계산 검증 리포트
생성일: [YYYY-MM-DD HH:MM]
커밋 해시: [git rev-parse HEAD 결과 또는 "N/A"]

## 1. 핵심 지표 요약

| 지표 | 값 | 비고 |
|---|---|---|
| WMAPE (공식) | 25.2% | Σ|err|/Σactual |
| MAPE (표준) | 35.0% | mean(|err|/actual) |
| 검증 주차 | 29주 | (또는 실제 값) |
| 총 실측 수확량 | 11.4 kg/m² | 전 작기 누적 |

## 2. 단계별 오차율 (WMAPE / MAPE 병기)

| 단계 | WMAPE | MAPE | 비고 |
|---|---|---|---|
| TOMGRO 단독 | [값]% | [값]% | 물리 모델 |
| + S&V (시차 7주) | [값]% | [값]% | EC 스트레스 |
| + XGBoost CV | 25.2% | 35.0% | 5-fold 선형 |

## 3. 파라미터 검증

| 파라미터 | 기대값 | 실제 사용값 | 상태 |
|---|---|---|---|
| LEAF_SHAPE_FACTOR | 0.5 | [코드에서 읽은 값] | ✓/✗ |
| PLANTING_DENSITY | 2.78 | [값] | ✓/✗ |
| LIGHT_TRANSMISSION | 0.50 | [값] | ✓/✗ |
| FRUIT_DM_CONTENT | 0.07 | [값] | ✓/✗ |
| EC_THRESHOLD | 2.5 | [값] | ✓/✗ |
| YIELD_SLOPE | 0.09 | [값] | ✓/✗ |
| TOMGRO_HARVEST_LAG | 8주 | [값] | ✓/✗ |
| SV_EC_LAG_BEFORE_HARVEST | 1주 (시차 7) | [값] | ✓/✗ |

## 4. 핵심 수치 스팟 체크

### Scene 1 (2025-11-12)
- 기대: TOMGRO 0.402 kg/m², LAI 3.027, S&V EC 7.69, yield 0.533
- 실측: [실행 결과값]
- 상태: ✓/✗

### 전 작기 통계
- 기대: WMAPE 25.2% (±1%)
- 실측: [값]
- 상태: ✓/✗

## 5. 발견 사항 / 이슈

[Claude Code 가 구현 중 발견한 사항을 자유 형식으로 기술]

예:
- 스펙이 WMAPE 를 사용하고 있었음 → MAPE 기준으로는 35.0%
- (있다면) 기존 코드와 차이점
- (있다면) 파라미터 튜닝으로 발견한 민감도
```

---

### 02_folder_structure.txt

```bash
# tree 명령 실행 결과 (최대 depth 3)
tree farm_ai_phase1/ -L 3 --charset ascii
```

설치 안되어 있으면 Python 으로:
```python
import os
def show_tree(path, prefix="", max_depth=3, current_depth=0):
    if current_depth >= max_depth: return
    items = sorted(os.listdir(path))
    for i, item in enumerate(items):
        if item.startswith('.') or item == '__pycache__': continue
        full_path = os.path.join(path, item)
        is_last = (i == len(items) - 1)
        print(f"{prefix}{'└── ' if is_last else '├── '}{item}")
        if os.path.isdir(full_path):
            show_tree(full_path, prefix + ('    ' if is_last else '│   '), max_depth, current_depth + 1)
```

---

### 03_test_results.txt

```bash
# pytest 상세 출력 전문
cd farm_ai_phase1 && pytest tests/ -v --tb=long > 03_test_results.txt 2>&1
```

다음 내용 포함 확인:
- 각 테스트 케이스 PASS/FAIL
- 실패 시 full traceback
- 총 소요 시간

---

### 04_scene_analysis.md

```markdown
# Scene 1/2/3 상세 분석

## Scene 1 (2025-11-12) — 저온기 한겨울

### 예측 흐름
- 내부 DLI (주간 누적): [값] mol/m²/week
- 주간 총광합성: [값] g CH₂O/m²
- 순 건물 생산: [값] g DM/m²
- 과실 건물 배분: [값] g DM/m² (비율 [%])
- TOMGRO 예측 FW: [값] kg/m²

### S&V 적용
- 수확 주차 (+ 8주): 2026-01-07
- S&V 기준 주차 (+ 7주, 수확 1주 전): 2025-12-31
- 슬라브 EC: [값] dS/m
- Relative yield: [값]
- TOMGRO × S&V: [값] kg/m²

### XGBoost 보정 (5-fold CV)
- 입력 피처: tomgro_sv, DLI, LAI = [값, 값, 값]
- CV 예측: [값] kg/m²

### 실측 vs 예측
- 실측 수확량 (2026-01-07): [값] kg/m²
- 최종 예측: [값] kg/m²
- 절대 오차: [값] kg/m²
- 오차율: [값]%

## Scene 2 (2025-08-13) — 고온기 초가을
[동일 구조]

## Scene 3 (2026-01-07) — 저온기 초봄
[동일 구조]

## 3개 Scene 비교표

| 지표 | Scene 1 | Scene 2 | Scene 3 |
|---|---|---|---|
| 기간 | 2025-11-12 | 2025-08-13 | 2026-01-07 |
| LAI | | | |
| DLI (mol/week) | | | |
| TOMGRO 예측 (kg) | | | |
| S&V yield | | | |
| 최종 예측 (kg) | | | |
| 실측 (kg) | | | |
| 오차율 (%) | | | |
```

---

### 05_monthly_breakdown.md

```markdown
# 월별 오차율 분석

## 전 작기 주차별 원본 데이터

| 주차 (week_end) | TOMGRO | +S&V | +XGBoost | 실측 | 오차율 |
|---|---|---|---|---|---|
| 2025-07-XX | | | | | |
| ... (전체 주차 나열) | | | | | |
| 2026-02-XX | | | | | |

## 월별 평균 (WMAPE)

| 월 | 유효 주차 수 | TOMGRO | +S&V | +XGBoost |
|---|---|---|---|---|
| 2025-07 | | | | |
| 2025-08 | | | | |
| ... | | | | |

## 시즌별 특성 분석

- **가을 (9~10월)**: [WMAPE 값]% — 안정 구간
- **초겨울 (11월)**: [WMAPE 값]% — 최저 구간
- **한겨울 (12~1월)**: [WMAPE 값]%
- **말기 (2월)**: [WMAPE 값]% — 최고 구간
```

---

### 06_metric_comparison.md

**중요** — WMAPE 와 MAPE 차이를 명확히 설명:

```markdown
# 평가 지표 비교 — WMAPE vs MAPE

## 수식 정의

### WMAPE (Weighted Mean Absolute Percentage Error)
```
WMAPE = Σ|예측 - 실측| / Σ실측 × 100
      = 총 절대오차 / 총 실측 × 100
```

특징:
- 큰 수확량 주차가 더 큰 가중치
- 비즈니스 관점: 총 kg 단위 기준
- 초기 생육기 소수확 이상치의 영향 완화

### MAPE (Mean Absolute Percentage Error)
```
MAPE = mean(|예측 - 실측| / 실측) × 100
     = 주차별 오차율의 단순 평균
```

특징:
- 모든 주차 동일 가중치
- 학계·산업 표준
- 소수확 주차의 큰 오차율이 과대 반영 가능

## 본 프로젝트 비교

| 단계 | WMAPE | MAPE | 차이 |
|---|---|---|---|
| TOMGRO 단독 | [값]% | [값]% | [값]%p |
| + S&V | [값]% | [값]% | [값]%p |
| + XGBoost | 25.2% | 35.0% | 9.8%p |

## 차이가 크게 나는 이유

1. **초기 생육기 소수확**
   - 7~8월 실측 0.05~0.1 kg/m² 수준
   - 예측 오차가 절대값으로 작아도 비율로는 큼 (60~80%)
   - MAPE 에서 이 주차들이 평균을 크게 끌어올림

2. **총 수확량 집중 시기**
   - 11~1월 실측 0.35~0.5 kg/m² 로 수확량 대부분 집중
   - 이 시기 오차율이 5~20% 수준으로 낮음
   - WMAPE 에서 이 시기 가중치가 높음

## 구체적 예시

주차 A (7월): 실측 0.05, 예측 0.08 → 절대오차 0.03, 오차율 60%
주차 B (11월): 실측 0.40, 예측 0.42 → 절대오차 0.02, 오차율 5%

- MAPE = (60 + 5) / 2 = **32.5%**
- WMAPE = (0.03 + 0.02) / (0.05 + 0.40) = 0.05 / 0.45 = **11.1%**

## 평가 지표 선택 근거

본 프로젝트는 **WMAPE 를 공식 지표로 채택**:
1. 비즈니스 의사결정 기준 (총 출하량 kg)
2. 농가 경제성 관점 (수확 비중 큰 시기가 중요)
3. Demand forecasting 업계에서 권장 (Hyndman & Athanasopoulos 2018)

단, 학술적 투명성을 위해 MAPE 도 병기.
```

---

### 07_code_snapshots/ — 핵심 코드 파일 복사

다음 파일들을 `cp` 또는 Python shutil 로 **읽기 전용** 복사:

```python
import shutil
files_to_copy = [
    'farm_ai_phase1/models/lai.py',
    'farm_ai_phase1/models/tomgro_week.py',
    'farm_ai_phase1/models/sonneveld_voogt.py',
    'farm_ai_phase1/pipeline/step6_xgboost_cv.py',
    'farm_ai_phase1/pipeline/step7_validate.py',  # 있으면
]
for f in files_to_copy:
    dest = os.path.join('verification_share/07_code_snapshots/', os.path.basename(f))
    if os.path.exists(f):
        shutil.copy(f, dest)
```

**이 파일들은 수정하지 말고 그대로 복사**. 리뷰어가 실제 실행 코드를 볼 수 있어야 함.

---

### images/

기존에 생성된 `viz/*.png` 를 복사:
```bash
cp farm_ai_phase1/viz/weekly_comparison.png verification_share/images/
cp farm_ai_phase1/viz/mape_chain.png verification_share/images/
cp farm_ai_phase1/viz/monthly_mape.png verification_share/images/
```

없으면 `viz/` 스크립트를 재실행:
```bash
cd farm_ai_phase1 && python viz/plot_weekly.py
```

---

### README.md (verification_share 루트)

```markdown
# Phase 1 검증 결과 공유 패키지

생성일: [YYYY-MM-DD]
프로젝트: GREF Farm LAB 방울토마토 재배 AI
대상 기간: 2025-07-09 ~ 2026-04-08 (40주 1작기)

## 핵심 결과
- **WMAPE 25.2%** (Phase 1 공식 지표)
- MAPE 35.0% (표준 지표, 참고용)
- 검증 주차: 29주
- 모든 단위 테스트 통과 ✓

## 파일 안내
| 파일 | 내용 |
|---|---|
| 01_validation_report.md | 핵심 지표 요약 + 파라미터 검증 |
| 02_folder_structure.txt | 프로젝트 폴더 구조 |
| 03_test_results.txt | pytest 결과 전문 |
| 04_scene_analysis.md | Scene 1/2/3 상세 비교 |
| 05_monthly_breakdown.md | 월별 오차율 분석 |
| 06_metric_comparison.md | WMAPE vs MAPE 비교 |
| 07_code_snapshots/ | 핵심 모델 코드 (읽기 전용) |
| images/ | 주차별·체인·월별 그래프 |

## 리뷰 포인트
1. SHAPE 0.5 (일반 0.7 → 본 농장 실측 기반 조정) 근거 확인
2. 투과율 50% 설정 근거 (Phase 2 PAR 센서 실측 예정)
3. S&V 시차 7주 (수확 1주 전 EC) — 재배사 피드백 반영
4. WMAPE 선택 근거

## 본 패키지 범위 밖
- 원본 데이터 CSV (용량·민감정보, 별도 제공)
- Phase 2 구현 예정 항목 (PHASE2_ROADMAP.md 별도 문서)
```

---

## 🚀 실행 명령어

Claude Code 에게 다음 한 줄로 요청:

```bash
# verification_share/ 폴더 생성 + 모든 리포트 파일 자동 생성
python generate_verification_share.py
```

이런 통합 스크립트 `generate_verification_share.py` 도 함께 생성 요청.

내용:
```python
"""
검증 결과 공유 패키지 생성 스크립트
1. farm_ai_phase1/ 의 계산 결과를 읽어옴
2. verification_share/ 폴더에 모든 리포트 파일 출력
"""
import os
import shutil
import subprocess
from datetime import datetime

# 1. 폴더 구조 생성
os.makedirs('verification_share/07_code_snapshots', exist_ok=True)
os.makedirs('verification_share/images', exist_ok=True)

# 2. 계산 결과 로드 (outputs/weekly_predictions.csv 등)
# 3. 각 .md 파일 생성
# 4. 테스트 결과 생성
# 5. 이미지 복사
# 6. 코드 스냅샷 복사

# (자세한 구현은 위 각 섹션 참조)
```

---

## ⚠️ 주의 사항

1. **실제 값 채우기**: `[값]`, `[값]%` 등으로 표시된 모든 플레이스홀더를 **실행 결과** 로 채울 것
2. **숫자 정확도**: 소수점 3자리까지 표시 (예: `0.402 kg/m²`)
3. **파일 경로**: 모든 경로는 `farm_ai_phase1/` 기준 상대 경로
4. **이미지 포맷**: PNG, 해상도 130 dpi 이상
5. **한글 파일명**: 사용 가능 (UTF-8 인코딩)

---

## ✅ 완료 기준

1. `verification_share/` 폴더 생성 완료
2. 8개 .md 파일 모두 실제 숫자로 채워짐
3. `02_folder_structure.txt` 에 전체 폴더 구조 기재
4. `03_test_results.txt` 에 pytest 결과 전문 포함
5. `07_code_snapshots/` 에 핵심 4~5개 .py 파일 복사
6. `images/` 에 3개 PNG 파일 포함
7. 전체 폴더를 ZIP 으로 압축 가능 (외부 공유용)

---

## 📦 최종 전달 형식

완료 후 `verification_share/` 폴더를 ZIP 으로 압축해서 전달:
```bash
cd verification_share
zip -r ../phase1_verification_$(date +%Y%m%d).zip .
```

결과물: `phase1_verification_20260420.zip` (또는 오늘 날짜)

이 ZIP 파일 하나로 외부 AI 전문가가 전체 검증 가능한 상태 도달.

---

## 💡 추가 요청 (선택)

Claude Code 가 추가로 발견한 이슈·개선점이 있으면 `verification_share/FINDINGS.md` 파일로 
별도 정리해주세요. 예:
- 파라미터 민감도 분석 결과
- 재현 불가능했던 부분
- 테스트 커버리지 개선 제안
- Phase 2 에서 우선 고려해야 할 기술 부채

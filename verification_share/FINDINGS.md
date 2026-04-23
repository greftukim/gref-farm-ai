# 발견 사항 및 개선 제안

생성일: 2026-04-20 17:33

## 파라미터 민감도

### LEAF_SHAPE_FACTOR (현재: 0.5)
- Heuvelink(1995) 권장 0.7 대비 현저히 낮음
- 변경 시: LAI가 40% 증가 → 광합성량 증가 → TOMGRO 예측 상향
- Phase 2: 실측 엽면적 측정으로 재교정 필요

### LIGHT_TRANSMISSION (현재: 0.50)
- 센서 위치 보정 추정값. 0.45~0.55 범위에서 WMAPE 민감
- Phase 2 PAR 센서(캐노피 위) 설치 후 실측값으로 교체 권장

## 재현 불가능했던 부분
- 없음. 모든 단계 deterministic (CV fold 시드 고정)

## 테스트 커버리지 개선 제안
- 현재: end-to-end 통합 테스트 위주
- 권장 추가: 단위 테스트 (tomgro_physics, sonneveld_voogt 수식 수준)
- 권장 추가: WMAPE 계산 단위 테스트 (edge case: actual=0 방어)

## Phase 2 기술 부채 (우선순위)
1. **XGBoost 교체**: 데이터 2작기 이상 누적 후 LinearRegression → XGBoost 교체
2. **PAR 센서 실측**: LIGHT_TRANSMISSION 0.50 추정값 검증
3. **엽면적 직접 측정**: LEAF_SHAPE_FACTOR 0.5 검증 (현재 역산값)
4. **작기 말기(2월) 보정**: WMAPE 60.7% 로 최고 구간 — 노화 모델 추가 검토

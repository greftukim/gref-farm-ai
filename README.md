# 방울토마토 재배 AI — 결과 보고 사이트

대규모 스마트팜 운영을 위한 방울토마토 수확량 예측 AI 시스템의 Phase 1.5 검증 결과를 공유하는 웹사이트입니다.

## 🌐 공개 사이트 보기

**👉 [https://greftukim.github.io/gref-farm-ai/](https://greftukim.github.io/gref-farm-ai/)**

## 🎯 Phase 1.5 핵심 성과

| 지표 | 값 |
|---|---|
| 통합 오차율 WMAPE | **21.7%** |
| 저온기 월별 최저 오차율 | 7.6% (11월) |
| DeePC 밴드 준수율 | 100% |
| 검증 주차 | 29주 (1작기) |

## 🔬 기술 구성

물리 모델 + 머신러닝 + 제어 처방의 하이브리드 구조:

- **TOMGRO** — 광합성·건물 배분 물리 모델
- **Sonneveld & Voogt** — EC 스트레스 경험식
- **XGBoost** — 잔차 보정 머신러닝
- **DeePC** — 데이터 기반 예측 제어

## 📑 사이트 내비게이션

- 개요: 핵심 지표·시스템 아키텍처·작기 정보
- 모델: TOMGRO · S&V · XGBoost · DeePC 개별 상세
- 통합 검증: 4단계 체인 성능 분석
- 부록: 농작업 연계·FarmWork 시스템
- 로드맵: Phase 1.5 → Phase 2·3 계획

## 📚 기반 문헌

- Heuvelink, E. (1995) PhD Thesis, WUR
- De Koning, A.N.M. (1994) PhD Thesis, WUR
- Sonneveld & Voogt (2009) Plant Nutrition of Greenhouse Crops, Springer
- FAO Irrigation and Drainage Paper No. 61 (2002)
- Chen & Guestrin (2016) XGBoost

## 📅 업데이트 이력

- 2026-04-20: Phase 1.5 반영 (WMAPE 21.7%)
- 2026-04-10: Phase 1 최초 버전 (WMAPE 25.2%)

---

© GREF Farm LAB 운영전략 · 2026

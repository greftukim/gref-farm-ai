# Phase 1 EC 스트레스 심층 분석 패키지
생성일: 2026-04-20

## 핵심 판정 결과
- **채택 시나리오: B** — S&V 시차 재조정으로 개선 가능
- 가설 A (EC->LAI): 기각 (r=-0.253)
- 가설 B (시차 재조정): 성립 (최적=7주, final=21.5%)
- 투과율 민감도: SENSITIVE_LOW (최적=0.30)
- 민감도 9개 조합: ROBUST

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

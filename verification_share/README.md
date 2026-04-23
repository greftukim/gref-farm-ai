# Phase 1 검증 결과 공유 패키지

생성일: 2026-04-20
프로젝트: GREF Farm LAB 방울토마토 재배 AI
대상 기간: 2025-07-09 ~ 2026-04-08 (작기 전체)

## 핵심 결과
- **WMAPE 25.2%** (Phase 1 공식 지표)
- MAPE 35.0% (표준 지표, 참고용)
- 검증 주차: 29주
- 총 실측 수확량: 10.23 kg/m²
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
1. LEAF_SHAPE_FACTOR 0.5 (일반 0.7 → 본 농장 실측 기반 조정) 근거 확인
2. 투과율 50% 설정 근거 (Phase 2 PAR 센서 실측 예정)
3. S&V 시차 7주 (수확 1주 전 EC) — 재배사 피드백 반영
4. WMAPE 선택 근거 (06_metric_comparison.md 참조)

## 본 패키지 범위 밖
- 원본 데이터 CSV (용량·민감정보, 별도 제공)
- Phase 2 구현 예정 항목 (PHASE2_ROADMAP.md 별도 문서)

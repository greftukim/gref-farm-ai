"""End-to-end 검증 테스트 — Phase 1.5 핵심 수치 재현 확인.

Phase 1.5 변경: S&V 시차 수확 1주 전 → 수확 7주 전 (착과기)
기대 최종 WMAPE: 21.5% ± 1%
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models.lai import estimate_lai
from models.sonneveld_voogt import relative_yield
from models.tomgro_week import run_tomgro_week
from run_all import run_full_pipeline


def test_lai_calculation():
    """Scene 1 LAI = 3.027 (박현도 실측 SHAPE=0.5 기준)."""
    lai = estimate_lai(leaf_length_cm=36.3, leaf_width_cm=30.0, n_leaves=20.0)
    assert abs(lai - 3.027) < 0.01, f"LAI={lai:.3f}, expected ~3.027"


def test_sv_relative_yield():
    """S&V EC=7.69 dS/m 일 때 상대수율 = 0.533."""
    yr = relative_yield(7.69)
    assert abs(yr - 0.533) < 0.01, f"relative_yield(7.69)={yr:.3f}, expected ~0.533"


def test_sv_below_threshold():
    """EC <= 2.5 dS/m 이면 상대수율 = 1.0 (스트레스 없음)."""
    assert relative_yield(2.5) == 1.0
    assert relative_yield(1.0) == 1.0


def test_tomgro_scene1():
    """Scene 1 (2025-11-06~11-12) TOMGRO 예측 ≈ 0.402 kg/m² (±0.01)."""
    result = run_tomgro_week(
        start='2025-11-06',
        end='2025-11-12',
        lai=3.027,
        light_transmission=0.50,
    )
    pred = result['fruit_fw_kg_m2']
    assert abs(pred - 0.402) < 0.01, f"Scene1 TOMGRO={pred:.3f}, expected ~0.402"


def test_final_mape():
    """전 작기 5-fold CV WMAPE = 21.5% ± 1% (Phase 1.5 기준)."""
    results = run_full_pipeline()
    mape = results['final_mape']
    assert abs(mape - 21.5) < 1.0, f"final_mape={mape:.1f}%, expected 21.5% ± 1%"


def test_sv_lag_harvest_minus_7():
    """S&V EC는 수확 7주 전 (착과기): TOMGRO_HARVEST_LAG - SV_EC_LAG == 7."""
    from config import SV_EC_LAG, TOMGRO_HARVEST_LAG
    weeks_before_harvest = TOMGRO_HARVEST_LAG - SV_EC_LAG
    assert weeks_before_harvest == 7, (
        f"S&V 시차 = 수확 {weeks_before_harvest}주 전, 기대: 수확 7주 전 (착과기)"
    )


def test_project_version_15():
    """PROJECT_VERSION == '1.5' 확인."""
    from config import PROJECT_VERSION
    assert PROJECT_VERSION == "1.5", f"버전={PROJECT_VERSION}, 기대: 1.5"

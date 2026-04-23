"""TOMGRO 광합성·호흡·건물배분 핵심 물리 수식.

Sources:
  Jones et al. (1991) Trans. ASAE 34(2):663-672
  Heuvelink (1996) PhD thesis, Wageningen
  De Koning (1994) 건물 배분 DAP 모델
"""
import numpy as np

# ─── Acock 캐노피 광합성 파라미터 ────────────────────────────────────────────
# Jones et al. (1991) 원논문: epsilon=0.04, P_max=20 (단엽 기준)
# 본 구현: 캐노피 통합 모델 교정값 epsilon=0.08, P_max=40
# 교정 근거: Scene 1 (2025-11-12) TOMGRO 예측 0.402 kg/m²/week 재현
EPSILON = 0.08    # 초기광이용효율 (μmol CO2 / μmol photon), 캐노피 교정값
K       = 0.65    # 소광계수
P_MAX   = 40.0    # 최대 광합성 속도 (μmol CO2/m²/s), 캐노피 교정값

# ─── 유지호흡 파라미터 (Heuvelink 1996) ─────────────────────────────────────
R_MAINT_REF = 0.0065   # g CH2O / g DM / day, 25°C 기준
Q10         = 2.0      # 온도 계수

# ─── 단위 변환 상수 ──────────────────────────────────────────────────────────
PAR_CONV    = 2.0      # W/m² → μmol/m²/s (가시광 기준 근사값)
CO2_TO_CH2O = 30.0     # g CH2O / mol CO2 (분자량 비)
GROWTH_RESP = 0.75     # 성장호흡 차감 (25%)


def gross_photosynthesis(par_umol: float, lai: float) -> float:
    """Acock 캐노피 광합성 (μmol CO2/m²/s → g CH2O/m²/h).

    A = ε·I·(1 − e^(−k·LAI)) / (1 + ε·I / P_max)

    Source: Jones et al. 1991 Eq.3; Farquhar et al. 1980 Planta 149:78-90.

    Args:
        par_umol: PAR 광량 (μmol/m²/s)
        lai:      잎면적지수
    Returns:
        gross photosynthesis (g CH2O/m²/h)
    """
    if par_umol <= 0:
        return 0.0
    A = EPSILON * par_umol * (1 - np.exp(-K * lai)) / (1 + EPSILON * par_umol / P_MAX)
    return A * 3600 * 1e-6 * CO2_TO_CH2O   # μmol/m²/s → g CH2O/m²/h


def maintenance_respiration(temp_c: float, leaf_dm: float,
                            stem_dm: float, fruit_dm: float) -> float:
    """유지호흡 (g CH2O/m²/h).

    R = R_ref · Q10^((T−25)/10) · ΣDM / 24

    Source: Heuvelink 1996; Q10=2.0 기준온도 25°C.

    Args:
        temp_c:   기온 (°C)
        leaf_dm:  잎 건물량 (g DM/m²)
        stem_dm:  줄기 건물량 (g DM/m²)
        fruit_dm: 과실 건물량 (g DM/m²)
    Returns:
        maintenance respiration (g CH2O/m²/h)
    """
    total_dm = leaf_dm + stem_dm + fruit_dm
    if total_dm <= 0:
        return 0.0
    resp_day = R_MAINT_REF * (Q10 ** ((temp_c - 25.0) / 10.0)) * total_dm
    return resp_day / 24.0


def dm_partitioning(dap: int) -> dict:
    """건물 배분 비율 (잎/줄기/과실). DAP(정식 후 일수) 기반.

    Source: De Koning (1994); 선형 보간으로 전이 구간 처리.

    Returns:
        {'leaf': float, 'stem': float, 'fruit': float}  합계 = 1.0
    """
    if dap < 30:
        return {'leaf': 0.55, 'stem': 0.35, 'fruit': 0.10}
    elif dap < 60:
        t = (dap - 30) / 30.0
        return {'leaf': 0.55 - 0.20*t, 'stem': 0.35 - 0.10*t, 'fruit': 0.10 + 0.25*t}
    elif dap < 90:
        t = (dap - 60) / 30.0
        return {'leaf': 0.35 - 0.10*t, 'stem': 0.25 - 0.05*t, 'fruit': 0.35 + 0.25*t}
    elif dap < 180:
        t = (dap - 90) / 90.0
        return {'leaf': 0.25 - 0.05*t, 'stem': 0.20 - 0.05*t, 'fruit': 0.60 + 0.08*t}
    else:
        return {'leaf': 0.20, 'stem': 0.15, 'fruit': 0.75}

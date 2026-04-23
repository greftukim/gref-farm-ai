"""TOMGRO 주간 시뮬레이션.

5분 PRIVA 데이터 → 1시간 집계 → 광합성·호흡 계산 → 건물 배분 → FW 환산.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from models.tomgro_physics import (
    gross_photosynthesis, maintenance_respiration, dm_partitioning,
    PAR_CONV, GROWTH_RESP, CO2_TO_CH2O,
)
from config import LIGHT_TRANSMISSION, FRUIT_DM_CONTENT, PLANTING_DATE

_DATA_DIR = Path(__file__).parent.parent / 'data'


def run_tomgro_week(start: str, end: str, lai: float,
                    light_transmission: float = LIGHT_TRANSMISSION,
                    priva_csv: str = None) -> dict:
    """TOMGRO 주간 시뮬레이션.

    처리 순서:
      1. PRIVA 5분 데이터 슬라이싱
      2. 1시간 평균 집계
      3. 시간별 광합성·호흡 계산
      4. 일별 순 건물 생산 (성장호흡 25% 차감)
      5. DAP 기반 건물 배분 (잎/줄기/과실)
      6. 과실 건물 → FW 환산 (÷ 0.07)

    Args:
        start: 주 시작일 'YYYY-MM-DD'
        end:   주 종료일 'YYYY-MM-DD'
        lai:   해당 주 LAI
        light_transmission: 외부→내부 투과율 (기본 0.50)
        priva_csv: PRIVA 데이터 경로 (None이면 data/priva_clean.csv)
    Returns:
        dict: fruit_fw_kg_m2, fruit_dm_g_m2, net_dm_g_m2,
              gross_photo_g_m2, dli_internal (mol/m²/week)
    """
    csv_path = priva_csv or str(_DATA_DIR / 'priva_clean.csv')
    priva = pd.read_csv(csv_path, parse_dates=['datetime']).set_index('datetime')

    mask = (priva.index >= start) & (priva.index <= end + ' 23:59:59')
    week_data = priva[mask]

    hourly = week_data.resample('1h').mean()

    planting = pd.Timestamp(PLANTING_DATE)
    dap_mid  = int((pd.Timestamp(end) - planting).days)

    partition    = dm_partitioning(dap_mid)
    leaf_dm = stem_dm = fruit_dm = 0.0
    total_gross = 0.0
    dli         = 0.0   # mol/m²

    for ts, row in hourly.iterrows():
        rad_w = float(row.get('radiation', 0) or 0)
        rad_internal = rad_w * light_transmission
        par_umol     = rad_internal * PAR_CONV
        dli         += par_umol * 3600 * 1e-6

        temp = float(row.get('meas grh temp', 20) or 20)

        gross    = gross_photosynthesis(par_umol, lai)
        resp     = maintenance_respiration(temp, leaf_dm, stem_dm, fruit_dm)
        net_h    = max(gross - resp, 0.0)

        # μmol CO2/m²/s → g CH2O/m²/h: already done in gross_photosynthesis
        # g CH2O → g DM: × 0.75(성장호흡) × 30/44(탄소환산)
        dm_h = net_h * GROWTH_RESP * (30.0 / 44.0)
        total_gross += gross

        leaf_dm  += dm_h * partition['leaf']
        stem_dm  += dm_h * partition['stem']
        fruit_dm += dm_h * partition['fruit']

    net_dm   = leaf_dm + stem_dm + fruit_dm
    fruit_fw = fruit_dm / FRUIT_DM_CONTENT / 1000.0   # g DM → kg FW/m²

    return {
        'fruit_fw_kg_m2':   round(fruit_fw, 3),
        'fruit_dm_g_m2':    round(fruit_dm, 2),
        'net_dm_g_m2':      round(net_dm, 2),
        'gross_photo_g_m2': round(total_gross, 2),
        'dli_internal':     round(dli, 2),
        'leaf_dm_g_m2':     round(leaf_dm, 2),
        'stem_dm_g_m2':     round(stem_dm, 2),
    }

"""LAI (잎면적지수) 계산 모델.

수식: LAI = L × W × SHAPE × N × ρ
  L, W : 엽장·엽폭 (m)
  SHAPE: 0.5  — 박현도 재배사 실측 (토마지노 방울토마토)
         (Heuvelink 1995 권장값 0.7과 다름 — 본 농장 교정값)
  N    : 줄기당 엽수 (매)
  ρ    : 재식밀도 2.78 주/m²
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import LEAF_SHAPE_FACTOR, PLANTING_DENSITY


def estimate_lai(leaf_length_cm: float, leaf_width_cm: float,
                 n_leaves: float) -> float:
    """엽장·엽폭·엽수 → LAI.

    Source: Heuvelink (1995) Scientia Horticulturae 61:77-99.
    SHAPE 0.5 적용: 본 농장 박현도 재배사 실측 (Heuvelink 권장 0.7 아님).

    Args:
        leaf_length_cm: 엽장 (cm)
        leaf_width_cm:  엽폭 (cm)
        n_leaves:       줄기당 엽수 (매)
    Returns:
        LAI (m²_leaf / m²_ground)
    """
    L = leaf_length_cm / 100.0
    W = leaf_width_cm / 100.0
    leaf_area = L * W * LEAF_SHAPE_FACTOR
    return leaf_area * n_leaves * PLANTING_DENSITY

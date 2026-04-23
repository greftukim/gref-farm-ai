"""Sonneveld & Voogt EC 스트레스 모델.

EC 스트레스에 의한 상대 수량 감소 계산.

Source:
  Sonneveld & Voogt (2009) Plant Nutrition of Greenhouse Crops.
  Springer, Chapter 6 "Salinity".
  FAO Irrigation and Drainage Paper No. 61 (2002).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import EC_THRESHOLD, YIELD_SLOPE


def relative_yield(slab_ec: float) -> float:
    """EC 스트레스에 의한 상대 수량 [0, 1].

    Yr = 1 − b·(ECe − ECt)   for ECe > ECt
    Yr = 1.0                  for ECe ≤ ECt

    ECt = 2.5 dS/m, b = 0.09 /dS·m (토마토, FAO 표준).
    본 농장: 고당도 재배 전략으로 EC를 의도적으로 높게 운영.

    Args:
        slab_ec: 슬라브 EC (dS/m)
    Returns:
        상대 수량 [0, 1]
    """
    if slab_ec <= EC_THRESHOLD:
        return 1.0
    return max(1.0 - YIELD_SLOPE * (slab_ec - EC_THRESHOLD), 0.0)

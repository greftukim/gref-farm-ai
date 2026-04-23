"""정제된 CSV 파일 로드 유틸리티."""
import pandas as pd
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / 'data'


def load_priva(path: str = None) -> pd.DataFrame:
    """PRIVA 5분 환경 데이터 로드.

    Returns:
        DatetimeIndex DataFrame — radiation(W/m²), meas grh temp(°C),
        meas CO2 conc(ppm) 포함.
    """
    p = Path(path) if path else _DATA_DIR / 'priva_clean.csv'
    df = pd.read_csv(p, parse_dates=['datetime'])
    return df.set_index('datetime').sort_index()


def load_irrigation(path: str = None) -> pd.DataFrame:
    """관수·수확 일별 데이터 로드.

    Returns:
        DatetimeIndex DataFrame — slab_ec(dS/m), actual_harvest(kg/m²/day).
    """
    p = Path(path) if path else _DATA_DIR / 'irrigation_main.csv'
    df = pd.read_csv(p, parse_dates=['date'])
    return df.set_index('date').sort_index()


def load_weekly(path: str = None) -> pd.DataFrame:
    """주간 생육 조사 데이터 로드.

    Returns:
        DataFrame — week_end, leaf_length_cm, leaf_width_cm, n_leaves.
    """
    p = Path(path) if path else _DATA_DIR / 'weekly_combined.csv'
    df = pd.read_csv(p, parse_dates=['week_end'])
    return df.sort_values('week_end').reset_index(drop=True)

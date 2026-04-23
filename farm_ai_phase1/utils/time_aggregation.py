"""시간 해상도 변환 유틸리티 (5분 → 시간 → 주간)."""
import pandas as pd


def aggregate_to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """5분 간격 데이터 → 1시간 평균."""
    return df.resample('1h').mean()


def aggregate_to_weekly(df: pd.DataFrame, agg_func: str = 'sum') -> pd.DataFrame:
    """일별 데이터 → 주간 집계 (월요일 기준 주 종료일 라벨).

    Args:
        agg_func: 'sum' | 'mean'
    """
    return df.resample('W-MON', closed='right', label='right').agg(agg_func)

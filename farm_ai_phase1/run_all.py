"""전체 파이프라인 단일 실행 스크립트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pathlib import Path
from pipeline import (step1_process_light, step2_aggregate, step3_compute_lai,
                      step4_tomgro_run, step5_sv_with_lag, step6_xgboost_cv,
                      step7_validate)


def run_full_pipeline() -> dict:
    """전체 파이프라인 실행 후 검증 결과 반환 (테스트용)."""
    base = Path(__file__).parent
    (base / 'processed').mkdir(exist_ok=True)
    (base / 'outputs').mkdir(exist_ok=True)
    step1_process_light.run()
    step2_aggregate.run()
    step3_compute_lai.run()
    step4_tomgro_run.run()
    step5_sv_with_lag.run()
    step6_xgboost_cv.run()
    return step7_validate.run()


if __name__ == '__main__':
    base = Path(__file__).parent
    (base / 'processed').mkdir(exist_ok=True)
    (base / 'outputs').mkdir(exist_ok=True)

    print("=" * 50)
    print("GREF Phase 1 -- 전체 파이프라인")
    print("=" * 50 + "\n")

    step1_process_light.run()
    step2_aggregate.run()
    step3_compute_lai.run()
    step4_tomgro_run.run()
    step5_sv_with_lag.run()
    _, mape = step6_xgboost_cv.run()
    results = step7_validate.run()

    print(f"\n{'='*50}")
    print(f"최종 MAPE: {results['final_mape']:.1f}%  (목표: 25.2% ± 1%)")
    print(f"{'='*50}")

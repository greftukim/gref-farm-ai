"""
3단계 모델 조합 다이어그램 재생성 (Phase 1.5 표기 제거).

출력: site_images/integration_chain_flow.png
모델 개별 설명은 이미지 내부에 넣지 않고 HTML 하단 카드로 처리.
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib as mpl
from matplotlib import font_manager

BASE = Path(__file__).parent.parent.parent
OUT  = BASE / 'site_images' / 'integration_chain_flow.png'


def _setup_korean_font():
    for fp in ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
               '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf'):
        if Path(fp).exists():
            font_manager.fontManager.addfont(fp)
    mpl.rcParams['font.family'] = 'NanumGothic'
    mpl.rcParams['axes.unicode_minus'] = False


# 블록 팔레트 (기존 톤 유지)
BLOCKS = [
    dict(name='TOMGRO',     sub='(광합성·건물)',      top_val='저온기 한겨울: 0.402 kg', pill='TOMGRO 단독\n오차 2.2%',  face='#6AA3D6', ptxt='#1F4E79', pface='#E8F2FB'),
    dict(name='+ S&V',      sub='(EC 수량 감소)',     top_val='저온기 한겨울: 0.293 kg', pill='S&V 단계\n오차 25.4%',    face='#E8B06A', ptxt='#7A4A12', pface='#FCEFD9'),
    dict(name='+ XGBoost',  sub='(ML 잔차 보정)',     top_val='저온기 한겨울: 0.378 kg', pill='풀체인\n오차 3.9%',       face='#D97575', ptxt='#7A1F1F', pface='#FBE5E5'),
    dict(name='실제 수확',   sub='(측정값)',           top_val='저온기 한겨울: 0.393 kg', pill='예측 오차\n기준',         face='#7DB670', ptxt='#2D5C20', pface='#E5F2E0'),
]


def main():
    _setup_korean_font()

    fig, ax = plt.subplots(figsize=(13, 6.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # 제목
    ax.text(50, 93, '방울토마토 수확량 예측 — 3단계 모델 조합',
            ha='center', va='center', fontsize=16, fontweight='bold', color='#222')

    # 블록 좌표
    box_w, box_h = 18, 26
    gap = 6
    total_w = 4 * box_w + 3 * gap
    left0 = (100 - total_w) / 2
    box_y = 42
    box_top = box_y + box_h   # 68

    for i, b in enumerate(BLOCKS):
        x = left0 + i * (box_w + gap)

        # 상단 값 라벨
        ax.text(x + box_w/2, box_top + 5, b['top_val'],
                ha='center', va='center', fontsize=10, color='#444')

        # 본 박스
        rect = mpatches.FancyBboxPatch((x, box_y), box_w, box_h,
                                       boxstyle='round,pad=0.02,rounding_size=1.5',
                                       linewidth=0, facecolor=b['face'], alpha=0.95)
        ax.add_patch(rect)
        ax.text(x + box_w/2, box_y + box_h*0.58, b['name'],
                ha='center', va='center', fontsize=15, fontweight='bold', color='white')
        ax.text(x + box_w/2, box_y + box_h*0.34, b['sub'],
                ha='center', va='center', fontsize=11, color='white')

        # 하단 pill
        pill_y = box_y - 11
        pill_w, pill_h = 14, 8
        pill_x = x + (box_w - pill_w)/2
        pill = mpatches.FancyBboxPatch((pill_x, pill_y), pill_w, pill_h,
                                       boxstyle='round,pad=0.02,rounding_size=1.5',
                                       linewidth=1.2, edgecolor=b['ptxt'],
                                       facecolor=b['pface'])
        ax.add_patch(pill)
        ax.text(pill_x + pill_w/2, pill_y + pill_h/2, b['pill'],
                ha='center', va='center', fontsize=10, color=b['ptxt'],
                fontweight='bold', linespacing=1.3)

        # 화살표 (마지막 제외)
        if i < len(BLOCKS) - 1:
            arr_x = x + box_w
            arr_y = box_y + box_h/2
            ax.annotate('', xy=(arr_x + gap - 0.5, arr_y), xytext=(arr_x + 0.5, arr_y),
                        arrowprops=dict(arrowstyle='->', lw=1.8, color='#666'))

    # 중간 서술
    ax.text(50, 24, '물리 모델(TOMGRO · S&V)로 이론 예측 → 머신러닝(XGBoost)으로 잔여 오차 보정 → 실측과 비교',
            ha='center', va='center', fontsize=11, color='#444')

    # 하단 기간 안내 박스
    info = mpatches.FancyBboxPatch((22, 6), 56, 10,
                                   boxstyle='round,pad=0.02,rounding_size=1.5',
                                   linewidth=1.3, edgecolor='#D4A050',
                                   facecolor='#FFF4DE')
    ax.add_patch(info)
    ax.text(50, 11, '저온기 한겨울 기준: 예측 주 2025-11-12 → 수확 주 2026-01-07 (8주 시차)',
            ha='center', va='center', fontsize=11, fontweight='bold', color='#7A5A0A')

    OUT.parent.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches='tight', facecolor='white')
    print(f'✅ saved: {OUT}')


if __name__ == '__main__':
    main()

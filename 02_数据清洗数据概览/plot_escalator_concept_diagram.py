from __future__ import annotations
# -*- coding: utf-8 -*-
"""话语扶梯概念图 · PPT 用。运行：python plot_escalator_concept_diagram.py"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = OUT  # compat / "escalator_concept_diagram.png"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "PingFang SC", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# Colors — match dashboard / PPT tone
BG = "#eceae6"
COPYRIGHT = "#4A6FA5"
COPYRIGHT_LIGHT = "#7a9bc4"
ALIEN = "#B03A3A"
ALIEN_LIGHT = "#d46464"
INK = "#2c2c2c"
MUTED = "#5a5a5a"
GOLD = "#c9a962"


def main() -> None:
    fig, ax = plt.subplots(figsize=(12, 6.8), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.8)
    ax.axis("off")

    # --- Left: copyright axis stations ---
    stations = [
        (1.2, 4.8, "主题 0", "《李白》改编舆论"),
        (1.2, 3.5, "主题 1", "道歉 · 维权"),
        (1.2, 2.2, "主题 3", "版权 · 举证"),
    ]
    for x, y, tid, name in stations:
        box = FancyBboxPatch(
            (x - 0.55, y - 0.42), 1.1, 0.84,
            boxstyle="round,pad=0.04,rounding_size=0.08",
            facecolor=COPYRIGHT, edgecolor="white", linewidth=1.5, alpha=0.95,
        )
        ax.add_patch(box)
        ax.text(x, y + 0.12, tid, ha="center", va="center", fontsize=11, fontweight="bold", color="white")
        ax.text(x, y - 0.15, name, ha="center", va="center", fontsize=8.5, color="#e8eef5")

    ax.text(1.2, 5.65, "版权轴起点", ha="center", fontsize=12, fontweight="bold", color=COPYRIGHT)
    ax.text(1.2, 5.35, "topic 0 / 1 / 3", ha="center", fontsize=9, color=MUTED)

    # --- Right: alien anchor ---
    anchor_x, anchor_y = 10.2, 4.5
    anchor = FancyBboxPatch(
        (anchor_x - 0.75, anchor_y - 0.55), 1.5, 1.1,
        boxstyle="round,pad=0.05,rounding_size=0.1",
        facecolor=ALIEN, edgecolor="white", linewidth=2, alpha=0.95,
    )
    ax.add_patch(anchor)
    ax.text(anchor_x, anchor_y + 0.22, "主题 4", ha="center", fontsize=12, fontweight="bold", color="white")
    ax.text(anchor_x, anchor_y - 0.05, "人身攻击", ha="center", fontsize=10, color="#fce8e8")
    ax.text(anchor_x, anchor_y - 0.28, "网暴 · 辱骂", ha="center", fontsize=8.5, color="#fce8e8")
    ax.text(anchor_x, anchor_y + 0.95, "网络锚点", ha="center", fontsize=11, fontweight="bold", color=ALIEN)

    # --- Escalator steps (staircase) ---
    step_w, step_h = 1.35, 0.55
    n_steps = 5
    x0, y0 = 2.4, 1.35
    for i in range(n_steps):
        sx = x0 + i * step_w * 0.72
        sy = y0 + i * step_h
        step = FancyBboxPatch(
            (sx, sy), step_w, step_h,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor="#d8dde8", edgecolor="#a8b4c8", linewidth=1.2, alpha=0.9,
        )
        ax.add_patch(step)

    ax.text(5.8, 0.55, "扶梯：仍在版权标签下，话语语义向上 / 向攻击锚点漂移", ha="center", fontsize=10,
            fontstyle="italic", color=MUTED)

    # Node colors: 0 / 1 / 3 on escalator (same blue family, different shade)
    topic_shades = [COPYRIGHT, "#5a7fb8", "#6d8fc4"]  # 0, 1, 3
    topic_labels = ["0", "1", "3"]
    node_positions = [
        (2.9, 1.55), (3.85, 2.05), (4.75, 2.55), (5.65, 3.05), (6.55, 3.55), (7.45, 4.05),
    ]
    for i, (nx, ny) in enumerate(node_positions):
        shade = topic_shades[i % 3]
        lbl = topic_labels[i % 3]
        c = Circle((nx, ny), 0.18, facecolor=shade, edgecolor="white", linewidth=1.8, zorder=5)
        ax.add_patch(c)
        ax.text(nx, ny, lbl, ha="center", va="center", fontsize=7.5, fontweight="bold", color="white", zorder=6)
        if i == 0:
            ax.text(nx, ny - 0.42, "用户", ha="center", fontsize=8, color=MUTED)
        if i == len(node_positions) - 1:
            ax.text(nx + 0.05, ny + 0.42, "颜色仍为 0 / 1 / 3", ha="center", fontsize=8.5,
                    fontweight="bold", color=COPYRIGHT)

    # Trajectory arrow along escalator
    ax.annotate(
        "", xy=(7.8, 4.25), xytext=(2.7, 1.45),
        arrowprops=dict(arrowstyle="-|>", color=GOLD, lw=2.2, connectionstyle="arc3,rad=0.08"),
        zorder=4,
    )
    ax.text(5.0, 3.95, "位置漂移", ha="center", fontsize=10, fontweight="bold", color=GOLD,
            rotation=28)

    # Pull toward anchor (dashed)
    pull = FancyArrowPatch(
        (7.65, 4.2), (9.35, 4.45),
        arrowstyle="-|>", mutation_scale=14,
        linestyle="--", linewidth=1.8, color=ALIEN_LIGHT, alpha=0.85,
    )
    ax.add_patch(pull)
    ax.text(8.5, 4.75, "连边牵引 →", ha="center", fontsize=9, color=ALIEN)

    # --- Legend boxes bottom ---
    leg_y = 0.15
    items = [
        (COPYRIGHT, "节点颜色 = 当周众数主题（仍多为 0 / 1 / 3）"),
        (GOLD, "位移 = 语义升级 + 网络向 topic 4 靠拢"),
        (ALIEN, "topic 4 = 人身攻击（结果层，非全员改籍）"),
    ]
    lx = 0.35
    for color, txt in items:
        ax.add_patch(Circle((lx + 0.12, leg_y + 0.12), 0.1, facecolor=color, edgecolor="none"))
        ax.text(lx + 0.32, leg_y + 0.12, txt, ha="left", va="center", fontsize=9, color=INK)
        lx += 3.85

    # Title
    ax.text(6.0, 6.45, "话语扶梯效应（Escalator）", ha="center", fontsize=16, fontweight="bold", color=INK)
    ax.text(6.0, 6.05, "标签未改 · 语义已升 · 位置向人身攻击锚点漂移", ha="center", fontsize=11, color=MUTED)

    # Contrast callout
    callout = FancyBboxPatch(
        (8.55, 1.05), 3.15, 1.15,
        boxstyle="round,pad=0.06,rounding_size=0.1",
        facecolor="white", edgecolor=COPYRIGHT, linewidth=1.5, alpha=0.92,
    )
    ax.add_patch(callout)
    ax.text(10.12, 1.85, "扶梯 ≠ 换乘", ha="center", fontsize=10, fontweight="bold", color=COPYRIGHT)
    ax.text(10.12, 1.48, "全周期主导仍在版权轴", ha="center", fontsize=8.5, color=MUTED)
    ax.text(10.12, 1.18, "topic 4 占比 < 50%", ha="center", fontsize=8.5, color=MUTED)

    plt.tight_layout(pad=0.3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"已保存: {OUT}")


if __name__ == "__main__":
    main()

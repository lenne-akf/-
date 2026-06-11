#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反转前后用户立场归一化对比图（透明背景 PNG）"""
from __future__ import annotations

import sys
from pathlib import Path as _Path
_R = _Path(__file__).resolve().parent.parent
if str(_R) not in sys.path:
    sys.path.insert(0, str(_R))
import 项目路径 as P

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

BASE = Path(__file__).resolve().parent
OUT = BASE / "phase_stance_normalized.png"
OUT_V = BASE / "phase_stance_normalized_vertical.png"
OUT_PIE = BASE / "phase_stance_normalized_pie.png"
REVERSAL = "2026-04-01"

STANCE_TYPES = [
    "版权原教旨主义者",
    "Z世代/乐子人",
    "道德审判官",
    "路人/和事佬",
    "摇摆型",
    "未分类/边缘样本",
]
STANCE_COLORS = {
    "版权原教旨主义者": "#c9a962",
    "Z世代/乐子人": "#7eb8da",
    "道德审判官": "#c44d6a",
    "路人/和事佬": "#e8a060",
    "摇摆型": "#2d9a78",
    "未分类/边缘样本": "#9b8fa3",
}
STANCE_SHORT = {
    "版权原教旨主义者": "版权派",
    "Z世代/乐子人": "乐子人",
    "道德审判官": "道德审判",
    "路人/和事佬": "路人",
    "摇摆型": "摇摆型",
    "未分类/边缘样本": "未分类",
}


def pick_font() -> str:
    for name in ("Microsoft YaHei", "SimHei", "PingFang SC"):
        if name in {f.name for f in font_manager.fontManager.ttflist}:
            return name
    return "sans-serif"


def _pie_autopct(min_pct: float = 3.0):
    def _fmt(pct: float) -> str:
        return f"{pct:.1f}%" if pct >= min_pct else ""
    return _fmt


def plot_phase_pie(phase_data: list[dict]) -> None:
    """双环形饼图：反转前 / 反转后，透明底。"""
    ncols = len(phase_data)

    fig, axes = plt.subplots(1, ncols, figsize=(10.2, 5.6), facecolor="none")
    if ncols == 1:
        axes = [axes]
    fig.patch.set_alpha(0.0)

    legend_handles = None
    legend_labels = None

    for idx, (ax, block) in enumerate(zip(axes, phase_data)):
        ax.set_facecolor("none")
        ax.set_aspect("equal")

        sizes = [block["pcts"].get(st, 0) for st in STANCE_TYPES]
        colors = [STANCE_COLORS[st] for st in STANCE_TYPES]
        labels = [STANCE_SHORT[st] for st in STANCE_TYPES]

        explode = [0.0] * len(STANCE_TYPES)
        mj_idx = STANCE_TYPES.index("道德审判官")
        explode[mj_idx] = 0.05 if block["phase"] == "反转后" else 0.02

        wedges, texts, autotexts = ax.pie(
            sizes,
            explode=explode,
            colors=colors,
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.48, edgecolor="#ffffff", linewidth=3.0, antialiased=True),
            pctdistance=0.78,
            autopct=_pie_autopct(3.0),
            textprops={"fontsize": 10.5, "fontweight": "bold"},
        )

        for i, at in enumerate(autotexts):
            if at.get_text():
                st = STANCE_TYPES[i]
                at.set_color("#1a1018" if st in ("Z世代/乐子人", "路人/和事佬") else "#ffffff")
                at.set_fontsize(11 if sizes[i] >= 10 else 9.5)

        ax.text(
            0, 0.08, block["phase"], ha="center", va="center",
            fontsize=16, fontweight="bold", color="#2c1810",
        )
        ax.text(
            0, -0.10, f"{block['total']:,} 人", ha="center", va="center",
            fontsize=10.5, color="#8a7578",
        )

        if legend_handles is None:
            legend_handles = wedges
            legend_labels = labels

    if len(phase_data) == 2:
        before = phase_data[0]["pcts"].get("道德审判官", 0)
        after = phase_data[1]["pcts"].get("道德审判官", 0)
        delta = after - before
        arrow = "↑" if delta > 0 else "↓"
        fig.text(
            0.5, 0.155,
            f"道德审判  {before:.1f}%  →  {after:.1f}%  ({arrow}{abs(delta):.1f}pp)",
            ha="center", va="center", fontsize=11, fontweight="bold", color="#c44d6a",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#fff5f7", edgecolor="#f0c8d0", linewidth=0.8),
        )

    fig.suptitle(
        "反转前后 · 用户立场类型对比",
        fontsize=18, fontweight="bold", color="#2c1810", y=0.98,
    )
    fig.text(
        0.5, 0.905,
        f"反转节点 {REVERSAL} · 有效分类用户 · 归一化 100%",
        ha="center", va="top", fontsize=10, color="#8a7578",
    )

    fig.legend(
        legend_handles,
        legend_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.0),
        ncol=5,
        frameon=False,
        fontsize=10.5,
        handlelength=1.2,
        handleheight=0.9,
        columnspacing=1.6,
        labelcolor="#2c1810",
    )

    fig.subplots_adjust(left=0.04, right=0.96, top=0.84, bottom=0.12, wspace=0.06)
    fig.savefig(OUT_PIE, dpi=240, transparent=True, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(f"已保存: {OUT_PIE}")


def main() -> None:
    stats = json.loads((P.用户画像统计).read_text(encoding="utf-8"))
    phase_data = stats["phaseCross"]

    plt.rcParams["font.sans-serif"] = [pick_font()]
    plt.rcParams["axes.unicode_minus"] = False

    plot_phase_pie(phase_data)

    fig, ax = plt.subplots(figsize=(10, 3.8), facecolor="none")
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")

    y = np.arange(len(phase_data))
    bar_h = 0.52
    left = np.zeros(len(phase_data))

    for st in STANCE_TYPES:
        pcts = np.array([p["pcts"].get(st, 0) for p in phase_data])
        counts = [p["counts"].get(st, 0) for p in phase_data]
        bars = ax.barh(
            y,
            pcts,
            bar_h,
            left=left,
            label=STANCE_SHORT.get(st, st),
            color=STANCE_COLORS.get(st, "#888888"),
            edgecolor="white",
            linewidth=2.0,
        )
        for i, (bar, pct) in enumerate(zip(bars, pcts)):
            if pct >= 3.0:
                txt_color = "#1a1018" if st in ("Z世代/乐子人", "路人/和事佬") else "#ffffff"
                ax.text(
                    left[i] + pct / 2,
                    bar.get_y() + bar.get_height() / 2,
                    f"{pct:.1f}%",
                    ha="center",
                    va="center",
                    fontsize=11,
                    fontweight="bold",
                    color=txt_color,
                )
        left += pcts

    ax.set_xlim(0, 100)
    phases = [p["phase"] for p in phase_data]
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{ph}  ·  {phase_data[i]['total']:,} 人" for i, ph in enumerate(phases)],
        fontsize=12,
        fontweight="bold",
        color="#2c1810",
    )
    ax.invert_yaxis()

    fig.text(
        0.12,
        0.97,
        "反转前后 · 用户立场类型对比（归一化）",
        fontsize=16,
        fontweight="bold",
        color="#2c1810",
        ha="left",
    )
    fig.text(
        0.12,
        0.895,
        f"反转节点 {REVERSAL} · 有效分类用户 · 行内占比合计 100%",
        fontsize=9.5,
        color="#8a7578",
        ha="left",
    )

    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.tick_params(axis="x", colors="#7a6568", labelsize=9, pad=4)
    ax.tick_params(axis="y", length=0, pad=10)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#d4c4c4")
    ax.grid(axis="x", color="#e8dede", linestyle="-", linewidth=0.6, alpha=0.65)
    ax.set_axisbelow(True)

    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.52, 0.04),
        ncol=5,
        frameon=False,
        fontsize=10,
        handlelength=1.2,
        columnspacing=1.4,
        labelcolor="#2c1810",
    )

    fig.subplots_adjust(left=0.15, right=0.98, top=0.82, bottom=0.12)
    fig.savefig(OUT, dpi=200, transparent=True, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(f"已保存: {OUT}")

    # 竖向 100% 堆叠（两柱：反转前 / 反转后，便于贴 PPT）
    fig2, ax2 = plt.subplots(figsize=(5.2, 6.2), facecolor="none")
    fig2.patch.set_alpha(0.0)
    ax2.set_facecolor("none")

    x = np.arange(len(phase_data))
    bar_w = 0.55
    bottom = np.zeros(len(phase_data))

    for st in STANCE_TYPES:
        pcts = np.array([p["pcts"].get(st, 0) for p in phase_data])
        bars = ax2.bar(
            x,
            pcts,
            bar_w,
            bottom=bottom,
            label=STANCE_SHORT.get(st, st),
            color=STANCE_COLORS.get(st, "#888888"),
            edgecolor="white",
            linewidth=1.8,
        )
        for i, (bar, pct) in enumerate(zip(bars, pcts)):
            if pct >= 3.5:
                txt_color = "#1a1018" if st in ("Z世代/乐子人", "路人/和事佬") else "#ffffff"
                ax2.text(
                    bar.get_x() + bar.get_width() / 2,
                    bottom[i] + pct / 2,
                    f"{pct:.1f}%",
                    ha="center",
                    va="center",
                    fontsize=10,
                    fontweight="bold",
                    color=txt_color,
                )
        bottom += pcts

    ax2.set_ylim(0, 100)
    ax2.set_xticks(x)
    ax2.set_xticklabels(
        [f"{ph}\n({phase_data[i]['total']:,}人)" for i, ph in enumerate(phases)],
        fontsize=11,
        fontweight="bold",
        color="#2c1810",
    )
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax2.set_yticks([0, 20, 40, 60, 80, 100])
    ax2.tick_params(axis="y", colors="#7a6568", labelsize=9)
    ax2.tick_params(axis="x", length=0, pad=8)
    for spine in ("top", "right"):
        ax2.spines[spine].set_visible(False)
    ax2.spines["left"].set_color("#d4c4c4")
    ax2.spines["bottom"].set_color("#d4c4c4")
    ax2.grid(axis="y", color="#e8dede", linestyle="-", linewidth=0.6, alpha=0.65)
    ax2.set_axisbelow(True)

    fig2.text(
        0.5,
        0.98,
        "用户立场类型",
        fontsize=14,
        fontweight="bold",
        color="#2c1810",
        ha="center",
        va="top",
    )
    fig2.text(
        0.5,
        0.93,
        f"反转节点 {REVERSAL} · 归一化 100%",
        fontsize=8.5,
        color="#8a7578",
        ha="center",
        va="top",
    )

    handles, labels = ax2.get_legend_handles_labels()
    fig2.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.02),
        ncol=3,
        frameon=False,
        fontsize=9,
        handlelength=1.0,
        columnspacing=1.2,
        labelcolor="#2c1810",
    )

    fig2.subplots_adjust(left=0.12, right=0.96, top=0.88, bottom=0.14)
    fig2.savefig(OUT_V, dpi=200, transparent=True, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig2)
    print(f"已保存: {OUT_V}")


if __name__ == "__main__":
    main()

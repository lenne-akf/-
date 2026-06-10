# -*- coding: utf-8 -*-
"""页14 群体话语取向分化 — 高美观度可视化"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib import font_manager
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch

OUT_DIR = Path(__file__).resolve().parent
SUMMARY = OUT_DIR / "summary_v2.json"
FRAMEWORK = OUT_DIR / "framework_stats_corrected.json"

# ── Design tokens ──────────────────────────────────────────────
BG = "#EFEDE8"
PANEL = "#FFFFFF"
PANEL_EDGE = "#DDD8D0"
INK = "#1A1820"
INK2 = "#5A5668"
INK3 = "#8E8998"
RULE = "#E6E2DB"

# 参考稿配色：左藕紫 / 右墨绿
BAR_SHAN = "#8E7F9E"
BAR_LI = "#3A5C50"
BAR_SHAN_D = "#6E6080"
BAR_LI_D = "#2A4538"

SHAN = "#9B5A8A"
SHAN_D = "#7A4670"
SHAN_BG = "#F8F0F6"
LI = "#2F6678"
LI_D = "#234F5E"
LI_BG = "#EDF4F7"

LAYER_ORDER = ["版权议题", "职业评价", "人身指责", "其他"]
LAYER_COL = {
    "版权议题": "#4A6FA5",
    "职业评价": "#D4843A",
    "人身指责": "#C44E52",
    "其他": "#C8C3BB",
}
LAYER_LIGHT = {
    "版权议题": "#E8EEF6",
    "职业评价": "#FAF0E6",
    "人身指责": "#FBECEE",
    "其他": "#F3F1ED",
}

GROUPS = ["单依纯粉", "李荣浩粉"]
GROUP_KEYS = ["单粉", "李粉"]
GROUP_ACCENT = [BAR_SHAN, BAR_LI]


def setup_font():
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "SimHei"):
        if name in {f.name for f in font_manager.fontManager.ttflist}:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams.update({
        "axes.unicode_minus": False,
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "savefig.facecolor": BG,
        "axes.facecolor": PANEL,
        "axes.edgecolor": RULE,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "text.color": INK,
    })


def load_data():
    with open(SUMMARY, encoding="utf-8") as f:
        return json.load(f)


def _fs(base: float, font_scale: float = 1.0) -> float:
    return base * font_scale


def _clean_axis(ax, grid_y: bool = True, font_scale: float = 1.0):
    ax.set_facecolor(PANEL)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)
    ax.spines["left"].set_linewidth(0.6)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(axis="both", length=0, pad=6, labelsize=_fs(9.5, font_scale))
    if grid_y:
        ax.yaxis.grid(True, color=RULE, linewidth=0.7, linestyle="-", alpha=0.9)
        ax.set_axisbelow(True)


def _panel_title(ax, title: str, subtitle: str = "", font_scale: float = 1.0):
    ax.text(0, 1.06, title, transform=ax.transAxes, fontsize=_fs(12.5, font_scale),
            fontweight="bold", color=INK, va="bottom", ha="left")
    ax.plot([0, 0.028], [1.055, 1.055], transform=ax.transAxes,
            color=LI, linewidth=3, solid_capstyle="round", clip_on=False)
    if subtitle:
        ax.text(0, 1.01, subtitle, transform=ax.transAxes, fontsize=_fs(8.5, font_scale),
                color=INK3, va="bottom", ha="left")


def _hex_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _label_pct_clean(ax, x, y, val, segment_color: str, min_show: float = 5.0, font_scale: float = 1.0):
    if val < min_show:
        return
    txt_color = "#FFFFFF" if _hex_luminance(segment_color) < 150 else INK
    ax.text(x, y, f"{val:.1f}%", ha="center", va="center",
            fontsize=_fs(10, font_scale), fontweight="600", color=txt_color)


def plot_stacked_bar(data: dict, ax: plt.Axes, *, standalone: bool = False, return_handles: bool = False,
                     font_scale: float = 1.0):
    core = data["core_单李粉"]
    x = [0, 1]
    w = 0.52
    bottom = [0.0, 0.0]
    handles = []

    for layer in LAYER_ORDER:
        vals = [core[k]["content_layer_pct"].get(layer, 0) for k in GROUP_KEYS]
        color = LAYER_COL[layer]
        bars = ax.bar(x, vals, bottom=bottom, width=w, label=layer,
                      color=color, edgecolor="none", linewidth=0, zorder=3)
        handles.append(mpatches.Patch(facecolor=color, edgecolor="none", label=layer))
        for i, (bar, v) in enumerate(zip(bars, vals)):
            if v >= 5:
                _label_pct_clean(ax, bar.get_x() + bar.get_width() / 2, bottom[i] + v / 2, v, color,
                                 font_scale=font_scale)
        bottom = [b + v for b, v in zip(bottom, vals)]

    ax.set_xticks(x)
    ax.set_xticklabels(GROUPS, fontsize=_fs(11, font_scale), fontweight="600")
    ax.set_ylabel("评论占比 (%)", fontsize=_fs(10, font_scale), color=INK2, labelpad=8)
    ax.set_ylim(0, 100)
    ax.set_xlim(-0.55, 1.55)
    _clean_axis(ax, font_scale=font_scale)

    if standalone:
        ax.set_title("话语层级结构", fontsize=_fs(14, font_scale), fontweight="bold", color=INK, loc="left", pad=18)
    else:
        _panel_title(ax, "话语层级结构", font_scale=font_scale)

    if return_handles:
        return handles
    return None


def load_framework():
    if FRAMEWORK.exists():
        with open(FRAMEWORK, encoding="utf-8") as f:
            return json.load(f)
    return None


def plot_diverging_bar(data: dict, ax: plt.Axes, *, standalone: bool = False, font_scale: float = 1.0):
    """B · 单粉 vs 李粉 框架对立：指责取向 + 护主取向（修正编码）。"""
    fw = load_framework()
    if fw:
        rows = fw["rows"]
        shan_vals = [r["单粉"] for r in rows]
        li_vals = [r["李粉"] for r in rows]
        labels = [r["label"] for r in rows]
    else:
        core = data["core_单李粉"]
        labels = ["指责取向", "护主取向"]
        shan_vals = [
            core["单粉"]["content_layer_pct"].get("人身指责", 0),
            core["单粉"]["stance_pct"].get("护单/贬李", 0),
        ]
        li_vals = [
            core["李粉"]["content_layer_pct"].get("人身指责", 0),
            core["李粉"]["stance_pct"].get("护李/贬单", 0),
        ]

    y = list(range(len(labels)))[::-1]
    h = 0.58
    ax.barh(y, [-v for v in shan_vals], height=h, color=BAR_SHAN, edgecolor="none", zorder=3)
    ax.barh(y, li_vals, height=h, color=BAR_LI, edgecolor="none", zorder=3)

    for yi, lv, rv, lab in zip(y, shan_vals, li_vals, labels):
        if lv >= 0.5:
            ax.text(-lv - 0.6, yi, f"{round(lv)}%", ha="right", va="center",
                    fontsize=_fs(11, font_scale), fontweight="600", color=BAR_SHAN_D)
        if rv >= 0.5:
            ax.text(rv + 0.6, yi, f"{round(rv)}%", ha="left", va="center",
                    fontsize=_fs(11, font_scale), fontweight="600", color=BAR_LI_D)
        ax.text(0, yi, lab, ha="center", va="center", fontsize=_fs(10.5, font_scale),
                fontweight="600", color=INK, zorder=5,
                bbox=dict(boxstyle="round,pad=0.35", fc=PANEL, ec="none", alpha=0.85))

    ax.axvline(0, color="#AAAAAA", linewidth=0.9, zorder=2)
    mx = max(max(shan_vals), max(li_vals), 10) + 8
    step = 10 if mx <= 35 else 20
    tick_max = int((mx // step + 1) * step)
    ticks = list(range(-tick_max, tick_max + 1, step))
    if 0 not in ticks:
        ticks.append(0)
        ticks.sort()
    ax.set_xlim(-tick_max, tick_max)
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks], fontsize=_fs(8.5, font_scale), color=INK3)
    ax.set_ylim(-0.65, len(labels) - 0.35)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(axis="x", length=0, pad=4)

    if standalone:
        ax.set_title("单粉 vs 李粉  框架对立", fontsize=_fs(14, font_scale), fontweight="bold",
                      color=INK, loc="left", pad=16)
    else:
        _panel_title(ax, "单粉 vs 李粉 框架对立", font_scale=font_scale)


def plot_path_funnel(data: dict, ax: plt.Axes):
    core = data["core_单李粉"]
    stages = LAYER_ORDER[:3]
    x = [0, 1, 2]

    series = [
        ("李粉", "李荣浩粉", LI, LI_BG, "-"),
        ("单粉", "单依纯粉", SHAN, SHAN_BG, "--"),
    ]
    for gkey, gname, color, fill, ls in series:
        vals = [core[gkey]["content_layer_pct"].get(s, 0) for s in stages]
        ax.fill_between(x, vals, alpha=0.12, color=color, zorder=1)
        ax.plot(x, vals, color=color, linewidth=2.8, markersize=10,
                marker="o", markerfacecolor=PANEL, markeredgewidth=2.2, markeredgecolor=color,
                label=gname, linestyle=ls, zorder=4)
        for xi, v in zip(x, vals):
            offset = 1.8 if gkey == "李粉" else -1.8
            ax.annotate(f"{v:.1f}%", (xi, v + offset), fontsize=9, fontweight="700",
                        color=color, ha="center",
                        bbox=dict(boxstyle="round,pad=0.25", fc=PANEL, ec=color, lw=0.8, alpha=0.95))

    ax.set_xticks(x)
    ax.set_xticklabels(stages, fontsize=10, fontweight="500")
    ax.set_ylabel("占该群评论比例 (%)", fontsize=9.5, color=INK2, labelpad=8)
    ax.set_ylim(-2, 52)
    ax.set_xlim(-0.35, 2.35)
    _clean_axis(ax)
    leg = ax.legend(loc="upper right", frameon=True, fontsize=9, edgecolor=RULE,
                    facecolor=PANEL, framealpha=0.95, borderpad=0.8)
    leg.get_frame().set_linewidth(0.6)
    _panel_title(ax, "话语升级路径", "不含「其他」类中性评论")


def draw_quote_panel(ax: plt.Axes, examples: dict):
    ax.set_facecolor(PANEL)
    ax.axis("off")
    _panel_title(ax, "典型话语框架", "来自可识别粉籍用户的真实评论")

    cards = [
        (LI, LI_BG, LI_D, "李荣浩粉", "版权合规框架",
         examples["李粉_护李/贬单"][:2]),
        (SHAN, SHAN_BG, SHAN_D, "单依纯粉", "双标 / 反制框架",
         examples["单粉_护单/贬李"][:2]),
    ]

    tops = [0.97, 0.49]
    for (accent, bg, accent_d, group, frame, items), top in zip(cards, tops):
        box = FancyBboxPatch((0.02, top - 0.44), 0.96, 0.42, boxstyle="round,pad=0.012,rounding_size=0.015",
                             transform=ax.transAxes, facecolor=bg, edgecolor=accent,
                             linewidth=1.2, clip_on=False, zorder=1)
        ax.add_patch(box)
        ax.plot([0.02, 0.02], [top - 0.02, top - 0.42], transform=ax.transAxes,
                color=accent, linewidth=4, solid_capstyle="round", clip_on=False, zorder=2)
        ax.text(0.07, top - 0.04, group, transform=ax.transAxes, fontsize=10,
                fontweight="bold", color=accent_d, va="top")
        ax.text(0.07, top - 0.10, frame, transform=ax.transAxes, fontsize=8.5,
                color=INK3, va="top")
        yq = top - 0.17
        for e in items:
            txt = e["content"]
            if len(txt) > 52:
                txt = txt[:52] + "…"
            ax.text(0.07, yq, f"“{txt}”", transform=ax.transAxes, fontsize=9,
                    color=INK, va="top", linespacing=1.45, style="italic")
            yq -= 0.13


def add_legend_bar(fig: plt.Figure):
    handles = [mpatches.Patch(facecolor=LAYER_COL[k], edgecolor="none", label=k) for k in LAYER_ORDER]
    leg = fig.legend(handles=handles, loc="upper center", ncol=4, frameon=True,
                     bbox_to_anchor=(0.5, 0.902), fontsize=9, edgecolor=RULE,
                     facecolor=PANEL, columnspacing=1.6, handletextpad=0.5, borderpad=0.5)
    leg.get_frame().set_linewidth(0.6)
    for t in leg.get_texts():
        t.set_color(INK2)


def _legend_layer(fig: plt.Figure, handles, y: float = 0.98, font_scale: float = 1.0):
    leg = fig.legend(handles=handles, loc="upper center", ncol=4, frameon=True,
                     bbox_to_anchor=(0.5, y), fontsize=_fs(9.5, font_scale), edgecolor=PANEL_EDGE,
                     facecolor=PANEL, columnspacing=1.4, handletextpad=0.45,
                     borderpad=0.45, handlelength=1.2)
    leg.get_frame().set_linewidth(0.6)
    for t in leg.get_texts():
        t.set_color(INK2)


def save_fig1(data: dict):
    fig, ax = plt.subplots(figsize=(8.5, 6.0), facecolor=BG)
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_visible(False)
    handles = plot_stacked_bar(data, ax, standalone=True, return_handles=True)
    _legend_layer(fig, handles, y=0.96)
    fig.subplots_adjust(top=0.78, bottom=0.12, left=0.11, right=0.96)
    out = OUT_DIR / "fig1_话语层级堆叠条形图.png"
    fig.savefig(out, dpi=300, facecolor=BG)
    plt.close(fig)
    return out


def save_fig2(data: dict):
    fig, ax = plt.subplots(figsize=(8.5, 4.6), facecolor=BG)
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_visible(False)
    plot_diverging_bar(data, ax, standalone=True)
    fig.subplots_adjust(top=0.88, bottom=0.14, left=0.10, right=0.94)
    out = OUT_DIR / "fig2_框架对立发散图.png"
    fig.savefig(out, dpi=300, facecolor=BG)
    plt.close(fig)
    return out


def save_fig_combo_vertical(data: dict):
    font_scale = 1.65
    fig = plt.figure(figsize=(11.0, 14.0), facecolor=BG)
    gs = GridSpec(2, 1, figure=fig, height_ratios=[1.08, 0.92], hspace=0.38)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    for ax in (ax1, ax2):
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_visible(False)
    handles = plot_stacked_bar(data, ax1, standalone=True, return_handles=True, font_scale=font_scale)
    _legend_layer(fig, handles, y=0.955, font_scale=font_scale)
    plot_diverging_bar(data, ax2, standalone=True, font_scale=font_scale)
    fig.subplots_adjust(top=0.84, bottom=0.07, left=0.12, right=0.93, hspace=0.44)
    out = OUT_DIR / "fig_combo_竖排.png"
    fig.savefig(out, dpi=300, facecolor=BG)
    plt.close(fig)
    return out


def plot_single_premium(data: dict, plot_fn, title: str, fname: str, figsize=(8.5, 5.5)):
    fig, ax = plt.subplots(figsize=figsize, facecolor=BG)
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_visible(False)
    plot_fn(data, ax)
    fig.text(0.06, 0.96, title, fontsize=14, fontweight="bold", color=INK)
    fig.savefig(OUT_DIR / fname, dpi=300, bbox_inches="tight", facecolor=BG, pad_inches=0.2)
    plt.close(fig)


def main():
    setup_font()
    subprocess.run([sys.executable, str(OUT_DIR / "recalc_framework_stats.py")], check=True)
    data = load_data()

    p1 = save_fig1(data)
    p2 = save_fig2(data)
    p3 = save_fig_combo_vertical(data)
    print("Saved to:", OUT_DIR)
    print("  fig1:", p1)
    print("  fig2:", p2)
    print("  combo:", p3)
    print("  代表句:", OUT_DIR / "代表句_PPT素材.txt")
    print("  特点:", OUT_DIR / "页14_特点与原因.txt")


if __name__ == "__main__":
    main()

from __future__ import annotations
# -*- coding: utf-8 -*-
"""
Step 3：情感分析（SnowNLP）

输入：output/cleaned_comments.csv（须含 content 列）
输出：sentiment_results.csv、sentiment_report.txt、sentiment_distribution.png（1200×800）
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from matplotlib import patheffects as pe
from matplotlib.colors import LinearSegmentedColormap
from snownlp import SnowNLP

ROOT = Path(__file__).resolve().parent
OUT_DIR = OUT

INPUT_CSV = OUT_DIR / "cleaned_comments.csv"
OUT_CSV = OUT_DIR / "sentiment_results.csv"
OUT_REPORT = OUT_DIR / "sentiment_report.txt"
OUT_CHART = OUT_DIR / "sentiment_distribution.png"

POS_THRESHOLD = 0.65
NEG_THRESHOLD = 0.35
CHART_SIZE = (1200, 800)  # 像素


def score_to_label(score: float) -> str:
    if score >= POS_THRESHOLD:
        return "积极"
    if score <= NEG_THRESHOLD:
        return "消极"
    return "中性"


def analyze_sentiment(text: str) -> float:
    t = str(text).strip()
    if not t:
        return 0.5
    try:
        return float(SnowNLP(t).sentiments)
    except Exception:
        return 0.5


# 视觉系统（与 comment_insight 酒红基调 + 语义色协调）
_THEME = {
    "bg": "#f4f0f2",
    "card": "#ffffff",
    "ink": "#2a1a22",
    "ink_muted": "#6b5560",
    "ink_soft": "#9a8490",
    "accent": "#6b1d35",
    "accent_light": "#a83256",
    "line": "#e8dce1",
    "grid": "#efe6ea",
}
_SENTIMENT = {
    "积极": {"color": "#2d9a78", "light": "#7fd4b8", "dark": "#1e6b55", "icon": "↑"},
    "中性": {"color": "#8b7e8a", "light": "#c4bac2", "dark": "#5c525a", "icon": "—"},
    "消极": {"color": "#c44d6a", "light": "#e8a0b0", "dark": "#8b2942", "icon": "↓"},
}

# 图表/报告共用说明（避免「积极」被误解为站队）
LABEL_MEANING_NOTE = (
    "积极/中性/消极指评论用语的文本情感极性（SnowNLP），非支持某方立场；"
    "反讽、玩梗易误判，宜结合主题分析与抽样校验。"
)
REPORT_LABEL_SECTION = [
    "【标签含义】",
    "  积极：模型认为评论用词偏表扬、赞同、期待等（得分 ≥ 0.65）",
    "  中性：情绪不明显，多为陈述、吃瓜、疑问等（0.35 < 得分 < 0.65）",
    "  消极：模型认为用词偏批评、愤怒、失望等（得分 ≤ 0.35）",
    "  重要：以上均为算法对「文本语气」的分类，不等于支持单依纯或李荣浩，",
    "        也不等于舆论对谁有利；争议话题中的反讽、梗句可能标错。",
]


def setup_font() -> None:
    for name in ("Microsoft YaHei", "SimHei", "PingFang SC"):
        plt.rcParams["font.sans-serif"] = [name]
        plt.rcParams["axes.unicode_minus"] = False
        return


def _save_figure(fig: plt.Figure, out_path: Path) -> None:
    fig.savefig(out_path, dpi=100, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    try:
        from PIL import Image

        with Image.open(out_path) as im:
            if im.size != CHART_SIZE:
                im.resize(CHART_SIZE, Image.Resampling.LANCZOS).save(out_path)
    except ImportError:
        pass


def plot_distribution(
    counts: pd.Series,
    out_path: Path,
    scores: pd.Series | None = None,
    total_n: int | None = None,
) -> None:
    """生成 1200×800 专业级情感分布信息图。"""
    setup_font()
    order = ["积极", "中性", "消极"]
    labels = [l for l in order if l in counts.index]
    values = [int(counts.get(l, 0)) for l in labels]
    total = total_n or sum(values) or 1
    pcts = [v / total * 100 for v in values]
    mean_score = float(scores.mean()) if scores is not None and len(scores) else None

    fig = plt.figure(figsize=(12, 8), facecolor=_THEME["bg"])
    gs = gridspec.GridSpec(
        4, 12, figure=fig,
        height_ratios=[0.88, 1.05, 2.35, 0.82],
        hspace=0.42, wspace=0.5,
        left=0.055, right=0.96, top=0.91, bottom=0.08,
    )

    # —— 顶栏标题 ——
    ax_title = fig.add_subplot(gs[0, :])
    ax_title.set_axis_off()
    ax_title.text(
        0, 0.72, "评论情感结构分析",
        fontsize=26, fontweight=700, color=_THEME["ink"],
        transform=ax_title.transAxes, ha="left", va="center",
    )
    ax_title.text(
        0, 0.38,
        f"SnowNLP · 有效评论 {total:,} 条 · 积极 ≥{POS_THRESHOLD} · 消极 ≤{NEG_THRESHOLD}",
        fontsize=12.5, color=_THEME["ink_muted"],
        transform=ax_title.transAxes, ha="left", va="center",
    )
    note_lines = textwrap.fill(LABEL_MEANING_NOTE, width=72).splitlines()
    ax_title.text(
        0, 0.0, "\n".join(note_lines),
        fontsize=9.2, color=_THEME["ink_soft"], style="italic",
        transform=ax_title.transAxes, ha="left", va="bottom", linespacing=1.25,
    )
    if mean_score is not None:
        ax_title.text(
            1, 0.45, f"情感均分 {mean_score:.3f}",
            fontsize=13, fontweight=600, color=_THEME["accent"],
            transform=ax_title.transAxes, ha="right", va="center",
            bbox=dict(boxstyle="round,pad=0.45", facecolor=_THEME["card"],
                      edgecolor=_THEME["line"], linewidth=1),
        )

    # —— KPI 卡片 ——
    for i, (lab, val, pct) in enumerate(zip(labels, values, pcts)):
        ax_kpi = fig.add_subplot(gs[1, i * 4 : i * 4 + 4])
        ax_kpi.set_axis_off()
        meta = _SENTIMENT[lab]
        rect = mpatches.FancyBboxPatch(
            (0.02, 0.05), 0.96, 0.9,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=_THEME["card"], edgecolor=_THEME["line"], linewidth=1.2,
            transform=ax_kpi.transAxes, zorder=0,
        )
        ax_kpi.add_patch(rect)
        accent = mpatches.FancyBboxPatch(
            (0.02, 0.82), 0.96, 0.13,
            boxstyle="round,pad=0.01,rounding_size=0.06",
            facecolor=meta["color"], alpha=0.92,
            transform=ax_kpi.transAxes, zorder=1,
        )
        ax_kpi.add_patch(accent)
        ax_kpi.text(
            0.08, 0.88, f"{meta['icon']} {lab}",
            fontsize=13, fontweight=700, color="white",
            transform=ax_kpi.transAxes, va="center", zorder=2,
        )
        ax_kpi.text(
            0.08, 0.48, f"{val:,}",
            fontsize=28, fontweight=700, color=_THEME["ink"],
            transform=ax_kpi.transAxes, va="center", zorder=2,
        )
        ax_kpi.text(
            0.08, 0.22, f"占比 {pct:.1f}%",
            fontsize=12, color=_THEME["ink_muted"],
            transform=ax_kpi.transAxes, va="center", zorder=2,
        )

    # —— 横向条形图 ——
    ax_bar = fig.add_subplot(gs[2, 0:7])
    ax_bar.set_facecolor(_THEME["card"])
    for spine in ax_bar.spines.values():
        spine.set_visible(False)
    y_pos = np.arange(len(labels))
    bar_h = 0.52
    xmax = max(values) * 1.18 if values else 1

    for i, (lab, val, pct) in enumerate(zip(labels, values, pcts)):
        meta = _SENTIMENT[lab]
        grad = LinearSegmentedColormap.from_list(
            "g", [meta["light"], meta["color"], meta["dark"]], N=64
        )
        n_seg = 48
        seg_w = val / n_seg
        for s in range(n_seg):
            ax_bar.barh(
                y_pos[i], seg_w, left=s * seg_w, height=bar_h,
                color=grad(s / max(n_seg - 1, 1)), edgecolor="none",
                zorder=2,
            )
        ax_bar.barh(
            y_pos[i], val, height=bar_h,
            facecolor="none", edgecolor="white", linewidth=1.5, zorder=3,
        )
        label_txt = f"{val:,}  ({pct:.1f}%)"
        txt = ax_bar.text(
            val + xmax * 0.02, y_pos[i], label_txt,
            va="center", ha="left", fontsize=12, fontweight=600, color=_THEME["ink"],
            zorder=4,
        )
        txt.set_path_effects([pe.withStroke(linewidth=3, foreground=_THEME["card"])])

    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(labels, fontsize=13, fontweight=600)
    ax_bar.invert_yaxis()
    ax_bar.set_xlim(0, xmax)
    ax_bar.set_xlabel("评论数量", fontsize=11, color=_THEME["ink_muted"], labelpad=8)
    ax_bar.tick_params(axis="x", colors=_THEME["ink_soft"], labelsize=10)
    ax_bar.tick_params(axis="y", length=0)
    ax_bar.xaxis.grid(True, linestyle="-", linewidth=0.6, color=_THEME["grid"], zorder=0)
    ax_bar.set_axisbelow(True)
    ax_bar.text(
        -0.02, 1.06, "数量对比", fontsize=13, fontweight=700,
        color=_THEME["ink"], transform=ax_bar.transAxes, ha="left",
    )

    # —— 环形图 ——
    ax_donut = fig.add_subplot(gs[2, 7:12])
    ax_donut.set_facecolor(_THEME["card"])
    pie_colors = [_SENTIMENT[l]["color"] for l in labels]
    explode = [0.03 if l == "积极" else 0.01 for l in labels]
    wedges, _texts, autotexts = ax_donut.pie(
        values,
        colors=pie_colors,
        explode=explode,
        startangle=92,
        counterclock=False,
        wedgeprops=dict(width=0.42, edgecolor=_THEME["card"], linewidth=2.5),
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 5 else "",
        pctdistance=0.78,
        textprops=dict(fontsize=11, fontweight=700, color="white"),
    )
    for at in autotexts:
        at.set_path_effects([pe.withStroke(linewidth=2, foreground=_THEME["ink"], alpha=0.35)])

    centre = f"{total:,}\n条评论"
    if mean_score is not None:
        centre = f"均分\n{mean_score:.3f}\n\n{total:,} 条"
    ax_donut.text(
        0, 0, centre, ha="center", va="center",
        fontsize=12, fontweight=700, color=_THEME["ink"], linespacing=1.35,
    )

    leg_handles = [
        mpatches.Patch(facecolor=_SENTIMENT[l]["color"], edgecolor="none",
                       label=f"{l}  {p:.1f}%")
        for l, p in zip(labels, pcts)
    ]
    ax_donut.legend(
        handles=leg_handles, loc="upper center", bbox_to_anchor=(0.5, -0.06),
        ncol=3, frameon=False, fontsize=10, labelcolor=_THEME["ink_muted"],
    )
    ax_donut.text(
        0, 1.08, "结构占比", fontsize=13, fontweight=700,
        color=_THEME["ink"], ha="center", transform=ax_donut.transAxes,
    )

    # —— 得分分布（底部） ——
    if scores is not None and len(scores) > 0:
        ax_hist = fig.add_subplot(gs[3, :])
        ax_hist.set_facecolor(_THEME["card"])
        for spine in ("top", "right", "left"):
            ax_hist.spines[spine].set_visible(False)
        ax_hist.spines["bottom"].set_color(_THEME["line"])

        bins = np.linspace(0, 1, 41)
        n_hist, edges, patches = ax_hist.hist(
            scores.dropna(), bins=bins, color=_THEME["accent_light"],
            alpha=0.35, edgecolor="none", zorder=1,
        )
        for patch, left in zip(patches, edges[:-1]):
            if left >= POS_THRESHOLD:
                patch.set_facecolor(_SENTIMENT["积极"]["color"])
                patch.set_alpha(0.55)
            elif left + (edges[1] - edges[0]) <= NEG_THRESHOLD:
                patch.set_facecolor(_SENTIMENT["消极"]["color"])
                patch.set_alpha(0.55)
            else:
                patch.set_facecolor(_SENTIMENT["中性"]["color"])
                patch.set_alpha(0.45)

        ax_hist.axvline(POS_THRESHOLD, color=_SENTIMENT["积极"]["dark"],
                        ls="--", lw=1.2, alpha=0.85, zorder=3)
        ax_hist.axvline(NEG_THRESHOLD, color=_SENTIMENT["消极"]["dark"],
                        ls="--", lw=1.2, alpha=0.85, zorder=3)
        ax_hist.set_xlim(0, 1)
        ax_hist.set_ylabel("", visible=False)
        ax_hist.set_yticks([])
        ax_hist.set_xlabel("SnowNLP 情感得分（0 → 消极　1 → 积极）",
                           fontsize=10, color=_THEME["ink_muted"], labelpad=4)
        ax_hist.tick_params(axis="x", labelsize=9, colors=_THEME["ink_soft"])
        ax_hist.text(
            0.002, 0.92, "得分密度分布",
            fontsize=11, fontweight=600, color=_THEME["ink_muted"],
            transform=ax_hist.transAxes, va="top",
        )

    _save_figure(fig, out_path)


def write_report(df: pd.DataFrame, n_input: int, out_path: Path) -> None:
    n = len(df)
    mean = df["sentiment_score"].mean()
    std = df["sentiment_score"].std()
    lines = [
        "情感分析报告（SnowNLP）",
        "=" * 56,
        f"输入文件: {INPUT_CSV.name}",
        f"输入条数: {n_input}",
        f"输出条数: {n}",
        f"阈值: 积极 ≥ {POS_THRESHOLD}，消极 ≤ {NEG_THRESHOLD}，其余为中性",
        "",
        "一、整体分布",
        "-" * 40,
    ]
    vc = df["sentiment_label"].value_counts()
    for lab in ("积极", "中性", "消极"):
        c = int(vc.get(lab, 0))
        lines.append(f"  {lab}: {c} 条 ({c/n*100:.2f}%)")
    lines.extend([
        "",
        f"情感得分均值: {mean:.4f}",
        f"情感得分标准差: {std:.4f}",
        "",
        "二、分平台（如有 platform 列）",
        "-" * 40,
    ])
    if "platform" in df.columns:
        for plat, g in df.groupby("platform", sort=False):
            lines.append(f"\n  [{plat}] n={len(g)}")
            for lab in ("积极", "中性", "消极"):
                c = int((g["sentiment_label"] == lab).sum())
                lines.append(f"    {lab}: {c} ({c/len(g)*100:.1f}%)")
            lines.append(f"    均分: {g['sentiment_score'].mean():.4f}")
    else:
        lines.append("  （无 platform 列）")

    lines.extend([
        "",
        "三、标签含义（阅读图表前请先读）",
        "-" * 40,
        *REPORT_LABEL_SECTION,
        "",
        "四、方法局限与使用建议",
        "-" * 40,
        "SnowNLP 基于通用语料，对版权争议场景中的反讽、玩梗、阴阳怪气可能误判。",
        "建议：① 本图仅描述「评论用语的情绪分布」；② 立场/站队需结合 BERTopic 或人工编码；",
        "      ③ 答辩前抽取 50～100 条对照 sentiment_label 做一致性说明。",
        f"图表: {OUT_CHART.name}（{CHART_SIZE[0]}×{CHART_SIZE[1]} 像素，含脚注说明）",
        "",
    ])
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not INPUT_CSV.exists():
        raise SystemExit(f"未找到 {INPUT_CSV}，请先运行 preprocess_three_platforms.py")

    df_in = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    n_input = len(df_in)
    if "content" not in df_in.columns:
        raise SystemExit("cleaned_comments.csv 缺少 content 列")

    print(f"读取 {n_input} 条，开始 SnowNLP 情感分析…")
    df = df_in.copy()
    df["sentiment_score"] = df["content"].map(analyze_sentiment)
    df["sentiment_label"] = df["sentiment_score"].map(score_to_label)

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    write_report(df, n_input, OUT_REPORT)
    plot_distribution(
        df["sentiment_label"].value_counts(),
        OUT_CHART,
        scores=df["sentiment_score"],
        total_n=len(df),
    )

    n_out = len(pd.read_csv(OUT_CSV, encoding="utf-8-sig"))
    ok = n_out == n_input == len(df)
    print(f"\n已保存:\n  - {OUT_CSV}\n  - {OUT_REPORT}\n  - {OUT_CHART}")
    print(df["sentiment_label"].value_counts().to_string())
    print(f"\n验收: 输入 {n_input} 条，输出 {n_out} 条 → {'通过' if ok else '行数不一致'}")


if __name__ == "__main__":
    main()

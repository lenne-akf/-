from __future__ import annotations
# -*- coding: utf-8 -*-
"""
扶梯效应 · 单图：簇 0/1/3（版权类）向人身攻击(topic4)的占比演变。

输出：output/escalator_burst_timeline.png
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from build_topic_network import TOPIC_COLORS, _week_ranges

# paths via _paths
SENTIMENT = OUT / "sentiment_results.csv"
COMMENTS_TOPICS = OUT / "comments_with_topics.csv"
TOPIC_NAMING = OUT / "topic_naming.csv"
OUT_PNG = OUT / "escalator_burst_timeline.png"

CLUSTERS = (0, 1, 3)
ATTACK_TOPIC = 4

_THEME = {
    "bg": "#f7f4f5",
    "card": "#ffffff",
    "ink": "#2a1a22",
    "ink_muted": "#6b5560",
    "grid": "#e8dce1",
    "attack": "#8b2332",
}


def parse_date_yyyy_mm_dd(raw: str) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()[:10]
    return s if len(s) >= 10 and s[4] == "-" else None


def _week_ranges_full(work: pd.DataFrame) -> list[dict]:
    return _week_ranges(work, parse_date_yyyy_mm_dd, max_weeks=9999)


def _x_label(ph: dict) -> str:
    d0 = str(ph.get("date_start") or "")[:10]
    d1 = str(ph.get("date_end") or "")[:10]
    if len(d0) >= 10 and len(d1) >= 10 and d0 != d1:
        return f"{d0[5:]}\n{d1[5:]}"
    if len(d0) >= 10:
        return d0[5:]
    return str(ph.get("label") or "")


def _short_cluster_name(name: str, cluster_id: int) -> str:
    name = (name or "").strip()
    if not name or name == "nan":
        return f"簇{cluster_id}"
    if len(name) > 10:
        return name[:10] + "…"
    return name


def load_cluster_labels() -> dict[int, str]:
    labels = {0: "簇0", 1: "簇1", 3: "簇3"}
    if TOPIC_NAMING.exists():
        naming = pd.read_csv(TOPIC_NAMING, encoding="utf-8-sig")
        for _, row in naming.iterrows():
            tid = int(row["topic_id"])
            if tid in CLUSTERS:
                labels[tid] = _short_cluster_name(
                    str(row.get("chinese_name") or row.get("命名参考") or ""),
                    tid,
                )
    return labels


def collect_cluster_attack_evolution(merged: pd.DataFrame) -> tuple[list[dict], dict[int, np.ndarray]]:
    work = merged[merged["topic_id"] >= 0].copy()
    work["_date"] = work["created_at"].map(parse_date_yyyy_mm_dd)
    work = work[work["_date"].notna()]
    phases = _week_ranges_full(work)
    n = len(phases)

    series: dict[int, np.ndarray] = {c: np.full(n, np.nan) for c in CLUSTERS}

    for wi, wk in enumerate(phases):
        d0, d1 = wk.get("date_start"), wk.get("date_end")
        sub = work[work["_date"].between(d0, d1)] if d0 and d1 else work
        if sub.empty:
            continue

        dom_map: dict[str, int] = {}
        for uid, g in sub.groupby("user_id", sort=False):
            if pd.isna(uid):
                continue
            dom_map[str(uid)] = int(g["topic_id"].mode().iloc[0])

        sub = sub.copy()
        sub["_dom"] = sub["user_id"].astype(str).map(dom_map)

        for cluster in CLUSTERS:
            block = sub[sub["_dom"] == cluster]
            if block.empty:
                continue
            series[cluster][wi] = float((block["topic_id"] == ATTACK_TOPIC).mean() * 100.0)

    return phases, series


def plot_escalator_burst(
    phases: list[dict],
    series: dict[int, np.ndarray],
    cluster_labels: dict[int, str],
    out_path: Path = OUT_PNG,
) -> Path:
    n = len(phases)
    xs = np.arange(n)

    fig_w = max(12, 0.68 * n + 4.8)
    fig, ax = plt.subplots(figsize=(fig_w, 6.2), facecolor=_THEME["bg"])
    ax.set_facecolor(_THEME["card"])

    all_vals = np.concatenate([series[c] for c in CLUSTERS])
    valid = all_vals[~np.isnan(all_vals)]
    y_hi = max(float(valid.max()) * 1.18, 1.2) if valid.size else 6.0

    for cluster in CLUSTERS:
        y = series[cluster]
        color = TOPIC_COLORS[cluster % len(TOPIC_COLORS)]
        ax.plot(
            xs, y, color=color, linewidth=2.6, marker="o", markersize=6,
            markerfacecolor=color, markeredgecolor="white", markeredgewidth=1.2,
            label=cluster_labels[cluster], zorder=3,
        )
        ax.fill_between(xs, y, 0, color=color, alpha=0.10, zorder=2)

    ax.set_xticks(xs)
    ax.set_xticklabels([_x_label(phases[i]) for i in range(n)], fontsize=8.5, color=_THEME["ink"])
    ax.set_xlabel("时间（自然周）", fontsize=11, color=_THEME["ink"], labelpad=10)
    ax.set_ylabel("人身攻击评论占比（%）", fontsize=11, color=_THEME["ink"], labelpad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.1f}"))
    ax.set_xlim(-0.4, n - 0.6)
    ax.set_ylim(0, y_hi)
    ax.grid(axis="y", color=_THEME["grid"], linestyle="--", alpha=0.85, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.set_title(
        "版权类簇 · 人身攻击占比的时间演变",
        fontsize=15, fontweight="bold", color=_THEME["ink"], loc="left", pad=12,
    )
    ax.text(
        0, 1.015,
        "各簇用户 = 当周主导主题属于该簇；纵轴 = 其当周评论中人身攻击(topic4)所占比例",
        transform=ax.transAxes, fontsize=9.5, color=_THEME["ink_muted"],
    )

    ax.legend(loc="upper right", fontsize=9.5, frameon=True,
              facecolor="white", edgecolor=_THEME["grid"], ncol=1)

    fig.subplots_adjust(left=0.09, right=0.97, top=0.88, bottom=0.14)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, facecolor=_THEME["bg"], bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "PingFang SC", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    sentiment_df = pd.read_csv(SENTIMENT, encoding="utf-8-sig")
    topics_df = pd.read_csv(COMMENTS_TOPICS, encoding="utf-8-sig")
    merged = sentiment_df.merge(
        topics_df[["comment_id", "topic_id"]], on="comment_id", how="left",
    )
    labels = load_cluster_labels()
    phases, series = collect_cluster_attack_evolution(merged)
    path = plot_escalator_burst(phases, series, labels)
    print(f"已保存: {path}")


if __name__ == "__main__":
    main()

from __future__ import annotations
# -*- coding: utf-8 -*-
"""
静态图：Y=六主题 · X=全周期时间 · 背景=用户倾向 · 折线=评论占比（突出簇4迁移）

输出：output/topic_user_tendency_timeline.png
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


from collections import defaultdict
from pathlib import Path

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from build_topic_network import TOPIC_COLORS, _week_ranges

# paths via _paths
SENTIMENT = OUT / "sentiment_results.csv"
COMMENTS_TOPICS = OUT / "comments_with_topics.csv"
TOPIC_DIST = OUT / "topic_distribution.csv"
TOPIC_NAMING = OUT / "topic_naming.csv"
OUT_PNG = OUT / "topic_user_tendency_timeline.png"

# 0 = 不抽稀，保留数据内全部自然周
FULL_CYCLE_MAX_WEEKS = 0

_THEME = {
    "bg": "#f7f4f5",
    "card": "#ffffff",
    "ink": "#2a1a22",
    "ink_muted": "#6b5560",
    "grid": "#e8dce1",
    "accent": "#6b1d35",
    "t4": "#8b2332",
    "t0": "#c9a962",
}


def parse_date_yyyy_mm_dd(raw: str) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()[:10]
    return s if len(s) >= 10 and s[4] == "-" else None


def load_topic_table() -> pd.DataFrame:
    dist = pd.read_csv(TOPIC_DIST, encoding="utf-8-sig")
    if TOPIC_NAMING.exists():
        naming = pd.read_csv(TOPIC_NAMING, encoding="utf-8-sig")
        cols = [c for c in ("topic_id", "chinese_name", "命名参考") if c in naming.columns]
        dist = dist.merge(naming[cols], on="topic_id", how="left")
    if "chinese_name" not in dist.columns:
        dist["chinese_name"] = dist["topic_id"].map(lambda x: f"主题 {x}")
    dist["chinese_name"] = dist["chinese_name"].fillna(dist.get("命名参考", "")).astype(str)
    for i, r in dist.iterrows():
        if not str(r["chinese_name"]).strip() or str(r["chinese_name"]) == "nan":
            dist.at[i, "chinese_name"] = f"主题 {int(r['topic_id'])}"
    return dist.sort_values("topic_id").reset_index(drop=True)


def _week_ranges_full(work: pd.DataFrame, parse_date_fn) -> list[dict]:
    """全周期：不抽稀，保留每一自然周。"""
    return _week_ranges(work, parse_date_fn, max_weeks=9999)


def _wrap_label(name: str, max_chars: int = 11) -> str:
    name = (name or "").strip()
    if len(name) <= max_chars:
        return name
    parts: list[str] = []
    while len(name) > max_chars:
        cut = max_chars
        for sep in ("与", "·", "及", " "):
            pos = name[:max_chars].rfind(sep)
            if pos >= 4:
                cut = pos + 1
                break
        parts.append(name[:cut].rstrip("与·及 "))
        name = name[cut:].lstrip("与·及 ")
    if name:
        parts.append(name)
    return "\n".join(parts)


def _collect_user_tendencies(
    merged: pd.DataFrame,
    topic_df: pd.DataFrame,
) -> tuple[list[dict], list[dict], np.ndarray, np.ndarray, dict[str, list]]:
    name_by_id = {
        int(r["topic_id"]): str(r.get("chinese_name") or f"主题 {r['topic_id']}")
        for _, r in topic_df.iterrows()
    }
    topic_ids = sorted(name_by_id.keys())
    n_topics = len(topic_ids)

    work = merged[merged["topic_id"] >= 0].copy()
    work["_date"] = work["created_at"].map(parse_date_yyyy_mm_dd)
    work = work[work["_date"].notna()]
    week_defs = _week_ranges_full(work, parse_date_yyyy_mm_dd)
    n_weeks = len(week_defs)
    mean_mat = np.zeros((n_topics, n_weeks))
    comment_pct = np.zeros((n_topics, n_weeks))
    user_tracks: dict[str, list] = defaultdict(list)
    uid_col = "user_id"

    for wi, wk in enumerate(week_defs):
        d0, d1 = wk.get("date_start"), wk.get("date_end")
        sub = work[work["_date"].between(d0, d1)] if d0 and d1 else work
        if sub.empty:
            continue
        total = len(sub)
        tc = sub["topic_id"].value_counts().to_dict()
        for t in topic_ids:
            row = topic_ids.index(t)
            comment_pct[row, wi] = 100.0 * float(tc.get(t, 0)) / total

        week_vecs: list[dict[int, float]] = []
        for uid, g in sub.groupby(uid_col, sort=False):
            if pd.isna(uid):
                continue
            suid = str(uid)
            cnt = len(g)
            vec = g["topic_id"].value_counts().to_dict()
            dom = int(g["topic_id"].mode().iloc[0])
            tendencies = {int(t): float(c) / cnt for t, c in vec.items()}
            t4_share = tendencies.get(4, 0.0)
            user_tracks[suid].append({
                "week": wi,
                "dominant": dom,
                "tendencies": tendencies,
                "t4_share": t4_share,
                "count": cnt,
            })
            week_vecs.append(tendencies)
        if week_vecs:
            for t in topic_ids:
                row = topic_ids.index(t)
                mean_mat[row, wi] = float(np.mean([v.get(t, 0.0) for v in week_vecs]))

    topics = [
        {"topic_id": t, "name": name_by_id[t], "color": TOPIC_COLORS[t % len(TOPIC_COLORS)]}
        for t in topic_ids
    ]
    return week_defs, topics, mean_mat, comment_pct, dict(user_tracks)


def _pick_track_users(user_tracks: dict[str, list], max_lines: int = 45) -> set[str]:
    scored: list[tuple[float, str]] = []
    for uid, recs in user_tracks.items():
        if len(recs) < 2:
            continue
        recs = sorted(recs, key=lambda r: r["week"])
        doms = [r["dominant"] for r in recs]
        t4_vals = [r.get("t4_share") or 0 for r in recs]
        t4_max = max(t4_vals)
        t4_trend = t4_vals[-1] - t4_vals[0]
        switches = sum(1 for i in range(1, len(doms)) if doms[i] != doms[i - 1])
        to_t4 = doms[-1] == 4 and doms[0] != 4
        activity = sum(r["count"] for r in recs)
        score = activity + switches * 10 + t4_max * 150 + max(0, t4_trend) * 180
        if to_t4:
            score += 80
        if any(v > 0.05 for v in t4_vals):
            score += 30
        scored.append((score, uid))
    scored.sort(reverse=True)
    return {u for _, u in scored[:max_lines]}


def _x_label(ph: dict, wi: int) -> str:
    d0 = str(ph.get("date_start") or "")[:10]
    d1 = str(ph.get("date_end") or "")[:10]
    if len(d0) >= 10 and len(d1) >= 10 and d0 != d1:
        return f"{d0[5:]}\n{d1[5:]}"
    if len(d0) >= 10:
        return d0[5:]
    return ph.get("label") or f"W{wi + 1}"


def plot_tendency_timeline(
    phases: list[dict],
    topics: list[dict],
    avg_mat: np.ndarray,
    comment_pct: np.ndarray,
    user_tracks: dict[str, list],
    out_path: Path = OUT_PNG,
) -> Path:
    n_topics = len(topics)
    n_weeks = len(phases)
    topic_ids = [t["topic_id"] for t in topics]
    id_to_y = {tid: i for i, tid in enumerate(topic_ids)}
    row4 = id_to_y.get(4)
    row0 = id_to_y.get(0)

    fig_w = max(14, min(24, 0.55 * n_weeks + 5))
    fig = plt.figure(figsize=(fig_w, 8.6), facecolor=_THEME["bg"])
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.05, 3.2], hspace=0.08)
    ax_top = fig.add_subplot(gs[0])
    ax = fig.add_subplot(gs[1])
    ax_top.set_facecolor(_THEME["card"])
    ax.set_facecolor(_THEME["card"])

    xs = np.arange(n_weeks)

    # ── 上图：全周期评论占比（突出簇4 vs 簇0）──
    if row4 is not None:
        ax_top.plot(xs, comment_pct[row4], color=_THEME["t4"], linewidth=2.4,
                    marker="o", markersize=4.5, label="人身攻击 · 评论占比", zorder=3)
        ax_top.fill_between(xs, 0, comment_pct[row4], color=_THEME["t4"], alpha=0.12)
    if row0 is not None:
        ax_top.plot(xs, comment_pct[row0], color=_THEME["t0"], linewidth=2.0,
                    marker="s", markersize=3.8, alpha=0.85, label="版权舆论 · 评论占比", zorder=2)
    ax_top.set_ylabel("评论占比 %", fontsize=10, color=_THEME["ink_muted"])
    ax_top.set_xlim(-0.5, n_weeks - 0.5)
    ax_top.set_ylim(0, max(8, float(comment_pct.max()) * 1.15 + 0.5))
    ax_top.legend(loc="upper left", fontsize=9, frameon=True, facecolor="white", edgecolor=_THEME["grid"])
    ax_top.grid(axis="y", color=_THEME["grid"], linestyle="--", linewidth=0.5, alpha=0.9)
    ax_top.set_title(
        "话语向人身攻击迁移 · 全周期（按周）",
        fontsize=15, fontweight="bold", color=_THEME["ink"], pad=10, loc="left",
    )
    ax_top.text(
        0.0, 1.02,
        "上：各主题当周评论占比 · 下：用户平均主题倾向（背景）+ 典型用户轨迹 · 共 "
        f"{n_weeks} 周 · {phases[0].get('date_start', '')} ~ {phases[-1].get('date_end', '')}",
        transform=ax_top.transAxes, fontsize=9, color=_THEME["ink_muted"], va="bottom",
    )
    for spine in ("top", "right"):
        ax_top.spines[spine].set_visible(False)
    ax_top.tick_params(axis="x", labelbottom=False)
    ax_top.tick_params(axis="y", labelsize=8, colors=_THEME["ink_muted"])

    # ── 下图：热力 + 评论占比折线（叠在对应主题行）──
    cmap = LinearSegmentedColormap.from_list(
        "tendency",
        ["#f5f0f2", "#e8d5a3", "#c9a962", "#a83256", "#6b1d35"],
    )
    vmax = max(0.3, float(np.percentile(avg_mat[avg_mat > 0], 92)) if (avg_mat > 0).any() else 0.3)
    im = ax.imshow(
        avg_mat,
        aspect="auto",
        origin="lower",
        cmap=cmap,
        vmin=0,
        vmax=vmax,
        alpha=0.9,
        extent=[-0.5, n_weeks - 0.5, -0.5, n_topics - 0.5],
        zorder=1,
    )

    # 在主题行上叠评论占比（归一化到行内高度，数据驱动）
    pct_scale = 0.38
    for tid in (0, 4):
        if tid not in id_to_y:
            continue
        row = id_to_y[tid]
        ys = row + (comment_pct[row] / 100.0) * pct_scale
        col = _THEME["t4"] if tid == 4 else _THEME["t0"]
        ax.plot(xs, ys, color=col, linewidth=2.2, marker="o", markersize=3.5,
                markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=col,
                alpha=0.95, zorder=5, clip_on=True)

    rng = np.random.default_rng(42)
    track_users = _pick_track_users(user_tracks)

    for uid in track_users:
        recs = sorted(user_tracks[uid], key=lambda r: r["week"])
        xs_l, ys_l = [], []
        for r in recs:
            dom = r["dominant"]
            if dom not in id_to_y:
                continue
            wi = r["week"]
            t4 = r.get("t4_share") or 0
            base_y = id_to_y[dom]
            y_off = base_y
            if dom != 4 and t4 > 0.02 and row4 is not None:
                y_off = base_y + (row4 - base_y) * min(0.45, t4 * 0.75)
            xs_l.append(wi + rng.uniform(-0.12, 0.12))
            ys_l.append(y_off + rng.uniform(-0.06, 0.06))
        if len(xs_l) < 2:
            continue
        t4_peak = max((r.get("t4_share") or 0) for r in recs)
        col = "#8b2332" if t4_peak > 0.06 else "#7a8a9a"
        ax.plot(xs_l, ys_l, color=col, alpha=0.2, linewidth=0.9, zorder=2)

    y_labels = [_wrap_label(t["name"]) for t in topics]
    ax.set_yticks(np.arange(n_topics))
    ax.set_yticklabels(y_labels, fontsize=10, color=_THEME["ink"], linespacing=1.18)
    for i, t in enumerate(topics):
        lw = 2.8 if t["topic_id"] == 4 else 0
        ax.add_patch(mpatches.FancyBboxPatch(
            (-0.62, i - 0.28), 0.18, 0.56,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=t["color"], edgecolor=_THEME["t4"] if t["topic_id"] == 4 else "none",
            linewidth=lw, alpha=0.88, zorder=4,
            transform=ax.transData, clip_on=False,
        ))

    # X 轴：全周期每一周都标（小字号 + 换行防重叠）
    ax.set_xticks(xs)
    ax.set_xticklabels(
        [_x_label(phases[i] or {}, i) for i in range(n_weeks)],
        rotation=0, ha="center", fontsize=7.5, color=_THEME["ink_muted"],
    )
    ax.set_xlim(-0.55, n_weeks - 0.45)
    ax.set_ylim(-0.55, n_topics - 0.45)
    ax.set_xlabel("时间（全周期 · 按周）", fontsize=11, color=_THEME["ink"], labelpad=10)
    ax.set_ylabel("BERTopic 主题", fontsize=11, color=_THEME["ink"], labelpad=10)

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(_THEME["grid"])
    ax.spines["bottom"].set_color(_THEME["grid"])
    ax.grid(axis="x", color=_THEME["grid"], linestyle="--", linewidth=0.5, alpha=0.75, zorder=0)

    cbar = fig.colorbar(im, ax=ax, fraction=0.022, pad=0.015, aspect=32)
    cbar.set_label("用户平均倾向", fontsize=9, color=_THEME["ink_muted"])
    cbar.ax.tick_params(labelsize=8, colors=_THEME["ink_muted"])

    fig.subplots_adjust(left=0.24, right=0.97, top=0.93, bottom=0.12)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170, facecolor=_THEME["bg"], bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "PingFang SC", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    topic_df = load_topic_table()
    sentiment_df = pd.read_csv(SENTIMENT, encoding="utf-8-sig")
    topics_df = pd.read_csv(COMMENTS_TOPICS, encoding="utf-8-sig")
    merged = sentiment_df.merge(
        topics_df[["comment_id", "topic_id"]], on="comment_id", how="left",
    )

    phases, topics, avg_mat, comment_pct, user_tracks = _collect_user_tendencies(merged, topic_df)
    path = plot_tendency_timeline(phases, topics, avg_mat, comment_pct, user_tracks)
    print(f"已保存: {path} · 全周期 {len(phases)} 周")


if __name__ == "__main__":
    main()

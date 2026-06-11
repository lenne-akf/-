from __future__ import annotations
# -*- coding: utf-8 -*-
"""
粉籍 × BERTopic 主题 100% 堆叠条形图
- 条形长度排序体现各粉籍评论量（谁更活跃）
- 堆叠颜色体现舆论导向（聊什么主题）
输出：output/fandom_topic_stacked_bar.png
      output/fandom_composition_bar.png
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pool_filters import filter_pool_comments, pool_user_ids, valid_user_id_mask

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = OUT
PROJECT = ROOT.parent

FENJI_FILE = ROOT / "粉籍" / "user_id_fenji_conf80.csv"
RAW_COMMENTS = OUT / "comments_with_topics.csv"
TOPIC_NAMING = OUT / "topic_naming.csv"

EXCLUDE_FANDOM = {"路人", "无法判断", "无", "其他艺人粉"}
VALID_TOPIC_IDS = [0, 1, 2, 3, 4, 5]

VIZ_W, VIZ_H = 1280, 720

FANDOM_COLORS = {
    "双担": "#9c27b0",
    "单依纯粉": "#f44336",
    "李荣浩粉": "#2196f3",
    "黄霄云粉": "#ffc107",
    "路人": "#bdbdbd",
    "无法判断": "#cfd8dc",
    "其他艺人粉": "#78909c",
}

TOPIC_COLORS = {
    0: "#4e79a7",
    1: "#59a14f",
    2: "#e15759",
    3: "#76b7b2",
    4: "#edc948",
    5: "#b07aa1",
    -1: "#bab0ac",
}

TOPIC_ORDER = [0, 1, 3, 6, 2, 7, -1]


def load_topic_names() -> dict[int, str]:
    df = pd.read_csv(TOPIC_NAMING, encoding="utf-8-sig")
    names = {int(r["topic_id"]): str(r["chinese_name"]).strip() for _, r in df.iterrows()}
    names[-1] = "离群/其他"
    return names


def load_merged() -> pd.DataFrame:
    fenji = pd.read_csv(FENJI_FILE, dtype={"user_id": str})
    fenji = fenji[valid_user_id_mask(fenji["user_id"])].copy()
    raw = pd.read_csv(RAW_COMMENTS, dtype={"user_id": str, "comment_id": str})
    raw = filter_pool_comments(raw, pool_user_ids(fenji))
    raw["topic_id"] = pd.to_numeric(raw["topic_id"], errors="coerce").fillna(-1).astype(int)
    raw = raw.merge(
        fenji.rename(columns={"fenji": "fandom_label"}),
        on="user_id",
        how="left",
    )
    return raw


def topic_pct_table(comments: pd.DataFrame, min_comments: int = 3) -> pd.DataFrame:
    """各粉籍内主题占比（100%）。"""
    rows = []
    for fen, g in comments.groupby("fandom_label"):
        if pd.isna(fen):
            continue
        n = len(g)
        if n < min_comments:
            continue
        vc = g["topic_id"].value_counts()
        users = g["user_id"].nunique()
        for tid in TOPIC_ORDER:
            cnt = int(vc.get(tid, 0))
            if cnt == 0:
                continue
            rows.append({
                "fandom_label": fen,
                "topic_id": tid,
                "count": cnt,
                "pct": 100.0 * cnt / n,
                "comments": n,
                "users": users,
            })
    return pd.DataFrame(rows)


def build_stacked_bar(
    tbl: pd.DataFrame,
    topic_names: dict[int, str],
    *,
    title: str,
    subtitle: str,
) -> go.Figure:
    if tbl.empty:
        raise ValueError("无足够评论绘制堆叠图")

    meta = (
        tbl.groupby("fandom_label")
        .agg(comments=("comments", "first"), users=("users", "first"))
        .reset_index()
    )
    meta = meta.sort_values("comments", ascending=True)
    fandoms = meta["fandom_label"].tolist()

    fig = go.Figure()
    for tid in TOPIC_ORDER:
        sub = tbl[tbl["topic_id"] == tid]
        if sub.empty:
            continue
        pct_map = sub.set_index("fandom_label")["pct"]
        y = [pct_map.get(f, 0) for f in fandoms]
        fig.add_trace(
            go.Bar(
                name=topic_names.get(tid, f"主题{tid}"),
                y=fandoms,
                x=y,
                orientation="h",
                marker_color=TOPIC_COLORS.get(tid, "#999"),
                marker_line=dict(color="rgba(255,255,255,0.8)", width=0.5),
                hovertemplate=(
                    "%{y}<br>%{fullData.name}: %{x:.1f}%"
                    "<extra></extra>"
                ),
            )
        )

    y_labels = []
    for f in fandoms:
        row = meta[meta["fandom_label"] == f].iloc[0]
        y_labels.append(f"{f}  ({int(row['users'])}人·{int(row['comments'])}条)")

    fig.update_layout(
        barmode="stack",
        title=dict(
            text=f"{title}<br><sup>{subtitle}</sup>",
            x=0.5,
            font=dict(size=17, family="Microsoft YaHei, SimHei, sans-serif"),
        ),
        xaxis=dict(
            title="评论占比 (%)",
            range=[0, 100],
            ticksuffix="%",
            gridcolor="rgba(0,0,0,0.06)",
        ),
        yaxis=dict(
            title="",
            tickmode="array",
            tickvals=fandoms,
            ticktext=y_labels,
            automargin=True,
        ),
        legend=dict(
            title="BERTopic 主题",
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=1.02,
            font=dict(size=11, family="Microsoft YaHei, SimHei, sans-serif"),
        ),
        font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=12),
        width=VIZ_W,
        height=max(480, 80 + len(fandoms) * 52),
        margin=dict(l=200, r=220, t=90, b=50),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def build_composition_bar(fenji: pd.DataFrame, *, title: str) -> go.Figure:
    """粉籍人数占比（escalator/簇4 池）。"""
    vc = fenji["fandom_label"].value_counts()
    labels = vc.index.tolist()
    values = vc.values.tolist()
    colors = [FANDOM_COLORS.get(l, "#607d8b") for l in labels]

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            marker_line=dict(color="rgba(255,255,255,0.9)", width=1),
            text=[f"{v}人 ({100*v/sum(values):.1f}%)" for v in values],
            textposition="outside",
            hovertemplate="%{x}<br>%{y} 人<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            font=dict(size=16, family="Microsoft YaHei, SimHei, sans-serif"),
        ),
        xaxis_title="粉籍（算法推断）",
        yaxis_title="用户数",
        font=dict(family="Microsoft YaHei, SimHei, sans-serif"),
        width=VIZ_W,
        height=420,
        margin=dict(t=70, b=80),
        paper_bgcolor="#FFFFFF",
    )
    return fig


def build_dual_panel(
    tbl_all: pd.DataFrame,
    tbl_core: pd.DataFrame,
    topic_names: dict[int, str],
) -> go.Figure:
    """左：含路人全池；右：分析子集（去路人等）。"""
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "全池（含路人/无法判断）",
            "分析子集（去路人/无法判断/其他艺人粉）",
        ),
        horizontal_spacing=0.14,
    )

    for col, tbl in ((1, tbl_all), (2, tbl_core)):
        if tbl.empty:
            continue
        meta = (
            tbl.groupby("fandom_label")
            .agg(comments=("comments", "first"), users=("users", "first"))
            .reset_index()
            .sort_values("comments", ascending=False)
        )
        fandoms = meta["fandom_label"].tolist()[::-1]

        for tid in TOPIC_ORDER:
            sub = tbl[tbl["topic_id"] == tid]
            if sub.empty:
                continue
            pct_map = sub.set_index("fandom_label")["pct"]
            fig.add_trace(
                go.Bar(
                    name=topic_names.get(tid, f"T{tid}"),
                    y=fandoms,
                    x=[pct_map.get(f, 0) for f in fandoms],
                    orientation="h",
                    marker_color=TOPIC_COLORS.get(tid, "#999"),
                    showlegend=(col == 1),
                    legendgroup=f"t{tid}",
                    hovertemplate="%{y}<br>%{fullData.name}: %{x:.1f}%<extra></extra>",
                ),
                row=1,
                col=col,
            )

        fig.update_xaxes(title_text="评论占比 %", range=[0, 100], row=1, col=col)

    fig.update_layout(
        barmode="stack",
        title=dict(
            text=(
                "escalator/簇4 用户池 · 粉籍舆论导向对比"
                "<br><sup>条形标注：用户数·评论数；堆叠=各粉籍内部 BERTopic 主题占比</sup>"
            ),
            x=0.5,
            font=dict(size=16, family="Microsoft YaHei, SimHei, sans-serif"),
        ),
        font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=11),
        width=1600,
        height=780,
        legend=dict(title="BERTopic 主题", orientation="v", x=1.01, y=1),
        margin=dict(l=120, r=200, t=100, b=60),
    )
    return fig


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    topic_names = load_topic_names()
    raw = load_merged()

    fenji = raw[["user_id", "fandom_label", "confidence"]].drop_duplicates("user_id")

    # --- 1. 粉籍人数构成 ---
    fig_comp_all = build_composition_bar(
        fenji,
        title=f"escalator/簇4 用户池粉籍构成（conf≥80%，共 {len(fenji)} 人）",
    )
    out_comp = OUT_DIR / "fandom_composition_bar.png"
    fig_comp_all.write_image(str(out_comp), width=VIZ_W, height=420, scale=2)

    fenji_core = fenji[~fenji["fandom_label"].isin(EXCLUDE_FANDOM)]
    fig_comp_core = build_composition_bar(
        fenji_core,
        title=f"分析子集粉籍构成（去路人等，共 {len(fenji_core)} 人）",
    )
    out_comp_core = OUT_DIR / "fandom_composition_core_bar.png"
    fig_comp_core.write_image(str(out_comp_core), width=VIZ_W, height=420, scale=2)

    # --- 2. 100% 堆叠：舆论导向 ---
    tbl_all = topic_pct_table(raw, min_comments=5)
    raw_core = raw[~raw["fandom_label"].isin(EXCLUDE_FANDOM)]
    tbl_core = topic_pct_table(raw_core, min_comments=3)

    fig_stack = build_stacked_bar(
        tbl_core,
        topic_names,
        title="粉籍 × BERTopic 主题 · 舆论导向（100% 堆叠）",
        subtitle=(
            f"escalator/簇4 分析子集 · {raw_core['user_id'].nunique()} 人 · "
            f"{len(raw_core)} 条评论 · 粉籍=微博文本推断 conf≥80%"
        ),
    )
    out_stack = OUT_DIR / "fandom_topic_stacked_bar.png"
    fig_stack.write_image(str(out_stack), width=VIZ_W, height=fig_stack.layout.height, scale=2)

    # --- 3. 双面板对比 ---
    fig_dual = build_dual_panel(tbl_all, tbl_core, topic_names)
    out_dual = OUT_DIR / "fandom_topic_stacked_dual.png"
    fig_dual.write_image(str(out_dual), width=1600, height=780, scale=2)

    # CSV
    tbl_core.assign(
        topic_name=lambda d: d["topic_id"].map(topic_names)
    ).to_csv(OUT_DIR / "fandom_topic_pct.csv", index=False, encoding="utf-8-sig")

    print(f"[输出] {out_comp}")
    print(f"[输出] {out_comp_core}")
    print(f"[输出] {out_stack}")
    print(f"[输出] {out_dual}")
    print(f"[输出] {OUT_DIR / 'fandom_topic_pct.csv'}")
    print("\n分析子集各粉籍评论量:")
    print(
        raw_core.groupby("fandom_label")["comment_id"]
        .count()
        .sort_values(ascending=False)
        .to_string()
    )


if __name__ == "__main__":
    main()

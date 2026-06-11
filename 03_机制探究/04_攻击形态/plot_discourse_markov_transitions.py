from __future__ import annotations
# -*- coding: utf-8 -*-
"""
页12 · 用户话语状态 Markov 转移（接 Sankey 升级叙事）

三态：理性讨论(0/1/3) · 情绪动员(2) · 异化攻击(4/5)
按 user_id + created_at 排序，统计相邻评论转移概率。

输出：
  output/page12_markov_transition.png
  output/page12_markov_transition.csv
  output/page12_markov_key_transitions.csv

运行：python plot_discourse_markov_transitions.py
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent
CODE = Path(__file__).resolve().parent
PROJECT = ROOT.parent
OUT_DIR = OUT  # compat
sys.path.insert(0, str(CODE))

from plot_page18_logistic_convergence import FONT  # noqa: E402

ID_FILE = V5_USER_IDS
RAW = OUT / "comments_with_topics.csv"
PHASE_CSV = ROOT / "data" / "comments.csv"

VIZ_W, VIZ_H = 1000, 1080
TITLE_SIZE = 34
SUBTITLE_SIZE = 22
CELL_FONT = 30
AXIS_TITLE = 22
TICK_FONT = 20
CB_FONT = 18
STATE_LABELS = ["理性讨论", "情绪动员", "异化攻击"]
STATE_SHORT = ["理性", "动员", "异化"]
TOPIC_TO_STATE = {0: 0, 1: 0, 3: 0, 2: 1, 4: 2, 5: 2}
VALID_TOPICS = set(TOPIC_TO_STATE.keys())
MIN_USER_COMMENTS = 2


def load_sequences() -> pd.DataFrame:
    pool = {
        x.strip()
        for x in ID_FILE.read_text(encoding="utf-8").splitlines()
        if x.strip()
    }
    df = pd.read_csv(RAW, dtype={"user_id": str, "comment_id": str})
    df = df[df["user_id"].astype(str).isin(pool)].copy()
    df["topic_id"] = pd.to_numeric(df["topic_id"], errors="coerce")
    df = df[df["topic_id"].isin(VALID_TOPICS)].copy()
    df["state"] = df["topic_id"].astype(int).map(TOPIC_TO_STATE)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["created_at"])

    if PHASE_CSV.exists():
        ph = pd.read_csv(PHASE_CSV, dtype={"comment_id": str})
        if "phase" in ph.columns:
            df = df.merge(ph[["comment_id", "phase"]], on="comment_id", how="left")
    return df.sort_values(["user_id", "created_at"])


def collect_transitions(df: pd.DataFrame, burst_only: bool = False) -> tuple[np.ndarray, int, int]:
    counts = np.zeros((3, 3), dtype=int)
    n_users = 0
    n_trans = 0
    for _, g in df.groupby("user_id"):
        states = g["state"].astype(int).tolist()
        phases = g["phase"].tolist() if "phase" in g.columns else [None] * len(states)
        if len(states) < MIN_USER_COMMENTS:
            continue
        n_users += 1
        for i in range(len(states) - 1):
            if burst_only and not (
                phases[i] == "爆发期" or phases[i + 1] == "爆发期"
            ):
                continue
            a, b = states[i], states[i + 1]
            counts[a, b] += 1
            n_trans += 1
    return counts, n_users, n_trans


def counts_to_prob(counts: np.ndarray) -> np.ndarray:
    prob = np.zeros_like(counts, dtype=float)
    for i in range(3):
        row = counts[i].sum()
        if row > 0:
            prob[i] = counts[i] / row
    return prob


def key_transitions(prob: np.ndarray, counts: np.ndarray) -> pd.DataFrame:
    rows = []
    for i, src in enumerate(STATE_SHORT):
        for j, dst in enumerate(STATE_SHORT):
            rows.append(
                {
                    "from_state": STATE_LABELS[i],
                    "to_state": STATE_LABELS[j],
                    "count": int(counts[i, j]),
                    "prob": float(prob[i, j]),
                    "prob_pct": round(float(prob[i, j]) * 100, 1),
                }
            )
    return pd.DataFrame(rows)


def build_figure(
    prob: np.ndarray,
    counts: np.ndarray,
    n_users: int,
    n_trans: int,
    n_comments: int,
    burst_prob: np.ndarray | None = None,
) -> go.Figure:
    # 单元格只显示百分比，n 放 hover，避免大字重叠
    text = [[f"{prob[i, j]:.1%}" for j in range(3)] for i in range(3)]
    hover = [
        [
            f"从 {STATE_LABELS[i]} → {STATE_LABELS[j]}<br>"
            f"P = {prob[i, j]:.1%} · n = {counts[i, j]}"
            for j in range(3)
        ]
        for i in range(3)
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=prob,
            x=STATE_LABELS,
            y=STATE_LABELS,
            colorscale=[
                [0.0, "#F7F9FC"],
                [0.35, "#D4E2F4"],
                [0.65, "#E8B4A8"],
                [1.0, "#B03A3A"],
            ],
            zmin=0,
            zmax=max(0.35, float(prob.max()) * 1.05),
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=CELL_FONT, family=FONT, color="#1A2A3A"),
            customdata=hover,
            hovertemplate="%{customdata}<extra></extra>",
            xgap=4,
            ygap=4,
            showscale=True,
            colorbar=dict(
                title=dict(text="转移概率", font=dict(family=FONT, size=CB_FONT)),
                tickformat=".0%",
                tickfont=dict(size=TICK_FONT, family=FONT),
                len=0.72,
                thickness=22,
                y=0.5,
                x=1.02,
            ),
        )
    )
    fig.update_xaxes(
        title=dict(text="下一状态", font=dict(size=AXIS_TITLE, family=FONT), standoff=18),
        tickfont=dict(size=TICK_FONT, family=FONT),
        scaleanchor="y",
        scaleratio=1,
        constrain="domain",
    )
    fig.update_yaxes(
        title=dict(text="当前状态", font=dict(size=AXIS_TITLE, family=FONT), standoff=18),
        tickfont=dict(size=TICK_FONT, family=FONT),
        autorange="reversed",
        constrain="domain",
    )
    fig.update_layout(
        title=dict(
            text=(
                "用户话语 Markov 转移"
                f"<br><sup style='font-size:{SUBTITLE_SIZE}px'>{n_trans:,} 次转移</sup>"
            ),
            x=0.46,
            xanchor="center",
            font=dict(size=TITLE_SIZE, color="#1A2A3A", family=FONT),
        ),
        width=VIZ_W,
        height=VIZ_H,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAFBFD",
        margin=dict(l=130, r=110, t=115, b=105),
        font=dict(family=FONT),
    )
    return fig


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_sequences()
    counts, n_users, n_trans = collect_transitions(df)
    prob = counts_to_prob(counts)
    burst_counts, _, burst_trans = collect_transitions(df, burst_only=True)
    burst_prob = counts_to_prob(burst_counts) if burst_trans > 0 else None

    kt = key_transitions(prob, counts)
    kt.to_csv(OUT / "page12_markov_key_transitions.csv", index=False, encoding="utf-8-sig")

    mat_rows = []
    for i, src in enumerate(STATE_LABELS):
        for j, dst in enumerate(STATE_LABELS):
            mat_rows.append(
                {
                    "from": src,
                    "to": dst,
                    "count": int(counts[i, j]),
                    "prob": float(prob[i, j]),
                }
            )
    pd.DataFrame(mat_rows).to_csv(
        OUT / "page12_markov_transition.csv", index=False, encoding="utf-8-sig"
    )

    fig = build_figure(prob, counts, n_users, n_trans, len(df), burst_prob)
    png = OUT / "page12_markov_transition.png"
    fig.write_image(str(png), width=VIZ_W, height=VIZ_H, scale=3)
    print(f"[输出] {png}")

    print(f"\n评论 {len(df):,} · 可转移用户 {n_users:,} · 转移 {n_trans:,}")
    print("\n转移矩阵 (行=当前, 列=下一):")
    print(pd.DataFrame(prob, index=STATE_LABELS, columns=STATE_LABELS).map(lambda x: f"{x:.1%}").to_string())
    if burst_prob is not None:
        print(f"\n爆发期相邻对 {burst_trans} 次 · 理性→异化 {burst_prob[0,2]:.1%}")


if __name__ == "__main__":
    main()

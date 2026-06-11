from __future__ import annotations
# -*- coding: utf-8 -*-
"""
第三方拉踩 · 对比艺人 × 对比力度 × 对比对象
v5 escalator 全池（3993 人）

可视化：strip 散点 + 径向网络（与旧版相同）
  - 横轴：被拿来对比的第三方艺人（按加权力度排序）
  - 纵轴：对比力度 1–5
  - 颜色：四主题（对标贬损/版权类比/娱乐玩梗/劝阻捆绑）
  - 形状+描边：对比对象（单依纯/李荣浩/双方）

输出：
  output/third_party_comparison_strip.png
  output/third_party_comparison_network.png
  output/third_party_comparison_labeled.csv
  output/third_party_comparison_artist_summary.csv
  output/third_party_comparison_theme_summary.csv

运行：python plot_third_party_comparison_strip.py
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ROOT.parent
OUT = PROJECT_OUT
sys.path.insert(0, str(ROOT))


ID_FILE = V5_USER_IDS
RAW = PROJECT_OUT / "comments_with_topics.csv"

VIZ_W, VIZ_H = 1920, 1020
FONT = "Microsoft YaHei, SimHei, PingFang SC, sans-serif"
TITLE_SIZE = 32
AXIS_TITLE_SIZE = 26
TICK_SIZE = 22
LEGEND_SIZE = 22
NODE_LABEL_SIZE = 20
CORE_LABEL_SIZE = 26

# 与 template_attack_pulse_ppt 统一的暖红棕色系
TARGET_COLORS = {
    "单依纯": "#922B21",
    "李荣浩": "#641E16",
    "双方": "#D35400",
}
MODE_COLORS = {
    "对标贬损": "#922B21",
    "版权类比": "#C0392B",
    "娱乐玩梗": "#E74C3C",
    "劝阻捆绑": "#D35400",
}
THEME_MODES = ["对标贬损", "版权类比", "娱乐玩梗", "劝阻捆绑"]
THEME_SHORT = {
    "对标贬损": "对标贬损",
    "版权类比": "版权类比",
    "娱乐玩梗": "娱乐玩梗",
    "劝阻捆绑": "劝阻捆绑",
}
TARGET_SYMBOL = {"单依纯": "circle", "李荣浩": "square", "双方": "diamond"}

RE_STRONG = re.compile(
    r"就一个|不如|比不上|侮辱|疯子|内蹭|活腻|云泥之别|没实力|踩|蹭|模仿|"
    r"难[听闻]死|滚|恶心|丑|垃圾|碰瓷|低配|毁|网暴|拉踩|差远",
    re.I,
)
RE_MILD = re.compile(r"类比|差不多|版权|年轮|方文山|无所谓|玩梗|别带|不要侮辱", re.I)

from detect_gonghuo_users import (  # noqa: E402
    OTHER_ARTISTS,
    _RE_BOT_NOISE,
    _RE_DEFEND_THIRD,
    detect_rival_compare,
    detect_third_party,
)

EXTRA_ARTISTS = [
    "杨丞琳", "房东的猫", "陆虎", "莫文蔚", "梁静茹", "郭采洁", "郁可唯",
    "孙燕姿", "林俊杰", "陈奕迅", "方文山", "黄霄云", "黄霄雲", "常石磊",
    "李世恩", "欧阳娜娜", "房东的猫",
]
ALL_ARTISTS = list(dict.fromkeys(OTHER_ARTISTS + EXTRA_ARTISTS))
SKIP_ARTISTS = {"李荣浩", "单依纯", "李老师", "浩哥", "lrh", "单姐", "小单"}

_RE_WARN_BIND = re.compile(
    r"别带|不要侮辱|扯.{0,8}干什么|带上.{0,8}做什么|放过.{0,6}王菲|别乱带|无关艺人",
    re.I,
)


def infer_target(purpose: str, content: str) -> str:
    p, c = str(purpose), str(content)
    if "对比单依纯" in p or "护单" in p:
        return "单依纯"
    if "对比李荣浩" in p or "贬李" in p:
        return "李荣浩"
    if re.search(r"单依纯", c) and re.search(r"李荣浩|李老师|浩哥", c):
        if re.search(r"李荣浩.{0,30}(厉害|网暴|双标|伪)", c):
            return "李荣浩"
        if re.search(r"单依纯.{0,30}(不如|差|丑|难|蹭|模仿)", c):
            return "单依纯"
        return "双方"
    if re.search(r"单依纯|单yc|小单|这女的|她", c, re.I):
        if re.search(r"李荣浩|李老师", c):
            return "双方"
        return "单依纯"
    if re.search(r"李荣浩|李老师|浩哥|老李", c):
        return "李荣浩"
    return "双方"


def infer_mode(purpose: str, content: str, intent: str = "") -> str:
    blob = f"{purpose}{content}{intent}"
    if "拉踩/对比" in purpose or re.search(r"就一个|不如|模仿|蹭|内蹭|侮辱|仙气|疯子", blob):
        return "对标贬损"
    if "版权" in purpose or re.search(r"方文山|年轮|版权费|侵权判决|类比", blob):
        return "版权类比"
    if re.search(r"无所谓|玩梗|笑死|辱追|wow|抢钱|跳大神|睡着了|Eason", blob, re.I):
        return "娱乐玩梗"
    if re.search(r"别带|不要侮辱|扯.*干什么|带上.*做什么", blob):
        return "劝阻捆绑"
    if RE_STRONG.search(blob):
        return "对标贬损"
    return "背景提及"


def score_intensity(purpose: str, content: str, mode: str) -> float:
    base = {
        "对标贬损": 4.0,
        "版权类比": 3.0,
        "娱乐玩梗": 2.0,
        "劝阻捆绑": 1.5,
        "背景提及": 1.0,
    }.get(mode, 1.5)
    if "拉踩/对比" in purpose:
        base = max(base, 4.0)
    if "含负面词" in purpose:
        base = max(base, 3.0)
    c = str(content)
    if RE_STRONG.search(c):
        base += 1.0
    elif RE_MILD.search(c):
        base += 0.35
    if len(c) > 80 and mode == "对标贬损":
        base += 0.25
    return float(np.clip(base, 1.0, 5.0))


def mentioned_artists(text: str) -> list[str]:
    t = str(text or "")
    found = [a for a in ALL_ARTISTS if a in t and a not in SKIP_ARTISTS]
    if detect_third_party(t, "") and "王菲" not in found:
        found.insert(0, "王菲")
    return list(dict.fromkeys(found))


def infer_purpose(text: str) -> str:
    t = str(text or "")
    if detect_rival_compare(t):
        if re.search(r"李荣浩|李老师|浩哥", t) and re.search(r"不如|比不上|咖位|周杰伦|刘德华", t):
            return "拉踩/对比李荣浩"
        return "拉踩/对比单依纯"
    if _RE_WARN_BIND.search(t):
        return "含负面词-劝阻"
    if re.search(r"版权|年轮|类比|侵权判决|方文山|张碧晨|汪苏泷", t):
        return "版权类比"
    if re.search(r"不如|模仿|蹭|踩|侮辱|仙气|疯子|内蹭|就一个王菲", t):
        if re.search(r"李荣浩|李老师", t):
            return "拉踩/对比李荣浩"
        return "拉踩/对比单依纯"
    if re.search(r"拉踩|对比|含负面", t):
        return "拉踩/对比单依纯"
    if re.search(r"玩梗|无所谓|笑死", t, re.I):
        return "娱乐玩梗"
    return "背景提及/中性"


def build_v5_mention_rows() -> pd.DataFrame:
    """从 v5 escalator 全池扫描第三方艺人提及，生成 artist×comment 长表。"""
    uids = {x.strip() for x in ID_FILE.read_text(encoding="utf-8").splitlines() if x.strip()}
    df = pd.read_csv(RAW, dtype={"user_id": str, "comment_id": str})
    df = df[df["user_id"].astype(str).isin(uids)].copy()
    df["topic_id"] = pd.to_numeric(df.get("topic_id"), errors="coerce").fillna(-1).astype(int)

    rows = []
    for _, r in df.iterrows():
        text = str(r.get("content") or "").strip()
        if not text or _RE_BOT_NOISE.search(text) or _RE_DEFEND_THIRD.search(text):
            continue
        artists = mentioned_artists(text)
        if not artists:
            continue
        purpose = infer_purpose(text)
        for artist in artists:
            rows.append({
                "artist": artist,
                "purpose": purpose,
                "fandom_label": "未知",
                "topic_id": int(r["topic_id"]),
                "content": text,
                "comment_id": str(r["comment_id"]),
                "intent": "",
                "note": "",
            })
    return pd.DataFrame(rows)


def load_and_label() -> pd.DataFrame:
    df = build_v5_mention_rows()
    if df.empty:
        return df
    df["compare_mode"] = df.apply(
        lambda r: infer_mode(r["purpose"], r["content"], str(r.get("intent", ""))),
        axis=1,
    )
    df["compare_target"] = df.apply(
        lambda r: infer_target(r["purpose"], r["content"]), axis=1
    )
    df["intensity"] = df.apply(
        lambda r: score_intensity(r["purpose"], r["content"], r["compare_mode"]),
        axis=1,
    )
    keep = (df["compare_mode"] != "背景提及") | (df["intensity"] >= 2.5)
    keep |= df["purpose"].astype(str).str.contains("拉踩|对比|含负面|版权类比|娱乐", na=False)
    df = df[keep].copy()
    df["artist"] = df["artist"].astype(str).str.strip()
    return df


def export_theme_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(df)
    for mode in THEME_MODES:
        g = df[df["compare_mode"] == mode]
        if g.empty:
            continue
        top_art = g["artist"].value_counts().index[0]
        rows.append(
            {
                "theme": mode,
                "theme_label": THEME_SHORT[mode],
                "n": len(g),
                "pct": round(100 * len(g) / n, 1),
                "mean_intensity": round(g["intensity"].mean(), 2),
                "top_artist": top_art,
                "top_target": g["compare_target"].value_counts().index[0],
            }
        )
    return pd.DataFrame(rows)


def artist_order(df: pd.DataFrame, top_n: int = 12) -> list[str]:
    agg = (
        df.groupby("artist")
        .agg(weight=("intensity", "sum"), n=("comment_id", "nunique"))
        .reset_index()
    )
    agg = agg.sort_values(["weight", "n"], ascending=False)
    return agg["artist"].head(top_n).tolist()


def jitter_x(idx: int, n_at: int, seed: int = 42) -> float:
    rng = np.random.default_rng(seed + idx * 17)
    spread = min(0.32, 0.12 + 0.04 * n_at)
    return idx + rng.uniform(-spread, spread)


def build_figure(df: pd.DataFrame, theme_summary: pd.DataFrame) -> go.Figure:
    order = artist_order(df, top_n=12)
    df = df[df["artist"].isin(order)].copy()
    pos = {a: i for i, a in enumerate(order)}

    counts = df.groupby("artist").size()
    rng_master = np.random.default_rng(20260329)
    xs, ys, cs, ss, htext, modes, tgts = [], [], [], [], [], [], []
    for i, row in df.iterrows():
        a = row["artist"]
        xi = pos[a]
        n_at = int(counts[a])
        xj = xi + rng_master.uniform(-min(0.34, 0.1 + 0.045 * n_at), min(0.34, 0.1 + 0.045 * n_at))
        xs.append(xj)
        ys.append(row["intensity"])
        cs.append(TARGET_COLORS.get(row["compare_target"], "#666"))
        tgts.append(row["compare_target"])
        size_map = {"对标贬损": 13, "版权类比": 11, "娱乐玩梗": 9, "劝阻捆绑": 8}
        ss.append(size_map.get(row["compare_mode"], 9))
        snippet = str(row["content"])[:36].replace("\n", " ")
        htext.append(
            f"<b>{THEME_SHORT.get(row['compare_mode'], row['compare_mode'])}</b><br>"
            f"{row['artist']} → {row['compare_target']} · 力度 {row['intensity']:.1f}<br>"
            f"{snippet}…"
        )
        modes.append(row["compare_mode"])

    fig = go.Figure()

    # 强度带（violin 近似：每艺人用 scatter 填色轮廓）
    for a in order:
        sub = df[df["artist"] == a]
        if len(sub) < 2:
            continue
        xi = pos[a]
        y_vals = sub["intensity"].values
        y_grid = np.linspace(max(0.8, y_vals.min() - 0.3), min(5.2, y_vals.max() + 0.3), 40)
        # KDE-like envelope
        bw = 0.35
        dens = np.array(
            [np.sum(np.exp(-0.5 * ((y_grid - v) / bw) ** 2)) for v in y_vals]
        )
        dens = dens / (dens.max() + 1e-9) * 0.22
        x_left = xi - dens
        x_right = xi + dens
        x_poly = np.concatenate([x_left, x_right[::-1]])
        y_poly = np.concatenate([y_grid, y_grid[::-1]])
        fig.add_trace(
            go.Scatter(
                x=x_poly,
                y=y_poly,
                fill="toself",
                fillcolor="rgba(231,76,60,0.08)",
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # 均值菱形
    for a in order:
        sub = df[df["artist"] == a]
        xi = pos[a]
        m = sub["intensity"].mean()
        fig.add_trace(
            go.Scatter(
                x=[xi],
                y=[m],
                mode="markers",
                marker=dict(
                    symbol="diamond",
                    size=14,
                    color="#2C3E50",
                    line=dict(width=1.5, color="#FFFFFF"),
                ),
                hovertemplate=f"<b>{a}</b><br>均力度 {m:.2f}<br>提及 {len(sub)} 次<extra></extra>",
                showlegend=False,
            )
        )

    # 散点：颜色=四主题，形状=对比对象，大小编码力度
    for mode in THEME_MODES:
        idxs = [i for i in range(len(xs)) if modes[i] == mode]
        if not idxs:
            continue
        fig.add_trace(
            go.Scatter(
                x=[xs[i] for i in idxs],
                y=[ys[i] for i in idxs],
                mode="markers",
                name=THEME_SHORT[mode],
                marker=dict(
                    size=[8 + ys[i] * 1.8 for i in idxs],
                    color=MODE_COLORS[mode],
                    symbol=[TARGET_SYMBOL.get(tgts[i], "circle") for i in idxs],
                    opacity=0.88,
                    line=dict(
                        width=[2.4 if tgts[i] != "双方" else 1.6 for i in idxs],
                        color=[TARGET_COLORS.get(tgts[i], "#666") for i in idxs],
                    ),
                ),
                text=[htext[i] for i in idxs],
                hovertemplate="%{text}<extra></extra>",
            )
        )

    # 力度刻度参考线
    for y in [2, 3, 4, 5]:
        fig.add_hline(
            y=y,
            line=dict(color="rgba(44,62,80,0.08)", width=1, dash="dot"),
        )

    n_art = len(order)
    fig.update_layout(
        title=dict(
            text="第三方艺人拉踩：拿谁对比 · 对比力度几何（v5 escalator 全池）",
            x=0.5,
            xanchor="center",
            font=dict(size=TITLE_SIZE, color="#1A2A3A", family=FONT),
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(n_art)),
            ticktext=order,
            tickangle=-40,
            title="",
            showgrid=False,
            zeroline=False,
            tickfont=dict(size=TICK_SIZE, color="#2C3E50", family=FONT),
            range=[-0.7, n_art - 0.3],
        ),
        yaxis=dict(
            title=dict(
                text="对比力度（1弱 → 5强）",
                font=dict(size=AXIS_TITLE_SIZE, color="#2C3E50", family=FONT),
            ),
            range=[0.6, 5.45],
            dtick=1,
            gridcolor="rgba(44,62,80,0.06)",
            tickfont=dict(size=TICK_SIZE, family=FONT),
        ),
        legend=dict(
            title="",
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
            font=dict(size=LEGEND_SIZE, family=FONT),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(44,62,80,0.15)",
            borderwidth=1,
        ),
        annotations=[],
        plot_bgcolor="#FAFBFD",
        paper_bgcolor="#FFFFFF",
        width=VIZ_W,
        height=VIZ_H,
        margin=dict(l=100, r=60, t=120, b=240),
        hoverlabel=dict(font=dict(family=FONT, size=16)),
    )
    return fig


def _bezier(x0, y0, x1, y1, n: int = 30, bend: float = 0.35):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + bend
    t = np.linspace(0, 1, n)
    x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t**2 * x1
    y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t**2 * y1
    return x, y


def build_network_figure(df: pd.DataFrame, theme_summary: pd.DataFrame) -> go.Figure:
    """径向对比网络：外圈=第三方艺人，内圈=单/李；连线颜色=四主题，粗细=力度。"""
    summary = export_summary(df)
    top = summary.head(10)["artist"].tolist()
    sub = df[df["artist"].isin(top)].copy()

    targets = {
        "单依纯": (-0.42, -0.08),
        "李荣浩": (0.42, -0.08),
        "双方": (0.0, 0.02),
    }
    n = len(top)
    angles = np.linspace(np.pi * 0.92, np.pi * 0.08, n)
    radius = 0.92
    apos = {a: (radius * np.cos(t), radius * np.sin(t) + 0.05) for a, t in zip(top, angles)}

    edges = (
        sub.groupby(["artist", "compare_target", "compare_mode"], as_index=False)
        .agg(weight=("intensity", "sum"), n=("comment_id", "count"))
    )
    wmax = edges["weight"].max()

    fig = go.Figure()
    for mode in THEME_MODES:
        em = edges[edges["compare_mode"] == mode]
        if em.empty:
            continue
        for _, e in em.iterrows():
            a = e["artist"]
            if a not in apos:
                continue
            tgt = e["compare_target"]
            x0, y0 = apos[a]
            x1, y1 = targets.get(tgt, targets["双方"])
            bx, by = _bezier(x0, y0, x1, y1, bend=0.16 + 0.07 * (e["weight"] / wmax))
            lw = 1.0 + 4.8 * (e["weight"] / wmax)
            col = MODE_COLORS[mode]
            fig.add_trace(
                go.Scatter(
                    x=bx,
                    y=by,
                    mode="lines",
                    line=dict(color=col, width=lw),
                    opacity=0.42 + 0.48 * (e["weight"] / wmax),
                    hovertemplate=(
                        f"{THEME_SHORT[mode]}<br>{a} → {tgt}<br>"
                        f"累计力度 {e['weight']:.1f} · {int(e['n'])}条<extra></extra>"
                    ),
                    legendgroup=mode,
                    showlegend=False,
                )
            )

    # 四主题图例（仅保留四类）
    for mode in THEME_MODES:
        if mode not in set(sub["compare_mode"]):
            continue
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines",
                line=dict(color=MODE_COLORS[mode], width=6),
                name=THEME_SHORT[mode],
            )
        )

    for i, a in enumerate(top):
        g = sub[sub["artist"] == a]
        dom_mode = g["compare_mode"].value_counts().index[0]
        dom_tgt = g["compare_target"].value_counts().index[0]
        x, y = apos[a]
        if y > 0.55:
            tpos = "top center"
        elif y < 0.2:
            tpos = "bottom center"
        elif x < -0.15:
            tpos = "middle left"
        else:
            tpos = "middle right"
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                text=[a],
                textposition=tpos,
                textfont=dict(size=NODE_LABEL_SIZE, color="#2C3E50", family=FONT),
                marker=dict(
                    size=16 + 2.5 * summary.set_index("artist").loc[a, "mean_intensity"],
                    color=MODE_COLORS.get(dom_mode, "#FFFFFF"),
                    opacity=0.92,
                    line=dict(width=3, color=TARGET_COLORS.get(dom_tgt, "#5B7FA6")),
                ),
                hovertext=[
                    f"{a}<br>主主题 {THEME_SHORT[dom_mode]}<br>主对象 {dom_tgt}<br>"
                    f"加权 {summary.set_index('artist').loc[a, 'weighted_intensity']:.0f}"
                ],
                hoverinfo="text",
                showlegend=False,
            )
        )

    # 核心节点
    for name, (x, y) in targets.items():
        if name == "双方":
            continue
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                text=[name],
                textposition="bottom center",
                textfont=dict(size=CORE_LABEL_SIZE, color=TARGET_COLORS[name], family=FONT),
                marker=dict(
                    size=38,
                    color=TARGET_COLORS[name],
                    opacity=0.15,
                    line=dict(width=3, color=TARGET_COLORS[name]),
                ),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        title=dict(
            text="第三方拉踩对比网络：四主题 × 对比艺人 × 力度（v5 escalator 全池）",
            x=0.5,
            font=dict(size=TITLE_SIZE, color="#1A2A3A", family=FONT),
        ),
        xaxis=dict(visible=False, range=[-1.2, 1.2]),
        yaxis=dict(visible=False, range=[-0.62, 1.15], scaleanchor="x", scaleratio=1),
        legend=dict(
            title="",
            orientation="h",
            yanchor="top",
            y=-0.08,
            xanchor="center",
            x=0.5,
            font=dict(family=FONT, size=LEGEND_SIZE),
            bgcolor="rgba(255,255,255,0.96)",
            bordercolor="rgba(44,62,80,0.12)",
            borderwidth=1,
        ),
        annotations=[],
        plot_bgcolor="#FAFBFD",
        paper_bgcolor="#FFFFFF",
        width=VIZ_W,
        height=VIZ_H + 80,
        margin=dict(l=100, r=60, t=110, b=160),
    )
    return fig


def export_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for artist, g in df.groupby("artist"):
        rows.append(
            {
                "artist": artist,
                "n_mentions": len(g),
                "mean_intensity": round(g["intensity"].mean(), 2),
                "max_intensity": round(g["intensity"].max(), 2),
                "weighted_intensity": round(g["intensity"].sum(), 2),
                "top_target": g["compare_target"].value_counts().index[0],
                "top_mode": g["compare_mode"].value_counts().index[0],
            }
        )
    out = pd.DataFrame(rows).sort_values("weighted_intensity", ascending=False)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_and_label()
    if df.empty:
        raise SystemExit("v5 全池未检出第三方拉踩记录。")
    df.to_csv(OUT / "third_party_comparison_labeled.csv", index=False, encoding="utf-8-sig")
    summary = export_summary(df)
    summary.to_csv(OUT / "third_party_comparison_artist_summary.csv", index=False, encoding="utf-8-sig")

    theme_summary = export_theme_summary(df)
    theme_summary.to_csv(OUT / "third_party_comparison_theme_summary.csv", index=False, encoding="utf-8-sig")

    fig = build_figure(df, theme_summary)
    png = OUT / "third_party_comparison_strip.png"
    fig.write_image(str(png), width=VIZ_W, height=VIZ_H, scale=3)
    print(f"[输出] {png}")

    fig_net = build_network_figure(df, theme_summary)
    png_net = OUT / "third_party_comparison_network.png"
    fig_net.write_image(str(png_net), width=VIZ_W, height=VIZ_H + 80, scale=3)
    print(f"[输出] {png_net}")
    print(f"[标注] {len(df)} 条对比语义记录 · {df['artist'].nunique()} 位艺人")
    print(summary.head(10).to_string(index=False))


if __name__ == "__main__":
    main()

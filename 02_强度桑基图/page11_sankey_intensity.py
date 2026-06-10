# -*- coding: utf-8 -*-
"""
页11 · 强度分化桑基图（方案：阶段 → 议题 → 低/高强度）

用法：
  python page11_sankey_intensity.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent
IN_CSV = ROOT / "output" / "page11" / "page11_comments_scored.csv"
OUT = ROOT / "output" / "page11"
OUT_HTML = OUT / "page11_sankey_intensity.html"
OUT_PNG = OUT / "page11_sankey_intensity.png"
OUT_CSV = OUT / "page11_sankey_flows.csv"

PHASES = ["导火索期", "主题分化期", "扩散回落期"]
LAYERS = ["版权议题", "职业评价", "人身指责"]
INTENSITY = ["低强度", "高强度"]
THRESHOLD = 0.55

PHASE_COLORS = {"导火索期": "#c4a0ad", "主题分化期": "#9a8490", "扩散回落期": "#6b5560"}
LAYER_COLORS = {"版权议题": "#4a7c9e", "职业评价": "#e8a54b", "人身指责": "#6b1d35"}
INT_COLORS = {"低强度": "#d4c4cc", "高强度": "#6b1d35"}


def load_data() -> pd.DataFrame:
    df = pd.read_csv(IN_CSV)
    sub = df[~df["excluded"].astype(bool)].copy()
    sub = sub[sub["content_layer"].isin(LAYERS) & sub["phase"].isin(PHASES)]
    sub["intensity_bin"] = sub["attack_score"].apply(
        lambda x: "高强度" if float(x) >= THRESHOLD else "低强度"
    )
    return sub


def build_flow_table(sub: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ph in PHASES:
        for layer in LAYERS:
            for ib in INTENSITY:
                n = len(sub[(sub["phase"] == ph) & (sub["content_layer"] == layer) & (sub["intensity_bin"] == ib)])
                if n:
                    rows.append({
                        "phase": ph,
                        "content_layer": layer,
                        "intensity_bin": ib,
                        "n": n,
                        "node_phase_layer": f"{ph}·{layer}",
                        "node_layer_int": f"{layer}·{ib}",
                        "node_full": f"{ph}·{layer}·{ib}",
                    })
    return pd.DataFrame(rows)


def sankey_phase_topic_intensity(flow: pd.DataFrame) -> go.Figure:
    """三列：阶段 → 议题 → 强度（每条评论走一条路径，适合讲「何时、哪类议题、多尖」）"""
    labels: list[str] = []
    idx: dict[str, int] = {}

    def add(label: str) -> int:
        if label not in idx:
            idx[label] = len(labels)
            labels.append(label)
        return idx[label]

    sources, targets, values, link_colors = [], [], [], []

    for ph in PHASES:
        add(ph)
    for layer in LAYERS:
        add(layer)
    for ib in INTENSITY:
        add(ib)

    # 阶段 → 议题
    for ph in PHASES:
        for layer in LAYERS:
            v = int(flow[(flow["phase"] == ph) & (flow["content_layer"] == layer)]["n"].sum())
            if v:
                sources.append(idx[ph])
                targets.append(idx[layer])
                values.append(v)
                link_colors.append("rgba(74,124,158,0.35)")

    # 议题 → 强度（按阶段着色在 hover 展示）
    for layer in LAYERS:
        for ib in INTENSITY:
            v = int(flow[(flow["content_layer"] == layer) & (flow["intensity_bin"] == ib)]["n"].sum())
            if v:
                sources.append(idx[layer])
                targets.append(idx[ib])
                values.append(v)
                link_colors.append(
                    "rgba(107,29,53,0.55)" if ib == "高强度" else "rgba(212,196,204,0.45)"
                )

    node_colors = []
    for lb in labels:
        if lb in PHASE_COLORS:
            node_colors.append(PHASE_COLORS[lb])
        elif lb in LAYER_COLORS:
            node_colors.append(LAYER_COLORS[lb])
        else:
            node_colors.append(INT_COLORS.get(lb, "#888"))

    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node=dict(
                    pad=18,
                    thickness=22,
                    line=dict(color="#fff", width=1),
                    label=labels,
                    color=node_colors,
                ),
                link=dict(source=sources, target=targets, value=values, color=link_colors),
            )
        ]
    )
    fig.update_layout(
        title=dict(
            text="桑基图 A：阶段 → 议题 → 强度分化<br>"
            f"<sup>低强度=攻击分&lt;{THRESHOLD}；高强度=≥{THRESHOLD}；仅含版权/职业/人身三层议题</sup>",
            x=0.02,
            font=dict(size=18),
        ),
        font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=12),
        width=1100,
        height=620,
        margin=dict(l=20, r=20, t=80, b=20),
        paper_bgcolor="#f8f6f7",
    )
    return fig


def sankey_parallel_phases(sub: pd.DataFrame) -> go.Figure:
    """三列并行：各阶段的「议题·强度」组合宽度对比（适合讲「高强度池如何收缩」）"""
    cats = [f"{layer}·{ib}" for layer in LAYERS for ib in INTENSITY]
    labels: list[str] = []
    idx: dict[str, int] = {}

    def nid(ph: str, cat: str) -> int:
        key = f"{ph}|{cat}"
        if key not in idx:
            idx[key] = len(labels)
            labels.append(f"{ph}\n{cat.replace('·', ' ')}")
        return idx[key]

    sources, targets, values, link_colors = [], [], [], []

    for i, ph in enumerate(PHASES[:-1]):
        ph_next = PHASES[i + 1]
        for cat in cats:
            layer, ib = cat.split("·")
            n1 = len(
                sub[(sub["phase"] == ph) & (sub["content_layer"] == layer) & (sub["intensity_bin"] == ib)]
            )
            if n1 <= 0:
                continue
            sources.append(nid(ph, cat))
            targets.append(nid(ph_next, cat))
            values.append(n1)
            link_colors.append(
                "rgba(107,29,53,0.5)" if ib == "高强度" else "rgba(74,124,158,0.25)"
            )

    node_colors = []
    for lb in labels:
        if "高强度" in lb:
            node_colors.append("#6b1d35")
        elif "版权" in lb:
            node_colors.append("#4a7c9e")
        elif "职业" in lb:
            node_colors.append("#e8a54b")
        else:
            node_colors.append("#8b2942")

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=14,
                    thickness=18,
                    line=dict(color="#fff", width=0.5),
                    label=labels,
                    color=node_colors,
                ),
                link=dict(source=sources, target=targets, value=values, color=link_colors),
            )
        ]
    )
    fig.update_layout(
        title=dict(
            text="桑基图 B：三阶段并行——同类「议题·强度」池的规模变化<br>"
            "<sup>连线表示同一组合在相邻阶段的体量延续（结构迁移，非同一用户追踪）</sup>",
            x=0.02,
            font=dict(size=18),
        ),
        font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=10),
        width=1200,
        height=700,
        margin=dict(l=20, r=20, t=90, b=20),
        paper_bgcolor="#f8f6f7",
    )
    return fig


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sub = load_data()
    flow = build_flow_table(sub)
    flow.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    fig_a = sankey_phase_topic_intensity(flow)
    fig_b = sankey_parallel_phases(sub)

    # A 方案作为主推荐
    fig_a.write_html(str(OUT_HTML))
    fig_a.write_image(str(OUT_PNG), scale=2)
    fig_b.write_html(str(OUT / "page11_sankey_parallel.html"))

    # 高强度率表
    hi_rate = []
    for ph in PHASES:
        for layer in LAYERS:
            p = sub[(sub["phase"] == ph) & (sub["content_layer"] == layer)]
            if len(p):
                hi_rate.append({
                    "phase": ph,
                    "content_layer": layer,
                    "n": len(p),
                    "high_intensity_pct": round((p["intensity_bin"] == "高强度").mean() * 100, 1),
                })
    (OUT / "page11_intensity_by_topic_phase.json").write_text(
        json.dumps(hi_rate, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"桑基 A: {OUT_PNG}")
    print(f"交互: {OUT_HTML}")
    print(f"桑基 B: {OUT / 'page11_sankey_parallel.html'}")
    print(json.dumps(hi_rate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

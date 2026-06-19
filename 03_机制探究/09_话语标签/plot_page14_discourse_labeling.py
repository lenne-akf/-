from __future__ import annotations
# -*- coding: utf-8 -*-
"""
页14 · 话语标签体系（五类修辞）+ 标签→攻击类型桑基

运行：python plot_page14_discourse_labeling.py
"""
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, V5_USER_IDS, FENJI_OUTPUT, bootstrap_sys_path

bootstrap_sys_path()

import re

import pandas as pd
import plotly.graph_objects as go

from discourse_label_features import (  # noqa: E402
    ATTACK_TYPES,
    COPYRIGHT_AXIS_TOPICS,
    DIMENSION_PALETTE,
    DISCOURSE_LABELS,
    LABEL_PATTERNS,
    LABEL_TO_ATTACK,
    LABEL_TO_RHETORIC,
    MEME_RATIONALIZATION_LABELS,
    RHETORIC_CLASS_ORDER,
    RHETORIC_CLASS_PALETTE,
    STRICT_RATIONALIZATION_LABELS,
    _RE_DEFEND_OR_CONDEMN,
    classify_dimension,
    extract_label_names,
    rhetoric_class,
)
from topic_display import ALIEN_TOPIC_IDS  # noqa: E402

ID_FILE = V5_USER_IDS
RAW = OUT / "comments_with_topics.csv"

VIZ_W, VIZ_H = 1920, 1400
FONT = "Microsoft YaHei, SimHei, PingFang SC, sans-serif"
PINNED_WORDCLOUD = [
    "又如何呢", "亮甲梗", "打野梗", "时尚单品", "抄袭", "又当又立", "难听",
]

LABEL_COLORS = {
    name: RHETORIC_CLASS_PALETTE.get(rhetoric_class(name), "#888")
    for name in LABEL_PATTERNS
}


def load_pool() -> pd.DataFrame:
    pool = {
        x.strip()
        for x in ID_FILE.read_text(encoding="utf-8").splitlines()
        if x.strip()
    }
    df = pd.read_csv(RAW, dtype={"user_id": str, "comment_id": str})
    df = df[df["user_id"].astype(str).isin(pool)].copy()
    df["topic_id"] = pd.to_numeric(df["topic_id"], errors="coerce").fillna(-1).astype(int)
    df["content"] = df["content"].astype(str)
    return df


def _is_attack_context(text: str, topic_id: int) -> bool:
    if _RE_DEFEND_OR_CONDEMN.search(text):
        return False
    if topic_id in ALIEN_TOPIC_IDS:
        return True
    if classify_dimension(text) != "其他/综合":
        return True
    if topic_id in COPYRIGHT_AXIS_TOPICS + (2,) and re.search(
        r"单依纯|单姐|小单|李荣浩|难|丑|茶|心机|抄袭|飘|狂|没|不配|伪|甩|洗|蹭|毁|"
        r"贱|滚|恶心|下头|咖位|抬咖|资源|德不配|又能怎|又如何",
        text,
        re.I,
    ):
        return True
    return False


def resolve_attack_type(text: str, label: str) -> str:
    default = LABEL_TO_ATTACK.get(label, "其他/综合")
    dims = classify_dimension(text)
    if dims != "其他/综合":
        return dims
    return default


def build_label_records(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        text = str(r["content"])
        topic_id = int(r["topic_id"])
        if not _is_attack_context(text, topic_id):
            continue
        labels = extract_label_names(text)
        if not labels:
            continue
        for label in labels:
            rows.append(
                {
                    "comment_id": r["comment_id"],
                    "user_id": r["user_id"],
                    "content": text,
                    "topic_id": topic_id,
                    "label": label,
                    "rhetoric_class": rhetoric_class(label),
                    "attack_type": resolve_attack_type(text, label),
                    "on_copyright_axis": topic_id in COPYRIGHT_AXIS_TOPICS,
                    "is_strict_rationalization": label in STRICT_RATIONALIZATION_LABELS,
                    "like_count": pd.to_numeric(r.get("like_count", 0), errors="coerce"),
                }
            )
    return pd.DataFrame(rows)


def _bar_label_list(freq: pd.Series, top_n: int = 10) -> list[str]:
    labels = freq.head(top_n).index.tolist()
    for lab in PINNED_WORDCLOUD:
        if lab in freq.index and lab not in labels:
            labels.append(lab)
    labels = list(dict.fromkeys(labels))
    labels.sort(key=lambda l: (RHETORIC_CLASS_ORDER.index(LABEL_TO_RHETORIC[l]), -int(freq.get(l, 0))))
    return labels[:12]


def _score_example(labels: list[str], text: str, topic_id: int) -> int:
    score = 0
    meme_hits = [l for l in labels if l in MEME_RATIONALIZATION_LABELS]
    score += len(meme_hits) * 8
    if topic_id in COPYRIGHT_AXIS_TOPICS and meme_hits:
        score += 12
    pref = ["亮甲梗", "打野梗", "时尚单品", "又当又立", "洗白", "抄袭", "绿茶", "心机女", "难听"]
    score += len(labels) * 3
    score += sum(4 for p in pref if p in labels)
    if re.search(r"单依纯|单姐|@单依纯", text, re.I):
        score += 3
    if 20 <= len(text) <= 140:
        score += 2
    return score


def pick_examples(records: pd.DataFrame, n: int = 5) -> list[dict]:
    """优先覆盖：梗式合理化 → 论事框架化 → 其余修辞类。"""
    candidates: list[tuple[int, str, list[str], str, int]] = []
    for cid, g in records.groupby("comment_id"):
        labels = sorted(set(g["label"]))
        text = str(g["content"].iloc[0]).strip()
        if len(text) < 8:
            continue
        topic_id = int(g["topic_id"].iloc[0])
        score = _score_example(labels, text, topic_id)
        candidates.append((score, cid, labels, text, topic_id))
    candidates.sort(key=lambda x: x[0], reverse=True)

    priority_classes = ["梗式合理化", "论事框架化", "动机归因化", "直接扣帽", "能力贬损"]
    picked: list[dict] = []
    used_ids: set[str] = set()
    used_classes: set[str] = set()

    for rclass in priority_classes:
        for score, cid, labels, text, topic_id in candidates:
            if cid in used_ids:
                continue
            if rhetoric_class(labels[0]) != rclass and not any(
                rhetoric_class(l) == rclass for l in labels
            ):
                continue
            picked.append({"comment_id": cid, "content": text, "labels": labels, "score": score})
            used_ids.add(cid)
            used_classes.add(rclass)
            break
        if len(picked) >= n:
            break

    for score, cid, labels, text, topic_id in candidates:
        if cid in used_ids:
            continue
        picked.append({"comment_id": cid, "content": text, "labels": labels, "score": score})
        used_ids.add(cid)
        if len(picked) >= n:
            break
    return picked


def highlight_labels(text: str, labels: list[str]) -> str:
    out = text
    for lab in sorted(labels, key=len, reverse=True):
        pat = LABEL_PATTERNS[lab]
        out = re.sub(
            pat,
            lambda m: f"<b style='color:#B03A3A'>{m.group(0)}</b>",
            out,
            flags=re.I,
            count=1,
        )
    return out


def _truncate(text: str, max_len: int = 72) -> str:
    s = re.sub(r"\s+", " ", str(text).strip())
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


# 版面分区（paper 坐标 0–1）
PANEL_TOP = 0.94
PANEL_BOTTOM = 0.54
LEGEND_TOP = 0.53
LEGEND_BOTTOM = 0.475
EXAMPLES_TOP = 0.46


_RHETORIC_LEGEND_SHORT = {
    "梗式合理化": "梗式",
    "论事框架化": "论事",
    "动机归因化": "动机",
    "直接扣帽": "扣帽",
    "能力贬损": "能力",
}


def _add_rhetoric_legend(fig: go.Figure, rhetoric_summary: pd.Series) -> None:
    """条形图下方独立图例带，避免与 x 轴标题重叠。"""
    fig.add_annotation(
        x=0.065,
        y=LEGEND_TOP - 0.008,
        xref="paper",
        yref="paper",
        xanchor="left",
        yanchor="bottom",
        text="条形颜色 · 修辞类型",
        showarrow=False,
        font=dict(size=12, color="#888", family=FONT),
    )
    x0, step = 0.065, 0.082
    y_mid = (LEGEND_TOP + LEGEND_BOTTOM) / 2 - 0.006
    for i, cls in enumerate(RHETORIC_CLASS_ORDER):
        x = x0 + i * step
        color = RHETORIC_CLASS_PALETTE[cls]
        n = int(rhetoric_summary.get(cls, 0))
        short = _RHETORIC_LEGEND_SHORT[cls]
        fig.add_shape(
            type="rect",
            x0=x,
            y0=y_mid - 0.008,
            x1=x + 0.012,
            y1=y_mid + 0.008,
            xref="paper",
            yref="paper",
            fillcolor=color,
            line=dict(width=0),
            layer="above",
        )
        fig.add_annotation(
            x=x + 0.015,
            y=y_mid,
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="middle",
            text=f"{short} {n}",
            showarrow=False,
            font=dict(size=13, color="#444", family=FONT),
        )


def build_figure(
    freq: pd.Series,
    sankey_df: pd.DataFrame,
    examples: list[dict],
    rhetoric_summary: pd.Series,
) -> go.Figure:
    bar_labels = _bar_label_list(freq)
    bar_counts = [int(freq.get(l, 0)) for l in bar_labels]
    bar_colors = [LABEL_COLORS.get(l, "#888") for l in bar_labels]
    max_c = max(bar_counts) if bar_counts else 1

    fig = go.Figure()

    fig.add_shape(
        type="rect",
        x0=0.02, y0=PANEL_BOTTOM, x1=0.52, y1=PANEL_TOP,
        xref="paper", yref="paper",
        line=dict(color="rgba(74,111,165,0.25)", width=1.5),
        fillcolor="rgba(250,251,253,0.6)",
        layer="below",
    )
    fig.add_shape(
        type="rect",
        x0=0.54, y0=PANEL_BOTTOM, x1=0.99, y1=PANEL_TOP,
        xref="paper", yref="paper",
        line=dict(color="rgba(176,58,58,0.2)", width=1.5),
        fillcolor="rgba(255,252,252,0.5)",
        layer="below",
    )
    _add_rhetoric_legend(fig, rhetoric_summary)

    fig.add_trace(
        go.Bar(
            y=bar_labels,
            x=bar_counts,
            orientation="h",
            marker=dict(
                color=bar_colors,
                line=dict(color="rgba(255,255,255,0.9)", width=1.2),
            ),
            text=[f"{c}" for c in bar_counts],
            textposition="outside",
            textfont=dict(size=17, color="#444", family=FONT),
            cliponaxis=False,
            hovertemplate="%{y}<br>出现 %{x} 次<extra></extra>",
            showlegend=False,
        )
    )

    labels_left = sankey_df.groupby("label")["count"].sum().sort_values(ascending=False).index.tolist()
    labels_right = ATTACK_TYPES
    node_labels = labels_left + labels_right
    node_colors = (
        [LABEL_COLORS.get(l, "#888") for l in labels_left]
        + [DIMENSION_PALETTE[t] for t in labels_right]
    )
    idx = {n: i for i, n in enumerate(node_labels)}

    link_src, link_tgt, link_val, link_col = [], [], [], []
    for _, r in sankey_df.iterrows():
        if r["label"] not in idx:
            continue
        link_src.append(idx[r["label"]])
        link_tgt.append(idx[r["attack_type"]])
        link_val.append(int(r["count"]))
        link_col.append(LABEL_COLORS.get(r["label"], "#999"))

    fig.add_trace(
        go.Sankey(
            domain=dict(x=[0.56, 0.98], y=[PANEL_BOTTOM, PANEL_TOP]),
            arrangement="snap",
            node=dict(
                pad=18,
                thickness=18,
                line=dict(color="rgba(255,255,255,0.8)", width=1),
                label=node_labels,
                color=node_colors,
                hovertemplate="%{label}<extra></extra>",
            ),
            link=dict(
                source=link_src,
                target=link_tgt,
                value=link_val,
                color=[
                    f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.35)"
                    if c.startswith("#")
                    else "rgba(150,150,150,0.35)"
                    for c in link_col
                ],
                hovertemplate="%{source.label} → %{target.label}<br>%{value} 次<extra></extra>",
            ),
        )
    )

    markers = ["①", "②", "③", "④", "⑤"]
    fig.add_shape(
        type="rect",
        x0=0.02, y0=0.02, x1=0.99, y1=EXAMPLES_TOP,
        xref="paper", yref="paper",
        line=dict(color="rgba(176,58,58,0.35)", width=1.5),
        fillcolor="rgba(250,251,253,0.95)",
        layer="below",
    )
    fig.add_annotation(
        x=0.03,
        y=EXAMPLES_TOP - 0.008,
        xref="paper",
        yref="paper",
        xanchor="left",
        yanchor="top",
        align="left",
        text="<b>典型评论 · 按修辞类型各举一例</b>",
        showarrow=False,
        font=dict(size=26, color="#1A2A3A", family=FONT),
    )

    line_ys = [0.39, 0.325, 0.26, 0.195, 0.13]
    for i, ex in enumerate(examples[:5]):
        text = _truncate(ex["content"])
        html = highlight_labels(text, ex["labels"])
        rtags = "、".join(dict.fromkeys(rhetoric_class(l) for l in ex["labels"]))
        tag = "、".join(ex["labels"][:3])
        if len(ex["labels"]) > 3:
            tag += "…"
        fig.add_annotation(
            x=0.03,
            y=line_ys[i],
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="top",
            align="left",
            text=(
                f"<span style='color:#B03A3A;font-weight:bold;font-size:26px'>{markers[i]}</span> "
                f"<span style='font-size:20px;color:#888'>[{rtags}]</span> "
                f"<span style='font-size:21px;color:#666'>{tag}</span> "
                f"<span style='font-size:25px;color:#222'>{html}</span>"
            ),
            showarrow=False,
            width=1860,
        )

    fig.add_annotation(
        x=0.25,
        y=0.975,
        xref="paper",
        yref="paper",
        text=(
            "<b>话语标签 · 五类修辞</b><br>"
            "<sup>梗式含：又如何呢 / 亮甲 / 打野 / 时尚单品 / mean / 体面反讽</sup>"
        ),
        showarrow=False,
        font=dict(size=18, family=FONT, color="#1A2A3A"),
    )
    fig.add_annotation(
        x=0.77,
        y=0.975,
        xref="paper",
        yref="paper",
        text="<b>标签 → 攻击类型</b><br><sup>右侧节点色 = 攻击维度</sup>",
        showarrow=False,
        font=dict(size=20, family=FONT, color="#1A2A3A"),
    )

    fig.update_traces(
        textfont=dict(size=16, family=FONT, color="#1A2A3A"),
        selector=dict(type="sankey"),
    )
    fig.update_layout(
        title=dict(
            text="话语标签体系 · 从梗式合理化到直接贬损",
            x=0.5,
            xanchor="center",
            font=dict(size=28, color="#1A2A3A", family=FONT),
        ),
        font=dict(family=FONT),
        width=VIZ_W,
        height=VIZ_H,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAFBFD",
        margin=dict(l=40, r=40, t=100, b=36),
        xaxis=dict(
            domain=[0.06, 0.48],
            title=dict(
                text="出现次数",
                font=dict(size=14, family=FONT),
                standoff=18,
            ),
            range=[0, max_c * 1.18],
            tickfont=dict(size=15, family=FONT),
            gridcolor="rgba(44,62,80,0.08)",
            zeroline=False,
        ),
        yaxis=dict(
            domain=[PANEL_BOTTOM, PANEL_TOP - 0.02],
            tickfont=dict(size=18, family=FONT),
            automargin=True,
        ),
    )
    return fig


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_pool()
    records = build_label_records(df)
    if records.empty:
        raise RuntimeError("未匹配到标签化攻击评论，请检查规则。")

    freq = records["label"].value_counts()
    rhetoric_summary = records.groupby("rhetoric_class").size().reindex(
        RHETORIC_CLASS_ORDER, fill_value=0
    )
    sankey_df = (
        records.groupby(["label", "attack_type"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )
    sankey_df = sankey_df[sankey_df["label"].isin(freq.head(12).index)]

    bridge = records[records["on_copyright_axis"]].groupby("rhetoric_class").size()
    strict_bridge = records[
        records["is_strict_rationalization"] & records["on_copyright_axis"]
    ]["comment_id"].nunique()

    examples = pick_examples(records, n=5)

    freq.to_csv(OUT / "page14_label_frequencies.csv", header=["count"], encoding="utf-8-sig")
    rhetoric_summary.to_csv(
        OUT / "page14_rhetoric_class_summary.csv", header=["count"], encoding="utf-8-sig"
    )
    bridge.reindex(RHETORIC_CLASS_ORDER, fill_value=0).to_csv(
        OUT / "page14_rhetoric_on_copyright_axis.csv", header=["count"], encoding="utf-8-sig"
    )
    sankey_df.to_csv(OUT / "page14_label_sankey_links.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {
                "comment_id": ex["comment_id"],
                "content": ex["content"],
                "labels": "、".join(ex["labels"]),
                "rhetoric_classes": "、".join(
                    dict.fromkeys(rhetoric_class(l) for l in ex["labels"])
                ),
            }
            for ex in examples
        ]
    ).to_csv(OUT / "page14_label_example.csv", index=False, encoding="utf-8-sig")

    n_hit = records["comment_id"].nunique()
    fig = build_figure(freq, sankey_df, examples, rhetoric_summary)
    png = OUT / "page14_discourse_labeling.png"
    fig.write_image(str(png), width=VIZ_W, height=VIZ_H, scale=3)
    print(f"[输出] {png}")

    # 粉籍分析/output 与 PPT 同源，同步一份避免看到旧图
    FENJI_OUTPUT.mkdir(parents=True, exist_ok=True)
    fenji_png = FENJI_OUTPUT / "page14_discourse_labeling.png"
    fenji_png.write_bytes(png.read_bytes())
    print(f"[同步] {fenji_png}")
    print(f"标签化评论 {n_hit} 条 · 标签命中 {len(records)} 次")
    print(f"版权轴 + 梗式合理化评论 {strict_bridge} 条（扶梯桥接证据）")
    print("修辞类汇总:\n", rhetoric_summary.to_string())
    print("\nTop 标签:\n", freq.head(10).to_string())


if __name__ == "__main__":
    main()

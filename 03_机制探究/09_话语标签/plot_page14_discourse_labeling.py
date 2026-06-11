from __future__ import annotations
# -*- coding: utf-8 -*-
"""
页14 · 话语标签化：「合理批判」框架下的人身攻击

运行：python plot_page14_discourse_labeling.py
"""
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, V5_USER_IDS, bootstrap_sys_path

bootstrap_sys_path()

import re

import pandas as pd
import plotly.graph_objects as go

from discourse_label_features import (  # noqa: E402
    ATTACK_TYPES,
    DIMENSION_PALETTE,
    DISCOURSE_LABELS,
    _RE_DEFEND_OR_CONDEMN,
    classify_dimension,
    dimension_hits,
)
from topic_display import ALIEN_TOPIC_IDS  # noqa: E402

ID_FILE = V5_USER_IDS
RAW = OUT / "comments_with_topics.csv"

VIZ_W, VIZ_H = 1920, 1400
FONT = "Microsoft YaHei, SimHei, PingFang SC, sans-serif"
PINNED_WORDCLOUD = ["绿茶", "心机女", "资源咖", "德不配位", "又当又立"]

# (展示名, 匹配正则, 默认攻击类型)
DISCOURSE_LABELS: list[tuple[str, str, str]] = [
    ("抄袭", r"抄袭|抄歌|偷歌|侵权|盗用", "言论/观点攻击"),
    ("难听", r"难听|毁歌|难[听闻]|唱得.*差|魔改", "业务能力攻击"),
    ("又当又立", r"又当又立|双标|甩锅|两面", "言论/观点攻击"),
    ("资本推手", r"资本|水军|营销号|买热搜|公关|幕后|推手", "立场/阵营攻击"),
    ("蹭热度", r"蹭热度|蹭.*热|带节奏|占用.*资源", "立场/阵营攻击"),
    ("洗白", r"洗白|狡辩|小作文|诡辩|硬洗", "言论/观点攻击"),
    ("飘了", r"飘了|太狂|狂妄|嚣张|目中无人", "人品攻击"),
    ("明知故犯", r"明知故犯|知错还|故意.*(抄|唱)", "言论/观点攻击"),
    ("绿茶", r"绿茶[婊表妹]?|🍵|绿茶行为|绿茶精", "人品攻击"),
    ("心机女", r"心机女|心机|不安好心|不单纯|有心机", "人品攻击"),
    ("德不配位", r"德不配位|才不配位|位不配德", "业务能力攻击"),
    ("资源咖", r"资源咖|靠资源|抬咖|升咖|小咖|什么咖位|咖位", "业务能力攻击"),
    ("伪君子", r"伪君子|小人|卑劣|下作|Responsible", "人品攻击"),
    ("装无辜", r"装无辜|装单纯|装可怜|装模作样|人设", "人品攻击"),
    ("没教养", r"没教养|没素质|缺乏教养", "人品攻击"),
    ("没实力", r"没实力|没作品|不配当|能力不行", "业务能力攻击"),
    ("黑红", r"黑红|名声大噪|搞塌", "立场/阵营攻击"),
    ("又如何呢", r"又如何呢|又能怎", "言论/观点攻击"),
]

ATTACK_TYPES = [
    "人品攻击",
    "业务能力攻击",
    "言论/观点攻击",
    "立场/阵营攻击",
]

LABEL_COLORS = {
    "抄袭": "#8E44AD",
    "难听": "#2980B9",
    "又当又立": "#D35400",
    "资本推手": "#7F8C8D",
    "蹭热度": "#16A085",
    "洗白": "#E67E22",
    "飘了": "#C0392B",
    "明知故犯": "#A93226",
    "绿茶": "#27AE60",
    "心机女": "#2ECC71",
    "德不配位": "#1ABC9C",
    "资源咖": "#3498DB",
    "伪君子": "#E74C3C",
    "装无辜": "#9B59B6",
    "没教养": "#D68910",
    "没实力": "#5DADE2",
    "黑红": "#566573",
    "又如何呢": "#AF601A",
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
    if topic_id in (0, 1, 2, 3) and re.search(
        r"单依纯|单姐|小单|李荣浩|难|丑|茶|心机|抄袭|飘|狂|没|不配|伪|甩|洗|蹭|毁|"
        r"贱|滚|恶心|下头|咖位|抬咖|资源|德不配",
        text,
        re.I,
    ):
        return True
    return False


def extract_labels(text: str) -> list[str]:
    hits = []
    for name, pat, _ in DISCOURSE_LABELS:
        if re.search(pat, text, re.I):
            hits.append(name)
    return hits


def resolve_attack_type(text: str, label: str, default: str) -> str:
    dims = dimension_hits(text)
    if len(dims) == 1:
        return dims[0]
    if default in dims:
        return default
    if dims:
        return dims[0]
    return default


def build_label_records(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        text = str(r["content"])
        if not _is_attack_context(text, int(r["topic_id"])):
            continue
        labels = extract_labels(text)
        if not labels:
            continue
        for label in labels:
            default = next(d for n, _, d in DISCOURSE_LABELS if n == label)
            rows.append(
                {
                    "comment_id": r["comment_id"],
                    "user_id": r["user_id"],
                    "content": text,
                    "topic_id": int(r["topic_id"]),
                    "label": label,
                    "attack_type": resolve_attack_type(text, label, default),
                    "like_count": pd.to_numeric(r.get("like_count", 0), errors="coerce"),
                }
            )
    return pd.DataFrame(rows)


def _bar_label_list(freq: pd.Series, top_n: int = 10) -> list[str]:
    """高频标签 + 叙事核心标签，去重后按频次升序（便于水平条自下而上递增）。"""
    labels = freq.head(top_n).index.tolist()
    for lab in PINNED_WORDCLOUD:
        if lab in freq.index and lab not in labels:
            labels.append(lab)
    labels = list(dict.fromkeys(labels))
    labels.sort(key=lambda l: int(freq.get(l, 0)))
    return labels[:12]


def _score_example(labels: list[str], text: str, topic_id: int) -> int:
    pref = [
        "绿茶", "心机女", "又当又立", "装无辜", "资源咖", "德不配位", "没教养", "伪君子",
    ]
    score = len(labels) * 4
    score += sum(5 for p in pref if p in labels)
    if re.search(r"单依纯|单姐|@单依纯", text, re.I):
        score += 4
    if any(x in labels for x in ("绿茶", "心机女")):
        score += 6
    if 20 <= len(text) <= 120:
        score += 3
    if topic_id in ALIEN_TOPIC_IDS:
        score += 2
    return score


def _dominant_label(labels: list[str]) -> str:
    pref = ["绿茶", "心机女", "又当又立", "装无辜", "资源咖", "德不配位", "难听", "抄袭"]
    for p in pref:
        if p in labels:
            return p
    return labels[0] if labels else ""


def pick_examples(records: pd.DataFrame, n: int = 5) -> list[dict]:
    """选 n 条典型评论，优先高分且标签类型尽量不重复。"""
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
    picked: list[dict] = []
    used_labels: set[str] = set()
    used_ids: set[str] = set()

    for score, cid, labels, text, topic_id in candidates:
        if cid in used_ids:
            continue
        dom = _dominant_label(labels)
        if picked and dom in used_labels and len(picked) < n:
            continue
        picked.append({"comment_id": cid, "content": text, "labels": labels, "score": score})
        used_ids.add(cid)
        used_labels.add(dom)
        if len(picked) >= n:
            break

    if len(picked) < n:
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
        pat = next(p for n, p, _ in DISCOURSE_LABELS if n == lab)
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


def build_figure(
    freq: pd.Series,
    sankey_df: pd.DataFrame,
    examples: list[dict],
) -> go.Figure:
    bar_labels = _bar_label_list(freq)
    bar_counts = [int(freq.get(l, 0)) for l in bar_labels]
    bar_colors = [LABEL_COLORS.get(l, "#888") for l in bar_labels]
    max_c = max(bar_counts) if bar_counts else 1

    fig = go.Figure()

    fig.add_shape(
        type="rect",
        x0=0.02, y0=0.44, x1=0.52, y1=0.94,
        xref="paper", yref="paper",
        line=dict(color="rgba(74,111,165,0.25)", width=1.5),
        fillcolor="rgba(250,251,253,0.6)",
        layer="below",
    )
    fig.add_shape(
        type="rect",
        x0=0.54, y0=0.44, x1=0.99, y1=0.94,
        xref="paper", yref="paper",
        line=dict(color="rgba(176,58,58,0.2)", width=1.5),
        fillcolor="rgba(255,252,252,0.5)",
        layer="below",
    )

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
            domain=dict(x=[0.56, 0.98], y=[0.46, 0.94]),
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
                color=[f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.35)"
                       if c.startswith("#") else "rgba(150,150,150,0.35)"
                       for c in link_col],
                hovertemplate="%{source.label} → %{target.label}<br>%{value} 次<extra></extra>",
            ),
        )
    )

    markers = ["①", "②", "③", "④", "⑤"]

    fig.add_shape(
        type="rect",
        x0=0.02, y0=0.02, x1=0.99, y1=0.42,
        xref="paper", yref="paper",
        line=dict(color="rgba(176,58,58,0.35)", width=1.5),
        fillcolor="rgba(250,251,253,0.95)",
        layer="below",
    )
    fig.add_annotation(
        x=0.03,
        y=0.405,
        xref="paper",
        yref="paper",
        xanchor="left",
        yanchor="top",
        align="left",
        text="<b>典型评论 · 合理框架包装人身攻击</b>",
        showarrow=False,
        font=dict(size=26, color="#1A2A3A", family=FONT),
    )

    line_ys = [0.345, 0.278, 0.211, 0.144, 0.077]
    for i, ex in enumerate(examples[:5]):
        text = _truncate(ex["content"])
        html = highlight_labels(text, ex["labels"])
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
                f"<span style='font-size:21px;color:#666'>[{tag}]</span> "
                f"<span style='font-size:25px;color:#222'>{html}</span>"
            ),
            showarrow=False,
            width=1860,
        )

    fig.add_annotation(
        x=0.25,
        y=0.97,
        xref="paper",
        yref="paper",
        text="<b>「合理批判」话语标签</b><br><sup>表面讨论作品/立场 · 底层指向人身贬损</sup>",
        showarrow=False,
        font=dict(size=20, family=FONT, color="#1A2A3A"),
    )
    fig.add_annotation(
        x=0.77,
        y=0.97,
        xref="paper",
        yref="paper",
        text="<b>标签 → 攻击类型</b>",
        showarrow=False,
        font=dict(size=22, family=FONT, color="#1A2A3A"),
    )

    fig.update_traces(
        textfont=dict(size=16, family=FONT, color="#1A2A3A"),
        selector=dict(type="sankey"),
    )

    fig.update_layout(
        title=dict(
            text="话语标签化 · 「合理批判」框架下的人身攻击",
            x=0.5,
            xanchor="center",
            font=dict(size=28, color="#1A2A3A", family=FONT),
        ),
        font=dict(family=FONT),
        width=VIZ_W,
        height=VIZ_H,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAFBFD",
        margin=dict(l=40, r=40, t=100, b=30),
        xaxis=dict(
            domain=[0.06, 0.48],
            title=dict(text="出现次数", font=dict(size=16, family=FONT)),
            range=[0, max_c * 1.18],
            tickfont=dict(size=15, family=FONT),
            gridcolor="rgba(44,62,80,0.08)",
            zeroline=False,
        ),
        yaxis=dict(
            domain=[0.46, 0.92],
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
    sankey_df = (
        records.groupby(["label", "attack_type"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )
    sankey_df = sankey_df[sankey_df["label"].isin(freq.head(12).index)]

    examples = pick_examples(records, n=5)

    freq.to_csv(OUT / "page14_label_frequencies.csv", header=["count"], encoding="utf-8-sig")
    sankey_df.to_csv(OUT / "page14_label_sankey_links.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {
                "comment_id": ex["comment_id"],
                "content": ex["content"],
                "labels": "、".join(ex["labels"]),
            }
            for ex in examples
        ]
    ).to_csv(OUT / "page14_label_example.csv", index=False, encoding="utf-8-sig")

    n_hit = records["comment_id"].nunique()
    fig = build_figure(freq, sankey_df, examples)
    png = OUT / "page14_discourse_labeling.png"
    fig.write_image(str(png), width=VIZ_W, height=VIZ_H, scale=3)
    print(f"[输出] {png}")
    print(f"标签化评论 {n_hit} 条 · 标签命中 {len(records)} 次")
    print("Top 标签:\n", freq.head(10).to_string())
    print("\n示例 5 条:")
    for i, ex in enumerate(examples, 1):
        print(f"  {i}. [{','.join(ex['labels'])}] {ex['content'][:60]}")


if __name__ == "__main__":
    main()

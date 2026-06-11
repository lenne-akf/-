from __future__ import annotations
# -*- coding: utf-8 -*-
"""
699 粉籍子样本 · 嵌套 Logistic（粉籍 / 立场 / 标签 ΔAUC）

主体层：粉籍（单依纯 / 李荣浩 / 跨界）+ 立场光谱（道德审判 / 版权原教旨 / 乐子人；参照：路人/和事佬）
话语层：18 类话语标签（lbl_*）

因变量：话语异化 topic 4∪5（人身攻击 + 议题化人设贬损；与扶梯锚点 topic 4 相关但非同一定义）

输出：
  output/page_fenji_699_three_layer_logistic.png
  output/page_fenji_699_three_layer_coefficients.csv
  output/page_fenji_699_three_layer_layer_summary.csv
  output/page_fenji_699_three_layer_nested.csv
  output/page_fenji_699_stance_distribution.csv

运行：python plot_fenji_three_layer_logistic.py
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
CODE = Path(__file__).resolve().parent
OUT_DIR = OUT  # compat
sys.path.insert(0, str(CODE))

from discourse_label_features import (  # noqa: E402
    DISCOURSE_LABELS,
    add_label_columns,
    label_col,
    label_display,
)
from discourse_stance_features import (  # noqa: E402
    add_stance_columns,
    stance_display,
    stance_feature_cols,
)
from plot_page18_logistic_convergence import (  # noqa: E402
    FENJI_COLS,
    FONT,
    LAYER_COLORS,
    _hex_rgba,
    analysis_frame,
)

VIZ_W, VIZ_H = 1920, 1050

FENJI_SUBJECT_COLS = FENJI_COLS
STANCE_COLS = stance_feature_cols()
SUBJECT_COLS = FENJI_SUBJECT_COLS + STANCE_COLS
LABEL_NAMES = [n for n, _, _ in DISCOURSE_LABELS]
LABEL_COLS = [label_col(n) for n in LABEL_NAMES]
FEAT_COLS = SUBJECT_COLS + LABEL_COLS

# 左图三色：粉籍 / 立场 / 标签
TIER_COLORS = {
    "粉籍": "#A67C52",
    "立场": "#8B4A3A",
    "标签": "#B03A3A",
}

FEATURE_META: dict[str, tuple[str, str]] = {
    "fenji_shan": ("单依纯粉籍", "粉籍"),
    "fenji_li": ("李荣浩粉籍", "粉籍"),
    "cross_fenji": ("跨界粉籍", "粉籍"),
    **{c: (stance_display(c), "立场") for c in STANCE_COLS},
    **{label_col(n): (label_display(n), "标签") for n in LABEL_NAMES},
}


def prepare_frame() -> pd.DataFrame:
    df = analysis_frame()
    df = add_stance_columns(df)
    df = add_label_columns(df, names=LABEL_NAMES)
    return df


def _fit_auc(df: pd.DataFrame, cols: list[str]) -> tuple[LogisticRegression, float]:
    X = StandardScaler().fit_transform(df[cols].astype(float).values)
    y = df["y_alien"].values.astype(int)
    clf = LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)
    clf.fit(X, y)
    auc = float(roc_auc_score(y, clf.predict_proba(X)[:, 1]))
    return clf, auc


def coef_table(clf: LogisticRegression, cols: list[str]) -> pd.DataFrame:
    rows = []
    for col, coef in zip(cols, clf.coef_[0]):
        label, layer = FEATURE_META[col]
        rows.append(
            {
                "feature": col,
                "label": label,
                "layer": layer,
                "std_coef": float(coef),
                "abs_coef": abs(float(coef)),
                "direction": "↑异化" if coef > 0 else "↓异化",
            }
        )
    return (
        pd.DataFrame(rows)
        .query("abs_coef > 0.015")
        .sort_values("std_coef", ascending=True)
    )


def nested_blocks(df: pd.DataFrame) -> pd.DataFrame:
    """累积嵌套：粉籍 → +立场 → +话语（主体层内分步便于报告 ΔAUC）。"""
    order = [
        ("主体层·粉籍", FENJI_SUBJECT_COLS),
        ("主体层·立场", STANCE_COLS),
        ("话语层·标签", LABEL_COLS),
    ]
    base: list[str] = []
    rows = []
    prev = 0.5
    for name, cols in order:
        base = base + cols
        _, auc = _fit_auc(df, base)
        rows.append(
            {
                "block": name,
                "n_vars": len(base),
                "auc": round(auc, 4),
                "delta_auc": round(auc - prev, 4),
            }
        )
        prev = auc
    return pd.DataFrame(rows)


def coef_table_full(clf: LogisticRegression, cols: list[str]) -> pd.DataFrame:
    rows = []
    for col, coef in zip(cols, clf.coef_[0]):
        label, tier = FEATURE_META[col]
        rows.append(
            {
                "feature": col,
                "label": label,
                "layer": tier,
                "std_coef": float(coef),
                "abs_coef": abs(float(coef)),
                "direction": "↑异化" if coef > 0 else "↓异化",
            }
        )
    return pd.DataFrame(rows)


def coef_table(clf: LogisticRegression, cols: list[str]) -> pd.DataFrame:
    return (
        coef_table_full(clf, cols)
        .query("abs_coef > 0.015")
        .sort_values("std_coef", ascending=True)
    )


def tier_summary(full_coef: pd.DataFrame) -> pd.DataFrame:
    out = (
        full_coef.groupby("layer", as_index=False)
        .agg(relative_weight=("abs_coef", "sum"), n_features=("feature", "count"))
    )
    total = out["relative_weight"].sum()
    out["pct"] = (100.0 * out["relative_weight"] / total).round(1)
    order = ["粉籍", "立场", "标签"]
    out["layer_group"] = pd.Categorical(out["layer"], categories=order, ordered=True)
    return out.sort_values("layer_group").rename(columns={"layer": "tier"})


def build_convergence_panel(fig, nested: pd.DataFrame, tier_df: pd.DataFrame) -> None:
    """左 panel：自下而上 粉籍→立场→标签；红箭头沿右侧预测因变量。"""
    delta_map = dict(zip(nested["block"], nested["delta_auc"]))
    pct_map = dict(zip(tier_df["tier"], tier_df["pct"]))
    label_pct = float(pct_map.get("标签", 0))

    bx0, bx1 = 0.26, 0.76
    half = 0.07
    layers = [
        (
            "粉籍",
            "单依纯粉 · 李荣浩粉 · 跨界粉",
            0.32,
            TIER_COLORS["粉籍"],
            delta_map.get("主体层·粉籍", 0),
            pct_map.get("粉籍", 0),
            False,
        ),
        (
            "立场",
            "道德审判 · 版权原教旨 · 乐子人",
            0.54,
            TIER_COLORS["立场"],
            delta_map.get("主体层·立场", 0),
            pct_map.get("立场", 0),
            False,
        ),
        (
            "标签",
            "18 类话语标签",
            0.76,
            TIER_COLORS["标签"],
            delta_map.get("话语层·标签", 0),
            pct_map.get("标签", 0),
            True,
        ),
    ]

    fig.add_shape(
        type="rect", x0=0.02, y0=0.02, x1=0.98, y1=0.98,
        xref="x", yref="y", line=dict(width=0),
        fillcolor="rgba(250,251,253,0.95)",
    )
    fig.add_annotation(
        x=0.52, y=0.93,
        text="<b>嵌套 ΔAUC · 粉籍 → 立场 → 标签</b>",
        showarrow=False, xanchor="center",
        font=dict(size=16, color="#1A2A3A", family=FONT),
    )
    fig.add_annotation(
        x=0.52, y=0.895,
        text=(
            "<sup>↑ 灰箭头 = 模型逐层嵌套（+0.10 → +0.24 → +0.03）"
            " · 右侧红箭头 = 预测因变量 · 非因果时序</sup>"
        ),
        showarrow=False, xanchor="center",
        font=dict(size=10, color="#7F8C8D", family=FONT),
    )

    for name, subtitle, yc, color, d_auc, pct, is_label in layers:
        y0, y1 = yc - half, yc + half
        fig.add_shape(
            type="rect", x0=bx0, y0=y0, x1=bx1, y1=y1,
            xref="x", yref="y",
            line=dict(color=color, width=3.2 if is_label else 2.2),
            fillcolor=_hex_rgba(color, 0.16 if is_label else 0.10),
        )
        fig.add_shape(
            type="rect", x0=bx0, y0=y0, x1=bx0 + 0.045, y1=y1,
            xref="x", yref="y", line=dict(width=0), fillcolor=color,
        )
        fig.add_annotation(
            x=bx0 + 0.055, y=yc + 0.022,
            text=f"<b>{name}</b>  <span style='font-size:11px;color:#666'>{subtitle}</span>",
            showarrow=False, xanchor="left", yanchor="middle",
            font=dict(size=14, color="#1A2A3A", family=FONT),
        )
        if is_label:
            stat = f"嵌套 ΔAUC <b>{d_auc:+.2f}</b>  ·  |β*| <b>{pct:.0f}%</b> ↑跃升"
        else:
            stat = f"嵌套 ΔAUC <b>{d_auc:+.2f}</b>  ·  |β*| <b>{pct:.0f}%</b>"
        fig.add_annotation(
            x=bx0 + 0.055, y=yc - 0.028,
            text=stat,
            showarrow=False, xanchor="left", yanchor="middle",
            font=dict(size=11, color=color, family=FONT),
        )

    arrow_x = 0.51
    for ay, y_head, delta in [
        (0.32 + half, 0.54 - half, "+0.10"),
        (0.54 + half, 0.76 - half, "+0.24"),
    ]:
        fig.add_annotation(
            x=arrow_x, y=y_head, ax=arrow_x, ay=ay,
            xref="x", yref="y", axref="x", ayref="y",
            arrowhead=2, arrowsize=1.5, arrowwidth=3.0,
            arrowcolor="rgba(44,62,80,0.50)", showarrow=True, text="",
        )
        fig.add_annotation(
            x=arrow_x + 0.07, y=(ay + y_head) / 2,
            text=f"ΔAUC {delta}",
            showarrow=False, xanchor="left", yanchor="middle",
            font=dict(size=11, color="#5D6D7E", family=FONT),
        )

    fig.add_annotation(
        x=0.12, y=0.54,
        text="粉籍<br>↑<br>立场<br>↑<br>标签",
        showarrow=False, xanchor="center", yanchor="middle",
        font=dict(size=12, color="#7F8C8D", family=FONT),
    )

    dv_y0, dv_y1 = 0.04, 0.11
    fig.add_shape(
        type="rect", x0=0.30, y0=dv_y0, x1=0.74, y1=dv_y1,
        xref="x", yref="y",
        line=dict(color=LAYER_COLORS["结果层"], width=2.2),
        fillcolor=_hex_rgba(LAYER_COLORS["结果层"], 0.14),
    )
    fig.add_annotation(
        x=0.52, y=0.08,
        text="<b>舆论异化 / 空心化</b>  <span style='font-size:10px;color:#666'>(因变量)</span>",
        showarrow=False, xanchor="center", yanchor="middle",
        font=dict(size=13, color=LAYER_COLORS["结果层"], family=FONT),
    )

    fig.add_annotation(
        x=0.82, y=dv_y1, ax=0.82, ay=0.76 - half,
        xref="x", yref="y", axref="x", ayref="y",
        arrowhead=2, arrowsize=1.5, arrowwidth=3.2,
        arrowcolor=TIER_COLORS["标签"], showarrow=True, text="",
    )
    fig.add_annotation(
        x=0.86, y=0.42,
        text=f"预测因变量<br><sup>|β*| 标签 {label_pct:.0f}%</sup>",
        showarrow=False, xanchor="left", yanchor="middle",
        font=dict(size=10, color=TIER_COLORS["标签"], family=FONT),
    )

    fig.update_xaxes(visible=False, range=[0, 1], row=1, col=1)
    fig.update_yaxes(visible=False, range=[0, 1], row=1, col=1)


def layer_summary_grouped(coef_df: pd.DataFrame) -> pd.DataFrame:
    """双层汇总（主体=粉籍+立场 / 话语），供综合分析页对照。"""
    g = coef_df.copy()
    g["layer_group"] = g["layer"].map({"粉籍": "主体层", "立场": "主体层", "标签": "话语层"})
    out = (
        g.groupby("layer_group", as_index=False)
        .agg(relative_weight=("abs_coef", "sum"), n_features=("feature", "count"))
    )
    total = out["relative_weight"].sum()
    out["pct"] = (100.0 * out["relative_weight"] / total).round(1)
    order = ["主体层", "话语层"]
    out["layer_group"] = pd.Categorical(out["layer_group"], categories=order, ordered=True)
    return out.sort_values("layer_group")


def tier_color(tier: str) -> str:
    return TIER_COLORS.get(tier, LAYER_COLORS["主体层"])


def build_figure(
    coef_df: pd.DataFrame,
    tier_df: pd.DataFrame,
    nested: pd.DataFrame,
    auc: float,
) -> go.Figure:
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.42, 0.58],
        horizontal_spacing=0.06,
        specs=[[{"type": "xy"}, {"type": "xy"}]],
        subplot_titles=("", "Logistic 因素贡献（标准化 β*）"),
    )
    build_convergence_panel(fig, nested, tier_df)

    colors = [tier_color(r["layer"]) for _, r in coef_df.iterrows()]
    texts, positions = [], []
    for v in coef_df["std_coef"]:
        texts.append(f"{v:+.2f}")
        positions.append("inside" if abs(v) > 0.25 else "outside")

    fig.add_trace(
        go.Bar(
            y=coef_df["label"],
            x=coef_df["std_coef"],
            orientation="h",
            marker=dict(color=colors, line=dict(color="rgba(255,255,255,0.85)", width=1.2)),
            text=texts,
            textposition=positions,
            textfont=dict(size=13, color="#FFFFFF", family=FONT),
            cliponaxis=False,
            hovertemplate="%{y}<br>β* = %{x:.3f}<extra></extra>",
            showlegend=False,
        ),
        row=1, col=2,
    )
    fig.add_vline(x=0, line=dict(color="rgba(44,62,80,0.35)", width=2), row=1, col=2)
    fig.update_xaxes(
        title=dict(text="标准化系数 β*", font=dict(size=16, family=FONT), standoff=12),
        tickfont=dict(size=13, family=FONT),
        gridcolor="rgba(44,62,80,0.07)", zeroline=False, row=1, col=2,
    )
    fig.update_yaxes(tickfont=dict(size=14, family=FONT), row=1, col=2)

    for tier in ["粉籍", "立场", "标签"]:
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None], mode="markers",
                marker=dict(size=13, color=TIER_COLORS[tier], line=dict(width=1, color="#fff")),
                name=tier,
            )
        )

    fig.update_layout(
        title=dict(
            text=(
                "嵌套 Logistic · 粉籍 / 立场 / 标签"
                f"<br><sup>粉籍标注子样本 · AUC={auc:.2f} · 嵌套 ΔAUC 对比</sup>"
            ),
            x=0.5, xanchor="center",
            font=dict(size=26, color="#1A2A3A", family=FONT),
        ),
        font=dict(family=FONT),
        width=VIZ_W, height=VIZ_H,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FAFBFD",
        margin=dict(l=60, r=40, t=110, b=80),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.05,
            xanchor="center", x=0.78,
            font=dict(size=14, family=FONT),
        ),
    )
    fig.update_annotations(font=dict(size=17, family=FONT, color="#333"))
    return fig


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = prepare_frame()
    n_pos = int(df["y_alien"].sum())

    clf, auc = _fit_auc(df, FEAT_COLS)
    full_coef = coef_table_full(clf, FEAT_COLS)
    coef_df = coef_table(clf, FEAT_COLS)
    tier_df = tier_summary(full_coef)
    layer_df = layer_summary_grouped(full_coef)
    nested = nested_blocks(df)

    stance_dist = (
        df["stance_type"]
        .value_counts()
        .rename_axis("stance_type")
        .reset_index(name="count")
    )
    stance_dist["pct"] = (100 * stance_dist["count"] / len(df)).round(1)

    coef_df.to_csv(OUT / "page_fenji_699_three_layer_coefficients.csv", index=False, encoding="utf-8-sig")
    tier_df.to_csv(OUT / "page_fenji_699_three_tier_summary.csv", index=False, encoding="utf-8-sig")
    layer_df.to_csv(OUT / "page_fenji_699_three_layer_layer_summary.csv", index=False, encoding="utf-8-sig")
    nested.to_csv(OUT / "page_fenji_699_three_layer_nested.csv", index=False, encoding="utf-8-sig")
    stance_dist.to_csv(OUT / "page_fenji_699_stance_distribution.csv", index=False, encoding="utf-8-sig")
    df[["comment_id", "content", "stance_type", "y_alien"] + FEAT_COLS].to_csv(
        OUT / "page_fenji_699_three_layer_frame.csv", index=False, encoding="utf-8-sig"
    )

    fig = build_figure(coef_df, tier_df, nested, auc)
    png = OUT / "page_fenji_699_three_layer_logistic.png"
    fig.write_image(str(png), width=VIZ_W, height=VIZ_H, scale=3)

    print(f"[output] {png}")
    print(f"n={len(df)} · 异化={n_pos} · AUC={auc:.4f}")
    print("\n立场光谱分布:\n", stance_dist.to_string(index=False))
    print("\n|β| 权重（粉籍/立场/标签）:\n", tier_df.to_string(index=False))
    print("\n双层汇总:\n", layer_df.to_string(index=False))
    print("\n嵌套 ΔAUC:\n", nested.to_string(index=False))
    print("\nTop 系数:\n", coef_df.sort_values("abs_coef", ascending=False).head(12).to_string(index=False))


if __name__ == "__main__":
    main()

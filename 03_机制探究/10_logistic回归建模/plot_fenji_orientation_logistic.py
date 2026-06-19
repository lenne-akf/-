from __future__ import annotations
# -*- coding: utf-8 -*-
"""
群体话语取向分化 · 粉籍标注子样本 Logistic（三层汇聚版）

与早期 page18 同布局：左漏斗 + 右系数条
样本：699 条微博评论（有粉籍标注），说明「怎么说」>「谁在说」

输出：output/page_fenji_labeled_convergence.png
      output/page_fenji_orientation_logistic.csv

运行：python plot_fenji_orientation_logistic.py
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

from plot_page18_logistic_convergence import (  # noqa: E402
    DISCOURSE_COLS,
    FEATURE_META,
    FENJI_COLS,
    FONT,
    LAYER_COLORS,
    VIZ_W,
    _hex_rgba,
    analysis_frame,
    layer_summary,
)

VIZ_H = 1000
FEAT_COLS = ["phase_burst"] + FENJI_COLS + DISCOURSE_COLS

SUB_META = {
    "phase_burst": FEATURE_META["phase_burst"],
    **{c: FEATURE_META[c] for c in FENJI_COLS + DISCOURSE_COLS},
}


def fit_and_table(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    X = StandardScaler().fit_transform(df[FEAT_COLS].astype(float).values)
    y = df["y_alien"].values.astype(int)
    clf = LogisticRegression(max_iter=3000, class_weight="balanced", C=1.0)
    clf.fit(X, y)
    auc = float(roc_auc_score(y, clf.predict_proba(X)[:, 1]))
    rows = []
    for col, coef in zip(FEAT_COLS, clf.coef_[0]):
        label, layer = SUB_META[col]
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
    coef_df = pd.DataFrame(rows)
    coef_df = coef_df[coef_df["abs_coef"] > 0.02].sort_values("std_coef", ascending=True)
    return coef_df, auc


def build_fenji_convergence_panel(fig, layer_df: pd.DataFrame) -> None:
    pct_map = layer_df.set_index("layer")["pct"].to_dict()
    layers = [
        ("结构层", "事件阶段 · 爆发期", 0.82, LAYER_COLORS["结构层"]),
        ("主体层", "单依纯粉 · 李荣浩粉 · 跨界粉", 0.58, LAYER_COLORS["主体层"]),
        ("话语层", "情绪 · 攻击词 · 模板复读", 0.34, LAYER_COLORS["话语层"]),
    ]

    fig.add_shape(
        type="rect", x0=0.02, y0=0.02, x1=0.98, y1=0.98,
        xref="x", yref="y", line=dict(width=0),
        fillcolor="rgba(250,251,253,0.95)",
    )
    for name, subtitle, yc, color in layers:
        pct = pct_map.get(name, 0)
        fig.add_shape(
            type="rect", x0=0.10, y0=yc - 0.08, x1=0.90, y1=yc + 0.08,
            xref="x", yref="y", line=dict(color=color, width=2.5),
            fillcolor=_hex_rgba(color, 0.14),
        )
        fig.add_shape(
            type="rect", x0=0.10, y0=yc - 0.08, x1=0.16, y1=yc + 0.08,
            xref="x", yref="y", line=dict(width=0), fillcolor=color,
        )
        fig.add_annotation(
            x=0.52, y=yc + 0.02,
            text=f"<b>{name}</b>  <span style='font-size:14px;color:#555'>{subtitle}</span>",
            showarrow=False, xanchor="center",
            font=dict(size=17, color="#1A2A3A", family=FONT),
        )
        fig.add_annotation(
            x=0.52, y=yc - 0.035,
            text=f"Logistic 相对贡献 <b>{pct:.0f}%</b>",
            showarrow=False, xanchor="center",
            font=dict(size=14, color=color, family=FONT),
        )
        if yc > 0.40:
            fig.add_annotation(
                x=0.50, y=yc - 0.10, ax=0.50, ay=yc - 0.17,
                xref="x", yref="y", axref="x", ayref="y",
                arrowhead=2, arrowsize=1.3, arrowwidth=2.5,
                arrowcolor="rgba(44,62,80,0.30)", showarrow=True, text="",
            )

    fig.add_shape(
        type="rect", x0=0.18, y0=0.06, x1=0.82, y1=0.16,
        xref="x", yref="y",
        line=dict(color=LAYER_COLORS["结果层"], width=2.5),
        fillcolor=_hex_rgba(LAYER_COLORS["结果层"], 0.18),
    )
    fig.add_annotation(
        x=0.50, y=0.11,
        text="<b>舆论异化 / 空心化</b><br><sup>异化话语 · 多因素汇聚</sup>",
        showarrow=False,
        font=dict(size=18, color=LAYER_COLORS["结果层"], family=FONT),
    )
    fig.add_annotation(
        x=0.50, y=0.22, ax=0.50, ay=0.16,
        xref="x", yref="y", axref="x", ayref="y",
        arrowhead=2, arrowsize=1.5, arrowwidth=3,
        arrowcolor=LAYER_COLORS["结果层"], showarrow=True, text="",
    )
    fig.add_annotation(
        x=0.50, y=0.96,
        text="<b>三层汇聚解释框架</b><br><sup>粉籍可识别子样本 · 关联结构 · 非单线因果</sup>",
        showarrow=False,
        font=dict(size=20, color="#1A2A3A", family=FONT),
    )
    fig.update_xaxes(visible=False, range=[0, 1], row=1, col=1)
    fig.update_yaxes(visible=False, range=[0, 1], row=1, col=1)


def build_figure(coef_df: pd.DataFrame, layer_df: pd.DataFrame, auc: float, n: int) -> go.Figure:
    # 右图系数条用 SUB_META 着色
    coef_plot = coef_df.copy()
    coef_plot["feature"] = coef_plot["feature"]  # keep

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.44, 0.56],
        horizontal_spacing=0.05,
        specs=[[{"type": "xy"}, {"type": "xy"}]],
        subplot_titles=("", "Logistic 因素贡献"),
    )
    build_fenji_convergence_panel(fig, layer_df)

    colors = [LAYER_COLORS[SUB_META[f][1]] for f in coef_df["feature"]]
    texts, positions = [], []
    for v in coef_df["std_coef"]:
        texts.append(f"{v:+.2f}")
        positions.append("inside" if abs(v) > 0.35 else "outside")
    fig.add_trace(
        go.Bar(
            y=coef_df["label"],
            x=coef_df["std_coef"],
            orientation="h",
            marker=dict(color=colors, line=dict(color="rgba(255,255,255,0.85)", width=1.2)),
            text=texts, textposition=positions,
            textfont=dict(size=14, color="#FFFFFF", family=FONT),
            cliponaxis=False,
            hovertemplate="%{y}<br>β* = %{x:.3f}<extra></extra>",
            showlegend=False,
        ),
        row=1, col=2,
    )
    fig.add_vline(x=0, line=dict(color="rgba(44,62,80,0.35)", width=2), row=1, col=2)
    fig.update_xaxes(
        title=dict(text="标准化系数 β*", font=dict(size=16, family=FONT), standoff=12),
        tickfont=dict(size=14, family=FONT),
        gridcolor="rgba(44,62,80,0.07)", zeroline=False, row=1, col=2,
    )
    fig.update_yaxes(tickfont=dict(size=16, family=FONT), row=1, col=2)

    for layer in ["结构层", "主体层", "话语层"]:
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None], mode="markers",
                marker=dict(size=13, color=LAYER_COLORS[layer], line=dict(width=1, color="#fff")),
                name=layer, xaxis="x2", yaxis="y2",
            )
        )

    fig.update_layout(
        title=dict(
            text=(
                "综合解释框架"
                f"<br><sup>粉籍标注子样本 · 微博 · n={n:,} · AUC={auc:.2f}</sup>"
            ),
            x=0.5, xanchor="center",
            font=dict(size=28, color="#1A2A3A", family=FONT),
        ),
        font=dict(family=FONT),
        width=VIZ_W, height=VIZ_H,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FAFBFD",
        margin=dict(l=60, r=50, t=100, b=90),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.06,
            xanchor="center", x=0.78,
            font=dict(size=14, family=FONT),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(44,62,80,0.12)", borderwidth=1,
        ),
    )
    fig.update_annotations(font=dict(size=18, family=FONT, color="#333"), selector=dict(text="Logistic 因素贡献"))
    return fig


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = analysis_frame()
    coef_df, auc = fit_and_table(df)
    layer_df = layer_summary(coef_df)

    coef_df.to_csv(OUT / "page_fenji_orientation_logistic.csv", index=False, encoding="utf-8-sig")
    fig = build_figure(coef_df, layer_df, auc, len(df))
    png = OUT / "page_fenji_labeled_convergence.png"
    fig.write_image(str(png), width=VIZ_W, height=VIZ_H, scale=3)
    print(f"[output] {png}")
    print(layer_df.to_string(index=False))


if __name__ == "__main__":
    main()

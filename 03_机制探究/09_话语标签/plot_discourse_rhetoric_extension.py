from __future__ import annotations
# -*- coding: utf-8 -*-
"""
话语标签扩展 · 修辞类型 × 版权轴 × 阶段

回应「合理式标签需进一步下功夫」：
1. 五类修辞占比（强调仅「又如何呢」= 严格梗式合理化）
2. 版权轴评论上的修辞分布（扶梯桥接）
3. 梗式合理化 vs 论事框架化 按事件阶段

运行：python plot_discourse_rhetoric_extension.py
"""
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, V5_USER_IDS, FENJI_OUTPUT, bootstrap_sys_path

bootstrap_sys_path()

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from discourse_label_features import (  # noqa: E402
    COPYRIGHT_AXIS_TOPICS,
    MEME_RATIONALIZATION_LABELS,
    RHETORIC_CLASS_ORDER,
    RHETORIC_CLASS_PALETTE,
    STRICT_RATIONALIZATION_LABELS,
    extract_label_names,
    rhetoric_class,
)
from plot_page14_discourse_labeling import (  # noqa: E402
    _is_attack_context,
    build_label_records,
    load_pool,
)

# 事件阶段（与数据清洗包一致）
sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "数据清洗与数据概览"))
from event_phases import assign_phase  # noqa: E402

OUT_PNG = OUT / "page14_rhetoric_extension.png"
FENJI_PNG = FENJI_OUTPUT / "page14_rhetoric_extension.png"
FONT = "Microsoft YaHei, SimHei, sans-serif"


def setup_font() -> None:
    plt.rcParams.update({
        "font.sans-serif": [FONT, "DejaVu Sans"],
        "axes.unicode_minus": False,
        "font.size": 12,
    })


def comment_level_records(records: pd.DataFrame) -> pd.DataFrame:
    """每条评论一行：修辞类列表 + 是否版权轴 + 是否严格合理式。"""
    rows = []
    for cid, g in records.groupby("comment_id"):
        labels = sorted(set(g["label"]))
        rclasses = list(dict.fromkeys(rhetoric_class(l) for l in labels))
        rows.append(
            {
                "comment_id": cid,
                "topic_id": int(g["topic_id"].iloc[0]),
                "on_copyright_axis": int(g["topic_id"].iloc[0]) in COPYRIGHT_AXIS_TOPICS,
                "labels": labels,
                "rhetoric_classes": rclasses,
                "has_strict_rationalization": any(
                    l in STRICT_RATIONALIZATION_LABELS for l in labels
                ),
                "has_issue_framing": "论事框架化" in rclasses,
                "created_at": g.get("created_at", pd.Series([None])).iloc[0]
                if "created_at" in g.columns
                else None,
            }
        )
    return pd.DataFrame(rows)


def attach_phase(comments: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    meta = raw[["comment_id", "created_at"]].drop_duplicates("comment_id")
    out = comments.merge(meta, on="comment_id", how="left", suffixes=("", "_raw"))
    ts = out["created_at_raw"].fillna(out["created_at"])
    out["phase"] = [assign_phase(t) for t in ts]
    return out


def plot_extension(records: pd.DataFrame, comments: pd.DataFrame) -> None:
    setup_font()
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    fig.suptitle(
        "话语标签扩展 · 修辞类型与版权轴桥接",
        fontsize=16,
        fontweight="bold",
        y=1.02,
    )

    # --- A: 修辞类总量 ---
    ax = axes[0]
    rc = records.groupby("rhetoric_class").size().reindex(RHETORIC_CLASS_ORDER, fill_value=0)
    colors = [RHETORIC_CLASS_PALETTE[c] for c in rc.index]
    bars = ax.barh(rc.index, rc.values, color=colors, edgecolor="white")
    ax.set_xlabel("标签命中次数")
    ax.set_title("A · 五类修辞（全 v5 池）", fontweight="bold")
    ax.invert_yaxis()
    for b, v in zip(bars, rc.values):
        ax.text(v + max(rc.values) * 0.02, b.get_y() + b.get_height() / 2, str(int(v)), va="center")
    ax.text(
        0.02, 0.02,
        "仅「梗式合理化」= 借歌词/事件 meme 包装\n"
        f"（{' / '.join(MEME_RATIONALIZATION_LABELS)}）",
        transform=ax.transAxes,
        fontsize=9,
        color="#555",
        bbox=dict(boxstyle="round", facecolor="#FFF8F0", alpha=0.9),
    )

    # --- B: 版权轴上的修辞 ---
    ax = axes[1]
    cp = records[records["on_copyright_axis"]].groupby("rhetoric_class").size()
    cp = cp.reindex(RHETORIC_CLASS_ORDER, fill_value=0)
    ax.bar(
        cp.index,
        cp.values,
        color=[RHETORIC_CLASS_PALETTE[c] for c in cp.index],
        edgecolor="white",
    )
    ax.set_ylabel("标签命中次数")
    ax.set_title("B · 版权轴评论上的修辞\n(BERTopic 0/1/3)", fontweight="bold")
    ax.tick_params(axis="x", rotation=28)
    strict_n = int(comments[comments["has_strict_rationalization"] & comments["on_copyright_axis"]].shape[0])
    ax.text(
        0.5, 0.95,
        f"梗式合理化评论 {strict_n} 条\n= 标签仍在版权、话术已梗化",
        transform=ax.transAxes,
        ha="center",
        fontsize=9,
        color="#8B4513",
        bbox=dict(boxstyle="round", facecolor="#FFF8F0", alpha=0.95),
    )

    # --- C: 阶段 · 梗式 vs 论事框架（评论级）---
    ax = axes[2]
    phase_order = ["酝酿期", "爆发期", "扩散期", "回落期", "长尾期"]
    sub = comments[comments["phase"].isin(phase_order)].copy()
    series = {
        "梗式合理化": [],
        "论事框架化": [],
    }
    for ph in phase_order:
        block = sub[sub["phase"] == ph]
        series["梗式合理化"].append(int(block["has_strict_rationalization"].sum()))
        series["论事框架化"].append(int(block["has_issue_framing"].sum()))
    x = range(len(phase_order))
    w = 0.35
    ax.bar(
        [i - w / 2 for i in x],
        series["梗式合理化"],
        width=w,
        label="梗式合理化（严格）",
        color=RHETORIC_CLASS_PALETTE["梗式合理化"],
    )
    ax.bar(
        [i + w / 2 for i in x],
        series["论事框架化"],
        width=w,
        label="论事框架化",
        color=RHETORIC_CLASS_PALETTE["论事框架化"],
    )
    ax.set_xticks(list(x), phase_order, rotation=20)
    ax.set_ylabel("评论条数")
    ax.set_title("C · 阶段演化：两种「包装」路径", fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)

    plt.tight_layout()
    fig.savefig(OUT_PNG, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[输出] {OUT_PNG}")
    FENJI_OUTPUT.mkdir(parents=True, exist_ok=True)
    FENJI_PNG.write_bytes(OUT_PNG.read_bytes())
    print(f"[同步] {FENJI_PNG}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = load_pool()
    records = build_label_records(raw)
    if records.empty:
        raise RuntimeError("无标签记录，请先运行 plot_page14_discourse_labeling.py")

    raw_ts = raw[["comment_id", "created_at"]].copy()
    records = records.merge(raw_ts, on="comment_id", how="left")
    comments = attach_phase(comment_level_records(records), raw)

    comments.to_csv(OUT / "page14_rhetoric_comment_level.csv", index=False, encoding="utf-8-sig")
    plot_extension(records, comments)

    strict = comments[comments["has_strict_rationalization"]]
    print(f"梗式合理化评论 {len(strict)} 条")
    print(f"其中版权轴 {int((strict['on_copyright_axis']).sum())} 条")


if __name__ == "__main__":
    main()

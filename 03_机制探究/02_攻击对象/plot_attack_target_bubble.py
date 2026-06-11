from __future__ import annotations
# -*- coding: utf-8 -*-
"""
v5 escalator 用户池 · 攻击对象气泡图

口径：
  - 用户：copyright_axis_escalator_v5_full_user_ids.txt（3993 人）
  - 评论：该用户在本事件中的全部发言

X 轴：攻击对象（艺人；单依纯、李荣浩固定，其余艺人按频次，<5 次归「其他艺人」）
Y 轴：平均情绪得分（−1～1）
气泡大小：评论频次
气泡颜色：攻击维度

运行：python plot_attack_target_bubble.py
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from matplotlib import colors as mcolors

ROOT = Path(__file__).resolve().parent.parent
CODE = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(CODE))
# legacy path removed

from detect_organizational_attack_personal import label_subset  # noqa: E402
from discourse_target_resolver import resolve_attack_target  # noqa: E402

OUT_DIR = OUT  # compat
ID_FILE = V5_USER_IDS
RAW = OUT / "comments_with_topics.csv"
SENT = OUT / "sentiment_results.csv"

ARTIST_GROUPS = {"单依纯", "李荣浩", "其他艺人"}
ARTIST_MIN_FREQ = 5
PINNED_ARTISTS = ("单依纯", "李荣浩")

DIMENSION_RULES: list[tuple[str, re.Pattern]] = [
    (
        "人品攻击",
        re.compile(
            r"人品|道德|虚伪|撒谎|双标|忘恩负义|私德|作风|伪君子|下头|绿茶|心机|"
            r"不要脸|没教养|没素质|又当又立|小人|卑劣|渣男|做作|狂|飘|塌|丑|"
            r"恶心|贱|滚|垃圾|废物|婊|没担当|Responsible|活人品|眼小|心胸",
            re.I,
        ),
    ),
    (
        "业务能力攻击",
        re.compile(
            r"能力不行|业务差|专业素养|技术差|不懂|外行|难听|毁歌|唱功|唱得|"
            r"难[听闻]|跑调|魔改|改得|毁|抽象|难评|唱.*鬼|没作品|没实力|不配|"
            r"总监制|魔改|翻唱.*难|侮辱.*歌",
            re.I,
        ),
    ),
    (
        "言论/观点攻击",
        re.compile(
            r"说错|言论不当|双标言论|前后矛盾|误导公众|装无辜|洗白|狡辩|诡辩|"
            r"带节奏|小作文|又如何呢又能怎|挑衅|嚣张|又当又立|引导网暴|"
            r"曲解|造谣|侮辱|抹黑|扣帽子",
            re.I,
        ),
    ),
    (
        "立场/阵营攻击",
        re.compile(
            r"站队|立场问题|水军|收钱|资本走狗|罕见|恨国|营销号|有组织|买热搜|"
            r"捂嘴|资本|公关|买黑|通稿|幕后|推手|黑子|喷子|阵营|粉圈|"
            r"单黑|互撕|引战",
            re.I,
        ),
    ),
]

DIMENSION_PALETTE = {
    "其他/综合": "#BBBBBB",
    "业务能力攻击": "#0072B2",
    "人品攻击": "#D55E00",
    "言论/观点攻击": "#E69F00",
    "立场/阵营攻击": "#CC79A7",
}


def setup_fonts() -> None:
    plt.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "Arial"],
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
        "axes.facecolor": "#FAFAFA",
    })


def darken(hex_color: str, factor: float = 0.65) -> tuple:
    r, g, b = mcolors.to_rgb(hex_color)
    return (r * factor, g * factor, b * factor)


def emotion_score(sentiment_01: float, text: str, dimension: str) -> float:
    """Y 轴：以情感模型为主；仅在有明确攻击维度时做负面词微调。"""
    sn = 2.0 * float(sentiment_01) - 1.0
    if dimension == "其他/综合":
        return float(np.clip(sn, -1.0, 1.0))
    t = str(text or "")
    neg_hits = len(re.findall(
        r"难听|恶心|滚|垃圾|丑|贱|不要脸|下头|毁|难[听闻]|伪|小人|网暴|侮辱",
        t,
        re.I,
    ))
    if neg_hits:
        sn = min(sn, 0.15) - neg_hits * 0.08
    return float(np.clip(sn, -1.0, 1.0))


def dimension_hits(text: str) -> list[str]:
    return [name for name, pat in DIMENSION_RULES if pat.search(str(text or ""))]


def classify_dimension(text: str) -> str:
    hits = dimension_hits(text)
    if len(hits) >= 2:
        return "其他/综合"
    if len(hits) == 1:
        return hits[0]
    return "其他/综合"


def raw_artist_name(group: str, display: str) -> str | None:
    if group == "单依纯" or display == "单依纯":
        return "单依纯"
    if group == "李荣浩" or display == "李荣浩":
        return "李荣浩"
    if group == "其他艺人":
        return display
    return None


def build_artist_axis(atk: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """映射 X 轴艺人标签，并返回排序后的 X 轴类目。"""
    df = atk.copy()
    df["_raw_artist"] = df.apply(
        lambda r: raw_artist_name(str(r["attack_target_group"]), str(r["attack_target"])),
        axis=1,
    )

    other_counts = (
        df.loc[df["_raw_artist"].notna() & ~df["_raw_artist"].isin(PINNED_ARTISTS), "_raw_artist"]
        .value_counts()
    )
    promoted = [name for name, cnt in other_counts.items() if cnt >= ARTIST_MIN_FREQ]

    def map_x(raw: object) -> str:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return "其他"
        if raw in PINNED_ARTISTS:
            return raw
        if raw in promoted:
            return raw
        return "其他艺人"

    df["attack_target_x"] = df["_raw_artist"].apply(map_x)

    promoted_sorted = sorted(promoted, key=lambda n: -other_counts[n])
    x_order = list(PINNED_ARTISTS) + promoted_sorted
    if (df["attack_target_x"] == "其他艺人").any():
        x_order.append("其他艺人")
    # 「其他」= 未点名艺人，不进 X 轴作图
    return df.drop(columns=["_raw_artist"]), x_order


def dim_x_offsets(items: list[str]) -> dict[str, float]:
    n = len(items)
    if n <= 1:
        return {items[0]: 0.0} if items else {}
    span = min(0.55, 0.18 * (n - 1))
    step = span / (n - 1)
    start = -span / 2
    return {d: start + i * step for i, d in enumerate(items)}


def load_v5_ids() -> set[str]:
    lines = ID_FILE.read_text(encoding="utf-8").strip().splitlines()
    return {x.strip() for x in lines if x.strip()}


def build_attack_frame(uids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(RAW, dtype={"user_id": str, "comment_id": str})
    sent = pd.read_csv(SENT, dtype={"comment_id": str})[["comment_id", "sentiment_score"]]
    pool = raw[raw["user_id"].astype(str).isin(uids)].merge(sent, on="comment_id", how="left")
    pool["topic_id"] = pd.to_numeric(pool["topic_id"], errors="coerce").fillna(-1).astype(int)
    pool["sentiment_score"] = pd.to_numeric(pool["sentiment_score"], errors="coerce").fillna(0.5)

    user_stats = pd.DataFrame({"user_id": list(uids)})
    user_stats["has_attack_tendency"] = True
    user_stats["total_comments"] = user_stats["user_id"].map(
        pool.groupby("user_id").size().to_dict()
    ).fillna(0).astype(int)

    rows = []
    for _, r in pool.iterrows():
        text = str(r.get("content") or "")
        tid = int(r["topic_id"])
        dim = classify_dimension(text) if dimension_hits(text) else "其他/综合"
        ann = resolve_attack_target(text)
        rows.append({
            "user_id": r["user_id"],
            "comment_id": r["comment_id"],
            "content": text,
            "attack_dimension": dim,
            "attack_target": ann.attack_target_display,
            "attack_target_group": ann.attack_target_group,
            "attack_subset": label_subset(r) or "",
            "topic_id": tid,
            "sentiment_raw": float(r["sentiment_score"]),
            "emotion_score": emotion_score(r["sentiment_score"], text, dim),
        })

    atk = pd.DataFrame(rows)
    if atk.empty:
        return atk, user_stats

    atk, _ = build_artist_axis(atk)
    user_stats["escalator_comments"] = user_stats["user_id"].map(
        atk.groupby("user_id").size().to_dict()
    ).fillna(0).astype(int)
    return atk, user_stats


def aggregate_bubbles(atk: pd.DataFrame, x_order: list[str]) -> pd.DataFrame:
    g = (
        atk.groupby(["attack_target_x", "attack_dimension"], as_index=False)
        .agg(
            freq=("comment_id", "count"),
            mean_emotion=("emotion_score", "mean"),
            users=("user_id", "nunique"),
        )
    )
    g["x_order"] = g["attack_target_x"].map({d: i for i, d in enumerate(x_order)})
    dim_freq = g.groupby("attack_dimension")["freq"].sum().sort_values(ascending=False)
    g["dim_order"] = g["attack_dimension"].map({d: i for i, d in enumerate(dim_freq.index)})
    g = g.sort_values(["x_order", "dim_order"])
    g["extreme"] = g["mean_emotion"] < -0.8
    return g


def plot_bubble(df: pd.DataFrame, x_order: list[str], out_png: Path) -> None:
    setup_fonts()
    x_map = {d: i for i, d in enumerate(x_order)}

    dim_order = (
        df.groupby("attack_dimension")["freq"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    x_offsets = dim_x_offsets(dim_order)

    freqs = df["freq"].values
    fmin, fmax = freqs.min(), freqs.max()
    size_min, size_max = 200, 3200

    def bubble_size(f: float) -> float:
        if fmax <= fmin:
            return (size_min + size_max) / 2
        return size_min + (f - fmin) / (fmax - fmin) * (size_max - size_min)

    fig_w = max(16, 1.8 * len(x_order) + 5)
    fig, ax = plt.subplots(figsize=(fig_w, 9), dpi=180)

    for _, row in df.iterrows():
        dim = row["attack_dimension"]
        x = x_map[row["attack_target_x"]] + x_offsets.get(dim, 0.0)
        y = row["mean_emotion"]
        fill = DIMENSION_PALETTE.get(dim, "#BBBBBB")
        ax.scatter(
            x, y,
            s=bubble_size(row["freq"]),
            c=fill,
            alpha=0.50,
            edgecolors=darken(fill),
            linewidths=2.0,
            zorder=3,
        )

    ax.axhline(0, color="#888888", linestyle="--", linewidth=1.2, zorder=1)
    ax.text(
        len(x_order) - 0.45, 0.03, "中立",
        fontsize=14, color="#555555", ha="right", va="bottom",
    )

    ax.set_xticks(range(len(x_order)))
    ax.set_xticklabels(x_order, fontsize=18, fontweight="medium")
    ax.set_xlim(-0.65, len(x_order) - 0.35)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("攻击对象（艺人，按提及频次排序）", fontsize=20, labelpad=12)
    ax.set_ylabel("平均情绪得分（越负攻击越强）", fontsize=20, labelpad=12)
    ax.tick_params(axis="y", labelsize=16, width=1.2, length=6)
    ax.grid(True, linestyle="-", linewidth=0.5, color="#DDDDDD", alpha=0.9, zorder=0)
    ax.set_axisbelow(True)

    ax.set_title(
        "攻击指向气泡图：对象、情绪强度与攻击维度",
        fontsize=24,
        fontweight="bold",
        pad=20,
    )

    present_dims = [d for d in dim_order if d in set(df["attack_dimension"])]
    handles = [
        mpatches.Patch(
            facecolor=DIMENSION_PALETTE.get(d, "#BBBBBB"),
            edgecolor=darken(DIMENSION_PALETTE.get(d, "#BBBBBB")),
            linewidth=2.0,
            alpha=0.50,
            label=d,
        )
        for d in present_dims
    ]
    ax.legend(
        handles=handles,
        title="攻击维度",
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=min(len(present_dims), 3),
        fontsize=15,
        title_fontsize=17,
        frameon=True,
        edgecolor="#CCCCCC",
        fancybox=False,
    )

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.22)
    fig.savefig(out_png, bbox_inches="tight", facecolor="white", pad_inches=0.3)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    uids = load_v5_ids()
    print(f"[输入] v5 escalator 用户 {len(uids)} 人")

    atk, user_stats = build_attack_frame(uids)
    if atk.empty:
        raise SystemExit("未匹配到评论。")

    atk, x_order = build_artist_axis(atk)
    plot_atk = atk[atk["attack_target_x"] != "其他"].copy()
    bubble = aggregate_bubbles(plot_atk, x_order)
    n_with_comments = int((user_stats["total_comments"] > 0).sum())

    user_stats.to_csv(OUT / "attack_target_bubble_user_coverage.csv", index=False, encoding="utf-8-sig")
    bubble.to_csv(OUT / "attack_target_bubble_data.csv", index=False, encoding="utf-8-sig")
    atk.to_csv(OUT / "attack_target_bubble_comments.csv", index=False, encoding="utf-8-sig")
    plot_bubble(bubble, x_order, OUT / "attack_target_bubble.png")

    print(f"[X 轴艺人] {' · '.join(x_order)}")
    print(f"[评论] 全量 {len(atk)} 条 · 作图 {len(plot_atk)} 条（已排除未点名「其他」{len(atk)-len(plot_atk)} 条）")
    print(f"[X 轴分布]\n{plot_atk['attack_target_x'].value_counts().to_string()}")
    print(f"[维度分布]\n{atk['attack_dimension'].value_counts().to_string()}")
    print(f"[气泡]\n{bubble[['attack_target_x','attack_dimension','freq','mean_emotion','users']].to_string(index=False)}")
    print(f"[输出] {OUT / 'attack_target_bubble.png'}")


if __name__ == "__main__":
    main()

from __future__ import annotations
# -*- coding: utf-8 -*-
"""
页12 · 模板化攻击：短时脉冲式自发跟风
v5 escalator 全池（3993 人）· PPT 用图

检测口径：
  - 仅统计攻击类模板（短句梗 / 人身攻击词 / topic4）
  - 跨用户相同标准化文本 ≥2 用户，或 30 分钟内同模板 ≥3 条
  - 排除「支持维权」等版权控评话术

输出：
  - output/template_attack_pulse_ppt.png   主图（脉冲 + Top 模板）
  - output/template_attack_pulse_data.csv
  - output/template_attack_pulse_templates.csv
  - output/template_attack_pulse_peaks.csv

运行：python plot_template_attack_pulse.py
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

ROOT = Path(__file__).resolve().parent.parent
CODE = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(CODE))
# legacy path removed

from detect_organizational_attack import normalize_content, setup_matplotlib  # noqa: E402

MIN_TEMPLATE_HAN = 4
ORG_MIN_COUNT = 2
ORG_MIN_USERS = 2
PEAK_STD_MULT = 1.5
RE_ATTACK_SHORT = re.compile(
    r"^(难听死了|难听的要死|笑死我了|笑死|恶心死了|真不要脸)[！!…\.]*$",
    re.I,
)
ATTACK_TEMPLATE_HINT = re.compile(
    r"难听|恶心|不要脸|垃圾|贱|滚|人品|下头|绿茶|伪君子|狂|毁歌|难[听闻]|"
    r"小丑|甩锅|眼小|心胸|Responsible|又当又立|洗白|网暴|侮辱|抹黑",
    re.I,
)
ATTACK_TOPIC_ID = 4

OUT_DIR = OUT  # compat
ID_FILE = V5_USER_IDS
RAW = OUT / "comments_with_topics.csv"

BURST_WINDOW_MIN = 30
TOP_TEMPLATES = 6


def setup_ppt_fonts() -> None:
    setup_matplotlib()
    plt.rcParams.update({
        "font.size": 14,
        "axes.titlesize": 20,
        "axes.labelsize": 18,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 14,
    })


def han_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", str(text or "")))


def load_v5_pool() -> pd.DataFrame:
    uids = {
        x.strip()
        for x in ID_FILE.read_text(encoding="utf-8").splitlines()
        if x.strip()
    }
    df = pd.read_csv(RAW, dtype={"user_id": str, "comment_id": str})
    df = df[df["user_id"].astype(str).isin(uids)].copy()
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df = df[df["created_at"].notna()].copy()
    df["created_at"] = df["created_at"].dt.tz_convert("Asia/Shanghai")
    df["content_norm"] = df["content"].map(normalize_content)
    df["han_len"] = df["content"].map(han_count)
    df["topic_id"] = pd.to_numeric(df.get("topic_id"), errors="coerce").fillna(-1).astype(int)
    df["hour"] = df["created_at"].dt.floor("h")
    df["hour_label"] = df["hour"].dt.strftime("%m-%d %H:00")
    return df


def is_attack_template_text(text: str, topic_id: int = -1) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    if RE_ATTACK_SHORT.match(t):
        return True
    if int(topic_id) == ATTACK_TOPIC_ID:
        return True
    return bool(ATTACK_TEMPLATE_HINT.search(t))


def detect_template_clusters(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["han_len"] >= MIN_TEMPLATE_HAN].copy()
    sub = sub[sub.apply(lambda r: is_attack_template_text(r["content"], r.get("topic_id", -1)), axis=1)]
    grp = (
        sub.groupby("content_norm", as_index=False)
        .agg(
            count=("comment_id", "count"),
            users=("user_id", "nunique"),
            first_at=("created_at", "min"),
            last_at=("created_at", "max"),
            span_minutes=("created_at", lambda s: (s.max() - s.min()).total_seconds() / 60),
            sample=("content", "first"),
        )
        .query("count >= @ORG_MIN_COUNT")
        .sort_values(["users", "count"], ascending=False)
    )
    grp["is_org_signal"] = (grp["users"] >= ORG_MIN_USERS) | (
        (grp["count"] >= 3) & (grp["span_minutes"] <= BURST_WINDOW_MIN)
    )
    return grp


def mark_template_comments(df: pd.DataFrame, clusters: pd.DataFrame) -> pd.DataFrame:
    org_norms = set(clusters.loc[clusters["is_org_signal"], "content_norm"])
    multi_norms = set(clusters.loc[clusters["users"] >= 2, "content_norm"])

    def classify(row) -> tuple[bool, str]:
        text = str(row["content"] or "").strip()
        norm = str(row["content_norm"] or "")
        tid = int(row.get("topic_id", -1))
        if not is_attack_template_text(text, tid):
            return False, ""
        if RE_ATTACK_SHORT.match(text):
            return True, "短句梗模板"
        if norm in org_norms:
            if norm in multi_norms:
                return True, "跨用户复读"
            return True, "短时集中复读"
        return False, ""

    flags = df.apply(classify, axis=1, result_type="expand")
    df = df.copy()
    df["is_template"] = flags[0].astype(bool)
    df["template_type"] = flags[1]
    df["is_cross_user"] = df["content_norm"].isin(multi_norms)
    return df


def hourly_pulse(tpl: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    hourly = (
        tpl.groupby("hour", as_index=False)
        .agg(
            count=("comment_id", "count"),
            users=("user_id", "nunique"),
            cross_user=("is_cross_user", "sum"),
        )
        .sort_values("hour")
    )
    hourly["hour_label"] = hourly["hour"].dt.strftime("%m-%d %H:00")
    if hourly.empty:
        return hourly, 0.0
    mu = hourly["count"].mean()
    sigma = hourly["count"].std(ddof=0)
    thr = mu + PEAK_STD_MULT * sigma if sigma > 0 else mu + 1
    hourly["is_peak"] = hourly["count"] > thr
    hourly["threshold"] = thr
    return hourly, thr


def truncate_label(text: str, max_len: int = 28) -> str:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def plot_ppt(
    hourly: pd.DataFrame,
    thr: float,
    top_templates: pd.DataFrame,
    stats: dict,
    out_png: Path,
) -> None:
    setup_ppt_fonts()
    fig = plt.figure(figsize=(16, 9), dpi=180)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.35, 1.05], hspace=0.58)
    ax_pulse = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    x = np.arange(len(hourly))
    base_color = "#E74C3C"
    peak_color = "#922B21"
    colors = [peak_color if r["is_peak"] else base_color for _, r in hourly.iterrows()]
    ax_pulse.bar(x, hourly["count"], color=colors, alpha=0.82, width=0.85, edgecolor="white", linewidth=0.6)

    ax_pulse.axhline(thr, color="#2C3E50", ls="--", lw=1.8, label=f"脉冲阈值 μ+{PEAK_STD_MULT}σ = {thr:.1f}")

    step = max(1, len(hourly) // 6)
    ax_pulse.set_xticks(x[::step])
    ax_pulse.set_xticklabels(hourly["hour_label"].iloc[::step], rotation=25, ha="right")
    ax_pulse.tick_params(axis="x", pad=6)
    ax_pulse.set_ylabel("模板化评论数 / 小时")
    ax_pulse.set_title("模板化攻击 · 小时脉冲分布（v5 escalator 全池）", fontweight="bold", pad=14)
    ax_pulse.grid(axis="y", linestyle="-", alpha=0.35, color="#DDDDDD")
    ax_pulse.set_axisbelow(True)
    ax_pulse.margins(x=0.02)

    peak_rows = hourly[hourly["is_peak"]]
    for _, r in peak_rows.iterrows():
        idx = hourly.index.get_loc(r.name)
        ax_pulse.annotate(
            f"{int(r['count'])}条/{int(r['users'])}人",
            (idx, r["count"]),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=12,
            color="#641E16",
            fontweight="bold",
        )

    ax_pulse.legend(loc="upper right", frameon=True)

    if top_templates.empty:
        ax_bar.text(0.5, 0.5, "无显著模板簇", ha="center", va="center", transform=ax_bar.transAxes)
    else:
        show = top_templates.head(TOP_TEMPLATES).iloc[::-1]
        labels = [
            f"{truncate_label(r['sample'], 24)}  ({int(r['count'])}次·{int(r['users'])}人)"
            for _, r in show.iterrows()
        ]
        bar_colors = ["#C0392B" if r["users"] >= 2 else "#E67E22" for _, r in show.iterrows()]
        y = np.arange(len(show))
        ax_bar.barh(y, show["count"], color=bar_colors, alpha=0.85, edgecolor="#7B241C", linewidth=1.2)
        ax_bar.set_yticks(y)
        ax_bar.set_yticklabels(labels, fontsize=13)
        ax_bar.set_xlabel("出现次数")
        ax_bar.set_title("高频模板话术（跨用户跟风）", fontweight="bold", pad=18)
        ax_bar.grid(axis="x", linestyle="-", alpha=0.35, color="#DDDDDD")
        ax_bar.set_axisbelow(True)

        handles = [
            mpatches.Patch(facecolor="#C0392B", edgecolor="#7B241C", label="≥2 用户跨发（自发跟风）"),
            mpatches.Patch(facecolor="#E67E22", edgecolor="#7B241C", label="单用户短时复读"),
        ]
        ax_bar.legend(handles=handles, loc="lower right", fontsize=12)

    fig.subplots_adjust(top=0.96, bottom=0.08, hspace=0.58)
    fig.savefig(out_png, bbox_inches="tight", facecolor="white", pad_inches=0.2)
    plt.close(fig)


def build_peak_table(hourly: pd.DataFrame, tpl: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in hourly[hourly["is_peak"]].iterrows():
        h = r["hour"]
        sub = tpl[tpl["hour"] == h]
        vc = sub["content_norm"].value_counts()
        top_norm = vc.index[0] if len(vc) else ""
        sample = sub.loc[sub["content_norm"] == top_norm, "content"].iloc[0] if len(vc) else ""
        rows.append({
            "hour": h.strftime("%Y-%m-%d %H:00"),
            "template_count": int(r["count"]),
            "users": int(r["users"]),
            "cross_user_count": int(r["cross_user"]),
            "top_template_count": int(vc.iloc[0]) if len(vc) else 0,
            "top_template_sample": sample,
        })
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_v5_pool()
    clusters = detect_template_clusters(df)
    org_clusters = clusters[clusters["is_org_signal"]].copy()
    df = mark_template_comments(df, clusters)

    tpl = df[df["is_template"]].copy()
    hourly, thr = hourly_pulse(tpl)
    top_show = org_clusters.head(TOP_TEMPLATES).copy()
    peaks = build_peak_table(hourly, tpl)

    stats = {
        "id_users": len({
            x.strip()
            for x in ID_FILE.read_text(encoding="utf-8").splitlines()
            if x.strip()
        }),
        "pool_users": df["user_id"].nunique(),
        "pool_comments": len(df),
        "template_comments": len(tpl),
        "template_users": tpl["user_id"].nunique(),
        "cross_user_groups": int((org_clusters["users"] >= 2).sum()),
        "peak_hours": int(hourly["is_peak"].sum()) if not hourly.empty else 0,
        "threshold": round(thr, 2),
    }

    plot_ppt(hourly, thr, top_show, stats, OUT / "template_attack_pulse_ppt.png")

    summary = pd.DataFrame([stats])
    summary.to_csv(OUT / "template_attack_pulse_data.csv", index=False, encoding="utf-8-sig")
    org_clusters.to_csv(OUT / "template_attack_pulse_templates.csv", index=False, encoding="utf-8-sig")
    peaks.to_csv(OUT / "template_attack_pulse_peaks.csv", index=False, encoding="utf-8-sig")
    tpl.to_csv(OUT / "template_attack_pulse_comments.csv", index=False, encoding="utf-8-sig")

    print(f"[池] {stats['pool_users']} 人 · {stats['pool_comments']} 条评论")
    print(f"[模板化] {stats['template_comments']} 条 · {stats['template_users']} 用户")
    print(f"[跨用户模板组] {stats['cross_user_groups']} · 脉冲峰值 {stats['peak_hours']} 小时")
    if not top_show.empty:
        print("[Top 模板]")
        for _, r in top_show.head(5).iterrows():
            print(f"  · {int(r['count'])}次/{int(r['users'])}人 「{str(r['sample'])[:40]}」")
    print(f"[输出] {OUT / 'template_attack_pulse_ppt.png'}")


if __name__ == "__main__":
    main()

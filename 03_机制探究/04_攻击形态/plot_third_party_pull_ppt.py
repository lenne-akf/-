from __future__ import annotations
# -*- coding: utf-8 -*-
"""
页13 · 第三方拉踩：贬损、类比、玩梗、劝阻捆绑
v5 escalator 全池（3993 人）· PPT 用图（风格同 template_attack_pulse_ppt）

输出：
  - output/third_party_pull_ppt.png
  - output/third_party_pull_data.csv
  - output/third_party_pull_comments.csv
  - output/third_party_pull_theme_summary.csv

运行：python plot_third_party_pull_ppt.py
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

from detect_gonghuo_users import (  # noqa: E402
    OTHER_ARTISTS,
    _RE_BOT_NOISE,
    _RE_DEFEND_THIRD,
    detect_rival_compare,
    detect_third_party,
)
from detect_organizational_attack import normalize_content, setup_matplotlib  # noqa: E402
from plot_third_party_comparison_strip import infer_mode, infer_target  # noqa: E402

OUT_DIR = OUT  # compat
ID_FILE = V5_USER_IDS
RAW = OUT / "comments_with_topics.csv"

PEAK_STD_MULT = 1.5
TOP_EXAMPLES = 6

THEME_ORDER = ["对标贬损", "版权类比", "娱乐玩梗", "劝阻捆绑"]
THEME_LABEL = {
    "对标贬损": "① 贬损",
    "版权类比": "② 类比",
    "娱乐玩梗": "③ 玩梗",
    "劝阻捆绑": "④ 劝阻捆绑",
}
THEME_COLORS = {
    "对标贬损": "#922B21",
    "版权类比": "#C0392B",
    "娱乐玩梗": "#E74C3C",
    "娱乐玩梗_alt": "#E67E22",
    "劝阻捆绑": "#D35400",
}
PULSE_BASE = "#E74C3C"
PULSE_PEAK = "#922B21"

_RE_SHAN = re.compile(r"单依纯|单姐|小单|依依|依纯", re.I)
_RE_LI = re.compile(r"李荣浩|李老师|浩哥|老李", re.I)
EXTRA_ARTISTS = ["黄霄云", "黄霄雲", "常石磊"]
_RE_WARN_BIND = re.compile(
    r"别带|不要侮辱|扯.{0,8}干什么|带上.{0,8}做什么|放过.{0,6}王菲|别乱带|无关艺人|"
    r"勿乱带|不要.*捆绑|别.*拖.*下水",
    re.I,
)
_RE_MEME = re.compile(r"无所谓|玩梗|笑死|辱追|抢钱|跳大神|睡着了|wow", re.I)
_RE_EVENT_CTX = re.compile(r"单依纯|李荣浩|版权|李白|改编|侵权|维权|翻唱", re.I)


def setup_ppt_fonts() -> None:
    setup_matplotlib()
    plt.rcParams.update({
        "font.size": 16,
        "axes.titlesize": 22,
        "axes.labelsize": 20,
        "xtick.labelsize": 16,
        "ytick.labelsize": 15,
        "legend.fontsize": 15,
    })


def load_v5_pool() -> pd.DataFrame:
    uids = {x.strip() for x in ID_FILE.read_text(encoding="utf-8").splitlines() if x.strip()}
    df = pd.read_csv(RAW, dtype={"user_id": str, "comment_id": str})
    df = df[df["user_id"].astype(str).isin(uids)].copy()
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df = df[df["created_at"].notna()].copy()
    df["created_at"] = df["created_at"].dt.tz_convert("Asia/Shanghai")
    df["topic_id"] = pd.to_numeric(df.get("topic_id"), errors="coerce").fillna(-1).astype(int)
    df["hour"] = df["created_at"].dt.floor("h")
    df["hour_label"] = df["hour"].dt.strftime("%m-%d %H:00")
    df["content_norm"] = df["content"].map(normalize_content)
    return df


def mentioned_artists(text: str) -> list[str]:
    t = str(text or "")
    pool = list(dict.fromkeys(OTHER_ARTISTS + EXTRA_ARTISTS))
    found = [a for a in pool if a in t]
    return list(dict.fromkeys(found))


def is_third_party_comment(text: str) -> bool:
    t = str(text or "").strip()
    if not t or _RE_BOT_NOISE.search(t):
        return False
    if _RE_DEFEND_THIRD.search(t):
        return False
    if _RE_WARN_BIND.search(t):
        return True
    if _RE_MEME.search(t) and _RE_EVENT_CTX.search(t):
        return True
    if detect_third_party(t, ""):
        return True
    if detect_rival_compare(t):
        return True
    arts = mentioned_artists(t)
    if not arts:
        return False
    if re.search(
        r"不如|模仿|蹭|踩|拉踩|类比|年轮|版权|侵权|侮辱|仙气|疯子|"
        r"内蹭|碰瓷|对标|差远|一个王菲|就一个|难|丑",
        t,
        re.I,
    ):
        return True
    if (_RE_SHAN.search(t) or _RE_LI.search(t)) and _RE_EVENT_CTX.search(t):
        return True
    return False


def infer_purpose(text: str) -> str:
    t = str(text or "")
    if detect_rival_compare(t):
        if _RE_LI.search(t) and re.search(r"不如|比不上|咖位|周杰伦|刘德华", t):
            return "拉踩/对比李荣浩"
        return "拉踩/对比单依纯"
    if _RE_WARN_BIND.search(t):
        return "含负面词-劝阻"
    if re.search(r"版权|年轮|类比|侵权判决|方文山|张碧晨|汪苏泷", t):
        return "版权类比"
    if re.search(r"不如|模仿|蹭|踩|侮辱|仙气|疯子|内蹭|就一个王菲", t):
        if _RE_LI.search(t):
            return "拉踩/对比李荣浩"
        return "拉踩/对比单依纯"
    if re.search(r"拉踩|对比", t):
        return "拉踩/对比单依纯"
    return "含负面词-目标待读"


def classify_mode(text: str, purpose: str) -> str:
    mode = infer_mode(purpose, text, "")
    if mode != "背景提及":
        return mode
    if _RE_WARN_BIND.search(text):
        return "劝阻捆绑"
    if _RE_MEME.search(text):
        return "娱乐玩梗"
    if re.search(r"版权|年轮|类比|侵权判决|方文山|张碧晨|汪苏泷", text):
        return "版权类比"
    if re.search(r"不如|模仿|蹭|踩|侮辱|仙气|疯子|内蹭|就一个王菲|难|丑", text, re.I):
        return "对标贬损"
    return "对标贬损"


def label_third_party(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        text = str(r["content"] or "")
        if not is_third_party_comment(text):
            continue
        purpose = infer_purpose(text)
        mode = classify_mode(text, purpose)
        target = infer_target(purpose, text)
        artist = mentioned_artists(text)
        artist_str = artist[0] if artist else ("王菲" if re.search(r"王菲", text) else "其他")
        rows.append({
            "user_id": r["user_id"],
            "comment_id": r["comment_id"],
            "content": text,
            "content_norm": r["content_norm"],
            "created_at": r["created_at"],
            "hour": r["hour"],
            "hour_label": r["hour_label"],
            "topic_id": r["topic_id"],
            "compare_mode": mode,
            "compare_target": target,
            "third_artist": artist_str,
            "purpose": purpose,
        })
    return pd.DataFrame(rows)


def hourly_pulse(tp: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    hourly = (
        tp.groupby("hour", as_index=False)
        .agg(count=("comment_id", "count"), users=("user_id", "nunique"))
        .sort_values("hour")
    )
    hourly["hour_label"] = hourly["hour"].dt.strftime("%m-%d %H:00")
    if hourly.empty:
        return hourly, 0.0
    mu, sigma = hourly["count"].mean(), hourly["count"].std(ddof=0)
    thr = mu + PEAK_STD_MULT * sigma if sigma > 0 else mu + 1
    hourly["is_peak"] = hourly["count"] > thr
    return hourly, thr


def theme_panel(tp: pd.DataFrame) -> pd.DataFrame:
    """四类形态：固定展示每类条数 + 代表话术。"""
    rows = []
    for mode in THEME_ORDER:
        sub = tp[tp["compare_mode"] == mode]
        if sub.empty:
            rows.append({
                "compare_mode": mode,
                "theme_label": THEME_LABEL[mode],
                "count": 0,
                "users": 0,
                "sample": "（本池未检出）",
            })
            continue
        vc = sub.groupby("content_norm").agg(
            count=("comment_id", "count"),
            users=("user_id", "nunique"),
            sample=("content", "first"),
        ).reset_index().sort_values("count", ascending=False)
        top = vc.iloc[0]
        rows.append({
            "compare_mode": mode,
            "theme_label": THEME_LABEL[mode],
            "count": int(sub["comment_id"].count()),
            "users": int(sub["user_id"].nunique()),
            "sample": str(top["sample"]),
        })
    return pd.DataFrame(rows)


def truncate_label(text: str, max_len: int = 22) -> str:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def plot_ppt(hourly: pd.DataFrame, thr: float, examples: pd.DataFrame, theme_counts: pd.DataFrame, out_png: Path) -> None:
    setup_ppt_fonts()
    fig = plt.figure(figsize=(16, 9), dpi=180)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.35, 1.05], hspace=0.58)
    ax_pulse = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    x = np.arange(len(hourly))
    colors = [PULSE_PEAK if r["is_peak"] else PULSE_BASE for _, r in hourly.iterrows()]
    ax_pulse.bar(x, hourly["count"], color=colors, alpha=0.82, width=0.85, edgecolor="white", linewidth=0.6)
    ax_pulse.axhline(thr, color="#2C3E50", ls="--", lw=1.8, label=f"脉冲阈值 μ+{PEAK_STD_MULT}σ = {thr:.1f}")

    step = max(1, len(hourly) // 6)
    ax_pulse.set_xticks(x[::step])
    ax_pulse.set_xticklabels(hourly["hour_label"].iloc[::step], rotation=25, ha="right")
    ax_pulse.tick_params(axis="x", pad=6)
    ax_pulse.set_ylabel("第三方拉踩评论数 / 小时", fontsize=20)
    ax_pulse.set_title("第三方拉踩 · 小时脉冲分布（v5 escalator 全池）", fontweight="bold", pad=14)
    ax_pulse.grid(axis="y", linestyle="-", alpha=0.35, color="#DDDDDD")
    ax_pulse.set_axisbelow(True)
    ax_pulse.margins(x=0.02)

    for _, r in hourly[hourly["is_peak"]].iterrows():
        idx = hourly.index.get_loc(r.name)
        ax_pulse.annotate(
            f"{int(r['count'])}条/{int(r['users'])}人",
            (idx, r["count"]),
            textcoords="offset points", xytext=(0, 8),
            ha="center", fontsize=13, color="#641E16", fontweight="bold",
        )
    ax_pulse.legend(loc="upper right", frameon=True)

    if examples.empty:
        ax_bar.text(0.5, 0.5, "无显著第三方拉踩", ha="center", va="center", transform=ax_bar.transAxes)
    else:
        show = examples.iloc[::-1]
        labels = [
            f"{r['theme_label']}：{truncate_label(r['sample'])}  ({int(r['count'])}条·{int(r['users'])}人)"
            for _, r in show.iterrows()
        ]
        counts = show["count"].replace(0, 0.3).values  # 零值留可见细条
        bar_colors = [THEME_COLORS.get(r["compare_mode"], "#C0392B") for _, r in show.iterrows()]
        y = np.arange(len(show))
        ax_bar.barh(y, counts, color=bar_colors, alpha=0.85, edgecolor="#7B241C", linewidth=1.2)
        ax_bar.set_yticks(y)
        ax_bar.set_yticklabels(labels, fontsize=14)
        ax_bar.set_xlabel("出现次数", fontsize=20)
        ax_bar.set_title("四类拉踩形态 · 代表话术", fontweight="bold", pad=18)
        ax_bar.grid(axis="x", linestyle="-", alpha=0.35, color="#DDDDDD")
        ax_bar.set_axisbelow(True)

        handles = [
            mpatches.Patch(facecolor=THEME_COLORS[m], edgecolor="#7B241C", label=THEME_LABEL[m])
            for m in THEME_ORDER if m in set(show["compare_mode"])
        ]
        ax_bar.legend(handles=handles, loc="lower right", fontsize=13, title="形态", title_fontsize=14)

    fig.subplots_adjust(top=0.96, bottom=0.08, hspace=0.58)
    fig.savefig(out_png, bbox_inches="tight", facecolor="white", pad_inches=0.2)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pool = load_v5_pool()
    tp = label_third_party(pool)
    hourly, thr = hourly_pulse(tp)
    examples = theme_panel(tp)

    theme_summary = (
        tp.groupby("compare_mode", as_index=False)
        .agg(comments=("comment_id", "count"), users=("user_id", "nunique"))
    )
    theme_summary["theme_label"] = theme_summary["compare_mode"].map(THEME_LABEL)
    theme_summary = theme_summary.sort_values(
        "compare_mode", key=lambda s: s.map({m: i for i, m in enumerate(THEME_ORDER)})
    )

    stats = {
        "pool_users": pool["user_id"].nunique(),
        "pool_comments": len(pool),
        "tp_comments": len(tp),
        "tp_users": tp["user_id"].nunique(),
        "peak_hours": int(hourly["is_peak"].sum()) if not hourly.empty else 0,
        "threshold": round(thr, 2),
    }

    plot_ppt(hourly, thr, examples, theme_summary, OUT / "third_party_pull_ppt.png")

    pd.DataFrame([stats]).to_csv(OUT / "third_party_pull_data.csv", index=False, encoding="utf-8-sig")
    theme_summary.to_csv(OUT / "third_party_pull_theme_summary.csv", index=False, encoding="utf-8-sig")
    tp.to_csv(OUT / "third_party_pull_comments.csv", index=False, encoding="utf-8-sig")

    print(f"[池] {stats['pool_users']} 人 · {stats['pool_comments']} 条")
    print(f"[第三方拉踩] {stats['tp_comments']} 条 · {stats['tp_users']} 用户 · 峰值 {stats['peak_hours']} 小时")
    print(f"[四类形态]\n{theme_summary.to_string(index=False)}")
    print(f"[输出] {OUT / 'third_party_pull_ppt.png'}")


if __name__ == "__main__":
    main()

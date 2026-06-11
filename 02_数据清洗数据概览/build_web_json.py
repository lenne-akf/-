from __future__ import annotations
# -*- coding: utf-8 -*-
"""
Step 5：聚合 JSON（供网页屏 1 / 屏 2）

输入：output/cleaned_comments.csv、sentiment_results.csv、
      topic_distribution.csv、topic_naming.csv、comments_with_topics.csv
输出：overview_stats.json、analysis_viz.json
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, PKG_CLEAN, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import json
import re
from collections import Counter
from pathlib import Path

import jieba
import numpy as np
import pandas as pd

# paths via _paths

CLEANED = OUT / "cleaned_comments.csv"
SENTIMENT = OUT / "sentiment_results.csv"
TOPIC_DIST = OUT / "topic_distribution.csv"
TOPIC_NAMING = OUT / "topic_naming.csv"
COMMENTS_TOPICS = OUT / "comments_with_topics.csv"

OUT_OVERVIEW = OUT / "overview_stats.json"
OUT_ANALYSIS = OUT / "analysis_viz.json"
DASHBOARD_TEMPLATE = OVERVIEW / "数据清洗与数据概览" / "dispute_dashboard.template.html"
OUT_DASHBOARD = OVERVIEW / 'dispute_dashboard.html'

PLATFORM_LABEL = {
    "xiaohongshu": "小红书",
    "weibo": "微博",
    "douyin": "抖音",
}

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

STOP = set(
    "的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 "
    "自己 这 那 吗 吧 啊 呢 哦 嗯 哈 呀 还 把 被 让 给 对 从 而 已 以 及 与 或 但 如果 "
    "什么 怎么 为什么 可以 这个 那个 真的 感觉 觉得 就是 不是 我们 他们 你们 她 他 它 "
    "单依纯 李荣浩 李白 评论 转发 微博 视频".split()
)


def load_stopwords() -> set[str]:
    words = set(STOP)
    for fname in ("hit_stopwords.txt", "stopwords_baidu.txt", "stopwords_scu.txt"):
        path = PKG_CLEAN / fname
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "gbk"):
            try:
                raw = path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                raw = None
        if raw:
            for line in raw.splitlines():
                w = line.strip()
                if w and not w.startswith("#"):
                    words.add(w)
    return words


def parse_date_yyyy_mm_dd(raw: str) -> str | None:
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    parts = s.split()
    if len(parts) >= 4 and parts[-1].isdigit() and len(parts[-1]) == 4:
        try:
            y = int(parts[-1])
            mo = MONTH_MAP.get(parts[1], 0)
            d = int(parts[2])
            if mo:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except ValueError:
            pass
    return None


def tokenize_counter(texts: list[str], stopwords: set[str], top_n: int = 20) -> list[dict]:
    cnt: Counter[str] = Counter()
    for t in texts:
        for w in jieba.lcut(str(t)):
            w = w.strip()
            if len(w) < 2 or w in stopwords or w.isdigit():
                continue
            if re.fullmatch(r"[\W_]+", w) and not re.search(r"[\u4e00-\u9fff]", w):
                continue
            cnt[w] += 1
    return [{"word": w, "count": int(c)} for w, c in cnt.most_common(top_n)]


def to_int_like(val) -> int:
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return 0


REP_COMMENTS_PER_TOPIC = 15


def pick_topic_representatives(merged: pd.DataFrame, topic_id: int, n: int = REP_COMMENTS_PER_TOPIC) -> list[str]:
    sub = merged[merged["topic_id"] == topic_id].copy()
    if sub.empty:
        return []
    if "like_count" in sub.columns:
        sub["_likes"] = sub["like_count"].map(to_int_like)
        sub["_clen"] = sub["content"].astype(str).str.len()
        sub = sub.sort_values(["_likes", "_clen"], ascending=False)
    else:
        sub["_clen"] = sub["content"].astype(str).str.len()
        sub = sub.sort_values("_clen", ascending=False)
    seen: set[str] = set()
    out: list[str] = []
    for _, r in sub.iterrows():
        t = str(r.get("content", "")).strip()
        if len(t) < 4 or t in seen:
            continue
        seen.add(t)
        out.append(t[:320])
        if len(out) >= n:
            break
    return out


def pick_top_comments(df: pd.DataFrame, n: int = 10) -> list[dict]:
    work = df.copy()
    work["_likes"] = work["like_count"].map(to_int_like) if "like_count" in work.columns else 0
    work["_len"] = work["content"].astype(str).str.len()
    if work["_likes"].max() > 0:
        work = work.sort_values(["_likes", "_len"], ascending=False)
    else:
        work = work.sort_values("_len", ascending=False)
    rows = []
    for _, r in work.head(n).iterrows():
        plat = str(r.get("platform", ""))
        rows.append({
            "comment_id": str(r.get("comment_id", "")),
            "platform": plat,
            "platform_label": PLATFORM_LABEL.get(plat, plat),
            "content": str(r.get("content", ""))[:280],
            "like_count": int(r["_likes"]),
            "user_name": str(r.get("user_name", "")),
            "post_id": str(r.get("post_id", "")),
            "created_at": str(r.get("created_at", "")),
        })
    return rows


def build_explore(df: pd.DataFrame, overview: dict) -> dict:
    """屏1 探索页：发现卡片 + 时间阶段（仿 dashboard_template）。"""
    kpi = overview["kpi"]
    platforms = overview["platform"]
    ts = overview["time_series"]
    top_p = max(platforms, key=lambda x: x["count"]) if platforms else {"label": "—", "pct": 0, "count": 0}
    peak = max(ts, key=lambda x: x["count"]) if ts else {"date": "—", "count": 0}

    findings = [
        {
            "icon": "💬",
            "stat": f"{kpi['total_comments']:,}",
            "title": "三平台评论总量",
            "title_en": "Comment Volume",
            "detail": f"清洗后 {kpi['total_comments']:,} 条 · {kpi['total_users']:,} 用户 · {kpi['total_posts']:,} 帖子。",
        },
        {
            "icon": "📱",
            "stat": f"{top_p['pct']}%",
            "title": f"{top_p['label']}声量主导",
            "title_en": "Platform Dominance",
            "detail": f"{top_p['label']} {top_p['count']:,} 条，其余平台构成分层舆论场。",
        },
        {
            "icon": "📈",
            "stat": f"{peak['count']:,}",
            "title": f"峰值日 {peak['date']}",
            "title_en": "Peak Day",
            "detail": f"{peak['date']} 单日 {peak['count']:,} 条，时间分布呈明显起伏。",
        },
    ]

    work = df.copy()
    work["_date"] = work["created_at"].map(parse_date_yyyy_mm_dd)

    from event_phases import EVENT_PHASE_WINDOWS

    phases: list[dict] = []
    if not ts:
        plat_rows = [
            {"platform": p["platform"], "label": p["label"], "count": p["count"]}
            for p in platforms
        ]
        phases.append({
            "label": "全周期",
            "label_en": "Full Period",
            "date_start": "",
            "date_end": "",
            "count": kpi["total_comments"],
            "desc": "全部清洗评论。",
            "platform": plat_rows,
            "dominant_platform": top_p["label"],
        })
    else:
        data_max = str(work["_date"].max() or "")[:10]
        for cn, en, d0, d1 in EVENT_PHASE_WINDOWS:
            end = (d1 or data_max)[:10]
            mask = work["_date"].between(d0, end) if d0 and end else work["_date"].notna()
            sub = work[mask]
            cnt = int(len(sub))
            chunk_ts = [x for x in ts if d0 <= x["date"] <= end]
            plat_rows = []
            for plat, label in (
                ("weibo", "微博"),
                ("douyin", "抖音"),
                ("xiaohongshu", "小红书"),
            ):
                c = int((sub["platform"] == plat).sum()) if len(sub) else 0
                plat_rows.append({"platform": plat, "label": label, "count": c})
            dom = max(plat_rows, key=lambda x: x["count"])["label"] if plat_rows else "—"
            phases.append({
                "label": cn,
                "label_en": en,
                "date_start": d0,
                "date_end": end,
                "count": cnt,
                "desc": f"{d0} 至 {end}，共 {cnt:,} 条。",
                "platform": plat_rows,
                "dominant_platform": dom,
                "time_slice": chunk_ts,
            })

    return {
        "findings": findings,
        "phases": phases,
        "plat_colors": {
            "weibo": "#E67E22",
            "douyin": "#8B7AA8",
            "xiaohongshu": "#C44D6A",
        },
    }


def build_surface_3d(df: pd.DataFrame, max_points: int = 42) -> dict:
    """日期 × 平台评论量，供屏1 层叠 3D 曲面图。"""
    plat_order = [
        ("douyin", "抖音"),
        ("weibo", "微博"),
        ("xiaohongshu", "小红书"),
    ]
    work = df.copy()
    work["_date"] = work["created_at"].map(parse_date_yyyy_mm_dd)
    work = work[work["_date"].notna()]
    if work.empty:
        return {"dates": [], "layers": [], "granularity": "day"}

    cross = (
        work.groupby(["_date", "platform"], observed=True)
        .size()
        .unstack(fill_value=0)
    )
    cross = cross.sort_index()
    granularity = "day"
    if len(cross) > max_points:
        cross.index = pd.to_datetime(cross.index)
        cross = cross.resample("W", label="left").sum()
        cross = cross[cross.sum(axis=1) > 0]
        granularity = "week"
    dates = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in cross.index]
    layers = []
    for pid, label in plat_order:
        if pid in cross.columns:
            vals = [int(cross.loc[d, pid]) for d in cross.index]
        else:
            vals = [0] * len(dates)
        layers.append({"platform": pid, "label": label, "values": vals})
    matrix = []
    for pid, _ in plat_order:
        layer = next((x for x in layers if x["platform"] == pid), None)
        matrix.append(layer["values"] if layer else [0] * len(dates))

    return {
        "dates": dates,
        "layers": layers,
        "granularity": granularity,
        "heatmap": {
            "platforms": [label for _, label in plat_order],
            "platform_ids": [pid for pid, _ in plat_order],
            "matrix": matrix,
        },
        "static_image": "platform_time_surface.png",
    }


def build_overview(df: pd.DataFrame, stopwords: set[str]) -> dict:
    n = len(df)
    posts = df["post_id"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
    users = df["user_id"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()

    plat_counts = df["platform"].value_counts()
    platform = []
    for plat, cnt in plat_counts.items():
        p = str(plat)
        platform.append({
            "platform": p,
            "label": PLATFORM_LABEL.get(p, p),
            "count": int(cnt),
            "pct": round(cnt / n * 100, 2) if n else 0,
        })
    platform.sort(key=lambda x: -x["count"])

    dates = [parse_date_yyyy_mm_dd(x) for x in df["created_at"]]
    date_series = Counter(d for d in dates if d)
    time_series = [{"date": d, "count": int(c)} for d, c in sorted(date_series.items())]

    overview = {
        "meta": {
            "title": "单依纯×李荣浩《李白》争议 · 数据概览",
            "source": "cleaned_comments.csv（含微博数据2/detail_comments）",
            "generated_by": "build_web_json.py",
        },
        "kpi": {
            "total_comments": n,
            "total_posts": int(posts),
            "total_users": int(users),
        },
        "platform": platform,
        "time_series": time_series,
        "surface_3d": build_surface_3d(df),
        "word_freq_top20": tokenize_counter(df["content"].tolist(), stopwords, 20),
        "top_comments": pick_top_comments(df, 10),
    }
    overview["explore"] = build_explore(df, overview)
    try:
        from render_wordcloud_frames import build_wordcloud_timeline, render_wordcloud_frames

        wc_tl = build_wordcloud_timeline(
            df,
            overview["explore"].get("phases", []),
            lambda texts, top_n: tokenize_counter(texts, stopwords, top_n),
            parse_date_yyyy_mm_dd,
            top_n=120,
        )
        overview["wordcloud_timeline"] = render_wordcloud_frames(wc_tl)
    except Exception as exc:
        print(f"[警告] 词云时间轴未生成: {exc}")
        overview["wordcloud_timeline"] = {"mask_image": "mask.png", "frames": [], "top_n": 70}
    return overview


PLAT_ORDER = [
    ("weibo", "微博"),
    ("douyin", "抖音"),
    ("xiaohongshu", "小红书"),
]
SENT_ORDER = ["积极", "中性", "消极"]


def build_platform_compare(merged: pd.DataFrame, topic_df: pd.DataFrame, top_topics: int = 8) -> dict:
    """屏3：分平台情感结构 + 主主题分布矩阵。"""
    sentiment_by_platform = []
    for pid, label in PLAT_ORDER:
        sub = merged[merged["platform"].astype(str) == pid]
        n = len(sub)
        items = []
        for lab in SENT_ORDER:
            c = int((sub["sentiment_label"] == lab).sum()) if n else 0
            items.append({
                "label": lab,
                "count": c,
                "pct": round(c / n * 100, 2) if n else 0,
            })
        scores = sub["sentiment_score"].astype(float) if n else pd.Series(dtype=float)
        sentiment_by_platform.append({
            "platform": pid,
            "label": label,
            "total": n,
            "mean_score": round(float(scores.mean()), 4) if n else 0,
            "items": items,
        })

    name_map = {int(r["topic_id"]): str(r["chinese_name"]) for _, r in topic_df.iterrows()}
    sub_topics = merged[merged["topic_id"].fillna(-1).astype(int) >= 0] if "topic_id" in merged.columns else merged.iloc[0:0]
    topic_columns: list[dict] = []
    topic_matrix: list[dict] = []
    if len(sub_topics):
        top_ids = (
            sub_topics.groupby("topic_id")
            .size()
            .sort_values(ascending=False)
            .head(top_topics)
            .index.tolist()
        )
        topic_columns = [
            {
                "topic_id": int(tid),
                "name": name_map.get(int(tid), f"主题 {int(tid)}"),
            }
            for tid in top_ids
        ]
        for pid, label in PLAT_ORDER:
            sub = sub_topics[sub_topics["platform"].astype(str) == pid]
            cells = []
            counts = []
            for col in topic_columns:
                tid = col["topic_id"]
                c = int((sub["topic_id"] == tid).sum())
                counts.append(c)
                cells.append({"topic_id": tid, "name": col["name"], "count": c})
            row_total = sum(counts)
            row_div = row_total or 1
            for cell in cells:
                cell["row_pct"] = round(100 * cell["count"] / row_div, 2)
            topic_matrix.append({
                "platform": pid,
                "label": label,
                "row_total": int(row_total),
                "cells": cells,
            })
        # 列内占比：各主题在三平台间的结构
        for j, col in enumerate(topic_columns):
            tid = col["topic_id"]
            col_sum = sum(
                int((sub_topics[sub_topics["platform"].astype(str) == pid]["topic_id"] == tid).sum())
                for pid, _ in PLAT_ORDER
            ) or 1
            for row in topic_matrix:
                if j < len(row["cells"]):
                    row["cells"][j]["col_pct"] = round(100 * row["cells"][j]["count"] / col_sum, 2)

    return {
        "sentiment_by_platform": sentiment_by_platform,
        "topic_columns": topic_columns,
        "topic_matrix": topic_matrix,
    }


def load_topic_table() -> pd.DataFrame:
    from topic_labels import label_from_keywords

    dist = pd.read_csv(TOPIC_DIST, encoding="utf-8-sig")
    # 驾驶舱仅展示主报告主题（≥80 条）；碎屑簇 4/5 等不并入屏 2

    if TOPIC_NAMING.exists():
        naming = pd.read_csv(TOPIC_NAMING, encoding="utf-8-sig")
        cols = ["topic_id", "chinese_name"]
        if "命名参考" in naming.columns:
            cols.append("命名参考")
        dist = dist.merge(naming[cols], on="topic_id", how="left")

    def _clean_name(val) -> str:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        s = str(val).strip()
        return "" if s.lower() == "nan" else s

    def name_row(r):
        cn = _clean_name(r.get("chinese_name"))
        if cn:
            return cn
        ref = _clean_name(r.get("命名参考"))
        if ref and ref != "版权维权与抄袭争议":
            return ref
        return label_from_keywords(int(r["topic_id"]), str(r.get("keywords", "")))

    dist["chinese_name"] = dist.apply(name_row, axis=1)
    used: dict[str, int] = {}
    unique = []
    for _, r in dist.iterrows():
        n = str(r["chinese_name"])
        if n in used:
            n = f"{n}（ID{int(r['topic_id'])}）"
        used[n] = used.get(n, 0) + 1
        unique.append(n)
    dist["chinese_name"] = unique
    return dist.sort_values("doc_count", ascending=False).reset_index(drop=True)


def build_analysis(
    sentiment_df: pd.DataFrame,
    topic_df: pd.DataFrame,
    merged: pd.DataFrame,
) -> dict:
    n = len(sentiment_df)
    sent_order = ["积极", "中性", "消极"]
    vc = sentiment_df["sentiment_label"].value_counts()
    sentiment_items = []
    for lab in sent_order:
        c = int(vc.get(lab, 0))
        sentiment_items.append({
            "label": lab,
            "count": c,
            "pct": round(c / n * 100, 2) if n else 0,
        })

    topics = []
    for _, r in topic_df.iterrows():
        tid = int(r["topic_id"])
        kws = [k.strip() for k in str(r["keywords"]).split(",") if k.strip()][:8]
        reps = pick_topic_representatives(merged, tid, REP_COMMENTS_PER_TOPIC)
        if len(reps) < REP_COMMENTS_PER_TOPIC:
            for i in range(1, 4):
                col = f"representative_comment_{i}"
                if col not in r.index or pd.isna(r[col]):
                    continue
                t = str(r[col]).strip()[:320]
                if t and t not in reps:
                    reps.append(t)
        topics.append({
            "topic_id": tid,
            "chinese_name": str(r["chinese_name"]),
            "doc_count": int(r["doc_count"]),
            "keywords": kws,
            "representative_comments": reps[:REP_COMMENTS_PER_TOPIC],
        })

    cross = []
    if "topic_id" in merged.columns:
        sub = merged[merged["topic_id"] >= 0]
        name_map = {int(r["topic_id"]): str(r["chinese_name"]) for _, r in topic_df.iterrows()}
        for tid in sorted(sub["topic_id"].unique()):
            g = sub[sub["topic_id"] == tid]
            row = {
                "topic_id": int(tid),
                "chinese_name": name_map.get(int(tid), f"主题 {tid}"),
                "total": len(g),
            }
            for lab in sent_order:
                row[lab] = int((g["sentiment_label"] == lab).sum())
            cross.append(row)
        cross.sort(key=lambda x: -x["total"])

    scores = sentiment_df["sentiment_score"].astype(float)
    hist, edges = np.histogram(scores, bins=20, range=(0.0, 1.0))
    histogram = [
        {
            "bin_start": round(float(edges[i]), 3),
            "bin_end": round(float(edges[i + 1]), 3),
            "count": int(hist[i]),
        }
        for i in range(len(hist))
    ]

    return {
        "meta": {
            "title": "情感与主题分析",
            "sources": [
                "sentiment_results.csv",
                "topic_distribution.csv",
                "topic_naming.csv",
                "comments_with_topics.csv",
            ],
        },
        "sentiment": {
            "total": n,
            "mean_score": round(float(scores.mean()), 4),
            "items": sentiment_items,
            "thresholds": {"positive": 0.65, "negative": 0.35},
            "histogram": histogram,
        },
        "topics": topics,
        "sentiment_by_topic": cross,
        "topic_network": {},
        "assets": {
            "sentiment_chart": "sentiment_distribution.png",
            "topic_chart": "topic_viz.png",
            "topic_intertopic_chart": "topic_viz_intertopic.png",
        },
        "notes": {
            "sentiment": "积极/中性/消极为 SnowNLP 文本情感，非站队立场",
            "topics": "仅含 topic_distribution 主报告主题；topic_id=-1 为离群",
        },
    }


def _script_safe_json(obj: dict) -> str:
    """内嵌到 <script>，避免 </script> 截断。"""
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e")


def build_standalone_dashboard(overview: dict, analysis: dict) -> None:
    if not DASHBOARD_TEMPLATE.exists():
        print(f"跳过单页 HTML：未找到 {DASHBOARD_TEMPLATE.name}")
        return
    template = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    payload = _script_safe_json({"overview": overview, "analysis": analysis})
    inject = f"window.__DISPUTE__ = {payload};"
    html = template.replace("/*__BUILD_INJECT__*/", inject)
    OUT_DASHBOARD.write_text(html, encoding="utf-8")
    print(f"已保存: {OUT_DASHBOARD}（双击即可打开，无需 http.server）")


def verify(overview: dict, analysis: dict, df: pd.DataFrame, sentiment_df: pd.DataFrame) -> None:
    assert overview["kpi"]["total_comments"] == len(df)
    assert sum(x["count"] for x in overview["platform"]) == len(df)
    assert analysis["sentiment"]["total"] == len(sentiment_df)
    ssum = sum(x["count"] for x in analysis["sentiment"]["items"])
    assert ssum == len(sentiment_df)
    print("验收: KPI 与 CSV 行数一致")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jieba.setLogLevel(jieba.logging.INFO)

    df = pd.read_csv(CLEANED, encoding="utf-8-sig")
    sentiment_df = pd.read_csv(SENTIMENT, encoding="utf-8-sig")
    topic_df = load_topic_table()

    if COMMENTS_TOPICS.exists():
        topics_df = pd.read_csv(COMMENTS_TOPICS, encoding="utf-8-sig")
        merged = sentiment_df.merge(
            topics_df[["comment_id", "topic_id"]],
            on="comment_id",
            how="left",
        )
    else:
        merged = sentiment_df.copy()
        merged["topic_id"] = -1

    stopwords = load_stopwords()
    overview = build_overview(df, stopwords)
    analysis = build_analysis(sentiment_df, topic_df, merged)
    overview["platform_compare"] = build_platform_compare(merged, topic_df)
    try:
        from render_wordcloud_frames import (
            build_platform_wordcloud,
            render_platform_wordcloud_frames,
        )

        pwc = build_platform_wordcloud(
            df,
            overview["explore"].get("phases", []),
            lambda texts, top_n: tokenize_counter(texts, stopwords, top_n),
            parse_date_yyyy_mm_dd,
            top_n=100,
        )
        overview["platform_wordcloud"] = render_platform_wordcloud_frames(pwc)
    except Exception as exc:
        print(f"[警告] 分平台词云未生成: {exc}")
        overview["platform_wordcloud"] = {
            "output_dir": "output/wordcloud_platform",
            "platforms": [{"platform": p, "label": l} for p, l in PLAT_ORDER],
            "frames": [],
        }
    try:
        from build_topic_escalator import build_topic_escalator

        analysis["topic_escalator"] = build_topic_escalator(
            merged,
            topic_df,
            parse_date_yyyy_mm_dd,
            source_topic_id=0,
            target_topic_id=4,
        )
    except Exception as exc:
        print(f"[警告] 主题扶梯未生成: {exc}")
        analysis["topic_escalator"] = {}

    try:
        from build_topic_network import build_topic_id_network

        analysis["topic_network"] = build_topic_id_network(
            merged,
            topic_df,
            overview.get("explore", {}).get("phases", []),
            parse_date_yyyy_mm_dd,
            max_weeks=28,
            users_per_week=100,
            global_users=100,
        )
    except Exception as exc:
        print(f"[警告] 主题网络未生成: {exc}")
        analysis["topic_network"] = {}

    try:
        from plot_topic_tendency_timeline import main as plot_topic_tendency_timeline

        plot_topic_tendency_timeline()
    except Exception as exc:
        print(f"[警告] 主题倾向静态图未生成: {exc}")

    try:
        from plot_escalator_burst_timeline import main as plot_escalator_burst_timeline

        plot_escalator_burst_timeline()
    except Exception as exc:
        print(f"[警告] 扶梯爆发静态图未生成: {exc}")

    try:
        from plot_topic_network_phases import main as plot_topic_network_phases

        plot_topic_network_phases()
    except Exception as exc:
        print(f"[警告] 主题网络四阶段拼图未生成: {exc}")

    OUT_OVERVIEW.write_text(
        json.dumps(overview, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    OUT_ANALYSIS.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    json.loads(OUT_OVERVIEW.read_text(encoding="utf-8"))
    json.loads(OUT_ANALYSIS.read_text(encoding="utf-8"))
    verify(overview, analysis, df, sentiment_df)

    print(f"已保存: {OUT_OVERVIEW}")
    print(f"已保存: {OUT_ANALYSIS}")
    print(f"屏1: 评论 {overview['kpi']['total_comments']:,} · 平台 {len(overview['platform'])} · "
          f"趋势 {len(overview['time_series'])} 天")
    pc = overview.get("platform_compare") or {}
    n_pwc = len((overview.get("platform_wordcloud") or {}).get("frames", []))
    esc = analysis.get("topic_escalator") or {}
    esc_sum = esc.get("summary") or {}
    print(f"屏2: 情感 {analysis['sentiment']['total']:,} · 主题 {len(analysis['topics'])} · "
          f"交叉表 {len(analysis['sentiment_by_topic'])} 行 · "
          f"扶梯用户 {esc_sum.get('user_count', 0)}")
    print(f"屏3: 分平台情感 {len(pc.get('sentiment_by_platform', []))} · "
          f"主题列 {len(pc.get('topic_columns', []))} · 分平台词云帧 {n_pwc}")
    build_standalone_dashboard(overview, analysis)

    try:
        from render_platform_surface import render_surface_png

        if overview.get("surface_3d", {}).get("dates"):
            render_surface_png(overview["surface_3d"], OUT / "platform_time_surface.png")
    except Exception as exc:
        print(f"[警告] 静态曲面图未生成: {exc}")

    wc = overview.get("wordcloud_timeline") or {}
    n_wc = sum(1 for f in wc.get("frames", []) if f.get("image"))
    if n_wc:
        print(f"[词云] 已生成 {n_wc} 张阶段词云 (mask.png → output/wordcloud/)")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Step 6：聚合 JSON 并构建驾驶舱（屏3：三平台对比 + 用户画像）

输入：cleaned_comments.csv
输出：overview_stats.json、屏3数据明细.txt（HTML 由 用户画像分析.py 生成 屏3_仪表盘.html）
"""
from __future__ import annotations

import sys
from pathlib import Path as _Path
_R = _Path(__file__).resolve().parent.parent
if str(_R) not in sys.path:
    sys.path.insert(0, str(_R))
import 项目路径 as P

import json
import re
from collections import Counter
from pathlib import Path

import jieba
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
WORKSPACE = P.根目录
OUT = P.中间结果
USER_PROFILE_STATS = P.用户画像统计

CLEANED = OUT / "cleaned_comments.csv"

OUT_OVERVIEW = P.概览JSON
OUT_SCREEN3 = OUT / "screen3_data.txt"
OUT_SCREEN3_ROOT = P.屏3导出

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
        path = ROOT / fname
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
    """探索页：发现卡片 + 时间阶段。"""
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

    phase_labels = [
        ("酝酿期", "Emergence"),
        ("爆发期", "Outbreak"),
        ("扩散期", "Diffusion"),
        ("回落期", "Cooldown"),
        ("长尾期", "Tail"),
    ]
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
        n_phases = min(5, max(2, len(ts) // 4))
        chunk = max(1, (len(ts) + n_phases - 1) // n_phases)
        for i in range(n_phases):
            chunk_ts = ts[i * chunk : (i + 1) * chunk if i < n_phases - 1 else len(ts)]
            if not chunk_ts:
                continue
            d0, d1 = chunk_ts[0]["date"], chunk_ts[-1]["date"]
            cnt = sum(x["count"] for x in chunk_ts)
            mask = work["_date"].between(d0, d1) if d0 and d1 else work["_date"].notna()
            sub = work[mask]
            plat_rows = []
            for plat, label in (
                ("weibo", "微博"),
                ("douyin", "抖音"),
                ("xiaohongshu", "小红书"),
            ):
                c = int((sub["platform"] == plat).sum()) if len(sub) else 0
                plat_rows.append({"platform": plat, "label": label, "count": c})
            dom = max(plat_rows, key=lambda x: x["count"])["label"] if plat_rows else "—"
            cn, en = phase_labels[i] if i < len(phase_labels) else (f"阶段{i+1}", f"Phase {i+1}")
            phases.append({
                "label": cn,
                "label_en": en,
                "date_start": d0,
                "date_end": d1,
                "count": cnt,
                "desc": f"{d0} 至 {d1}，共 {cnt:,} 条（阶段内按日累计）。",
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
    """日期 × 平台评论量，供分平台堆叠面积图。"""
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
    return overview


def load_user_profile_stats() -> dict | None:
    if not USER_PROFILE_STATS.exists():
        print(f"[警告] 未找到 {USER_PROFILE_STATS.name}，屏3 用户画像需先运行 user_profile_analysis.py")
        return None
    return json.loads(USER_PROFILE_STATS.read_text(encoding="utf-8"))


def export_screen3_txt(overview: dict, user_profile: dict | None) -> None:
    """导出屏3（三平台对比 + 用户画像）全部图表数据为可读 txt。"""
    lines: list[str] = [
        "=" * 72,
        "屏3 · 三平台对比与用户画像 · 数据明细",
        f"生成: build_web_json.py · 事件: 单依纯×李荣浩《李白》争议",
        "=" * 72,
        "",
    ]

    # ── A. 三平台概览 ──
    lines += ["【A. 三平台声量概览】", ""]
    kpi = overview.get("kpi") or {}
    lines.append(f"  全样本评论: {kpi.get('total_comments', 0):,} 条")
    for p in overview.get("platform") or []:
        lines.append(
            f"  {p.get('label', p.get('platform'))}: "
            f"{p.get('count', 0):,} 条 ({p.get('pct', 0)}%)"
        )
    lines.append("")

    # ── B. 评论量随时间（分平台堆叠） ──
    surf = overview.get("surface_3d") or {}
    dates = surf.get("dates") or []
    layers = surf.get("layers") or []
    if dates and layers:
        lines += ["【B. 评论量随时间变化（分平台 · 周聚合）】", ""]
        header = f"  {'日期':<12}" + "".join(f"{ly.get('label', ''):>10}" for ly in layers)
        lines.append(header)
        for i, d in enumerate(dates):
            row = f"  {d:<12}"
            for ly in layers:
                vals = ly.get("values") or []
                v = vals[i] if i < len(vals) else 0
                row += f"{v:>10,}"
            lines.append(row)
        lines.append("")

    # ── C. 用户画像 ──
    if not user_profile:
        lines += [
            "【C. 用户画像与立场光谱】",
            "  （未生成：请先运行 python user_profile_analysis.py）",
            "",
        ]
    else:
        meta = user_profile.get("meta") or {}
        summary = user_profile.get("summary") or {}
        lines += [
            "【C. 用户画像与立场光谱】",
            f"  分析单元: user_id · 全样本用户 {summary.get('analysisUsers', 0):,} "
            f"（含未分类 {summary.get('unclassifiedCount', summary.get('excludedUnclassified', 0)):,}）",
            f"  反转节点: {meta.get('reversalDate', '2026-04-01')} · {meta.get('reversalNote', '')}",
            f"  方法: {meta.get('method', '')}",
            "",
        ]
        if meta.get("historyEnrichment"):
            he = meta["historyEnrichment"]
            lines.append(
                f"  历史博文增强: 爬取 {he.get('targets', 0)} 人，"
                f"成功 {he.get('fetched', 0)} 人，新分类 {he.get('reclassified', 0)} 人"
            )
            lines.append("")

        lines += ["  F1. 立场类型占比（Wilson 95% CI）", ""]
        for d in user_profile.get("typeDistribution") or []:
            if d.get("count", 0) == 0:
                continue
            lines.append(
                f"    {d.get('type')}: {d.get('count')} ({d.get('pct')}%)  "
                f"CI [{d.get('ci_low')}%, {d.get('ci_high')}%]"
            )
        lines.append("")

        lines += ["  F2. 平台 × 用户类型", ""]
        for p in user_profile.get("platformCross") or []:
            lines.append(f"    {p.get('platform')} (n={p.get('total')}):")
            top = sorted(
                (p.get("counts") or {}).items(),
                key=lambda x: -x[1],
            )[:5]
            for st, c in top:
                if c:
                    pct = (p.get("pcts") or {}).get(st, 0)
                    lines.append(f"      {st}: {c} ({pct}%)")
            lines.append("")

        lines += ["  F3. 用户类型 × 情绪强度", ""]
        for ec in user_profile.get("emotionCross") or []:
            lines.append(
                f"    {ec.get('type')}: mean={ec.get('mean')} median={ec.get('median')} "
                f"Q1={ec.get('q1')} Q3={ec.get('q3')} (n={ec.get('count')})"
            )
        lines.append("")

        lines += ["  F4. 时间阶段 × 用户类型", ""]
        for ph in user_profile.get("phaseCross") or []:
            lines.append(f"    {ph.get('phase')} (n={ph.get('total')}):")
            for st, c in sorted((ph.get("counts") or {}).items(), key=lambda x: -x[1]):
                if c:
                    pct = (ph.get("pcts") or {}).get(st, 0)
                    lines.append(f"      {st}: {c} ({pct}%)")
            lines.append("")

        ps = user_profile.get("profileSummary") or {}
        lines += ["  F5. 粉丝归属 / 职业线索 Top", ""]
        for k, v in (ps.get("fanGroup") or {}).items():
            lines.append(f"    粉丝: {k}: {v}")
        for k, v in list((ps.get("occupation") or {}).items())[:6]:
            lines.append(f"    职业: {k}: {v}")
        lines.append("")

        lines += [
            f"  F7. 摇摆型用户 (n={summary.get('swingCount', 0)}, "
            f"{summary.get('swingPct', 0)}%)",
            "  规则：两者都夸单依纯+李荣浩，或两者都骂",
            "",
        ]
        for u in (user_profile.get("topSwingUsers") or [])[:15]:
            lines.append(
                f"    @{u.get('user_name', '—')}: "
                f"李荣浩向{u.get('pro_lrh', 0)} / 单依纯向{u.get('pro_syc', 0)} · "
                f"{u.get('platforms', '')} · "
                f"{(u.get('sample') or '')[:50]}"
            )
        lines.append("")

        uncl = user_profile.get("unclassifiedReasons") or {}
        if uncl:
            lines += ["  F8. 未分类用户说明", ""]
            total_uncl = summary.get("excludedUnclassified", 0)
            lines.append(f"    合计 {total_uncl:,} 人")
            for reason, cnt in (uncl.get("reasonCounts") or {}).items():
                lines.append(f"      · {reason}: {cnt:,}")
            lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    OUT_SCREEN3.write_text(text, encoding="utf-8")
    OUT_SCREEN3_ROOT.write_text(text, encoding="utf-8")
    print(f"已保存: {OUT_SCREEN3}")
    print(f"已同步: {OUT_SCREEN3_ROOT}")


def verify(overview: dict, df: pd.DataFrame) -> None:
    assert overview["kpi"]["total_comments"] == len(df)
    assert sum(x["count"] for x in overview["platform"]) == len(df)
    print("验收: KPI 与 CSV 行数一致")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jieba.setLogLevel(jieba.logging.INFO)

    df = pd.read_csv(CLEANED, encoding="utf-8-sig")

    stopwords = load_stopwords()
    overview = build_overview(df, stopwords)

    OUT_OVERVIEW.write_text(
        json.dumps(overview, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    json.loads(OUT_OVERVIEW.read_text(encoding="utf-8"))
    verify(overview, df)

    print(f"已保存: {OUT_OVERVIEW}")
    print(f"驾驶舱: 评论 {overview['kpi']['total_comments']:,} 条")
    user_profile = load_user_profile_stats()
    export_screen3_txt(overview, user_profile)


if __name__ == "__main__":
    main()

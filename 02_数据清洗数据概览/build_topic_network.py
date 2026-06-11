from __future__ import annotations
# -*- coding: utf-8 -*-
"""用户节点 × 主题集聚 · 按周连续快照，供 D3 平滑插值播放。"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import math
from collections import defaultdict

import pandas as pd

TOPIC_COLORS = [
    "#c9a962", "#3db88a", "#8b7aa8", "#e67e22", "#5c7a8a",
    "#e05a7a", "#722f37", "#9a3050",
]


def _topic_layout(
    topic_ids: list[int],
    cx: float = 0.5,
    cy: float = 0.48,
    radius: float = 0.19,
) -> dict[str, list[float]]:
    """固定主题锚点，六主题紧凑圆环。"""
    n = max(1, len(topic_ids))
    out: dict[str, list[float]] = {}
    for i, tid in enumerate(sorted(topic_ids)):
        ang = 2 * math.pi * i / n - math.pi / 2
        out[str(tid)] = [cx + radius * math.cos(ang), cy + radius * math.sin(ang)]
    return out


def _week_ranges(work: pd.DataFrame, parse_date_fn, max_weeks: int = 36) -> list[dict]:
    dates = work["_date"].dropna()
    if dates.empty:
        return [{"label": "全周期", "date_start": "", "date_end": "", "week_key": "all"}]
    grp = work.assign(_dt=pd.to_datetime(work["_date"], errors="coerce")).dropna(subset=["_dt"])
    grp = grp.set_index("_dt").groupby(pd.Grouper(freq="W-MON", label="left"))
    ranges: list[dict] = []
    for wk, g in grp:
        if g.empty:
            continue
        ranges.append({
            "label": str(wk)[:10] if hasattr(wk, "__str__") else str(wk),
            "date_start": g["_date"].min(),
            "date_end": g["_date"].max(),
            "week_key": str(wk),
        })
    if len(ranges) > max_weeks:
        step = max(1, len(ranges) // max_weeks)
        ranges = ranges[::step][:max_weeks]
    return ranges or [{"label": "全周期", "date_start": "", "date_end": "", "week_key": "all"}]


def _topic_vector(counts: dict[int, int], topic_ids: list[int]) -> list[float]:
    return [float(counts.get(t, 0)) for t in topic_ids]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


def _jitter(uid: str, salt: str = "") -> tuple[float, float]:
    h = hash(uid + salt) % 10000
    ang = 2 * math.pi * h / 10000
    dist = 0.012 + (hash(uid + salt + "r") % 100) / 5500
    return dist * math.cos(ang), dist * math.sin(ang)


def _pull_toward_4(vec: dict[int, int], cnt: int, tid: int) -> tuple[float, float]:
    """按用户当周评论中主题4占比，计算向簇4锚点的轻微偏移强度。"""
    c = max(1, cnt)
    w4 = float(vec.get(4, 0)) / c
    if tid == 4 or w4 < 0.02:
        return 0.0, round(w4, 3)
    # 占比越高偏移越大，上限压低以免过于夸张
    strength = min(0.24, w4 * 0.68)
    if tid in {0, 1, 3} and w4 >= 0.06:
        strength = min(0.28, strength + w4 * 0.1)
    return round(strength, 3), round(w4, 3)


def build_topic_id_network(
    merged: pd.DataFrame,
    topic_df: pd.DataFrame,
    phases: list[dict] | None,
    parse_date_fn,
    min_edge_weight: float = 0.32,
    max_weeks: int = 32,
    users_per_week: int = 100,
    global_users: int = 100,
    escalator_user_ids: list[str] | None = None,
) -> dict:
    """节点=user_id，颜色=窗口内主导主题，位置=主题锚点，边=评论主题向量余弦相似。"""
    del escalator_user_ids  # 保留参数兼容 build_web_json 旧调用

    work = merged[merged["topic_id"] >= 0].copy()
    work["_date"] = work["created_at"].map(parse_date_fn)
    work = work[work["_date"].notna()]

    topics_meta = []
    topic_ids: list[int] = []
    for _, r in topic_df.iterrows():
        tid = int(r["topic_id"])
        topic_ids.append(tid)
        name = str(r.get("chinese_name") or f"主题 {tid}")
        topics_meta.append({
            "topic_id": tid,
            "name": name,
            "short_name": name[:10] + ("…" if len(name) > 10 else ""),
            "doc_count": int(r["doc_count"]),
            "color": TOPIC_COLORS[tid % len(TOPIC_COLORS)],
        })

    layout = _topic_layout(topic_ids)
    week_defs = _week_ranges(work, parse_date_fn, max_weeks=max_weeks)

    uid_col = "user_id"
    if uid_col not in work.columns:
        work[uid_col] = work.index.astype(str)

    global_pool: list[str] = []
    if len(work):
        vc = (
            work[work[uid_col].notna() & (work[uid_col].astype(str).str.strip() != "")]
            .groupby(uid_col)
            .size()
            .sort_values(ascending=False)
        )
        global_pool = [str(u) for u in vc.head(global_users).index.tolist()]

    snapshots: dict[str, dict] = {}
    for pi, wk in enumerate(week_defs):
        d0, d1 = wk["date_start"], wk["date_end"]
        sub = work[work["_date"].between(d0, d1)] if d0 and d1 else work

        topic_counts = sub.groupby("topic_id").size().to_dict() if len(sub) else {}
        total_comments = int(len(sub))
        shares = []
        for tm in topics_meta:
            tid = tm["topic_id"]
            c = int(topic_counts.get(tid, 0))
            shares.append({
                "topic_id": tid,
                "name": tm["name"],
                "count": c,
                "pct": round(100 * c / total_comments, 1) if total_comments else 0,
                "color": tm["color"],
            })
        shares.sort(key=lambda x: -x["count"])
        dom = shares[0] if shares and shares[0]["count"] > 0 else None

        user_stats: dict[str, dict] = {}
        if len(sub):
            for uid, g in sub.groupby(uid_col):
                if pd.isna(uid) or str(uid).strip() == "":
                    continue
                suid = str(uid)
                vec_counts: dict[int, int] = defaultdict(int)
                for t in g["topic_id"]:
                    vec_counts[int(t)] += 1
                tid = int(g["topic_id"].mode().iloc[0])
                user_stats[suid] = {"topic_id": tid, "count": len(g), "vec": vec_counts}

        active_sorted = sorted(user_stats.items(), key=lambda x: -x[1]["count"])
        active_ids = {u for u, _ in active_sorted[:users_per_week]}
        active_ids.update(global_pool)

        nodes: list[dict] = []
        vectors: dict[str, list[float]] = {}
        p4 = layout.get("4", [0.5, 0.5])
        for uid in active_ids:
            st = user_stats.get(uid)
            pull_4, t4_share = 0.0, 0.0
            if st:
                tid = st["topic_id"]
                cnt = st["count"]
                vec = _topic_vector(st["vec"], topic_ids)
                pull_4, t4_share = _pull_toward_4(st["vec"], cnt, tid)
                opacity = 0.55 + min(0.45, cnt / 18)
                r = max(5, min(14, 4 + cnt ** 0.4))
            else:
                tid = -1
                cnt = 0
                vec = [0.0] * len(topic_ids)
                opacity = 0.06
                r = 3

            if tid >= 0 and str(tid) in layout:
                lx, ly = layout[str(tid)]
                jx, jy = _jitter(uid, str(pi))
                tx = lx + (p4[0] - lx) * pull_4 + jx
                ty = ly + (p4[1] - ly) * pull_4 + jy
                color = TOPIC_COLORS[tid % len(TOPIC_COLORS)]
            else:
                tx, ty = 0.5, 0.5
                color = "#475569"

            nodes.append({
                "id": uid,
                "user_id": uid,
                "topic_id": tid,
                "label": "…" + str(uid)[-8:],
                "count": cnt,
                "color": color,
                "r": r,
                "opacity": opacity,
                "tx": tx,
                "ty": ty,
                "pull_4": pull_4,
                "t4_share": t4_share,
            })
            vectors[uid] = vec

        edge_w: dict[tuple[str, str], float] = defaultdict(float)
        active_list = [uid for uid in active_ids if user_stats.get(uid)]
        for i, ua in enumerate(active_list):
            va = vectors.get(ua)
            if not va or sum(va) == 0:
                continue
            for ub in active_list[i + 1 :]:
                vb = vectors.get(ub)
                if not vb or sum(vb) == 0:
                    continue
                sim = _cosine(va, vb)
                if sim >= min_edge_weight:
                    key = tuple(sorted((ua, ub)))
                    edge_w[key] = sim

        links = [
            {"source": a, "target": b, "weight": float(w), "opacity": min(0.9, 0.25 + w * 0.55)}
            for (a, b), w in edge_w.items()
        ]

        snapshots[str(pi)] = {
            "phase_index": pi,
            "label": wk.get("label", f"W{pi + 1}"),
            "date_start": d0,
            "date_end": d1,
            "nodes": nodes,
            "links": links,
            "comment_count": total_comments,
            "topic_shares": shares,
            "dominant_topic_id": dom["topic_id"] if dom else None,
            "dominant_topic_name": dom["name"] if dom else "—",
            "dominant_topic_pct": dom["pct"] if dom else 0,
        }

    return {
        "title": "用户 × 主题集聚网络",
        "subtitle": "节点=user_id · 颜色=当周主导主题 · 位置偏移=当周人身攻击评论占比 · 边=主题向量相似",
        "mode": "weekly_users",
        "topics": topics_meta,
        "topic_layout": layout,
        "user_pool_size": len(global_pool),
        "phases": [
            {
                "index": i,
                "label": s.get("label", ""),
                "date_start": s.get("date_start", ""),
                "date_end": s.get("date_end", ""),
            }
            for i, s in enumerate(week_defs)
        ],
        "snapshots": snapshots,
        "playback": {"hold_ms": 900, "transition_ms": 700, "fps": 60},
    }

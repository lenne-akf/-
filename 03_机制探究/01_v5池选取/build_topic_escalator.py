from __future__ import annotations
# -*- coding: utf-8 -*-
"""
主题扶梯（Escalator）：主导主题仍为 A，但话语向量/语义向 B 漂移且未「出站」归类的用户。

典型观察：屏2 网络中主题 0（改编舆论）节点随时间向 topic 4（人身攻击）锚点靠拢，
节点颜色仍为主题 0，因为 BERTopic 按单条评论打标，周度主导仍取众数。
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import math
import re
from collections import Counter, defaultdict

import pandas as pd

from topic_labels import MAIN_TOPIC_NAMES

# 目标 topic 4 的高危词（用于「仍在主题 0 但话语升级」检测）
ATTACK_LEXICON = (
    "人身攻击", "网暴", "辱骂", "去死", "滚", "贱", "丑", "恶心", "垃圾", "不要脸",
    "死", "骂", "撕", "贱人", "婊", "废物", "狗", "支持维权", "墙倒", "没教养",
    "人品", "白眼", "拽", "mean",
)

PLATFORM_LABEL = {"weibo": "微博", "douyin": "抖音", "xiaohongshu": "小红书"}


def _display_order(topic_df: pd.DataFrame) -> list[int]:
    return [int(x) for x in topic_df.sort_values("doc_count", ascending=False)["topic_id"].tolist()]


def display_id(topic_id: int, order: list[int]) -> int:
    tid = int(topic_id)
    return order.index(tid) if tid in order else tid


def _topic_name(tid: int) -> str:
    return MAIN_TOPIC_NAMES.get(int(tid), f"主题 {tid}")


def _week_key(series: pd.Series, parse_date_fn) -> pd.Series:
    dt = pd.to_datetime(series.map(parse_date_fn), errors="coerce")
    return dt.dt.to_period("W-MON").astype(str)


def _cosine_dict(a: dict[int, int], b: dict[int, int], topic_ids: list[int]) -> float:
    va = [float(a.get(t, 0)) for t in topic_ids]
    vb = [float(b.get(t, 0)) for t in topic_ids]
    dot = sum(x * y for x, y in zip(va, vb))
    na = math.sqrt(sum(x * x for x in va))
    nb = math.sqrt(sum(x * x for x in vb))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


def _has_bridge_lexicon(text: str) -> bool:
    s = str(text or "")
    return any(w in s for w in ATTACK_LEXICON)


def build_topic_escalator(
    merged: pd.DataFrame,
    topic_df: pd.DataFrame,
    parse_date_fn,
    source_topic_id: int = 0,
    target_topic_id: int = 4,
    min_comments: int = 1,
    min_target_share: float = 0.02,
    min_drift_gain: float = 0.02,
    min_cosine_to_target: float = 0.08,
    max_target_dom_week_ratio: float = 0.62,
    top_users: int = 50,
    sample_comments: int = 12,
) -> dict:
    """
    识别「扶梯用户」：全周期主导主题 = source，话语向 target 漂移；允许少量周次目标成为周主导（未改全周期众数）。
    """
    order = _display_order(topic_df)
    src, tgt = int(source_topic_id), int(target_topic_id)
    src_name = _topic_name(src)
    tgt_name = _topic_name(tgt)
    disp_src = display_id(src, order)
    disp_tgt = display_id(tgt, order)

    work = merged[merged["topic_id"] >= 0].copy()
    if work.empty or "user_id" not in work.columns:
        return _empty_route(src, tgt, src_name, tgt_name, disp_src, disp_tgt)

    work["_date"] = work["created_at"].map(parse_date_fn)
    work = work[work["user_id"].notna() & (work["user_id"].astype(str).str.strip() != "")]
    topic_ids = order

    user_rows: list[dict] = []
    bridge_comments: list[dict] = []
    escalator_uids: set[str] = set()

    for uid, g in work.groupby("user_id"):
        suid = str(uid)
        n = len(g)
        if n < min_comments:
            continue

        vec = Counter(int(t) for t in g["topic_id"])
        dom = int(vec.most_common(1)[0][0])
        if dom != src:
            continue

        n_tgt = int(vec.get(tgt, 0))
        n_src = int(vec.get(src, 0))
        target_share = n_tgt / n

        # 周度目标占比趋势
        g2 = g.copy()
        g2["_wk"] = _week_key(g2["created_at"], parse_date_fn)
        wk_shares: list[float] = []
        for _, wg in g2.groupby("_wk", sort=True):
            if len(wg) < 1:
                continue
            wk_shares.append(float((wg["topic_id"] == tgt).sum()) / len(wg))
        drift_gain = (wk_shares[-1] - wk_shares[0]) if len(wk_shares) >= 2 else 0.0

        # 未「出站」：目标主题成为周主导的周占比低于阈值
        wk_modes = []
        for _, wg in g2.groupby("_wk", sort=True):
            wk_modes.append(int(wg["topic_id"].mode().iloc[0]))
        tgt_dom_weeks = sum(1 for m in wk_modes if m == tgt)
        target_dom_week_ratio = tgt_dom_weeks / len(wk_modes) if wk_modes else 0.0
        ever_dom_target = target_dom_week_ratio >= max_target_dom_week_ratio

        vec_dict = dict(vec)
        cos_to_target = _cosine_dict(vec_dict, {tgt: 1}, topic_ids)

        bridge_n = int(g.apply(lambda r: r["topic_id"] == src and _has_bridge_lexicon(r.get("content", "")), axis=1).sum())

        plat_vc = g["platform"].astype(str).value_counts()
        top_plat = str(plat_vc.index[0]) if len(plat_vc) else ""

        scores = g["sentiment_score"].astype(float) if "sentiment_score" in g.columns else pd.Series([0.5] * n)
        g_sorted = g2.sort_values("_date")
        half = max(1, n // 2)
        early = scores.iloc[:half].mean()
        late = scores.iloc[half:].mean()
        sent_delta = float(late - early)

        # 扶梯指数：目标占比 + 趋势 + 与目标向量相似 + 桥接词密度
        score = (
            0.35 * min(1.0, target_share / 0.35)
            + 0.25 * min(1.0, max(0, drift_gain) / 0.25)
            + 0.25 * cos_to_target
            + 0.15 * min(1.0, bridge_n / max(1, n_src))
        )

        # 至少有一条信号：目标评论、占比、周趋势、向量相似、桥接词
        has_signal = (
            n_tgt >= 1
            or target_share >= min_target_share
            or drift_gain >= min_drift_gain
            or bridge_n >= 1
            or cos_to_target >= min_cosine_to_target
        )
        # 「未出站」：全周期众数仍是 source；周主导为目标不超过 max_target_dom_week_ratio
        qualifies = dom == src and has_signal and not ever_dom_target
        if not qualifies:
            continue

        escalator_uids.add(suid)
        user_rows.append({
            "user_id": suid,
            "user_label": "…" + suid[-8:],
            "comment_count": n,
            "dominant_topic_id": dom,
            "target_topic_count": n_tgt,
            "target_share_pct": round(target_share * 100, 1),
            "source_share_pct": round(n_src / n * 100, 1),
            "drift_gain_pct": round(drift_gain * 100, 1),
            "cosine_to_target": round(cos_to_target, 3),
            "bridge_comment_count": bridge_n,
            "escalator_score": round(score, 3),
            "platform": top_plat,
            "platform_label": PLATFORM_LABEL.get(top_plat, top_plat),
            "sentiment_early": round(float(early), 3),
            "sentiment_late": round(float(late), 3),
            "sentiment_delta": round(sent_delta, 3),
            "target_dom_week_ratio_pct": round(target_dom_week_ratio * 100, 1),
            "ever_dominant_target": ever_dom_target,
        })

        for _, r in g.iterrows():
            if len(bridge_comments) >= sample_comments * 3:
                break
            if int(r["topic_id"]) != src:
                continue
            if not _has_bridge_lexicon(r.get("content", "")):
                continue
            bridge_comments.append({
                "user_id": suid,
                "user_label": "…" + suid[-8:],
                "platform_label": PLATFORM_LABEL.get(str(r.get("platform", "")), ""),
                "created_at": str(r.get("created_at", ""))[:10],
                "content": str(r.get("content", ""))[:220],
                "sentiment_label": str(r.get("sentiment_label", "")),
                "like_count": int(r.get("like_count", 0) or 0),
            })

    user_rows.sort(key=lambda x: -x["escalator_score"])
    top = user_rows[:top_users]

    weekly_esc: dict[str, dict] = {}
    if escalator_uids:
        esc_df = work[work["user_id"].astype(str).isin(escalator_uids)].copy()
        esc_df["_wk"] = _week_key(esc_df["created_at"], parse_date_fn)
        for wk, wg in esc_df.groupby("_wk", sort=True):
            tgt_n = int((wg["topic_id"] == tgt).sum())
            bridge_n = int(
                wg.apply(
                    lambda r: int(r["topic_id"]) == src and _has_bridge_lexicon(r.get("content", "")),
                    axis=1,
                ).sum()
            )
            weekly_esc[str(wk)] = {
                "target_comments": tgt_n,
                "bridge_comments": bridge_n,
                "count": tgt_n + bridge_n,
            }

    # 聚合画像
    n_users = len(user_rows)
    n_comments = sum(u["comment_count"] for u in user_rows)
    avg_target = sum(u["target_share_pct"] for u in user_rows) / n_users if n_users else 0
    deltas = [u["sentiment_delta"] for u in user_rows if u.get("sentiment_delta") == u.get("sentiment_delta")]
    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    plat_agg = Counter(u["platform_label"] for u in user_rows)

    reasons = [
        {
            "title": "算法层：颜色≠位移",
            "detail": "网络节点颜色取当周评论的众数主题（仍为主题 "
            f"{disp_src}），位置却受同类用户连边与力导向牵引，向主题 {disp_tgt} 锚点靠拢；"
            "单条已标为人身攻击的评论不足以改写整周主导色。",
        },
        {
            "title": "话语层：改编槽内升级",
            "detail": f"约 {sum(u['bridge_comment_count'] for u in user_rows)} 条评论 BERTopic 仍归主题 {disp_src}，"
            f"但文本含攻击/网暴类词汇，属于「扶梯」上的语义抬升而未改票。",
        },
        {
            "title": "情感层：后期更消极",
            "detail": f"扶梯用户后期情感均分较前期平均 {avg_delta:+.3f}（SnowNLP），"
            "与向人身攻击议题漂移的时间节奏一致。",
        },
        {
            "title": "平台层",
            "detail": "主要发声平台：" + " · ".join(
                f"{k} {v}人" for k, v in plat_agg.most_common(3)
            ) if plat_agg else "—",
        },
    ]

    wk_series = [{"week": w, **v} for w, v in sorted(weekly_esc.items())]

    return {
        "concept": "escalator",
        "title": "主题扶梯（Escalator）",
        "subtitle": "主导主题未改，但话语与网络位置向另一主题漂移",
        "route": {
            "source_topic_id": src,
            "target_topic_id": tgt,
            "display_source": disp_src,
            "display_target": disp_tgt,
            "source_name": src_name,
            "target_name": tgt_name,
            "label": f"主题 {disp_src} → 主题 {disp_tgt}",
        },
        "definition": (
            f"扶梯用户：全周期主导仍为「{src_name}」（编号 {disp_src}），"
            f"但目标主题「{tgt_name}」（编号 {disp_tgt}）占比或周度趋势显著，"
            f"且目标成为周主导的周占比 < {int(max_target_dom_week_ratio * 100)}%（放宽：允许短暂「到站」未改全周期标签）。"
        ),
        "criteria": {
            "min_comments": min_comments,
            "min_target_share": min_target_share,
            "min_drift_gain": min_drift_gain,
            "min_cosine_to_target": min_cosine_to_target,
            "max_target_dom_week_ratio": max_target_dom_week_ratio,
        },
        "summary": {
            "user_count": n_users,
            "comment_count": n_comments,
            "avg_target_share_pct": round(avg_target, 1),
            "avg_sentiment_delta": round(avg_delta, 3),
            "bridge_comment_total": sum(u["bridge_comment_count"] for u in user_rows),
        },
        "reasons": reasons,
        "weekly_intensity": wk_series,
        "weekly_intensity_note": (
            "强度 = 扶梯用户池内当周评论条数（非用户数）："
            f"已标为目标主题（{tgt_name}）的评论 + 仍标为主题 {disp_src} 但含攻击/网暴桥接词的评论，二者相加。"
        ),
        "top_users": top,
        "sample_bridge_comments": bridge_comments[:sample_comments],
    }


def _empty_route(src, tgt, src_name, tgt_name, disp_src, disp_tgt) -> dict:
    return {
        "concept": "escalator",
        "title": "主题扶梯（Escalator）",
        "route": {
            "source_topic_id": src,
            "target_topic_id": tgt,
            "display_source": disp_src,
            "display_target": disp_tgt,
            "source_name": src_name,
            "target_name": tgt_name,
            "label": f"主题 {disp_src} → 主题 {disp_tgt}",
        },
        "summary": {"user_count": 0, "comment_count": 0},
        "top_users": [],
        "sample_bridge_comments": [],
        "weekly_intensity": [],
        "reasons": [],
    }

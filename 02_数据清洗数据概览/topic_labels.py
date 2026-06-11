from __future__ import annotations
# -*- coding: utf-8 -*-
"""根据 BERTopic 关键词生成唯一、可读的中文主题名。"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


# 主报告 6 个主题（屏2 展示顺序 0–5）
MAIN_TOPIC_NAMES = {
    0: "《李白》改编与舆论反馈",
    1: "道歉与抄袭维权",
    2: "粉丝应援与品牌代言",
    3: "版权归属与举证",
    4: "人身攻击与网暴辱骂",
    5: "总监制与人设争议",
}


def label_from_keywords(topic_id: int, keywords: str) -> str:
    """按 topic_id 优先返回主议题名称，避免关键词误匹配。"""
    tid = int(topic_id)
    if tid in MAIN_TOPIC_NAMES:
        return MAIN_TOPIC_NAMES[tid]

    kws = [k.strip() for k in str(keywords).split(",") if k.strip()]
    s = ",".join(kws)
    if not s:
        return f"主题簇 {tid}"

    if any(x in s for x in ("人身攻击", "网暴", "辱骂", "去死", "滚蛋", "贱", "婊", "不要脸", "败类")):
        return "人身攻击与网暴辱骂"
    if any(x in s for x in ("总监制", "衣服", "拽", "mean", "人品", "墙倒", "没教养", "没素质", "白眼", "态度")):
        return "总监制与人设争议"
    if any(x in s for x in ("纯纯", "单依", "代言人", "品牌", "巡演", "香奈儿")):
        return "粉丝应援与品牌代言"
    if any(x in s for x in ("版权", "本人", "证据", "尊重", "意识", "承担", "承认", "授权")):
        return "版权归属与举证"
    if any(x in s for x in ("道歉", "抄袭", "原谅", "赔偿", "违法", "团队", "侵权")):
        return "道歉与抄袭维权"
    if any(x in s for x in ("又能怎", "如何呢", "难听", "改编", "翻唱", "李白", "音乐")):
        return "《李白》改编与舆论反馈"

    if len(kws) >= 2:
        return f"{kws[0]}·{kws[1]}"
    return kws[0]


def ensure_unique_names(rows: list[dict]) -> list[dict]:
    """同一图表内主题名不重复。"""
    seen: dict[str, int] = {}
    out = []
    for r in rows:
        name = str(r.get("chinese_name", "")).strip()
        if not name:
            name = label_from_keywords(int(r["topic_id"]), str(r.get("keywords", "")))
        if name in seen:
            seen[name] += 1
            name = f"{name}（{int(r['topic_id'])}）"
        else:
            seen[name] = 1
        out.append({**r, "chinese_name": name})
    return out

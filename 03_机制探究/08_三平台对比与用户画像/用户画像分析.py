#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5：用户画像与立场光谱分析

以 user_id 为分析单元，对三平台评论用户进行立场分类与交叉分析。
运行: python user_profile_analysis.py
产出: user_profile_results.csv, user_profile_stats.json/js, user_profile_report.txt, *.png
"""

from __future__ import annotations

import sys
from pathlib import Path as _Path
_R = _Path(__file__).resolve().parent.parent
if str(_R) not in sys.path:
    sys.path.insert(0, str(_R))
import 项目路径 as P

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

BASE = Path(__file__).resolve().parent
IN_CLEANED = P.评论数据
OUT_USERS = P.用户画像CSV
OUT_JSON = P.用户画像统计
OUT_JS = P.用户画像JS
OUT_REPORT = P.用户画像报告
OUT_HTML = P.屏3HTML
HTML_TEMPLATE = P.用户画像JS模板

# 舆论反转节点：李荣浩从「维权者」转为「被指控侵权者」（小眼睛事件曝光）
REVERSAL_DATE = datetime(2026, 4, 1)

PLAT_NAMES = {"weibo": "微博", "douyin": "抖音", "xiaohongshu": "小红书"}

STANCE_TYPES = [
    "版权原教旨主义者",
    "Z世代/乐子人",
    "道德审判官",
    "路人/和事佬",
    "摇摆型",
    "未分类/边缘样本",
]
ACTIVE_STANCE_TYPES = [t for t in STANCE_TYPES if t != "未分类/边缘样本"]
UNCLASSIFIED = "未分类/边缘样本"
STANCE_SCORE_THRESHOLD = 1.0
HISTORY_TEXT_WEIGHT = 0.55

STANCE_COLORS = {
    "版权原教旨主义者": "#c9a962",
    "Z世代/乐子人": "#7eb8da",
    "道德审判官": "#c44d6a",
    "路人/和事佬": "#e8a060",
    "摇摆型": "#2d9a78",
    "未分类/边缘样本": "#9b8fa3",
}
OUT_PHASE_CHART = BASE / "user_phase_stance_chart.png"
OUT_EMOTION_CHART = BASE / "user_emotion_stance_chart.png"
OUT_OCCUPATION_CHART = BASE / "user_occupation_stance_heatmap.png"

STANCE_SHORT = {
    "版权原教旨主义者": "版权派",
    "Z世代/乐子人": "乐子人",
    "道德审判官": "道德审判",
    "路人/和事佬": "路人/和事佬",
    "摇摆型": "摇摆型",
    "未分类/边缘样本": "未分类",
}

TOPIC_SHORT = {
    "《李白》改编与舆论反馈": "李白改编",
    "道歉与抄袭维权": "道歉维权",
    "粉丝应援与品牌代言": "粉丝应援",
    "版权归属与举证": "版权举证",
    "人身攻击与网暴辱骂": "人身攻击",
    "总监制与人设争议": "人设争议",
}

WINE_CMAP = LinearSegmentedColormap.from_list(
    "wine_soft", ["#faf7f2", "#efe0c8", "#d9b896", "#b8896a", "#8b5a4a", "#722f37"],
)


def classified_users(users: list[dict]) -> list[dict]:
    return [u for u in users if u["stance_type"] != UNCLASSIFIED]

# ── 规则词典 ──────────────────────────────────────────────

LEGAL_KW = [
    "法律", "条例", "著作权", "版权法", "依法", "起诉", "法院", "律师",
    "合法", "违法", "侵权", "抄袭", "证据", "维权", "原创", "著作权法",
    "知识产权", "法务", "判决", "诉讼", "条例", "法规",
]
ANTI_EMOTION_KW = [
    "理性", "不要网暴", "冷静", "就事论事", "不要情绪化", "理性讨论",
    "合理监督", "依法处理", "走法律", "法律途径", "不要带节奏",
]
MEME_KW = [
    "乐子", "整活", "笑死", "绷不住", "绝绝子", "吃瓜", "看戏", "路过",
    "不明觉厉", "键盘侠", "抽象", "逆天", "典", "蚌埠住", "乐", "hhh",
    "笑拥", "难绷", "整段", "玩梗", "梗图", "二创", "魔改",
]
MORAL_KW = [
    "去死", "贱", "恶心", "滚", " shame", "双标", "打脸", "虚伪", "绿茶",
    "茶", "不要脸", "无耻", "垃圾", "人渣", "败类", "脑残", "傻", "蠢",
    "装", "作", "恶心", "吐了", "下头", "晦气", "死", "骂", "喷",
]
PEACE_KW = [
    "差不多得了", "两边都不对", "各打五十大板", "和稀泥", "理性吃瓜",
    "谁对谁错", "路人", "中立", "不站队", "都有问题", "各退一步",
    "和平", "各自发展", "别吵了", "散了吧",
]
PRO_LRH = [
    "支持李荣浩", "李荣浩维权", "李荣浩全", "守护李荣浩", "李荣浩吧",
    "单依纯侵权", "尊重原创", "支持维权", "李荣浩创作", "李荣浩硬气",
]
PRO_SYC = [
    "支持单依纯", "放过单依纯", "纯妹妹", "单姐", "妹妹没错",
    "李荣浩过分", "欺负", "李荣浩双标", "李荣浩也侵权", "小眼睛",
]
FAN_LRH = ["李荣浩粉丝", "浩哥", "我哥", "李老师", "李荣浩全肯定", "鲸鱼", "李荣浩吧"]
FAN_SYC = ["单依纯粉丝", "纯妹妹", "单姐", "纯粉", "单依纯官方", "纯丝", "单依纯全国"]
SYC_NAMES = ["单依纯", "纯妹妹", "单姐", "syc", "SYc", "单依纯官方"]
LRH_NAMES = ["李荣浩", "浩哥", "李老师", "lrh", "LRH", "李老师"]
# 夸单依纯：正面描述词
PRAISE_SYC_KW = [
    "支持单依纯", "放过单依纯", "纯妹妹", "单姐", "美女", "实力", "歌手",
    "好听", "优秀", "漂亮", "爱", "加油", "厉害", "女神", "宝藏", "绝了",
    "太好", "真好", "喜欢单", "单依纯棒", "纯宝",
]
# 辱骂/攻击单依纯
ATTACK_SYC_KW = [
    "单依纯侵权", "单依纯抄袭", "单依纯茶", "单依纯恶心", "单依纯滚",
    "单依纯贱", "单依纯双标", "单依纯不要脸", "单依纯垃圾", "讨厌单依纯",
    "单依纯过分", "单依纯装", "抵制单依纯",
]
# 夸李荣浩 / 维权派
PRAISE_LRH_KW = [
    "支持李荣浩", "李荣浩维权", "李荣浩全", "守护李荣浩", "李荣浩吧",
    "支持维权", "尊重原创", "李荣浩创作", "李荣浩硬气", "李荣浩棒",
    "李荣浩对", "李荣浩没错", "浩哥", "李老师",
]
# 攻击李荣浩
ATTACK_LRH_KW = [
    "李荣浩过分", "李荣浩双标", "李荣浩也侵权", "李荣浩抄袭", "李荣浩恶心",
    "李荣浩滚", "讨厌李荣浩", "李荣浩不要脸", "李荣浩装", "李荣浩小眼睛",
    "李荣浩虚伪", "李荣浩垃圾",
]

OCCUPATION_RULES = {
    "学生": ["学生", "考研", "大学", "高中", "作业", "考试", "校园", "宿舍", "课代表"],
    "律师/法律": ["律师", "法务", "法律工作", "法学生", "律所"],
    "老师": ["老师", "教师", "教授", "班主任", "讲师"],
    "媒体/自媒体": ["记者", "新闻", "博主", "小编", "媒体", "工作室", "官方"],
}


def pick_font() -> str:
    from matplotlib import font_manager
    for name in ["Microsoft YaHei", "SimHei", "PingFang SC"]:
        if name in {f.name for f in font_manager.fontManager.ttflist}:
            return name
    return "sans-serif"


def load_merged_rows() -> list[dict]:
    """读取 cleaned_comments.csv"""
    if not IN_CLEANED.exists():
        raise FileNotFoundError(f"缺少 {IN_CLEANED}")
    return list(csv.DictReader(open(IN_CLEANED, encoding="utf-8-sig")))


def parse_date(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d"]:
        try:
            clean = s.replace("+08:00", "").replace("+0800", "")
            if fmt == "%Y-%m-%d %H:%M:%S%z":
                clean = s[:19]
            elif fmt == "%Y/%m/%d %H:%M":
                clean = s[:16]
            elif fmt == "%Y/%m/%d":
                clean = s[:10]
            else:
                clean = clean[: len(fmt.replace("%z", ""))]
            return datetime.strptime(clean, fmt.replace("%z", ""))
        except ValueError:
            continue
    # Twitter: "Sat May 30 18:48:36 +0800 2026"
    m = re.match(r"(\w{3}) (\w{3}) (\d{1,2})", s)
    if m:
        year_m = re.search(r"(\d{4})\s*$", s)
        if year_m:
            months = {
                "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
                "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
            }
            year = int(year_m.group(1))
            if 2000 <= year <= 2100:
                return datetime.strptime(
                    f"{year}-{months.get(m.group(2), '01')}-{int(m.group(3)):02d}",
                    "%Y-%m-%d",
                )
    return None


def count_hits(text: str, kws: list[str]) -> tuple[int, list[str]]:
    hits = [k for k in kws if k in text]
    return len(hits), hits


POLAR_POS = ["支持", "好", "棒", "赞", "喜欢", "优秀", "加油", "厉害", "漂亮", "爱", "酷"]
POLAR_NEG = ["垃圾", "恶心", "滚", "死", "贱", "讨厌", "失望", "无耻", "过分", "烂", "喷"]


def emotion_intensity(text: str) -> float:
    """情绪强度：极性词 + 辱骂词 + 感叹符（LIWC 风格简化版）"""
    _, moral_h = count_hits(text, MORAL_KW)
    _, pos_h = count_hits(text, POLAR_POS)
    _, neg_h = count_hits(text, POLAR_NEG)
    excl = text.count("!") + text.count("！")
    raw = len(moral_h) * 0.14 + len(neg_h) * 0.1 + len(pos_h) * 0.06 + excl * 0.035
    return min(1.0, raw)


def comment_attitude(text: str) -> dict[str, bool]:
    """
    单条评论对单依纯/李荣浩的态度：
    - praise_syc: 夸/支持单依纯
    - attack_syc: 辱骂/攻击单依纯 → 维权派信号
    - praise_lrh: 夸/支持李荣浩/维权
    - attack_lrh: 辱骂/攻击李荣浩
    """
    t = text or ""
    has_syc = any(n in t for n in SYC_NAMES)
    has_lrh = any(n in t for n in LRH_NAMES)
    _, moral_h = count_hits(t, MORAL_KW)
    _, neg_h = count_hits(t, POLAR_NEG)
    _, pos_h = count_hits(t, POLAR_POS)
    _, ps_kw = count_hits(t, PRAISE_SYC_KW)
    _, as_kw = count_hits(t, ATTACK_SYC_KW)
    _, pl_kw = count_hits(t, PRAISE_LRH_KW)
    _, al_kw = count_hits(t, ATTACK_LRH_KW)

    attack_syc = bool(as_kw) or (
        has_syc and (moral_h or neg_h)
    )
    praise_syc = bool(ps_kw) or (
        has_syc and not attack_syc and (pos_h or any(k in t for k in ["美女", "实力", "歌手", "好听", "优秀", "漂亮", "爱", "时尚", "女歌手"]))
    ) or (count_hits(t, PRO_SYC)[0] > 0 and not attack_syc)

    attack_lrh = bool(al_kw) or (
        has_lrh and (moral_h or neg_h) and not praise_syc
    ) or ("李荣浩" in t and any(k in t for k in ["过分", "双标", "也侵权", "小眼睛"]) and not count_hits(t, PRO_LRH)[0])
    praise_lrh = bool(pl_kw) or (
        has_lrh and not attack_lrh and (pos_h or count_hits(t, PRO_LRH)[0] > 0 or count_hits(t, FAN_LRH)[0] > 0)
    ) or (count_hits(t, PRO_LRH)[0] > 0 and not has_syc and not attack_syc)

    # 未提单依纯但明确攻击性 framing
    if ("单依纯侵权" in t or "单依纯抄袭" in t) and (moral_h or neg_h or "支持维权" in t or "支持李荣浩" in t):
        attack_syc = True
        if not pos_h:
            praise_syc = False

    return {
        "praise_syc": praise_syc,
        "attack_syc": attack_syc,
        "praise_lrh": praise_lrh,
        "attack_lrh": attack_lrh,
    }


def comment_direction(text: str) -> str:
    att = comment_attitude(text)
    if att["praise_lrh"] or att["attack_syc"]:
        return "pro_lrh"
    if att["praise_syc"] or att["attack_lrh"]:
        return "pro_syc"
    if att["praise_syc"] and att["praise_lrh"]:
        return "mixed"
    if att["attack_syc"] and att["attack_lrh"]:
        return "mixed"
    return "neutral"


def classify_fan_camp(texts: list[str]) -> dict:
    """
    用户级粉丝阵营（用户规则）：
    - 夸/支持单依纯 → 单依纯粉
    - 辱骂单依纯 → 维权派
    - 两者都夸 或 两者都吐槽 → 摇摆型
    - 其余 → 路人
    """
    totals = Counter()
    for t in texts:
        att = comment_attitude(t)
        for k, v in att.items():
            if v:
                totals[k] += 1

    ps = totals["praise_syc"]
    asc = totals["attack_syc"]
    pl = totals["praise_lrh"]
    al = totals["attack_lrh"]

    is_swing = (ps > 0 and pl > 0) or (asc > 0 and al > 0)

    if is_swing:
        group = "摇摆型"
        conf = min(0.9, 0.55 + (ps + pl + asc + al) * 0.03)
        evidence = []
        if ps and pl:
            evidence.append(f"夸单依纯×{ps} + 夸李荣浩×{pl}")
        if asc and al:
            evidence.append(f"骂单依纯×{asc} + 骂李荣浩×{al}")
    elif ps > 0 and ps >= asc:
        # 夸单依纯为主（如「时尚美女实力女歌手单依纯」）
        group = "单依纯粉"
        conf = min(0.88, 0.5 + ps * 0.04)
        evidence = [f"夸/支持单依纯×{ps}"]
        if asc:
            evidence.append(f"(少量攻击信号×{asc}，以夸为主)")
        if al:
            evidence.append(f"攻击李荣浩×{al}")
    elif asc > 0 and asc > ps:
        # 辱骂单依纯为主 → 维权派
        group = "李荣浩粉/维权派"
        conf = min(0.88, 0.5 + asc * 0.06)
        evidence = [f"辱骂/攻击单依纯×{asc}"]
    elif pl > 0:
        group = "李荣浩粉/维权派"
        conf = min(0.85, 0.45 + pl * 0.08)
        evidence = [f"支持李荣浩/维权×{pl}"]
    elif al > 0:
        group = "单依纯粉"
        conf = min(0.85, 0.45 + al * 0.08)
        evidence = [f"攻击李荣浩×{al}"]
    else:
        group = "路人/无明确归属"
        conf = 0.35
        evidence = ["无明确站队信号"]

    return {
        "fan_group": group,
        "fan_confidence": round(conf, 2),
        "fan_evidence": evidence,
        "is_swing": is_swing,
        "praise_syc": ps,
        "attack_syc": asc,
        "praise_lrh": pl,
        "attack_lrh": al,
    }


def classify_comment(text: str, post_count_hint: int = 99) -> dict:
    """单条评论立场信号打分"""
    t = text or ""
    legal_n, legal_h = count_hits(t, LEGAL_KW)
    anti_n, anti_h = count_hits(t, ANTI_EMOTION_KW)
    meme_n, meme_h = count_hits(t, MEME_KW)
    moral_n, moral_h = count_hits(t, MORAL_KW)
    peace_n, peace_h = count_hits(t, PEACE_KW)

    scores = {
        "版权原教旨主义者": legal_n * 2 + anti_n * 3,
        "Z世代/乐子人": meme_n * 2 + (1 if meme_n > 0 and len(t) < 20 else 0),
        "道德审判官": moral_n * 2 + (2 if "!" in t or "！" in t else 0),
        "路人/和事佬": 0,
    }
    # 路人/和事佬：需有和事关键词；低频(≤2条)额外加权
    if peace_n > 0:
        scores["路人/和事佬"] = peace_n * 3 + (2 if post_count_hint <= 2 else 0)

    best = max(scores, key=scores.get)
    best_score = scores[best]
    if best_score == 0:
        return {
            "stance": "未分类/边缘样本",
            "confidence": 0.2,
            "scores": scores,
            "evidence": ["无显著立场信号词"],
            "direction": comment_direction(t),
        }

    evidence_map = {
        "版权原教旨主义者": legal_h[:3] + anti_h[:2],
        "Z世代/乐子人": meme_h[:4],
        "道德审判官": moral_h[:4],
        "路人/和事佬": peace_h[:3],
    }
    conf = min(0.95, 0.35 + best_score * 0.08)
    return {
        "stance": best,
        "confidence": round(conf, 2),
        "scores": scores,
        "evidence": evidence_map.get(best, [])[:5] or ["综合文本特征"],
        "direction": comment_direction(t),
    }


def classify_user_stance(
    texts: list[str],
    weights: list[float] | None = None,
    post_count_hint: int = 1,
) -> dict:
    """用户级立场：跨多条文本累加信号分，提升低信号用户的可分类率。"""
    if not texts:
        return {
            "stance": UNCLASSIFIED,
            "confidence": 0.2,
            "evidence": ["无显著立场信号词"],
            "scores": {},
            "direction_counts": Counter(),
        }

    total_scores: Counter = Counter()
    evidence_map: defaultdict[str, list] = defaultdict(list)
    conf_weight: Counter = Counter()
    count_by_stance: Counter = Counter()
    direction_counts: Counter = Counter()

    for i, t in enumerate(texts):
        w = weights[i] if weights and i < len(weights) else 1.0
        r = classify_comment(t, post_count_hint)
        direction_counts[r["direction"]] += w
        if r["stance"] == UNCLASSIFIED:
            for st, sc in r["scores"].items():
                if sc > 0:
                    total_scores[st] += sc * w
            continue
        count_by_stance[r["stance"]] += w
        conf_weight[r["stance"]] += r["confidence"] * w
        for st, sc in r["scores"].items():
            total_scores[st] += sc * w
        for ev in r["evidence"]:
            if ev not in evidence_map[r["stance"]]:
                evidence_map[r["stance"]].append(ev)

    if not total_scores:
        return {
            "stance": UNCLASSIFIED,
            "confidence": 0.2,
            "evidence": ["无显著立场信号词"],
            "scores": {},
            "direction_counts": direction_counts,
        }

    best = max(total_scores, key=total_scores.get)
    best_score = total_scores[best]

    if best_score < STANCE_SCORE_THRESHOLD:
        return {
            "stance": UNCLASSIFIED,
            "confidence": round(min(0.45, 0.2 + best_score * 0.08), 2),
            "evidence": ["无显著立场信号词"] if best_score == 0 else [f"弱信号:{best}({best_score:.1f})"],
            "scores": dict(total_scores),
            "direction_counts": direction_counts,
        }

    avg_conf = conf_weight[best] / max(count_by_stance[best], 0.01) if count_by_stance[best] else 0.5
    conf = min(0.95, 0.28 + best_score * 0.045 + avg_conf * 0.2)
    return {
        "stance": best,
        "confidence": round(conf, 2),
        "evidence": evidence_map[best][:6] or ["综合文本特征"],
        "scores": dict(total_scores),
        "direction_counts": direction_counts,
    }


def dedupe_extra_texts(comment_texts: list[str], extra_texts: list[str]) -> list[str]:
    """去掉与评论重复的历史博文，避免重复计分。"""
    comment_keys = {(t or "").strip()[:100] for t in comment_texts if (t or "").strip()}
    seen: set[str] = set()
    out: list[str] = []
    for t in extra_texts:
        key = (t or "").strip()[:100]
        if not key or key in comment_keys or key in seen:
            continue
        seen.add(key)
        out.append(t.strip())
    return out


def is_weibo_numeric_user(uid: str, recs: list[dict]) -> bool:
    if not uid.isdigit():
        return False
    return any(r.get("platform") == "weibo" for r in recs)


def collect_enrich_targets(
    users: list[dict],
    by_user: dict[str, list[dict]],
    limit: int,
) -> list[tuple[str, str]]:
    """优先未分类、评论数少、置信度低的微博数字 UID。"""
    targets: list[tuple[str, str, float]] = []
    for u in users:
        uid = u["user_id"]
        if u["stance_type"] != UNCLASSIFIED:
            continue
        recs = by_user.get(uid, [])
        if not is_weibo_numeric_user(uid, recs):
            continue
        priority = u["post_count"] + u.get("stance_confidence", 0.2) * 2
        targets.append((uid, u.get("user_name", ""), priority))
    targets.sort(key=lambda x: x[2])
    return [(uid, name) for uid, name, _ in targets[:limit]]


def enrich_weibo_user_histories(
    targets: list[tuple[str, str]],
    max_pages: int = 2,
    max_posts: int = 20,
) -> dict[str, list[str]]:
    """爬取微博用户往期博文（内存，不保存）。无 Cookie 或失败时返回空 dict。"""
    try:
        from weibo_scraper import WeiboScraper, try_load_cookie
    except ImportError:
        print("  [!] 无法导入 weibo_scraper，跳过历史博文增强", flush=True)
        return {}

    cookie = try_load_cookie()
    if not cookie:
        print("  [!] 未找到微博 Cookie（cookie.txt / WEIBO_COOKIE），跳过历史博文增强", flush=True)
        return {}

    scraper = WeiboScraper(cookie)
    history: dict[str, list[str]] = {}
    total = len(targets)
    for i, (uid, name) in enumerate(targets, 1):
        label = name or uid
        try:
            texts = scraper.fetch_user_timeline_texts(
                uid, max_pages=max_pages, max_posts=max_posts, verbose=False,
            )
            if texts:
                history[uid] = texts
            if i % 10 == 0 or i == total:
                print(
                    f"  历史博文: {i}/{total} 用户，已获取 {len(history)} 人有有效文本",
                    flush=True,
                )
        except Exception as e:
            print(f"  [!] uid={uid} ({label}) 爬取失败: {e}", flush=True)
    return history


def infer_occupation(texts: list[str]) -> tuple[str, float]:
    blob = " ".join(texts)
    best_occ, best_n = "未知", 0
    for occ, kws in OCCUPATION_RULES.items():
        n, _ = count_hits(blob, kws)
        if n > best_n:
            best_occ, best_n = occ, n
    if best_n == 0:
        return "未知", 0.25
    return best_occ, min(0.8, 0.35 + best_n * 0.15)


def infer_fan_group(texts: list[str]) -> tuple[str, float]:
    info = classify_fan_camp(texts)
    return info["fan_group"], info["fan_confidence"]


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return round(max(0, centre - margin) * 100, 1), round(min(1, centre + margin) * 100, 1)


def aggregate_user(
    uid: str,
    recs: list[dict],
    extra_texts: list[str] | None = None,
    enriched: bool = False,
) -> dict:
    texts = [r["content"] for r in recs]
    extra = dedupe_extra_texts(texts, extra_texts or [])
    all_texts = texts + extra
    weights = [1.0] * len(texts) + [HISTORY_TEXT_WEIGHT] * len(extra)

    names = list({r.get("user_name", "") for r in recs if r.get("user_name")})
    platforms = list({r["platform"] for r in recs})
    plat_label = "+".join(PLAT_NAMES.get(p, p) for p in sorted(platforms))

    fan_info = classify_fan_camp(all_texts)
    is_swing = fan_info["is_swing"]

    stance_result = classify_user_stance(all_texts, weights, post_count_hint=len(recs))
    directions = stance_result["direction_counts"]

    if is_swing:
        primary = "摇摆型"
        conf = fan_info["fan_confidence"]
        evidence = fan_info["fan_evidence"] + [
            f"方向: 李荣浩向{directions.get('pro_lrh', 0):.1f} 单依纯向{directions.get('pro_syc', 0):.1f}",
        ]
    else:
        primary = stance_result["stance"]
        conf = stance_result["confidence"]
        evidence = list(stance_result["evidence"])

    if extra and primary != UNCLASSIFIED:
        evidence = evidence[:5] + [f"历史博文辅助({len(extra)}条)"]

    occ, o_conf = infer_occupation(all_texts)
    fan = fan_info["fan_group"]
    f_conf = fan_info["fan_confidence"]

    intensities = [emotion_intensity(t) for t in texts]
    avg_intensity = round(sum(intensities) / len(intensities), 3) if intensities else 0.0

    phases = []
    for r in recs:
        dt = parse_date(r.get("created_at", ""))
        if dt:
            phases.append("反转后" if dt >= REVERSAL_DATE else "反转前")
    phase_counter = Counter(phases)

    parsed_dates = [parse_date(r.get("created_at", "")) for r in recs]
    parsed_dates = [d for d in parsed_dates if d]
    first_seen = min(parsed_dates).strftime("%Y-%m-%d") if parsed_dates else ""

    return {
        "user_id": uid,
        "user_name": names[0] if names else "",
        "post_count": len(recs),
        "platforms": plat_label,
        "primary_platform": PLAT_NAMES.get(
            Counter(r["platform"] for r in recs).most_common(1)[0][0], ""
        ),
        "stance_type": primary,
        "stance_confidence": conf,
        "stance_evidence": evidence,
        "fan_group": fan,
        "fan_confidence": round(f_conf, 2),
        "fan_evidence": "|".join(fan_info["fan_evidence"]),
        "praise_syc": fan_info["praise_syc"],
        "attack_syc": fan_info["attack_syc"],
        "praise_lrh": fan_info["praise_lrh"],
        "attack_lrh": fan_info["attack_lrh"],
        "occupation": occ,
        "occupation_confidence": round(o_conf, 2),
        "avg_emotion_intensity": avg_intensity,
        "direction_pro_lrh": fan_info["praise_lrh"] + fan_info["attack_syc"],
        "direction_pro_syc": fan_info["praise_syc"] + fan_info["attack_lrh"],
        "phase_before": phase_counter.get("反转前", 0),
        "phase_after": phase_counter.get("反转后", 0),
        "first_seen": first_seen,
        "sample_content": texts[0][:80] if texts else "",
        "history_posts_used": len(extra),
        "enriched": 1 if enriched and extra else 0,
    }


def build_cross_tables(users: list[dict]) -> dict:
    """交叉分析基于全样本用户（含未分类/边缘样本）"""
    n = len(users)
    uncl_n = sum(1 for u in users if u["stance_type"] == UNCLASSIFIED)
    stance_counts = Counter(u["stance_type"] for u in users)

    type_pct = []
    for st in STANCE_TYPES:
        c = stance_counts.get(st, 0)
        lo, hi = wilson_ci(c, n)
        type_pct.append({
            "type": st,
            "count": c,
            "pct": round(c / n * 100, 2) if n else 0,
            "ci_low": lo,
            "ci_high": hi,
        })

    plat_stance: dict[str, Counter] = defaultdict(Counter)
    for u in users:
        plat_stance[u["primary_platform"]][u["stance_type"]] += 1

    platform_cross = []
    for plat in ["微博", "抖音", "小红书"]:
        c = plat_stance.get(plat, Counter())
        total = sum(c.get(st, 0) for st in STANCE_TYPES) or 1
        platform_cross.append({
            "platform": plat,
            "counts": {st: c.get(st, 0) for st in STANCE_TYPES},
            "pcts": {st: round(c.get(st, 0) / total * 100, 1) for st in STANCE_TYPES},
            "total": total,
        })

    intensity_by_type: dict[str, list[float]] = defaultdict(list)
    for u in users:
        intensity_by_type[u["stance_type"]].append(u["avg_emotion_intensity"])

    emotion_cross = []
    for st in STANCE_TYPES:
        vals = intensity_by_type.get(st, [])
        if vals:
            emotion_cross.append({
                "type": st,
                "mean": round(float(np.mean(vals)), 3),
                "median": round(float(np.median(vals)), 3),
                "q1": round(float(np.percentile(vals, 25)), 3),
                "q3": round(float(np.percentile(vals, 75)), 3),
                "count": len(vals),
            })

    phase_stance: dict[str, Counter] = {"反转前": Counter(), "反转后": Counter()}
    for u in users:
        if u["phase_before"] > 0:
            phase_stance["反转前"][u["stance_type"]] += 1
        if u["phase_after"] > 0:
            phase_stance["反转后"][u["stance_type"]] += 1

    phase_cross = []
    for phase in ["反转前", "反转后"]:
        c = phase_stance[phase]
        total = sum(c.get(st, 0) for st in STANCE_TYPES) or 1
        phase_cross.append({
            "phase": phase,
            "counts": {st: c.get(st, 0) for st in STANCE_TYPES},
            "pcts": {st: round(c.get(st, 0) / total * 100, 1) for st in STANCE_TYPES},
            "total": total,
        })

    return {
        "analysisUserCount": n,
        "unclassifiedCount": uncl_n,
        "excludedUnclassified": 0,
        "typeDistribution": type_pct,
        "platformCross": platform_cross,
        "emotionCross": emotion_cross,
        "phaseCross": phase_cross,
    }


def unclassified_reasons(users: list[dict]) -> list[dict]:
    reasons = Counter()
    samples = []
    for u in users:
        if u["stance_type"] != "未分类/边缘样本":
            continue
        if u["post_count"] <= 1:
            reasons["仅1条评论，信号不足"] += 1
        elif u["avg_emotion_intensity"] < 0.15:
            reasons["内容过短/无立场关键词"] += 1
        else:
            reasons["多主题混合，无法归入单一类型"] += 1
        if len(samples) < 5:
            samples.append({
                "user_name": u["user_name"],
                "content": u["sample_content"],
                "post_count": u["post_count"],
            })
    return {
        "reasonCounts": dict(reasons),
        "samples": samples,
        "total": sum(1 for u in users if u["stance_type"] == "未分类/边缘样本"),
    }


def build_scatter_timeline(points: list[dict]) -> dict:
    dates = sorted({p["date"] for p in points if p.get("date")})
    if not dates:
        return {
            "frames": [],
            "start": None,
            "end": None,
            "reversalDate": REVERSAL_DATE.strftime("%Y-%m-%d"),
            "intervalDays": 3,
        }
    start = datetime.strptime(dates[0], "%Y-%m-%d")
    end = datetime.strptime(dates[-1], "%Y-%m-%d")
    frames: list[str] = []
    cur = start
    step_days = 3
    while cur <= end:
        frames.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=step_days)
    if frames[-1] != dates[-1]:
        frames.append(dates[-1])
    return {
        "start": dates[0],
        "end": dates[-1],
        "frames": frames,
        "reversalDate": REVERSAL_DATE.strftime("%Y-%m-%d"),
        "intervalDays": step_days,
    }


def scatter_data(users: list[dict], limit: int = 800) -> tuple[list[dict], dict]:
    """立场散点（全样本用户），含首次发言日期供时间轴动画"""
    import random
    random.seed(42)
    pool = [u for u in users if u.get("first_seen")]
    pool.sort(key=lambda u: u["first_seen"])
    if len(pool) > limit:
        step = len(pool) / limit
        pool = [pool[int(i * step)] for i in range(limit)]
    all_pts = [{
        "x": round(max(0, min(1, u["stance_confidence"] + random.uniform(-0.05, 0.05))), 2),
        "y": round(u["avg_emotion_intensity"], 3),
        "type": u["stance_type"],
        "date": u["first_seen"],
    } for u in pool]
    return all_pts, build_scatter_timeline(all_pts)


def plot_phase_stance_chart(cross: dict) -> Path | None:
    """时间阶段 × 用户类型 · 100% 堆叠条形图（透明底，可单独用于 PPT）"""
    phase_data = cross.get("phaseCross") or []
    if not phase_data:
        return None

    font = pick_font()
    plt.rcParams["font.sans-serif"] = [font]
    plt.rcParams["axes.unicode_minus"] = False

    phases = [p["phase"] for p in phase_data]
    types = [st for st in STANCE_TYPES if any(p["counts"].get(st, 0) for p in phase_data)]

    fig, ax = plt.subplots(figsize=(10, 3.5), facecolor="none")
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")

    y = np.arange(len(phases))
    bar_h = 0.48
    left = np.zeros(len(phases))

    for st in types:
        pcts = np.array([p["pcts"].get(st, 0) for p in phase_data])
        counts = [p["counts"].get(st, 0) for p in phase_data]
        bars = ax.barh(
            y, pcts, bar_h, left=left, label=st,
            color=STANCE_COLORS.get(st, "#888888"),
            edgecolor="white", linewidth=2.0,
        )
        for i, (bar, pct, cnt) in enumerate(zip(bars, pcts, counts)):
            if pct >= 3.0:
                txt_color = "#1a1018" if st in ("Z世代/乐子人", "路人/和事佬") else "#ffffff"
                ax.text(
                    left[i] + pct / 2, bar.get_y() + bar.get_height() / 2,
                    f"{pct:.1f}%",
                    ha="center", va="center", fontsize=10, fontweight="bold", color=txt_color,
                )
        left += pcts

    ax.set_xlim(0, 100)
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{ph}  ·  {phase_data[i]['total']:,} 人" for i, ph in enumerate(phases)],
        fontsize=11, fontweight="bold", color="#2c1810",
    )
    ax.invert_yaxis()

    fig.text(
        0.14, 0.96, "时间阶段 × 用户立场类型",
        fontsize=16, fontweight="bold", color="#2c1810", ha="left", va="top",
    )
    fig.text(
        0.14, 0.885,
        f"反转节点 {REVERSAL_DATE.strftime('%Y-%m-%d')}（李荣浩小眼睛事件）· 有效分类用户",
        fontsize=9.5, color="#8a7578", ha="left", va="top",
    )

    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.tick_params(axis="x", colors="#7a6568", labelsize=9, pad=4)
    ax.tick_params(axis="y", length=0, pad=10)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#d4c4c4")
    ax.grid(axis="x", color="#e8dede", linestyle="-", linewidth=0.6, alpha=0.65)
    ax.set_axisbelow(True)

    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles, labels,
        loc="upper center", bbox_to_anchor=(0.55, 0.06),
        ncol=len(types), frameon=False, fontsize=9,
        handlelength=1.2, columnspacing=1.5, labelcolor="#2c1810",
    )

    fig.subplots_adjust(left=0.14, right=0.98, top=0.80, bottom=0.14)
    _save_transparent(fig, OUT_PHASE_CHART)
    plt.close(fig)
    return OUT_PHASE_CHART


def _setup_chart_style() -> None:
    plt.rcParams["font.sans-serif"] = [pick_font()]
    plt.rcParams["axes.unicode_minus"] = False


def _style_clean_ax(ax, grid_x: bool = True) -> None:
    ax.set_facecolor("none")
    ax.patch.set_alpha(0.0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#ddd0d0")
    if grid_x:
        ax.grid(axis="x", color="#ebe3e3", linestyle="-", linewidth=0.55, alpha=0.8)
        ax.set_axisbelow(True)


def _save_transparent(fig, path: Path, **kwargs) -> None:
    """保存 PNG：画布、坐标轴、色条均为透明背景。"""
    fig.patch.set_alpha(0.0)
    fig.patch.set_facecolor("none")
    for ax in fig.get_axes():
        ax.set_facecolor("none")
        ax.patch.set_alpha(0.0)
    opts = dict(dpi=220, transparent=True, bbox_inches="tight", pad_inches=0.12,
                facecolor="none", edgecolor="none")
    opts.update(kwargs)
    fig.savefig(path, **opts)


def plot_emotion_stance_chart(cross: dict) -> Path | None:
    """用户类型 × 情绪强度 · 均值点 + IQR 区间（透明底）"""
    data = sorted(cross.get("emotionCross") or [], key=lambda x: -x["mean"])
    if not data:
        return None

    _setup_chart_style()
    fig, ax = plt.subplots(figsize=(9.5, 3.5), facecolor="none")

    y = np.arange(len(data))
    xmax = max(ec["q3"] for ec in data) * 1.22

    for i, ec in enumerate(data):
        st = ec["type"]
        color = STANCE_COLORS.get(st, "#888888")
        q1, q3, mean, med = ec["q1"], ec["q3"], ec["mean"], ec["median"]
        ax.barh(
            i, q3 - q1, left=q1, height=0.22, color=color, alpha=0.22,
            edgecolor="none", zorder=1,
        )
        ax.hlines(i, q1, q3, colors=color, linewidth=2.2, alpha=0.65, zorder=2)
        ax.scatter(
            mean, i, s=88, color=color, edgecolors="white", linewidth=1.8, zorder=4,
        )
        ax.scatter(
            med, i, s=42, color="white", edgecolors=color, linewidth=1.4, zorder=5, marker="D",
        )
        ax.text(
            min(mean + 0.006, xmax * 0.92), i, f"μ={mean:.3f}",
            va="center", ha="left", fontsize=8.5, color="#6a5558",
        )

    ax.set_xlim(0, xmax)
    ax.set_yticks(y)
    ax.set_yticklabels([d["type"] for d in data], fontsize=10, color="#2c1810")
    ax.invert_yaxis()
    ax.set_xlabel("情绪强度（LIWC 简化）", fontsize=9.5, color="#8a7578", labelpad=6)
    ax.tick_params(axis="x", colors="#9a8588", labelsize=8.5, pad=3)
    ax.tick_params(axis="y", length=0, pad=8)
    _style_clean_ax(ax)

    fig.text(
        0.12, 0.97, "用户类型 × 情绪强度",
        fontsize=16, fontweight="bold", color="#2c1810", ha="left", va="top",
    )
    fig.text(
        0.12, 0.895, "● 均值  ◇ 中位数  — 四分位区间（Q1–Q3）· 有效分类用户",
        fontsize=9, color="#8a7578", ha="left", va="top",
    )

    fig.subplots_adjust(left=0.22, right=0.94, top=0.82, bottom=0.14)
    _save_transparent(fig, OUT_EMOTION_CHART)
    plt.close(fig)
    return OUT_EMOTION_CHART


def plot_occupation_chart(users: list[dict]) -> Path | None:
    """职业 × 用户立场类型热力图（行内占比，透明底）"""
    stance_cols = STANCE_TYPES

    occ_stance: dict[str, Counter] = defaultdict(Counter)
    for u in users:
        occ = u.get("occupation", "未知")
        st = u.get("stance_type", "")
        if occ == "未知" or st not in stance_cols:
            continue
        occ_stance[occ][st] += 1

    occ_rows = sorted(occ_stance.keys(), key=lambda o: -sum(occ_stance[o].values()))
    if not occ_rows:
        return None

    counts = np.array([
        [occ_stance[occ].get(st, 0) for st in stance_cols]
        for occ in occ_rows
    ], dtype=float)
    row_pct = np.zeros_like(counts)
    for i in range(len(occ_rows)):
        s = counts[i].sum()
        if s > 0:
            row_pct[i] = counts[i] / s * 100
    identified_n = int(counts.sum())
    n_all = len(users)

    fig, ax = plt.subplots(figsize=(9.5, 3.0 + 0.38 * len(occ_rows)), facecolor="none")

    im = ax.imshow(row_pct, aspect="auto", cmap=WINE_CMAP, vmin=0, vmax=max(55, row_pct.max() * 1.05))

    for i in range(len(occ_rows)):
        for j in range(len(stance_cols)):
            c = int(counts[i, j])
            p = row_pct[i, j]
            if c == 0:
                continue
            txt_color = "#ffffff" if p >= 28 else "#3d2a28"
            ax.text(
                j, i, f"{c}\n{p:.0f}%",
                ha="center", va="center", fontsize=8.5, color=txt_color, fontweight="medium",
            )

    ax.set_xticks(range(len(stance_cols)))
    ax.set_xticklabels(
        [STANCE_SHORT.get(st, st) for st in stance_cols],
        fontsize=10, color="#2c1810",
    )
    ax.set_yticks(range(len(occ_rows)))
    ax.set_yticklabels(occ_rows, fontsize=10.5, color="#2c1810")
    ax.tick_params(length=0, pad=6)

    for spine in ax.spines.values():
        spine.set_visible(False)

    cbar = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.02, aspect=20)
    cbar.ax.set_facecolor("none")
    cbar.ax.patch.set_alpha(0.0)
    cbar.ax.tick_params(labelsize=8, colors="#8a7578")
    cbar.set_label("行内占比 (%)", fontsize=8.5, color="#8a7578", labelpad=6)
    cbar.outline.set_visible(False)

    fig.text(
        0.12, 0.97, "职业 × 用户立场类型",
        fontsize=16, fontweight="bold", color="#2c1810", ha="left", va="top",
    )
    fig.text(
        0.12, 0.905,
        f"文本职业线索 × 立场归类 · 已识别 {identified_n:,} 人（占全样本用户 {identified_n / n_all * 100:.1f}%）",
        fontsize=9, color="#8a7578", ha="left", va="top",
    )

    fig.subplots_adjust(left=0.16, right=0.90, top=0.78, bottom=0.16)
    _save_transparent(fig, OUT_OCCUPATION_CHART)
    plt.close(fig)
    return OUT_OCCUPATION_CHART


def plot_charts(users: list[dict], cross: dict):
    font = pick_font()
    plt.rcParams["font.sans-serif"] = [font]
    plt.rcParams["axes.unicode_minus"] = False

    # 1. 占比饼图/条形图
    fig, ax = plt.subplots(figsize=(10, 6))
    labels = [d["type"] for d in cross["typeDistribution"] if d["count"] > 0]
    sizes = [d["count"] for d in cross["typeDistribution"] if d["count"] > 0]
    colors = ["#9B59B6", "#4DA3FF", "#E74C3C", "#F1C40F", "#1ABC9C"]
    ax.barh(labels[::-1], sizes[::-1], color=colors[: len(labels)][::-1])
    ax.set_xlabel("用户数")
    ax.set_title("用户立场类型占比（全样本）")
    fig.tight_layout()
    fig.savefig(BASE / "user_stance_distribution.png", dpi=150)
    plt.close()

    # 2. 平台×类型热力图
    fig, ax = plt.subplots(figsize=(12, 5))
    plats = [p["platform"] for p in cross["platformCross"]]
    data = []
    active_types = [st for st in STANCE_TYPES if any(
        cross["platformCross"][i]["counts"].get(st, 0) > 0 for i in range(len(plats))
    )]
    for st in active_types:
        row = [cross["platformCross"][i]["pcts"].get(st, 0) for i in range(len(plats))]
        data.append(row)
    if data:
        im = ax.imshow(data, aspect="auto", cmap="Purples")
        ax.set_xticks(range(len(plats)))
        ax.set_xticklabels(plats)
        ax.set_yticks(range(len(active_types)))
        ax.set_yticklabels(active_types)
        for i in range(len(active_types)):
            for j in range(len(plats)):
                ax.text(j, i, f"{data[i][j]:.1f}%", ha="center", va="center", fontsize=8)
        ax.set_title("平台 × 用户类型（行百分比 %）")
        fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(BASE / "user_platform_heatmap.png", dpi=150)
    plt.close()

    # 3. 情绪箱线图
    fig, ax = plt.subplots(figsize=(11, 6))
    box_data = []
    box_labels = []
    for ec in cross["emotionCross"]:
        vals = [u["avg_emotion_intensity"] for u in users if u["stance_type"] == ec["type"]]
        if vals:
            box_data.append(vals)
            box_labels.append(ec["type"][:8])
    if box_data:
        ax.boxplot(box_data, tick_labels=box_labels, patch_artist=True,
                   boxprops=dict(facecolor="#BB8FCE", alpha=0.6))
        ax.set_ylabel("情绪强度")
        ax.set_title("用户类型 × 情绪强度")
        plt.xticks(rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(BASE / "user_emotion_boxplot.png", dpi=150)
    plt.close()

    plot_phase_stance_chart(cross)
    plot_emotion_stance_chart(cross)
    plot_occupation_chart(users)


def write_report(users: list[dict], cross: dict, uncl: dict, enrich_meta: dict | None = None):
    n = cross["analysisUserCount"]
    uncl_n = cross.get("unclassifiedCount", uncl["total"])
    lines = [
        "=" * 60,
        "用户画像与立场光谱分析报告",
        f"分析单元: user_id · 全样本用户 {n}（含未分类 {uncl_n} 人）· 反转节点 {REVERSAL_DATE.date()}",
        "=" * 60,
        "",
    ]
    if enrich_meta and enrich_meta.get("enabled"):
        lines += [
            "【历史博文辅助分类】",
            f"  尝试增强: {enrich_meta.get('targets', 0)} 人 · 获取历史文本: {enrich_meta.get('fetched', 0)} 人",
            f"  重新分类成功: {enrich_meta.get('reclassified', 0)} 人",
            f"  未分类: {enrich_meta.get('unclassifiedBefore', 0)} → {enrich_meta.get('unclassifiedAfter', 0)}",
            "",
        ]
    lines += ["【一、立场类型占比（Wilson 95% CI，全样本）】"]
    for d in cross["typeDistribution"]:
        if d["count"] == 0:
            continue
        lines.append(
            f"  {d['type']}: {d['count']} ({d['pct']}%)  CI [{d['ci_low']}%, {d['ci_high']}%]"
        )

    lines += ["", "【二、平台 × 用户类型】"]
    for p in cross["platformCross"]:
        lines.append(f"  {p['platform']} (n={p['total']}):")
        top = sorted(p["counts"].items(), key=lambda x: -x[1])[:4]
        for st, c in top:
            if c:
                lines.append(f"    {st}: {c} ({p['pcts'][st]}%)")

    lines += ["", "【三、用户类型 × 情绪强度】"]
    for ec in cross["emotionCross"]:
        lines.append(
            f"  {ec['type']}: mean={ec['mean']} median={ec['median']} "
            f"Q1={ec['q1']} Q3={ec['q3']} (n={ec['count']})"
        )

    lines += ["", "【四、时间阶段 × 用户类型】"]
    for ph in cross["phaseCross"]:
        lines.append(f"  {ph['phase']} (n={ph['total']}):")
        top = sorted(ph["counts"].items(), key=lambda x: -x[1])[:5]
        for st, c in top:
            if c:
                lines.append(f"    {st}: {c} ({ph['pcts'][st]}%)")

    lines += ["", "【五、未分类用户构成说明】", f"  合计 {uncl['total']} 人"]
    for reason, c in uncl["reasonCounts"].items():
        lines.append(f"    · {reason}: {c}")

    lines += ["", "【六、基础画像摘要（全样本）】"]
    fan_c = Counter(u["fan_group"] for u in users)
    occ_c = Counter(u["occupation"] for u in users)
    lines.append(f"  粉丝归属 Top: {fan_c.most_common(3)}")
    lines.append(f"  职业线索 Top: {occ_c.most_common(4)}")

    swing = [u for u in users if u["stance_type"] == "摇摆型"]
    lines += ["", f"【七、摇摆型样本 (n={len(swing)})】",
              "  规则：两者都夸单依纯+李荣浩，或两者都骂，才属摇摆型"]
    for u in swing[:8]:
        lines.append(
            f"  @{u['user_name']}: {u.get('fan_evidence', '')} · "
            f"夸纯{u.get('praise_syc', 0)}/骂纯{u.get('attack_syc', 0)}/"
            f"夸浩{u.get('praise_lrh', 0)}/骂浩{u.get('attack_lrh', 0)} · "
            f"{u['sample_content'][:40]}"
        )

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")


def export_user_profile_screen_js():
    """导出供 dispute_dashboard 屏3 嵌入的脚本"""
    if not HTML_TEMPLATE.exists():
        return
    tpl = HTML_TEMPLATE.read_text(encoding="utf-8")
    start = tpl.index("const STANCE_COLOR = {")
    end = tpl.index("async function loadData()")
    core = tpl[start:end]
    init_block = """
  function loadData() {
    if (window.__DISPUTE__ && window.__DISPUTE__.userProfile) return window.__DISPUTE__.userProfile;
    if (window.__USER_PROFILE__ && window.__USER_PROFILE__.userProfile) return window.__USER_PROFILE__.userProfile;
    return null;
  }
  function init() {
    if (_inited) { resizeAll(); return; }
    DATA = loadData();
    if (!DATA) return;
    var noteEl = document.getElementById("noteText");
    if (noteEl) {
      noteEl.textContent = DATA.meta.event + " · 全样本 "
        + fmt(DATA.meta.analysisUsers || DATA.summary.analysisUsers) + " 人"
        + "（含未分类 " + fmt(DATA.meta.unclassifiedCount || DATA.summary.unclassifiedCount || 0) + " 人）"
        + " · " + fmt(DATA.meta.totalComments) + " 条评论 · 生成 " + DATA.meta.generatedAt;
    }
    var classifiedSub = document.getElementById("classifiedSub");
    if (classifiedSub) {
      classifiedSub.textContent = "n = " + fmt(DATA.meta.analysisUsers || DATA.summary.analysisUsers)
        + " · 占比分母为全样本用户（含未分类/边缘样本）";
    }
    var phaseSub = document.getElementById("phaseSub");
    if (phaseSub) phaseSub.textContent = DATA.meta.reversalNote;
    renderKpi(DATA);
    renderStanceBar("chartStanceAll", DATA.typeDistribution);
    renderFan((DATA.profileSummary && DATA.profileSummary.fanGroup) || {});
    renderProfile(DATA.profileSummary || {});
    renderHeat(DATA.platformCross || [], DATA.stanceTypes || []);
    renderEmotion(DATA.emotionCross || []);
    renderPhase(DATA.phaseCross || [], DATA.stanceTypes || []);
    _inited = true;
    setTimeout(resizeAll, 120);
  }
"""
    js = (
        "// Auto-generated · do not edit · run user_profile_analysis.py\n"
        "window.UserProfileScreen = (function () {\n"
        "  var DATA = null;\n"
        "  var charts = [];\n"
        "  var _inited = false;\n"
        + core
        + init_block
        + "  return { init: init, resize: resizeAll };\n"
        "})();\n"
    )
    js_out = P.目录_前端 / "屏3用户画像.js"
    js_out.parent.mkdir(parents=True, exist_ok=True)
    js_out.write_text(js, encoding="utf-8")


def build_html(stats: dict) -> None:
    """生成独立屏3仪表盘页（内嵌 JSON，双击可打开）"""
    if not HTML_TEMPLATE.exists():
        return
    tpl = HTML_TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps({"userProfile": stats}, ensure_ascii=False)
    html = tpl.replace("__USER_PROFILE_JSON__", payload)
    OUT_HTML.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="用户画像与立场光谱分析")
    parser.add_argument(
        "--enrich",
        "--enrich-history",
        dest="enrich",
        action="store_true",
        help="爬取未分类微博用户的往期博文（内存，不保存）以辅助分类",
    )
    parser.add_argument(
        "--enrich-limit",
        type=int,
        default=300,
        help="最多爬取多少个未分类微博用户（默认 300）",
    )
    parser.add_argument(
        "--enrich-pages",
        type=int,
        default=2,
        help="每个用户爬取的时间线页数（默认 2）",
    )
    parser.add_argument(
        "--enrich-posts",
        type=int,
        default=20,
        help="每个用户最多使用的历史博文条数（默认 20）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Step 5 · 用户画像与立场光谱分析")
    print("=" * 60)

    try:
        rows = load_merged_rows()
    except FileNotFoundError as e:
        print(e)
        return

    print(f"输入评论: {len(rows)} 条")
    print(f"  来源: {IN_CLEANED.name}")

    by_user: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        uid = (r.get("user_id") or "").strip()
        plat = r.get("platform", "")
        if not uid:
            # 抖音无评论者 ID，以 comment_id 代表单次发言用户
            if plat == "douyin":
                cid = (r.get("comment_id") or "").strip()
                uid = f"douyin_cmt:{cid}" if cid else f"douyin_hash:{hash(r.get('content', '')[:40]) % 10**10}"
            else:
                name = (r.get("user_name") or "").strip()
                if name:
                    uid = f"{plat}:{name}"
                else:
                    uid = f"anon_{hash(r.get('content', '')[:30]) % 10**8}"
        by_user[uid].append(r)

    users = [aggregate_user(uid, recs) for uid, recs in by_user.items()]
    enrich_meta: dict = {"enabled": False}

    if args.enrich:
        uncl_before = sum(1 for u in users if u["stance_type"] == UNCLASSIFIED)
        weibo_uncl = sum(
            1 for u in users
            if u["stance_type"] == UNCLASSIFIED and is_weibo_numeric_user(u["user_id"], by_user[u["user_id"]])
        )
        print(f"\n[历史博文增强] 未分类 {uncl_before} 人，其中微博数字 UID {weibo_uncl} 人")
        targets = collect_enrich_targets(users, by_user, args.enrich_limit)
        enrich_meta = {
            "enabled": True,
            "targets": len(targets),
            "unclassifiedBefore": uncl_before,
        }
        if targets:
            print(f"  开始爬取 {len(targets)} 个用户（每用户 ≤{args.enrich_pages} 页 / {args.enrich_posts} 条）…")
            before_stance = {u["user_id"]: u["stance_type"] for u in users}
            history_cache = enrich_weibo_user_histories(
                targets,
                max_pages=args.enrich_pages,
                max_posts=args.enrich_posts,
            )
            enrich_meta["fetched"] = len(history_cache)
            users = [
                aggregate_user(
                    uid, recs,
                    extra_texts=history_cache.get(uid),
                    enriched=uid in history_cache,
                )
                for uid, recs in by_user.items()
            ]
            uncl_after = sum(1 for u in users if u["stance_type"] == UNCLASSIFIED)
            reclassified = sum(
                1 for uid in history_cache
                if before_stance.get(uid) == UNCLASSIFIED
                and any(
                    u["user_id"] == uid and u["stance_type"] != UNCLASSIFIED
                    for u in users
                )
            )
            enrich_meta["unclassifiedAfter"] = uncl_after
            enrich_meta["reclassified"] = reclassified
            print(
                f"  增强完成: 获取 {len(history_cache)} 人历史博文，"
                f"新分类 {reclassified} 人，未分类 {uncl_before} → {uncl_after}"
            )
        else:
            enrich_meta["fetched"] = 0
            enrich_meta["reclassified"] = 0
            enrich_meta["unclassifiedAfter"] = uncl_before
            print("  无可爬取的微博未分类用户，跳过")

    users.sort(key=lambda x: -x["post_count"])
    print(f"独立用户: {len(users)}")

    cross = build_cross_tables(users)
    uncl = unclassified_reasons(users)
    n_all = len(users)
    uncl_n = cross.get("unclassifiedCount", 0)

    fieldnames = list(users[0].keys()) if users else []
    with open(OUT_USERS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for u in users:
            row = dict(u)
            row["stance_evidence"] = "|".join(u["stance_evidence"])
            if isinstance(row.get("fan_evidence"), list):
                row["fan_evidence"] = "|".join(row["fan_evidence"])
            w.writerow(row)

    profile_summary = {
        "fanGroup": dict(Counter(u["fan_group"] for u in users).most_common(8)),
        "occupation": dict(Counter(u["occupation"] for u in users).most_common(6)),
    }

    swing_n = sum(1 for u in users if u["stance_type"] == "摇摆型")
    stats = {
        "meta": {
            "title": "用户画像与立场光谱",
            "event": "单依纯×李荣浩《李白》争议",
            "totalUsers": n_all,
            "analysisUsers": n_all,
            "unclassifiedCount": uncl_n,
            "excludedUnclassified": 0,
            "totalComments": len(rows),
            "reversalDate": REVERSAL_DATE.strftime("%Y-%m-%d"),
            "reversalNote": "2026-04-01 李荣浩从维权者转为被指控侵权者（小眼睛事件）",
            "generatedAt": datetime.now().strftime("%Y-%m-%d"),
            "method": "规则词典 + 用户级聚合；全样本用户统计（含未分类/边缘样本）"
            + ("；部分用户结合历史博文辅助分类（未持久化）" if enrich_meta.get("enabled") else ""),
            "sources": ["cleaned_comments.csv"],
            "dataNotes": [
                "微博/小红书：以 user_id 为用户单元",
                "抖音：原始数据无评论者 ID，以 comment_id 代理（每条评论=一个匿名用户声音）",
                "约 52% 微博帖子无 user_id，已回退为 platform:user_name 聚合",
                f"全样本 {n_all:,} 用户；其中未分类/边缘样本 {uncl_n:,} 人（占比 {uncl_n / n_all * 100:.1f}%）",
            ]
            + ([
                f"历史博文增强: 爬取 {enrich_meta.get('targets', 0)} 人，"
                f"成功 {enrich_meta.get('fetched', 0)} 人，新分类 {enrich_meta.get('reclassified', 0)} 人"
            ] if enrich_meta.get("enabled") else []),
            "historyEnrichment": enrich_meta if enrich_meta.get("enabled") else None,
        },
        "summary": {
            "analysisUsers": n_all,
            "unclassifiedCount": uncl_n,
            "swingCount": swing_n,
            "swingPct": round(swing_n / n_all * 100, 2) if n_all else 0,
            "excludedUnclassified": 0,
        },
        "typeDistribution": cross["typeDistribution"],
        "platformCross": cross["platformCross"],
        "emotionCross": cross["emotionCross"],
        "phaseCross": cross["phaseCross"],
        "profileSummary": profile_summary,
        "unclassifiedReasons": uncl,
        "stanceTypes": STANCE_TYPES,
        "platformLabels": PLAT_NAMES,
    }

    OUT_JSON.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JS.write_text(f"window.USER_PROFILE_STATS = {json.dumps(stats, ensure_ascii=False)};", encoding="utf-8")
    build_html(stats)
    export_user_profile_screen_js()

    write_report(users, cross, uncl, enrich_meta)
    print("生成图表...")
    plot_charts(users, cross)

    print(f"产出: {OUT_USERS}")
    print(f"产出: {OUT_JSON}")
    print(f"产出: {OUT_JS}")
    print(f"产出: {OUT_REPORT}")
    if OUT_HTML.exists():
        print(f"产出: {OUT_HTML}")
    if OUT_PHASE_CHART.exists():
        print(f"产出: {OUT_PHASE_CHART}")
    if OUT_EMOTION_CHART.exists():
        print(f"产出: {OUT_EMOTION_CHART}")
    if OUT_OCCUPATION_CHART.exists():
        print(f"产出: {OUT_OCCUPATION_CHART}")
    js_out = P.目录_前端 / "屏3用户画像.js"
    if js_out.exists():
        print(f"产出: {js_out}")
    print(f"[完成] 全样本用户 {n_all}（未分类 {uncl_n}），"
          f"摇摆型 {stats['summary']['swingCount']} ({stats['summary']['swingPct']}%)")


if __name__ == "__main__":
    main()

"""微博用户粉籍识别：从内容中自动发现艺人，并结合情感倾向判断。"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
COOKIE_FILE = BASE_DIR / "cookie"

MIN_DELAY = 1.5
MAX_DELAY = 2.5
MAX_POSTS = 50
MAX_PAGES = 3
CONFIDENCE_THRESHOLD = 0.7
MIN_FAN_SCORE = 2.0

# 粉丝向情感词（共现则加分）
POSITIVE_FAN = [
    "爱", "喜欢", "最爱", "心动", "支持", "加油", "冲", "打call", "打榜", "安利",
    "绝美", "太美", "太帅", "好看", "帅", "美", "可爱", "宝藏", "神仙", "绝了",
    "期待", "守护", "陪伴", "永远", "唯一", "本命", "墙头", "入坑", "真香",
    "啊啊啊", "awsl", "呜呜", "泪目", "感动", "骄傲", "优秀", "厉害", "棒",
    "签到", "应援", "做数据", "反黑", "控评", "专转", "净化", "发帖", "超话",
    "哥哥", "姐姐", "宝宝", "宝贝", "老婆", "老公", "崽", "女鹅", "儿砸",
    "出圈", "爆", "火", "红", "顶流", "实力", "才华", "努力", "值得",
]

# 明显非粉丝/负面倾向（共现则扣分）
NEGATIVE = [
    "讨厌", "恶心", "烦", "滚", "黑", "塌房", "翻车", "骂", "喷", "撕",
    "抵制", "避雷", "下头", "无语", "垃圾", "丑", "装", "假", "骗", "崩",
    "脱粉", "回踩", "路人转黑", "粉转黑", "不再", "算了", "失望",
    "气死", "毁了", "烂", "瞎", "崩溃", "退钱",
]

# 纯活动/平台词，不应作为艺人名
ENTITY_STOPWORDS = {
    "微博", "超话", "视频", "图片", "评论", "转发", "热搜", "话题", "网页链接",
    "中国", "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安",
    "今天", "明天", "昨天", "每日", "实时", "热门", "推荐", "关注", "粉丝",
    "开新年", "集卡", "红包", "抽奖", "直播", "综艺", "电影", "电视剧", "音乐",
    "分钟视频", "三分钟视频", "视频累计", "微博开新年", "微博抓马",
}

# 新闻/社会事件类词：含这些的子串大概率不是艺人
NEWS_LIKE = re.compile(
    r"车祸|遇害|男童|女童|纵火|烧死|判决|一审|二审|死缓|肇事|司机|"
    r"小区|物业|保安|监控|报警|立案|拘留|通报|回应|质疑|"
    r"游乐园|安全指南|消防|程序员|猝死|录音|传播|"
    r"追光吧|冲浪吧|人气榜|加光|闪耀|神器|"
    r"新闻|日报|晚报|电视台|卫视|央视|记者|爆料"
)

SENTENCE_SPLIT = re.compile(r"[。！？!?；;\n]+")
ENTITY_AT = re.compile(r"@([\u4e00-\u9fffA-Za-z0-9_·]{2,20})")
ENTITY_CHAOHUA = re.compile(r"#([^#\[\]]{2,20})\[超话\]")
ENTITY_HASHTAG = re.compile(r"#([^#@\[\]]{2,20})#")


def load_cookie() -> str:
    return COOKIE_FILE.read_text(encoding="utf-8").strip()


def make_session(cookie: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Cookie": cookie,
            "Referer": "https://weibo.com/",
            "Accept": "application/json, text/plain, */*",
        }
    )
    return session


def normalize_id_column(df: pd.DataFrame) -> pd.DataFrame:
    if "user_id" not in df.columns:
        df = df.rename(columns={df.columns[0]: "user_id"})
    df["user_id"] = df["user_id"].astype(str).str.strip()
    return df


def dedupe_ids(input_path: Path, output_path: Path) -> pd.DataFrame:
    df = normalize_id_column(pd.read_excel(input_path))
    before = len(df)
    deduped = df.drop_duplicates(subset=["user_id"], keep="first").reset_index(drop=True)
    deduped.to_excel(output_path, index=False)
    print(f"Dedup: {before} -> {len(deduped)} unique IDs -> {output_path.name}")
    return deduped


def is_weibo_uid(uid: str) -> bool:
    return bool(re.match(r"^\d{5,12}$", str(uid)))


def fetch_profile(session: requests.Session, uid: str) -> dict:
    url = f"https://weibo.com/ajax/profile/info?uid={uid}"
    resp = session.get(url, timeout=20)
    data = resp.json()
    if data.get("ok") != 1:
        raise RuntimeError(data.get("msg") or data.get("error") or "profile failed")
    user = data["data"]["user"]
    return {
        "screen_name": user.get("screen_name", ""),
        "description": user.get("description", ""),
        "gender": user.get("gender", ""),
        "location": user.get("location", ""),
        "followers_count": user.get("followers_count", 0),
        "friends_count": user.get("friends_count", 0),
        "statuses_count": user.get("statuses_count", 0),
        "verified": user.get("verified", False),
    }


def fetch_posts(session: requests.Session, uid: str) -> list[str]:
    posts: list[str] = []
    for page in range(1, MAX_PAGES + 1):
        url = f"https://weibo.com/ajax/statuses/mymblog?uid={uid}&page={page}&feature=0"
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            break
        data = resp.json()
        if data.get("ok") != 1:
            break
        items = data.get("data", {}).get("list", [])
        if not items:
            break
        for item in items:
            text = item.get("text_raw") or item.get("text") or ""
            text = re.sub(r"<[^>]+>", "", text)
            rt = item.get("retweeted_status")
            if rt:
                rt_text = rt.get("text_raw") or rt.get("text") or ""
                text += " " + re.sub(r"<[^>]+>", "", rt_text)
            posts.append(text)
            if len(posts) >= MAX_POSTS:
                return posts
        time.sleep(random.uniform(0.3, 0.6))
    return posts


def looks_like_artist(name: str) -> bool:
    """启发式判断实体是否像艺人/人物，而非新闻话题或活动。"""
    if NEWS_LIKE.search(name):
        return False
    cn = re.findall(r"[\u4e00-\u9fff]", name)
    en = re.findall(r"[A-Za-z]", name)
    if len(cn) >= 2 and len(cn) <= 6 and len(name) <= 8:
        return True
    if en and len(name) <= 15 and not re.search(r"\d{3,}", name):
        return True
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
        return True
    return False


def normalize_entity(name: str, source: str = "hashtag") -> str:
    name = name.strip().strip("#").strip()
    name = re.sub(r"\s+", "", name)
    if len(name) < 2 or len(name) > 20:
        return ""
    if name in ENTITY_STOPWORDS:
        return ""
    if re.fullmatch(r"[\dW]+", name):
        return ""
    if source == "hashtag" and len(name) > 10:
        return ""
    if not looks_like_artist(name):
        return ""
    return name


def extract_entities(text: str) -> list[tuple[str, str]]:
    """返回 (艺人名, 来源类型) 列表。来源: chaohua/at/hashtag/name"""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(raw: str, source: str) -> None:
        name = normalize_entity(raw, source)
        if name and name not in seen:
            seen.add(name)
            found.append((name, source))

    for m in ENTITY_CHAOHUA.finditer(text):
        add(m.group(1), "chaohua")
    for m in ENTITY_AT.finditer(text):
        add(m.group(1), "at")
    for m in ENTITY_HASHTAG.finditer(text):
        add(m.group(1), "hashtag")
    return found


def sentiment_score(text: str) -> float:
    """对一段文本计算情感倾向分，正为粉丝向，负为反感。"""
    score = 0.0
    for w in POSITIVE_FAN:
        score += text.count(w) * 1.0
    for w in NEGATIVE:
        score -= text.count(w) * 1.5
    return score


def score_entities_in_text(text: str, source_weight: float = 1.0) -> dict[str, float]:
    """在文本各句中，将情感分归属到共现艺人。"""
    entity_scores: dict[str, float] = defaultdict(float)
    for sentence in SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        entities = extract_entities(sentence)
        if not entities:
            continue
        sent = sentiment_score(sentence)
        for name, source in entities:
            weight = source_weight
            if source == "chaohua":
                weight *= 3.0
            elif source == "at":
                weight *= 1.5
            elif source == "hashtag":
                weight *= 1.2
            # 长超话名（多为游戏/IP）需有正面情感才计分
            if source == "chaohua" and len(name) > 8 and sent <= 0:
                continue
            if sent > 0:
                entity_scores[name] += sent * weight
            elif sent < 0:
                entity_scores[name] += sent * weight * 0.8
            elif source == "chaohua":
                entity_scores[name] += 1.0 * weight
    return dict(entity_scores)


def classify_user(profile: dict, posts: list[str]) -> dict:
    name_text = profile.get("screen_name", "")
    desc_text = profile.get("description", "")
    combined_scores: dict[str, float] = defaultdict(float)
    evidence: dict[str, list[str]] = defaultdict(list)

    for text, weight in [
        (name_text, 2.5),
        (desc_text, 2.0),
    ]:
        if not text:
            continue
        for entity, score in score_entities_in_text(text, weight).items():
            combined_scores[entity] += score
            if score > 0:
                evidence[entity].append(f"[简介/昵称] {text[:60]}")

    for post in posts:
        for entity, score in score_entities_in_text(post, 1.0).items():
            combined_scores[entity] += score
            if score >= 2:
                evidence[entity].append(post[:80])

    positive = {k: v for k, v in combined_scores.items() if v > 0}
    if not positive:
        return {
            "fandom_label": "无法判断",
            "predicted_fandom": "无法判断",
            "confidence": 0.0,
            "fan_score": 0.0,
            "sentiment_summary": "未发现明显粉丝向情感",
            "top_candidates": "",
            "evidence": "",
            "in_conf80": False,
        }

    total = sum(positive.values())
    ranked = sorted(positive.items(), key=lambda x: x[1], reverse=True)
    best_name, best_score = ranked[0]
    confidence = best_score / total if total > 0 else 0.0

    top3 = ranked[:3]
    top_candidates = "; ".join(f"{n}({s:.1f})" for n, s in top3)
    ev_text = " | ".join(evidence.get(best_name, [])[:3])

    in_conf = confidence >= CONFIDENCE_THRESHOLD and best_score >= MIN_FAN_SCORE
    pool_label = f"不在conf{int(CONFIDENCE_THRESHOLD * 100)}池"
    if in_conf:
        fandom_label = best_name
    elif best_score >= MIN_FAN_SCORE:
        fandom_label = pool_label
    else:
        fandom_label = "无法判断"

    sentiment_summary = "正面粉丝向" if best_score >= MIN_FAN_SCORE else "情感信号偏弱"

    return {
        "fandom_label": fandom_label,
        "predicted_fandom": best_name,
        "confidence": round(confidence, 4),
        "fan_score": round(best_score, 2),
        "sentiment_summary": sentiment_summary,
        "top_candidates": top_candidates,
        "evidence": ev_text[:500],
        "in_conf80": in_conf,
    }


def load_checkpoint(checkpoint_file: Path) -> dict:
    records_file = checkpoint_file.with_suffix(".jsonl")
    if checkpoint_file.exists():
        data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        if data.get("version") in (2, 3):
            if data.get("version") == 2 and data.get("records"):
                # 迁移旧版大文件：records 落盘到 jsonl，checkpoint 只留 done
                with records_file.open("w", encoding="utf-8") as f:
                    for row in data["records"]:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                data = {"version": 3, "done": data["done"]}
                save_checkpoint(data, checkpoint_file, records_file)
            if records_file.exists() and not data.get("records"):
                data["records"] = []
            return data
    return {"version": 3, "done": [], "records": []}


def save_checkpoint(checkpoint: dict, checkpoint_file: Path, records_file: Path | None = None) -> None:
    records_file = records_file or checkpoint_file.with_suffix(".jsonl")
    slim = {"version": 3, "done": checkpoint["done"]}
    checkpoint_file.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")


def append_record(row: dict, records_file: Path) -> None:
    with records_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_all_records(records_file: Path) -> list[dict]:
    if not records_file.exists():
        return []
    rows = []
    for line in records_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def crawl_all(
    input_file: Path,
    dedup_file: Path,
    output_file: Path,
    checkpoint_file: Path,
    resume: bool = False,
) -> pd.DataFrame:
    checkpoint = load_checkpoint(checkpoint_file) if resume else {"version": 3, "done": [], "records": []}
    records_file = checkpoint_file.with_suffix(".jsonl")
    done = set(checkpoint["done"])
    records = []  # 续爬只需 done 集合，结果从 jsonl 追加

    df = dedupe_ids(input_file, dedup_file)
    origin_map = {}
    if "origin" in df.columns:
        origin_map = dict(zip(df["user_id"].astype(str), df["origin"].astype(str)))
    all_ids = df["user_id"].astype(str).tolist()
    weibo_ids = [uid for uid in all_ids if is_weibo_uid(uid)]
    non_weibo_ids = [uid for uid in all_ids if not is_weibo_uid(uid)]

    print(f"Total: {len(all_ids)}, Weibo IDs: {len(weibo_ids)}, Non-Weibo: {len(non_weibo_ids)}")

    for uid in non_weibo_ids:
        if uid in done:
            continue
        records.append(
            {
                "user_id": uid,
                "origin": origin_map.get(uid, ""),
                "platform": "非微博ID",
                "screen_name": "",
                "description": "",
                "fandom_label": "跳过-非微博ID",
                "predicted_fandom": "",
                "confidence": 0.0,
                "fan_score": 0.0,
                "sentiment_summary": "",
                "top_candidates": "",
                "evidence": "",
                "posts_sample": "",
                "status": "skipped",
            }
        )
        done.add(uid)

    cookie = load_cookie()
    session = make_session(cookie)
    pending = [uid for uid in weibo_ids if uid not in done]

    for idx, uid in enumerate(pending, 1):
        print(f"[{idx}/{len(pending)}] Crawling {uid}...", flush=True)
        row = {
            "user_id": uid,
            "origin": origin_map.get(uid, ""),
            "platform": "微博",
            "screen_name": "",
            "description": "",
            "fandom_label": "",
            "predicted_fandom": "",
            "confidence": 0.0,
            "fan_score": 0.0,
            "sentiment_summary": "",
            "top_candidates": "",
            "evidence": "",
            "posts_sample": "",
            "status": "ok",
        }
        try:
            profile = fetch_profile(session, uid)
            posts = fetch_posts(session, uid)
            result = classify_user(profile, posts)

            row.update(
                {
                    "screen_name": profile.get("screen_name", ""),
                    "description": profile.get("description", ""),
                    "followers_count": profile.get("followers_count", 0),
                    "statuses_count": profile.get("statuses_count", 0),
                    "fandom_label": result["fandom_label"],
                    "predicted_fandom": result["predicted_fandom"],
                    "confidence": result["confidence"],
                    "fan_score": result["fan_score"],
                    "sentiment_summary": result["sentiment_summary"],
                    "top_candidates": result["top_candidates"],
                    "evidence": result["evidence"],
                    "posts_sample": " || ".join(posts[:3])[:500],
                }
            )

            print(
                f"  -> {row['screen_name']} | {row['fandom_label']} "
                f"(conf={row['confidence']:.0%}, score={row['fan_score']})",
                flush=True,
            )
        except Exception as exc:
            row["status"] = "error"
            row["fandom_label"] = "抓取失败"
            row["posts_sample"] = f"error: {exc}"
            print(f"  -> ERROR: {exc}", flush=True)

        records.append(row)
        done.add(uid)
        checkpoint["done"] = list(done)
        append_record(row, records_file)
        save_checkpoint(checkpoint, checkpoint_file, records_file)

        if idx % 20 == 0:
            print(f"  [checkpoint] {len(done)}/2582 done", flush=True)

        if idx < len(pending):
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    result_df = pd.DataFrame(load_all_records(records_file) or records)
    result_df.to_excel(output_file, index=False)
    print_summary(result_df, output_file)
    return result_df


def print_summary(df: pd.DataFrame, output_file: Path) -> None:
    print("\n=== Summary ===")
    print(f"Total records: {len(df)}")
    print("\nFandom labels (top 15):")
    print(df["fandom_label"].value_counts().head(15).to_string())
    pool_label = f"不在conf{int(CONFIDENCE_THRESHOLD * 100)}池"
    conf80 = (df["fandom_label"].notna() & ~df["fandom_label"].isin(
        [pool_label, "无法判断", "跳过-非微博ID", "抓取失败"]
    )).sum()
    print(f"\nIn conf{int(CONFIDENCE_THRESHOLD*100)} pool: {conf80} ({conf80 / max(len(df), 1) * 100:.1f}%)")
    print(f"Output: {output_file}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="微博粉籍爬取与推断")
    p.add_argument("--input", default="id.xlsx", help="输入 xlsx")
    p.add_argument("--dedup", default=None, help="去重后 xlsx，默认同名 _deduped")
    p.add_argument("--output", default=None, help="结果 xlsx，默认同名 _result")
    p.add_argument("--checkpoint", default=None, help="断点 json")
    p.add_argument("--resume", action="store_true", help="断点续爬")
    return p.parse_args()


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    stem = Path(args.input).stem
    input_file = BASE_DIR / args.input
    dedup_file = BASE_DIR / (args.dedup or f"{stem}_deduped.xlsx")
    output_file = BASE_DIR / (args.output or f"weibo_fandom_result_{stem}.xlsx")
    checkpoint_file = BASE_DIR / (args.checkpoint or f"crawl_checkpoint_{stem}.json")
    return input_file, dedup_file, output_file, checkpoint_file


if __name__ == "__main__":
    args = parse_args()
    paths = resolve_paths(args)
    crawl_all(*paths, resume=args.resume)

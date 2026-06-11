#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微博爬虫：单依纯 × 李荣浩 × 《李白》版权事件相关帖子

使用前请在浏览器登录 weibo.com，复制 Cookie 到 cookie.txt 或设置环境变量 WEIBO_COOKIE。

运行: python weibo_scraper.py
输出: weibo_posts.csv
"""

from __future__ import annotations

import sys
from pathlib import Path as _Path
_R = _Path(__file__).resolve().parent.parent
if str(_R) not in sys.path:
    sys.path.insert(0, str(_R))
import 项目路径 as P

import csv
import json
import os
import re
import sys
import time
import random
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# ── 配置 ──────────────────────────────────────────────────────────────────────

MIN_LIKES = 20
MIN_COMMENTS = 20
REQUEST_DELAY = (1.5, 3.0)
MAX_SEARCH_PAGES = 50
MAX_USER_PAGES = 30
MAX_COMMENT_PAGES = 5
MAX_COMMENTS_PER_POST = 100
OUTPUT_CSV = "weibo_posts.csv"
OUTPUT_COMMENTS_CSV = "weibo_comments.csv"
COOKIE_FILE = "cookie.txt"

COMMENT_CSV_FIELDS = [
    "帖子ID", "帖子链接", "帖子作者", "帖子作者UID", "来源类型", "帖子发布时间",
    "帖子话题标签", "帖子点赞数", "帖子评论数", "帖子转发数",
    "评论ID", "评论者", "评论者UID", "评论时间", "评论内容", "评论话题标签", "评论点赞数",
]

# 事件相关时间范围（可放宽以覆盖讨论余波）
EVENT_START = datetime(2026, 3, 25)
EVENT_END = datetime(2026, 5, 31, 23, 59, 59)

# 目标账号
TARGET_USERS: dict[str, str] = {
    "单依纯": "5598574734",
    "单依纯官方工作室": "6026098745",
    "李荣浩": "1739046981",
}

# 搜索关键词（覆盖当事人、工作室、超话、粉丝讨论）
SEARCH_KEYWORDS = [
    "单依纯 李荣浩 李白",
    "单依纯 李白 侵权",
    "李荣浩 单依纯 侵权",
    "单依纯 李荣浩",
    "李荣浩 李白 单依纯",
    "单依纯 道歉 李白",
    "李荣浩 喊话 单依纯",
    "#单依纯# 李白",
    "#李荣浩# 单依纯",
    "百沐娱乐 李白",
    "单依纯 强行侵权",
    "单依纯 版权 李白",
]

# 额外搜索的账号名称（运行时动态解析 UID）
EXTRA_USER_NAMES = ["百沐娱乐"]

def log(msg: str):
    print(msg, flush=True)


BASE_DIR = Path(__file__).resolve().parent


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def try_load_cookie() -> str | None:
    """读取 Cookie，不存在时返回 None（不退出进程）。"""
    env = os.environ.get("WEIBO_COOKIE", "").strip()
    if env:
        return env
    cookie_path = P.Cookie文件
    if cookie_path.exists():
        return cookie_path.read_text(encoding="utf-8").strip()
    return None


def load_cookie() -> str:
    cookie = try_load_cookie()
    if cookie:
        return cookie
    cookie_path = P.Cookie文件
    print(
        "错误：未找到微博 Cookie。\n"
        "请登录 https://weibo.com 后，在浏览器开发者工具 Network 中复制 Cookie，\n"
        f"保存到 {cookie_path} 或设置环境变量 WEIBO_COOKIE。"
    )
    sys.exit(1)


def parse_cookie_str(cookie_str: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def build_headers(cookie_str: str, referer: str = "https://weibo.com/") -> dict[str, str]:
    xsrf = parse_cookie_str(cookie_str).get("XSRF-TOKEN", "")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
        "Cookie": cookie_str,
        "X-Requested-With": "XMLHttpRequest",
    }
    if xsrf:
        headers["X-Xsrf-Token"] = unescape(xsrf)
    return headers


def sleep():
    time.sleep(random.uniform(*REQUEST_DELAY))


def clean_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text(separator="", strip=True)


def extract_topics(text: str) -> list[str]:
    """从正文或 HTML 中提取 #话题#"""
    raw = unescape(text or "")
    topics = re.findall(r"#([^#]+?)#", raw)
    # 去重保序
    seen: set[str] = set()
    result: list[str] = []
    for t in topics:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def is_event_related(text: str, topics: list[str], author: str = "") -> bool:
    """判断是否与单依纯 × 李荣浩 × 《李白》版权争议事件相关。"""
    from filter_libai_event import is_libai_copyright_event
    return is_libai_copyright_event(text, " ".join(topics), author)


def parse_weibo_time(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    formats = [
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%a %b %d %H:%M:%S +0800 %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=None)
        except ValueError:
            continue
    # 移动端 created_at: "Mon Mar 29 14:00:00 +0800 2026"
    m = re.match(
        r"(\w{3}) (\w{3}) (\d{1,2}) (\d{2}:\d{2}:\d{2}) ([+-]\d{4}) (\d{4})",
        s,
    )
    if m:
        try:
            return datetime.strptime(
                f"{m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)} {m.group(5)} {m.group(6)}",
                "%a %b %d %H:%M:%S %z %Y",
            ).replace(tzinfo=None)
        except ValueError:
            pass
    return None


def in_event_range(dt: datetime | None) -> bool:
    if dt is None:
        return True  # 无法解析时间时保留
    return EVENT_START <= dt <= EVENT_END


def passes_engagement(likes: int, comments: int) -> bool:
    return likes > MIN_LIKES or comments > MIN_COMMENTS


def normalize_comment_item(item: dict[str, Any], source: str = "pc") -> dict[str, Any]:
    """将 PC / 移动端评论 API 返回项统一为结构化字段。"""
    user = item.get("user") or {}
    text = item.get("text_raw") or clean_html(item.get("text", ""))
    created = item.get("created_at", "")
    likes = item.get("like_counts") or item.get("like_count") or 0
    cid = str(item.get("idstr") or item.get("id") or "")
    uid = str(user.get("idstr") or user.get("id") or "")
    root_id = str(item.get("rootidstr") or item.get("rootid") or cid)
    return {
        "comment_id": cid,
        "author": user.get("screen_name", ""),
        "author_uid": uid,
        "content": text,
        "time": created,
        "parsed_time": parse_weibo_time(created),
        "likes": int(likes or 0),
        "topics": extract_topics(item.get("text", "") + text),
        "root_comment_id": root_id,
        "source_api": source,
    }


def legacy_comment_to_normalized(raw: dict[str, Any]) -> dict[str, Any]:
    """兼容旧版 JSON 评论（无 comment_id）。"""
    created = raw.get("time", "")
    text = raw.get("text") or raw.get("content", "")
    return {
        "comment_id": str(raw.get("comment_id") or raw.get("id") or ""),
        "author": raw.get("author") or raw.get("user", ""),
        "author_uid": str(raw.get("author_uid") or ""),
        "content": text,
        "time": created,
        "parsed_time": parse_weibo_time(created),
        "likes": int(raw.get("likes") or 0),
        "topics": extract_topics(text),
        "root_comment_id": str(raw.get("root_comment_id") or raw.get("comment_id") or raw.get("id") or ""),
        "source_api": raw.get("source_api", "legacy"),
    }


def comment_row_from_post(post: dict[str, Any], comment: dict[str, Any]) -> dict[str, Any]:
    topics = post.get("topics") or []
    return {
        "帖子ID": post["mid"],
        "帖子链接": post["url"],
        "帖子作者": post["author"],
        "帖子作者UID": post["author_uid"],
        "来源类型": post["source_type"],
        "帖子发布时间": post["time"],
        "帖子话题标签": " #".join([""] + topics) if topics else "",
        "帖子点赞数": post["likes"],
        "帖子评论数": post["comments_count"],
        "帖子转发数": post["reposts_count"],
        "评论ID": comment.get("comment_id", ""),
        "评论者": comment.get("author", ""),
        "评论者UID": comment.get("author_uid", ""),
        "评论时间": comment.get("time", ""),
        "评论内容": comment.get("content", ""),
        "评论话题标签": " #".join([""] + comment.get("topics", [])) if comment.get("topics") else "",
        "评论点赞数": comment.get("likes", 0),
    }


# ── 爬虫核心 ──────────────────────────────────────────────────────────────────

class WeiboScraper:
    def __init__(self, cookie_str: str):
        self.cookie_str = cookie_str
        self.session = requests.Session()
        self.seen_mids: set[str] = set()
        self.posts: list[dict[str, Any]] = []
        self._warmup_session()

    def _warmup_session(self):
        for part in self.cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                self.session.cookies.set(k.strip(), v.strip())
        try:
            self.session.get("https://weibo.com/", headers=build_headers(self.cookie_str), timeout=15)
        except requests.RequestException:
            pass

    def _get(self, url: str, params: dict | None = None, referer: str = "https://weibo.com/") -> dict | list | None:
        headers = build_headers(self.cookie_str, referer)
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=20)
                if resp.status_code == 432 or resp.status_code == 403:
                    print(f"  [!] 请求被拦截 (HTTP {resp.status_code})，等待 30 秒后重试...")
                    time.sleep(30)
                    continue
                if resp.status_code != 200:
                    print(f"  [!] HTTP {resp.status_code}: {url}")
                    return None
                return resp.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                print(f"  [!] 请求失败 ({attempt + 1}/3): {e}")
                time.sleep(5)
        return None

    def _add_post(self, post: dict[str, Any]) -> bool:
        mid = str(post.get("mid", ""))
        if not mid or mid in self.seen_mids:
            return False
        if not passes_engagement(post["likes"], post["comments_count"]):
            return False
        if not is_event_related(post["content"], post["topics"], post.get("author", "")):
            return False
        if not in_event_range(post.get("parsed_time")):
            return False
        self.seen_mids.add(mid)
        self.posts.append(post)
        return True

    def _normalize_mblog(self, mblog: dict, source: str) -> dict[str, Any] | None:
        if not mblog:
            return None
        mid = str(mblog.get("id") or mblog.get("mid") or "")
        if not mid:
            return None

        text_raw = mblog.get("text_raw") or clean_html(mblog.get("text", ""))
        topics = extract_topics(mblog.get("text", "") + text_raw)
        # 从 topic_struct 补充话题
        for t in mblog.get("topic_struct") or []:
            title = t.get("topic_title") or t.get("topic_name", "")
            if title and title not in topics:
                topics.append(title)

        user = mblog.get("user") or {}
        created = mblog.get("created_at", "")
        dt = parse_weibo_time(created)

        likes = int(mblog.get("attitudes_count") or 0)
        comments_count = int(mblog.get("comments_count") or 0)
        reposts = int(mblog.get("reposts_count") or 0)
        uid = str(user.get("id") or "")
        screen_name = user.get("screen_name", "")

        bid = mblog.get("bid") or mid
        url = f"https://weibo.com/{uid}/{bid}" if uid else f"https://m.weibo.cn/detail/{mid}"

        return {
            "mid": mid,
            "content": text_raw,
            "time": created,
            "parsed_time": dt,
            "likes": likes,
            "comments_count": comments_count,
            "reposts_count": reposts,
            "topics": topics,
            "author": screen_name,
            "author_uid": uid,
            "source_type": source,
            "url": url,
            "comments": [],
        }

    # ── 搜索 ──

    def search_weibo(self, keyword: str, max_pages: int = MAX_SEARCH_PAGES):
        print(f"\n[搜索] {keyword}", flush=True)
        referer = "https://weibo.com/"

        for page in range(1, max_pages + 1):
            data = self._get(
                "https://weibo.com/ajax/statuses/search",
                params={"q": keyword, "page": page},
                referer=referer,
            )
            if not data:
                break

            cards = data.get("statuses") or data.get("data", {}).get("list", [])
            if not cards:
                break

            added = 0
            for card in cards:
                post = self._normalize_mblog(card, f"搜索:{keyword}")
                if post and self._add_post(post):
                    added += 1

            print(f"  第 {page} 页，新增 {added} 条", flush=True)
            if len(cards) < 10:
                break
            sleep()

    # ── 用户时间线 ──

    def fetch_user_posts(self, name: str, uid: str, max_pages: int = MAX_USER_PAGES):
        print(f"\n[用户] {name} (uid={uid})")
        for page in range(1, max_pages + 1):
            data = self._get(
                "https://weibo.com/ajax/statuses/mymblog",
                params={"uid": uid, "page": page, "feature": 0},
                referer=f"https://weibo.com/u/{uid}",
            )
            if not data:
                break
            posts_list = data.get("data", {}).get("list", [])
            if not posts_list:
                break

            added = 0
            stop_early = False
            for card in posts_list:
                dt = parse_weibo_time(card.get("created_at", ""))
                if dt and dt < EVENT_START:
                    stop_early = True
                    break
                post = self._normalize_mblog(card, f"用户:{name}")
                if post and self._add_post(post):
                    added += 1

            print(f"  第 {page} 页，新增 {added} 条")
            if stop_early or not posts_list:
                break
            since_id = data.get("data", {}).get("since_id")
            if since_id == "0" or since_id == 0:
                break
            sleep()

    def fetch_user_timeline_texts(
        self,
        uid: str,
        max_pages: int = 2,
        max_posts: int = 25,
        verbose: bool = False,
    ) -> list[str]:
        """
        拉取用户近期博文正文，仅内存返回，不持久化、不过滤事件/互动门槛。
        供用户画像分类增强使用。
        """
        texts: list[str] = []
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            if len(texts) >= max_posts:
                break
            data = self._get(
                "https://weibo.com/ajax/statuses/mymblog",
                params={"uid": uid, "page": page, "feature": 0},
                referer=f"https://weibo.com/u/{uid}",
            )
            if not data:
                break
            posts_list = data.get("data", {}).get("list", [])
            if not posts_list:
                break

            for card in posts_list:
                if len(texts) >= max_posts:
                    break
                text_raw = card.get("text_raw") or clean_html(card.get("text", ""))
                text_raw = (text_raw or "").strip()
                if len(text_raw) < 2:
                    continue
                rt = card.get("retweeted_status")
                if rt and (text_raw in ("转发微博", "轉發微博") or len(text_raw) <= 6):
                    rt_text = rt.get("text_raw") or clean_html(rt.get("text", ""))
                    if rt_text:
                        text_raw = f"{text_raw} {rt_text}".strip()
                key = text_raw[:80]
                if key in seen:
                    continue
                seen.add(key)
                texts.append(text_raw)

            if verbose:
                print(f"  uid={uid} 第{page}页 +{len(texts)}条")
            since_id = data.get("data", {}).get("since_id")
            if since_id == "0" or since_id == 0:
                break
            sleep()
        return texts

    # ── 超话 ──

    def fetch_super_topic(self, name: str, topic_name: str, max_pages: int = 30):
        print(f"\n[超话] {name}")
        containerid = self.resolve_super_topic_id(topic_name)
        if not containerid:
            print(f"  未找到超话 containerid: {topic_name}")
            return
        print(f"  containerid={containerid}")
        for page in range(1, max_pages + 1):
            data = self._get(
                "https://m.weibo.cn/api/container/getIndex",
                params={"containerid": f"{containerid}_-_feed", "page": page},
                referer=f"https://m.weibo.cn/p/index?containerid={containerid}",
            )
            if not data:
                break
            cards = data.get("data", {}).get("cards", [])
            if not cards:
                break
            added = 0
            for card in cards:
                mblog = card.get("mblog")
                if not mblog and card.get("card_group"):
                    for sub in card["card_group"]:
                        mblog = sub.get("mblog")
                        if mblog:
                            post = self._normalize_mblog(mblog, f"超话:{name}")
                            if post and self._add_post(post):
                                added += 1
                elif mblog:
                    post = self._normalize_mblog(mblog, f"超话:{name}")
                    if post and self._add_post(post):
                        added += 1
            print(f"  第 {page} 页，新增 {added} 条")
            sleep()

    def resolve_super_topic_id(self, topic_name: str) -> str | None:
        """通过搜索接口获取超话 containerid（100808 开头）"""
        url = "https://m.weibo.cn/api/container/getIndex"
        params = {"containerid": f"100103type=1&q={quote(topic_name)}", "page_type": "searchall"}
        headers = build_headers(self.cookie_str, "https://m.weibo.cn/")
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code != 200:
                return None
            matches = re.findall(r"100808[\da-f]{32}", resp.text)
            if matches:
                return matches[0]
            data = resp.json()
            for card in data.get("data", {}).get("cards", []):
                for key in ("scheme", "containerid", "page_url"):
                    m = re.search(r"100808[\da-f]{32}", str(card.get(key, "")))
                    if m:
                        return m.group(0)
        except (requests.RequestException, json.JSONDecodeError):
            return None
        return None

    def resolve_user_uid(self, name: str) -> str | None:
        """通过昵称搜索用户 UID"""
        data = self._get(
            "https://weibo.com/ajax/profile/info",
            params={"screen_name": name},
            referer="https://weibo.com/",
        )
        if data and data.get("data", {}).get("user", {}).get("id"):
            return str(data["data"]["user"]["id"])

        data = self._get(
            "https://m.weibo.cn/api/container/getIndex",
            params={"containerid": f"100103type=3&q={quote(name)}", "page_type": "searchall"},
            referer="https://m.weibo.cn/",
        )
        if not data:
            return None
        for card in data.get("data", {}).get("cards", []):
            for sub in card.get("card_group") or [card]:
                user = sub.get("user") or {}
                if user.get("screen_name") == name or name in str(user.get("screen_name", "")):
                    return str(user.get("id"))
        return None

    # ── 评论 ──

    def _fetch_comments_pc(self, post: dict[str, Any]) -> list[dict[str, Any]]:
        mid = post["mid"]
        all_comments: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        max_id = 0

        for _ in range(MAX_COMMENT_PAGES):
            data = self._get(
                "https://weibo.com/ajax/statuses/buildComments",
                params={
                    "flow": 0,
                    "is_reload": 1,
                    "id": mid,
                    "is_show_bulletin": 2,
                    "is_mix": 0,
                    "count": 20,
                    "uid": post.get("author_uid", ""),
                    "fetch_level": 0,
                    "max_id": max_id,
                },
                referer=post["url"],
            )
            if not data:
                break
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                normalized = normalize_comment_item(item, "pc")
                cid = normalized["comment_id"]
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                all_comments.append(normalized)
                if len(all_comments) >= MAX_COMMENTS_PER_POST:
                    break
            if len(all_comments) >= MAX_COMMENTS_PER_POST:
                break
            next_max = data.get("max_id", 0)
            if not next_max or next_max == max_id:
                break
            max_id = next_max
            sleep()
        return all_comments

    def _fetch_comments_mobile(self, post: dict[str, Any]) -> list[dict[str, Any]]:
        mid = post["mid"]
        all_comments: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        max_id = 0
        referer = f"https://m.weibo.cn/detail/{mid}"
        headers = build_headers(self.cookie_str, referer)
        headers["User-Agent"] = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )

        for _ in range(MAX_COMMENT_PAGES):
            params: dict[str, Any] = {"mid": mid, "max_id_type": 0}
            if max_id:
                params["max_id"] = max_id
            try:
                resp = self.session.get(
                    "https://m.weibo.cn/comments/hotflow",
                    params=params,
                    headers=headers,
                    timeout=20,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
            except (requests.RequestException, json.JSONDecodeError):
                break

            payload = data.get("data") or {}
            items = payload.get("data") or []
            if not items:
                break
            for item in items:
                normalized = normalize_comment_item(item, "mobile")
                cid = normalized["comment_id"]
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                all_comments.append(normalized)
                if len(all_comments) >= MAX_COMMENTS_PER_POST:
                    break
            if len(all_comments) >= MAX_COMMENTS_PER_POST:
                break
            next_max = payload.get("max_id", 0)
            if not next_max or next_max == max_id:
                break
            max_id = next_max
            sleep()
        return all_comments

    def fetch_comments(self, post: dict[str, Any], fallback: list[dict[str, Any]] | None = None):
        comments = self._fetch_comments_pc(post)
        if not comments:
            if fallback:
                comments = [legacy_comment_to_normalized(c) for c in fallback]
            else:
                comments = self._fetch_comments_mobile(post)
        post["comments"] = comments

    def fetch_all_comments(self, fallback_map: dict[str, list[dict[str, Any]]] | None = None):
        fallback_map = fallback_map or {}
        targets = [p for p in self.posts if p["comments_count"] > 0]
        print(f"\n[评论] 开始抓取 {len(targets)} 条帖子的评论...")
        for i, post in enumerate(targets, 1):
            print(
                f"  ({i}/{len(targets)}) mid={post['mid']} "
                f"预计 {post['comments_count']} 条评论"
            )
            self.fetch_comments(post, fallback=fallback_map.get(post["mid"]))
            print(f"    -> 实际获取 {len(post['comments'])} 条")
            sleep()

    # ── 导出 ──

    def export_csv(self, path: str = OUTPUT_CSV):
        out = P.微博数据 / path
        fieldnames = [
            "帖子ID", "作者", "作者UID", "来源类型", "发布时间", "帖子内容",
            "话题标签", "点赞数", "评论数", "转发数", "帖子链接",
            "评论列表(JSON)", "评论文本汇总",
        ]
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for p in sorted(self.posts, key=lambda x: x.get("parsed_time") or datetime.min, reverse=True):
                comments_json = json.dumps(p["comments"], ensure_ascii=False)
                comments_text = " | ".join(
                    f"{c.get('author') or c.get('user', '')}: {c.get('content') or c.get('text', '')}"
                    for c in p["comments"]
                )
                writer.writerow({
                    "帖子ID": p["mid"],
                    "作者": p["author"],
                    "作者UID": p["author_uid"],
                    "来源类型": p["source_type"],
                    "发布时间": p["time"],
                    "帖子内容": p["content"],
                    "话题标签": " #".join([""] + p["topics"]) if p["topics"] else "",
                    "点赞数": p["likes"],
                    "评论数": p["comments_count"],
                    "转发数": p["reposts_count"],
                    "帖子链接": p["url"],
                    "评论列表(JSON)": comments_json,
                    "评论文本汇总": comments_text,
                })
        print(f"\n[OK] 已导出 {len(self.posts)} 条帖子到 {out}")
        return out

    def export_comments_csv(
        self,
        path: str = OUTPUT_COMMENTS_CSV,
        posts: list[dict[str, Any]] | None = None,
    ):
        source_posts = posts if posts is not None else self.posts
        out = P.微博数据 / path
        rows: list[dict[str, Any]] = []
        for post in source_posts:
            for comment in post.get("comments") or []:
                rows.append(comment_row_from_post(post, comment))

        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COMMENT_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[OK] 已导出 {len(rows)} 条评论到 {out}")
        return out


def validate_cookie(cookie_str: str) -> bool:
    headers = build_headers(cookie_str)
    try:
        resp = requests.get(
            "https://weibo.com/ajax/profile/info",
            params={"uid": "1739046981"},
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool(data.get("ok") == 1 or data.get("data", {}).get("user"))
    except (requests.RequestException, json.JSONDecodeError):
        return False


def main():
    print("=" * 60)
    print("微博爬虫：单依纯 × 李荣浩 × 《李白》事件")
    print(f"筛选条件：点赞数 > {MIN_LIKES} 或 评论数 > {MIN_COMMENTS}")
    print(f"时间范围：{EVENT_START.date()} ~ {EVENT_END.date()}")
    print("=" * 60)

    cookie = load_cookie()
    if not validate_cookie(cookie):
        print("\n警告：Cookie 可能无效或已过期，请重新登录 weibo.com 并更新 cookie.txt")
        sys.exit(1)

    scraper = WeiboScraper(cookie)

    # 1. 抓取目标用户帖子
    for name, uid in TARGET_USERS.items():
        scraper.fetch_user_posts(name, uid)

    for name in EXTRA_USER_NAMES:
        uid = scraper.resolve_user_uid(name)
        if uid:
            print(f"\n[解析] {name} -> uid={uid}")
            scraper.fetch_user_posts(name, uid)
        else:
            print(f"\n[跳过] 未找到用户: {name}")

    # 2. 关键词搜索（粉丝帖、媒体帖、讨论帖）
    for kw in SEARCH_KEYWORDS:
        scraper.search_weibo(kw)

    # 3. 超话帖子
    for topic_name in ["单依纯", "李荣浩"]:
        scraper.fetch_super_topic(f"{topic_name}超话", topic_name)

    print(f"\n[汇总] 共收集 {len(scraper.posts)} 条符合条件的帖子（去重后）")

    # 4. 抓取评论
    scraper.fetch_all_comments()

    # 5. 导出 CSV
    scraper.export_csv()
    scraper.export_comments_csv()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从已有微博帖子 CSV 抓取评论，导出独立评论表 weibo_comments.csv。

用法: python scrape_weibo_comments.py
输入: weibo_posts.csv（可选合并 weibo_posts_超话.csv）
输出: weibo_comments.csv
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
import sys
from pathlib import Path
from typing import Any

from 微博帖子爬虫 import (
    BASE_DIR,
    OUTPUT_COMMENTS_CSV,
    OUTPUT_CSV,
    WeiboScraper,
    legacy_comment_to_normalized,
    load_cookie,
    validate_cookie,
)

POST_CSV_FILES = [
    OUTPUT_CSV,
    "weibo_posts_超话.csv",
]


def load_posts_from_csv(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        return []

    posts: list[dict[str, Any]] = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            mid = str(row.get("帖子ID", "")).strip()
            if not mid:
                continue
            topics_raw = row.get("话题标签", "") or ""
            topics = [t.strip() for t in topics_raw.split("#") if t.strip()]
            embedded_raw: list[dict[str, Any]] = []
            raw_json = row.get("评论列表(JSON)", "") or "[]"
            try:
                embedded_raw = json.loads(raw_json) if raw_json else []
            except json.JSONDecodeError:
                embedded_raw = []

            posts.append({
                "mid": mid,
                "content": row.get("帖子内容", ""),
                "time": row.get("发布时间", ""),
                "parsed_time": None,
                "likes": int(str(row.get("点赞数", 0)).replace(",", "") or 0),
                "comments_count": int(str(row.get("评论数", 0)).replace(",", "") or 0),
                "reposts_count": int(str(row.get("转发数", 0)).replace(",", "") or 0),
                "topics": topics,
                "author": row.get("作者", ""),
                "author_uid": str(row.get("作者UID", "")).strip(),
                "source_type": row.get("来源类型", ""),
                "url": row.get("帖子链接", ""),
                "comments": [],
                "_embedded_comments": embedded_raw,
            })
    return posts


def merge_posts(all_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for post in all_posts:
        mid = post["mid"]
        if mid not in merged:
            merged[mid] = post
            continue
        old = merged[mid]
        if not old.get("_embedded_comments") and post.get("_embedded_comments"):
            old["_embedded_comments"] = post["_embedded_comments"]
        if old["comments_count"] < post["comments_count"]:
            old["comments_count"] = post["comments_count"]
    return list(merged.values())


def build_fallback_map(posts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    fallback: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        raw_items = post.pop("_embedded_comments", [])
        if raw_items:
            fallback[post["mid"]] = raw_items
    return fallback


def update_posts_csv(posts: list[dict[str, Any]], csv_path: Path):
    if not csv_path.exists():
        return

    comment_map = {p["mid"]: p.get("comments", []) for p in posts}
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            mid = str(row.get("帖子ID", "")).strip()
            comments = comment_map.get(mid)
            if comments is not None:
                row["评论列表(JSON)"] = json.dumps(comments, ensure_ascii=False)
                row["评论文本汇总"] = " | ".join(
                    f"{c.get('author', '')}: {c.get('content', '')}" for c in comments
                )
            rows.append(row)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    print("=" * 60)
    print("微博评论抓取：从已有帖子 CSV 导出评论层数据")
    print("=" * 60)

    cookie = load_cookie()
    if not validate_cookie(cookie):
        print("\n警告：Cookie 可能无效或已过期，部分帖子评论可能无法通过 API 获取。")
        print("将尝试使用 CSV 中已有的评论 JSON 作为兜底。")

    all_posts: list[dict[str, Any]] = []
    for name in POST_CSV_FILES:
        path = BASE_DIR / name
        loaded = load_posts_from_csv(path)
        if loaded:
            print(f"  读取 {name}: {len(loaded)} 条帖子")
            all_posts.extend(loaded)

    if not all_posts:
        print("错误：未找到帖子 CSV，请先运行 weibo_scraper.py")
        sys.exit(1)

    posts = merge_posts(all_posts)
    fallback_map = build_fallback_map(posts)
    target_count = sum(1 for p in posts if p["comments_count"] > 0)
    print(f"\n待抓取评论的帖子: {target_count} 条（去重后共 {len(posts)} 条帖子）")
    print(f"其中 {len(fallback_map)} 条帖子有历史评论 JSON 可兜底\n")

    scraper = WeiboScraper(cookie)
    scraper.posts = posts
    scraper.fetch_all_comments(fallback_map=fallback_map)

    out_comments = scraper.export_comments_csv()
    update_posts_csv(posts, BASE_DIR / OUTPUT_CSV)

    total_comments = sum(len(p.get("comments") or []) for p in posts)
    with_id = sum(
        1
        for p in posts
        for c in (p.get("comments") or [])
        if c.get("comment_id")
    )
    print(f"\n汇总: 共 {total_comments} 条评论，其中 {with_id} 条含评论ID", flush=True)
    print(f"输出文件: {out_comments}", flush=True)


if __name__ == "__main__":
    main()

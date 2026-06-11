import sys
from pathlib import Path as _Path
_R = _Path(__file__).resolve().parent.parent
if str(_R) not in sys.path:
    sys.path.insert(0, str(_R))
import 项目路径 as P

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补充抓取超话帖子，合并到 weibo_posts_超话.csv。"""

import csv
import json
from pathlib import Path

from 李白事件过滤 import (
    is_libai_copyright_event,
    is_super_topic_post,
    SUPERTOPIC_CSV,
    SOURCE_CSV,
)
from 微博帖子爬虫 import (
    WeiboScraper,
    load_cookie,
    validate_cookie,
    MIN_LIKES,
    MIN_COMMENTS,
    passes_engagement,
    BASE_DIR,
)

SUPERTOPIC_SEARCH = [
    "#单依纯[超话]# 李白",
    "#单依纯[超话]# 李荣浩",
    "#单依纯[超话]# 侵权",
    "#李荣浩[超话]# 单依纯",
    "#李荣浩[超话]# 李白",
    "单依纯超话 李白",
    "单依纯超话 李荣浩 侵权",
    "李荣浩超话 单依纯",
    "单依纯超话 吴向飞",
]


def load_existing_mids(*paths: Path) -> set[str]:
    mids: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig") as f:
            mids.update(row["帖子ID"] for row in csv.DictReader(f))
    return mids


def posts_to_rows(posts: list) -> list[dict]:
    rows = []
    for p in posts:
        rows.append({
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
            "评论列表(JSON)": json.dumps(p["comments"], ensure_ascii=False),
            "评论文本汇总": " | ".join(
                f"{c.get('author') or c.get('user', '')}: {c.get('content') or c.get('text', '')}"
                for c in p["comments"]
            ),
        })
    return rows


def main():
    cookie = load_cookie()
    if not validate_cookie(cookie):
        print("Cookie 无效，请更新 cookie.txt")
        return

    existing_mids = load_existing_mids(SUPERTOPIC_CSV, BASE_DIR / "weibo_posts.csv")
    scraper = WeiboScraper(cookie)
    scraper.seen_mids = set(existing_mids)

    # 1. 搜索超话相关关键词
    for kw in SUPERTOPIC_SEARCH:
        scraper.search_weibo(kw, max_pages=15)

    # 2. 尝试 API 超话 feed
    for name in ["单依纯", "李荣浩"]:
        scraper.fetch_super_topic(f"{name}超话", f"{name}超话", max_pages=20)

    # 只保留：超话帖 + 事件相关 + 互动达标
    new_posts = []
    for p in scraper.posts:
        if not passes_engagement(p["likes"], p["comments_count"]):
            continue
        if not is_libai_copyright_event(p["content"], " ".join(p["topics"]), p["author"]):
            continue
        if not is_super_topic_post(p["content"], " ".join(p["topics"]), p["source_type"]):
            continue
        new_posts.append(p)

    print(f"\n新增超话帖: {len(new_posts)} 条", flush=True)

    if new_posts:
        scraper.posts = new_posts
        scraper.fetch_all_comments()

    # 3. 从全量备份中提取超话帖
    backup_rows = []
    if SOURCE_CSV.exists():
        with open(SOURCE_CSV, encoding="utf-8-sig") as f:
            backup_rows = list(csv.DictReader(f))

    old_st = []
    if SUPERTOPIC_CSV.exists():
        with open(SUPERTOPIC_CSV, encoding="utf-8-sig") as f:
            old_st = list(csv.DictReader(f))

    merged: dict[str, dict] = {}
    for r in old_st + backup_rows + posts_to_rows(new_posts):
        if not row_passes(r):
            continue
        if not is_super_topic_post(r["帖子内容"], r["话题标签"], r["来源类型"]):
            continue
        merged[r["帖子ID"]] = r

    fieldnames = list(next(iter(merged.values())).keys()) if merged else [
        "帖子ID", "作者", "作者UID", "来源类型", "发布时间", "帖子内容",
        "话题标签", "点赞数", "评论数", "转发数", "帖子链接",
        "评论列表(JSON)", "评论文本汇总",
    ]
    rows = list(merged.values())
    with open(SUPERTOPIC_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"超话 CSV 共 {len(rows)} 条 -> {SUPERTOPIC_CSV}", flush=True)


def row_passes(row: dict) -> bool:
    return is_libai_copyright_event(row["帖子内容"], row["话题标签"], row["作者"])


if __name__ == "__main__":
    main()

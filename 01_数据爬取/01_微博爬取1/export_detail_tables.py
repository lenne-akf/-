# -*- coding: utf-8 -*-
"""
将 MediaCrawler 原始 detail CSV 整理到 output/（与 search 分开）。

输出：
  output/detail_posts.csv      — detail 模式抓到的帖元数据
  output/detail_comments.csv   — detail 模式抓到的一级评论（含二级若开启）

用法（detail 爬取完成后）：
  python export_detail_tables.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PLATFORM = "weibo"
EVENT = "李白侵权舆情"


def _load(pattern: str, raw_dir: Path) -> pd.DataFrame:
    files = sorted(raw_dir.glob(pattern))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files], ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-dir",
        default=str(PROJECT_ROOT / "MediaCrawler" / "data" / "weibo" / "csv"),
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent / "output"),
    )
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    posts = _load("detail_contents_*.csv", raw_dir)
    comments = _load("detail_comments_*.csv", raw_dir)

    if posts.empty and comments.empty:
        print(f"未找到 detail_*.csv，请先运行 run_uv.bat detail：{raw_dir}")
        return

    if not posts.empty:
        posts["note_id"] = posts["note_id"].astype(str)
        posts = posts.sort_values("last_modify_ts", ascending=False, na_position="last")
        posts = posts.drop_duplicates(subset=["note_id"], keep="first")
        posts["platform"] = PLATFORM
        posts["event"] = EVENT
        posts["crawl_source"] = "detail"

    if not comments.empty:
        comments["comment_id"] = comments["comment_id"].astype(str)
        comments = comments.sort_values("last_modify_ts", ascending=False, na_position="last")
        comments = comments.drop_duplicates(subset=["comment_id"], keep="first")
        comments["platform"] = PLATFORM
        comments["event"] = EVENT
        comments["crawl_source"] = "detail"

    posts_path = out_dir / "detail_posts.csv"
    comments_path = out_dir / "detail_comments.csv"
    if not posts.empty:
        posts.to_csv(posts_path, index=False, encoding="utf-8-sig")
    if not comments.empty:
        comments.to_csv(comments_path, index=False, encoding="utf-8-sig")

    print(f"detail 帖: {posts_path} ({len(posts)} 行)" if not posts.empty else "detail 帖: 无")
    print(
        f"detail 评: {comments_path} ({len(comments)} 行)"
        if not comments.empty
        else "detail 评: 无"
    )


if __name__ == "__main__":
    main()

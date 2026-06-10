# -*- coding: utf-8 -*-
"""
轻量微博评论爬取：Playwright 发 hotflow 请求，输出格式与 MediaCrawler CSV 一致。

用法（在 weibo_crawl 目录，使用 .venv_new）：
  python fetch_comments_fast.py
  python fetch_comments_fast.py --ids output/detail_note_ids.txt --max-comments 200
  python fetch_comments_fast.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import APIRequestContext, sync_playwright

CODE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Cookie 文件路径（相对 代码/ 目录）；真实内容写在 cookies.txt，勿上传
COOKIES = "cookies.txt"

CSV_COLUMNS = [
    "comment_id",
    "create_time",
    "create_date_time",
    "note_id",
    "content",
    "sub_comment_count",
    "comment_like_count",
    "last_modify_ts",
    "ip_location",
    "parent_comment_id",
    "user_id",
    "nickname",
    "gender",
    "profile_url",
    "avatar",
]

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
)
HOTFLOW_URL = "https://m.weibo.cn/comments/hotflow"
MOBILE_HOME = "https://m.weibo.cn"


def _setup_playwright_env() -> None:
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        default = Path("D:/playwright-browsers")
        if default.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(default)


def _read_cookies(override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    path = CODE_DIR / COOKIES
    if not path.is_file():
        raise RuntimeError(f"未找到 {path}，请创建 cookies.txt 并粘贴微博 Cookie")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    raise RuntimeError(f"{path} 为空，请粘贴微博 Cookie")


def _cookie_to_dict(cookie: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _inject_cookies(context, cookie: str) -> None:
    for key, value in _cookie_to_dict(cookie).items():
        context.add_cookies(
            [{"name": key, "value": value, "domain": ".weibo.cn", "path": "/"}]
        )


def _rfc2822_to_china_datetime(rfc2822_time: str) -> datetime:
    dt = datetime.strptime(rfc2822_time, "%a %b %d %H:%M:%S %z %Y")
    return dt.astimezone(timezone(timedelta(hours=8)))


def _rfc2822_to_timestamp(rfc2822_time: str) -> int:
    dt = datetime.strptime(rfc2822_time, "%a %b %d %H:%M:%S %z %Y")
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def _parse_comment(note_id: str, item: dict) -> dict:
    user = item.get("user") or {}
    raw_text = item.get("text") or ""
    content = re.sub(r"<.*?>", "", raw_text)
    created_at = item.get("created_at") or ""
    return {
        "comment_id": str(item.get("id", "")),
        "create_time": _rfc2822_to_timestamp(created_at) if created_at else 0,
        "create_date_time": str(_rfc2822_to_china_datetime(created_at)) if created_at else "",
        "note_id": note_id,
        "content": content,
        "sub_comment_count": str(item.get("total_number", 0)),
        "comment_like_count": str(item.get("like_count", 0)),
        "last_modify_ts": int(time.time() * 1000),
        "ip_location": (item.get("source") or "").replace("来自", ""),
        "parent_comment_id": str(item.get("rootid") or item.get("id") or ""),
        "user_id": str(user.get("id", "")),
        "nickname": user.get("screen_name", ""),
        "gender": user.get("gender", ""),
        "profile_url": user.get("profile_url", ""),
        "avatar": user.get("profile_image_url", ""),
    }


def _load_existing(csv_path: Path) -> tuple[set[str], Counter[str]]:
    seen_ids: set[str] = set()
    per_note: Counter[str] = Counter()
    if not csv_path.exists():
        return seen_ids, per_note
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = str(row.get("comment_id", "")).strip()
            nid = str(row.get("note_id", "")).strip()
            if cid:
                seen_ids.add(cid)
            if nid:
                per_note[nid] += 1
    return seen_ids, per_note


def _fetch_page(
    request: APIRequestContext,
    cookie: str,
    note_id: str,
    max_id: int,
    max_id_type: int,
) -> dict[str, Any]:
    params = {"id": note_id, "mid": note_id, "max_id_type": str(max_id_type)}
    if max_id > 0:
        params["max_id"] = str(max_id)
    cookie_dict = _cookie_to_dict(cookie)
    headers = {
        "Referer": f"https://m.weibo.cn/detail/{note_id}",
        "Origin": "https://m.weibo.cn",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
    }
    xsrf = cookie_dict.get("XSRF-TOKEN")
    if xsrf:
        headers["X-XSRF-TOKEN"] = xsrf

    resp = request.get(HOTFLOW_URL, params=params, headers=headers, timeout=30000)
    final_url = resp.url
    if "login.sina.com.cn" in final_url or "passport" in final_url:
        raise RuntimeError("Cookie 已失效（跳转登录页），请更新 代码/cookies.txt")

    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status} note={note_id}")

    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"非 JSON 响应 note={note_id}: {resp.text()[:200]}") from exc

    if data.get("ok") == -100 or str(data.get("errno")) == "-100":
        raise RuntimeError("CAPTCHA_-100")
    if data.get("ok") == 0:
        msg = data.get("msg") or data
        inner = data.get("data") if isinstance(data.get("data"), dict) else {}
        if not (inner.get("data") if isinstance(inner, dict) else None):
            print(f"  警告: API ok=0，跳过该帖（可能已删/无评论）: {msg}")
            return {"data": [], "max_id": 0, "max_id_type": 0}
        raise RuntimeError(f"API 错误 note={note_id}: {msg}")
    return data.get("data") or {}


def fetch_note_comments(
    request: APIRequestContext,
    cookie: str,
    note_id: str,
    max_comments: int,
    page_sleep: tuple[float, float],
    captcha_retries: int,
    captcha_wait: int,
    page,
) -> list[dict]:
    rows: list[dict] = []
    max_id = -1
    max_id_type = 0
    while len(rows) < max_comments:
        for attempt in range(captcha_retries + 1):
            try:
                payload = _fetch_page(request, cookie, note_id, max_id, max_id_type)
                break
            except RuntimeError as exc:
                if str(exc) != "CAPTCHA_-100" or attempt >= captcha_retries:
                    raise
                print(
                    f"  触发验证码，请在浏览器窗口打开 m.weibo.cn 完成验证，"
                    f"{captcha_wait}s 后重试 ({attempt + 1}/{captcha_retries})..."
                )
                page.goto(MOBILE_HOME, wait_until="domcontentloaded", timeout=120000)
                time.sleep(captcha_wait)

        comment_list = payload.get("data") or []
        max_id = int(payload.get("max_id") or 0)
        max_id_type = int(payload.get("max_id_type") or 0)
        if not comment_list:
            break
        remaining = max_comments - len(rows)
        if len(comment_list) > remaining:
            comment_list = comment_list[:remaining]
        rows.extend(_parse_comment(note_id, c) for c in comment_list)
        if max_id == 0:
            break
        lo, hi = page_sleep
        time.sleep(random.uniform(lo, hi))
    return rows


def main() -> None:
    _setup_playwright_env()
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="轻量抓取微博帖评论（hotflow + Playwright）")
    parser.add_argument(
        "--ids",
        default=str(base / "output" / "detail_note_ids.txt"),
        help="note_id 列表，一行一个",
    )
    parser.add_argument(
        "--out",
        default=str(
            PROJECT_ROOT / "MediaCrawler" / "data" / "weibo" / "csv" / "detail_comments_2026-06-04.csv"
        ),
        help="输出 CSV（追加写入，与 MediaCrawler 同格式）",
    )
    parser.add_argument("--max-comments", type=int, default=200, help="每帖最多抓取条数")
    parser.add_argument("--page-sleep-min", type=float, default=3.0, help="翻页最小间隔秒")
    parser.add_argument("--page-sleep-max", type=float, default=5.0, help="翻页最大间隔秒")
    parser.add_argument("--note-sleep-min", type=float, default=5.0, help="帖间最小间隔秒")
    parser.add_argument("--note-sleep-max", type=float, default=8.0, help="帖间最大间隔秒")
    parser.add_argument("--captcha-wait", type=int, default=120, help="遇验证码等待秒数")
    parser.add_argument("--captcha-retries", type=int, default=2, help="验证码重试次数")
    parser.add_argument("--headless", action="store_true", help="无头模式（遇验证码时建议关闭）")
    parser.add_argument("--dry-run", action="store_true", help="只统计待爬 id，不请求")
    parser.add_argument("--cookie", default="", help="临时覆盖 cookies.txt 中的 Cookie")
    args = parser.parse_args()

    ids_path = Path(args.ids)
    out_path = Path(args.out)
    note_ids = [ln.strip() for ln in ids_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    seen_comment_ids, per_note_counts = _load_existing(out_path)

    pending: list[str] = []
    for nid in note_ids:
        have = per_note_counts.get(nid, 0)
        if have >= args.max_comments:
            continue
        pending.append(nid)

    print(f"总帖数: {len(note_ids)} | 已有足够评论: {len(note_ids) - len(pending)} | 待爬: {len(pending)}")
    print(f"已有评论行: {sum(per_note_counts.values())} | 输出: {out_path}")
    if args.dry_run:
        if pending:
            print(f"下一批待爬: {pending[0]}（已有 {per_note_counts.get(pending[0], 0)} 条）")
        return

    if not pending:
        print("全部已完成，无需爬取。")
        return

    cookie = _read_cookies(args.cookie or None)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_path.exists() or out_path.stat().st_size == 0

    done_notes = 0
    new_rows = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(user_agent=USER_AGENT, locale="zh-CN")
        _inject_cookies(context, cookie)
        page = context.new_page()
        page.goto(MOBILE_HOME, wait_until="domcontentloaded", timeout=120000)
        time.sleep(2)
        request = context.request

        with out_path.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            if write_header:
                writer.writeheader()

            for idx, note_id in enumerate(pending, start=1):
                already = per_note_counts.get(note_id, 0)
                need = args.max_comments - already
                print(f"[{idx}/{len(pending)}] note={note_id} 已有={already} 目标再抓={need}")

                try:
                    batch = fetch_note_comments(
                        request,
                        cookie,
                        note_id,
                        need,
                        (args.page_sleep_min, args.page_sleep_max),
                        args.captcha_retries,
                        args.captcha_wait,
                        page,
                    )
                except RuntimeError as exc:
                    print(f"停止: {exc}")
                    browser.close()
                    sys.exit(2)

                written = 0
                for row in batch:
                    cid = row["comment_id"]
                    if cid in seen_comment_ids:
                        continue
                    writer.writerow(row)
                    seen_comment_ids.add(cid)
                    per_note_counts[note_id] += 1
                    written += 1
                f.flush()
                new_rows += written
                done_notes += 1
                total = per_note_counts[note_id]
                print(f"  -> 新写入 {written} 条，该帖合计 {total} 条")

                if idx < len(pending):
                    time.sleep(random.uniform(args.note_sleep_min, args.note_sleep_max))

        browser.close()

    print(f"完成: 处理 {done_notes} 帖，新写入 {new_rows} 条评论")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
小红书评论爬虫（Playwright + Cookie）

产出（默认 ../data/）：
  notes_{ts}.csv
  comments_{ts}.csv
  original_data_{ts}.csv   ← preprocess 会读取 original_data_*.csv

用法：
  python crawl_xhs.py                  # 搜笔记 + 抓评论
  python crawl_xhs.py --test           # 1 关键词 · 5 笔记 · 5 评论/条
  python crawl_xhs.py --headless       # 无界面（Cookie 失效时会报错）
  python crawl_xhs.py --notes-only     # 只搜笔记
  python crawl_xhs.py --comments-only ../data/notes_xiaohongshu.csv
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
from playwright.async_api import Page, Response, async_playwright

import config


def safe_print(msg: str, **kwargs: Any) -> None:
    try:
        print(msg, **kwargs)
    except UnicodeEncodeError:
        text = msg.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        )
        print(text, **kwargs)


def parse_cookies(raw: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for part in raw.replace("Cookie:", "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        for domain in (".xiaohongshu.com", "www.xiaohongshu.com"):
            items.append(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": domain,
                    "path": "/",
                }
            )
    return items


def parse_count(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        pass
    mult = 1
    if "万" in s or re.search(r"[wW]$", s):
        mult = 10000
        s = re.sub(r"[万wW]", "", s)
    elif "千" in s or re.search(r"[kK]$", s):
        mult = 1000
        s = re.sub(r"[千kK]", "", s)
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


def ts_to_str(ts: Any) -> str:
    if ts is None or ts == "":
        return ""
    if isinstance(ts, str):
        s = ts.strip()
        if re.match(r"\d{4}[-/]\d{1,2}", s):
            return s.replace("/", "-")
        return s
    try:
        n = int(ts)
        if n > 1_000_000_000_000:
            n //= 1000
        return datetime.fromtimestamp(n).strftime("%Y/%m/%d %H:%M")
    except (TypeError, ValueError, OSError):
        return str(ts)


def build_note_url(note_id: str, xsec_token: str = "") -> str:
    base = f"https://www.xiaohongshu.com/explore/{note_id}"
    if xsec_token:
        return f"{base}?xsec_token={quote(xsec_token)}&xsec_source=pc_search"
    return base


class XHSCrawler:
    def __init__(self) -> None:
        self.notes: dict[str, dict[str, Any]] = {}
        self.comments: list[dict[str, Any]] = []
        self._current_keyword = ""

    def _note_key(self, note_id: str) -> str:
        return note_id

    def _add_note(self, item: dict[str, Any], keyword: str) -> None:
        note_id = str(item.get("id") or item.get("note_id") or "").strip()
        if not note_id:
            return
        if len([n for n in self.notes.values() if n.get("keyword") == keyword]) >= config.MAX_NOTES_PER_KEYWORD:
            return
        user = item.get("user") or {}
        interact = item.get("interact_info") or item.get("interactInfo") or {}
        xsec = item.get("xsec_token") or item.get("xsecToken") or ""
        title = item.get("title") or item.get("display_title") or item.get("displayTitle") or ""
        desc = item.get("desc") or item.get("description") or ""
        self.notes[self._note_key(note_id)] = {
            "note_id": note_id,
            "title": title,
            "desc": desc,
            "type": item.get("type") or item.get("note_type") or "",
            "user_id": str(user.get("user_id") or user.get("userId") or user.get("id") or ""),
            "user_name": user.get("nickname") or user.get("nick_name") or user.get("name") or "",
            "liked_count": parse_count(interact.get("liked_count") or interact.get("likedCount")),
            "collected_count": parse_count(
                interact.get("collected_count") or interact.get("collectedCount")
            ),
            "comment_count": parse_count(
                interact.get("comment_count") or interact.get("commentCount")
            ),
            "share_count": parse_count(interact.get("share_count") or interact.get("shareCount")),
            "publish_time": ts_to_str(item.get("time") or item.get("publish_time") or ""),
            "tags": ",".join(
                t.get("name", "") if isinstance(t, dict) else str(t)
                for t in (item.get("tag_list") or item.get("tagList") or [])
            ),
            "xsec_token": xsec,
            "note_url": build_note_url(note_id, xsec),
            "keyword": keyword,
        }

    def _add_comment(self, note: dict[str, Any], c: dict[str, Any]) -> None:
        cid = str(c.get("id") or c.get("comment_id") or "").strip()
        if not cid:
            return
        note_id = note["note_id"]
        if sum(1 for x in self.comments if x.get("post_id") == note_id) >= config.MAX_COMMENTS_PER_NOTE:
            return
        user = c.get("user_info") or c.get("user") or {}
        self.comments.append(
            {
                "keyword": note.get("keyword") or self._current_keyword,
                "post_id": note_id,
                "post_title": note.get("title") or "",
                "comment_id": cid,
                "content": str(c.get("content") or c.get("text") or "").strip(),
                "comment_time": ts_to_str(c.get("create_time") or c.get("time") or c.get("timestamp")),
                "like_count": parse_count(c.get("like_count") or c.get("liked_count") or 0),
                "user_id": str(user.get("user_id") or user.get("userId") or user.get("id") or ""),
                "user_name": user.get("nickname") or user.get("nick_name") or user.get("name") or "",
                "ip_location": c.get("ip_location") or c.get("ipLocation") or "",
                "parent_comment_id": str(c.get("target_comment", {}).get("id") or "0"),
                "platform": config.PLATFORM,
                "event": config.EVENT_NAME,
            }
        )

    async def _on_response(self, response: Response) -> None:
        url = response.url
        if response.status != 200:
            return
        if "search/notes" not in url and "comment/page" not in url and "comment/sub/page" not in url:
            return
        try:
            data = await response.json()
        except Exception:
            return
        if "search/notes" in url:
            items = (
                data.get("data", {}).get("items")
                or data.get("data", {}).get("notes")
                or []
            )
            for raw in items:
                item = raw.get("note_card") or raw.get("note") or raw
                if isinstance(item, dict):
                    self._add_note(item, self._current_keyword)
            return
        note_id = ""
        m = re.search(r"note_id=([a-f0-9]+)", url)
        if m:
            note_id = m.group(1)
        note = self.notes.get(note_id) or {}
        comments = data.get("data", {}).get("comments") or []
        for c in comments:
            if note:
                self._add_comment(note, c)
            sub = c.get("sub_comments") or c.get("subComments") or []
            for sc in sub:
                if note:
                    self._add_comment(note, sc)

    async def search_keyword(self, page: Page, keyword: str) -> None:
        self._current_keyword = keyword
        safe_print(f"\n[搜索] {keyword}")
        url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes"
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)
        before_kw = len([n for n in self.notes.values() if n.get("keyword") == keyword])
        now_kw = before_kw
        for _ in range(config.MAX_SCROLL_ROUNDS):
            await page.mouse.wheel(0, 2800)
            await asyncio.sleep(config.SLEEP_AFTER_SCROLL)
            now_kw = len([n for n in self.notes.values() if n.get("keyword") == keyword])
            if now_kw - before_kw >= config.MAX_NOTES_PER_KEYWORD:
                break
        safe_print(f"  → 本关键词笔记 {now_kw} 条")

    async def fetch_comments_for_note(self, page: Page, note: dict[str, Any]) -> None:
        title = (note.get("title") or note.get("note_id") or "")[:28]
        safe_print(f"评论 · {title}")
        url = note.get("note_url") or build_note_url(note["note_id"], note.get("xsec_token") or "")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(1.5)
        before = sum(1 for c in self.comments if c.get("post_id") == note["note_id"])
        for _ in range(8):
            await page.mouse.wheel(0, 1200)
            await asyncio.sleep(0.8)
        after = sum(1 for c in self.comments if c.get("post_id") == note["note_id"])
        safe_print(f"  +{after - before} 条")

    async def _run_browser(self, fetch_search: bool, fetch_comments: bool) -> None:
        if not config.COOKIE_FILE.exists():
            raise FileNotFoundError(
                f"未找到 Cookie 文件: {config.COOKIE_FILE}\n"
                "请在浏览器登录小红书后，将 Cookie 粘贴到该文件（勿提交 Git）。"
            )
        raw = config.COOKIE_FILE.read_text(encoding="utf-8").strip()
        cookies = parse_cookies(raw)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=config.HEADLESS)
            context = await browser.new_context(user_agent=config.USER_AGENT, locale="zh-CN")
            await context.add_cookies(cookies)
            page = await context.new_page()
            page.on("response", lambda resp: asyncio.create_task(self._on_response(resp)))

            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            if "login" in page.url.lower():
                if config.HEADLESS:
                    raise RuntimeError(
                        "Cookie 可能已过期（headless 无法手动登录）。"
                        "请更新 概览分析/小红书数据爬取/Cookie 后重试。"
                    )
                safe_print("Cookie 可能已过期，请在浏览器中登录后按回车继续…")
                input()
                await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")

            if fetch_search:
                for idx, keyword in enumerate(config.KEYWORDS):
                    await self.search_keyword(page, keyword)
                    if idx < len(config.KEYWORDS) - 1:
                        await asyncio.sleep(config.SLEEP_BETWEEN_KEYWORDS)

            notes_list = list(self.notes.values())
            if fetch_comments and notes_list:
                safe_print(f"\n共 {len(notes_list)} 条笔记，开始抓取评论…")
                for i, note in enumerate(notes_list, 1):
                    safe_print(f"[{i}/{len(notes_list)}]", end=" ")
                    await self.fetch_comments_for_note(page, note)
                    if i % 25 == 0:
                        self.save(prefix="checkpoint")
                    if i < len(notes_list):
                        await asyncio.sleep(config.SLEEP_BETWEEN_NOTES)
            elif not fetch_comments:
                safe_print(f"\n共收集 {len(notes_list)} 条笔记（--notes-only，跳过评论）")

            await browser.close()

        self.save()

    def _notes_csv_from_argv(self) -> Path | None:
        for i, arg in enumerate(sys.argv):
            if arg == "--comments-only" and i + 1 < len(sys.argv):
                path = Path(sys.argv[i + 1])
                if not path.is_absolute():
                    path = config.PROJECT_DIR / path
                if not path.exists():
                    raise FileNotFoundError(f"未找到笔记文件: {path}")
                return path
        return None

    def load_notes_from_csv(self, path: Path) -> None:
        def cell(value: Any) -> str:
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return ""
            text = str(value).strip()
            return "" if text.lower() == "nan" else text

        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        for _, row in df.iterrows():
            note_id = cell(row.get("note_id"))
            if not note_id:
                continue
            xsec_token = cell(row.get("xsec_token"))
            self.notes[note_id] = {
                "note_id": note_id,
                "title": cell(row.get("title")),
                "desc": cell(row.get("desc")),
                "keyword": cell(row.get("keyword")),
                "xsec_token": xsec_token,
                "note_url": cell(row.get("note_url")) or build_note_url(note_id, xsec_token),
            }
        safe_print(f"从 {path.name} 加载 {len(self.notes)} 条笔记，仅补抓评论")

    async def run(self) -> None:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        notes_csv = self._notes_csv_from_argv()
        if notes_csv:
            self.load_notes_from_csv(notes_csv)
            if "--test" in sys.argv:
                keep = list(self.notes.keys())[:5]
                self.notes = {k: self.notes[k] for k in keep}
                safe_print(f"[测试模式] 仅补抓 {len(self.notes)} 条笔记的评论")
            await self._run_browser(fetch_search=False, fetch_comments=True)
            return

        await self._run_browser(
            fetch_search=True,
            fetch_comments="--notes-only" not in sys.argv,
        )

    def save(self, prefix: str = "") -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = f"{prefix}_{ts}" if prefix else ts
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        notes_path = config.OUTPUT_DIR / f"notes_{label}.csv"
        comments_path = config.OUTPUT_DIR / f"comments_{label}.csv"
        merged_path = config.OUTPUT_DIR / f"original_data_{label}.csv"

        notes_df = pd.DataFrame(list(self.notes.values()))
        comments_df = pd.DataFrame(self.comments)
        if not notes_df.empty:
            notes_df.to_csv(notes_path, index=False, encoding="utf-8-sig")
        if not comments_df.empty:
            comments_df.to_csv(comments_path, index=False, encoding="utf-8-sig")
            comments_df.to_csv(merged_path, index=False, encoding="utf-8-sig")

        safe_print(f"\n[保存] 笔记 {len(notes_df)} → {notes_path.name}")
        safe_print(f"[保存] 评论 {len(comments_df)} → {comments_path.name}")
        if not comments_df.empty:
            safe_print(f"[保存] 合并 {merged_path.name}")


async def main() -> None:
    if "--headless" in sys.argv:
        config.HEADLESS = True

    if "--test" in sys.argv:
        config.MAX_NOTES_PER_KEYWORD = 5
        config.MAX_COMMENTS_PER_NOTE = 5
        config.MAX_SCROLL_ROUNDS = 2
        config.KEYWORDS = config.KEYWORDS[:1]
        safe_print("[测试模式] 仅爬 1 个关键词、5 条笔记")

    crawler = XHSCrawler()
    await crawler.run()


if __name__ == "__main__":
    asyncio.run(main())

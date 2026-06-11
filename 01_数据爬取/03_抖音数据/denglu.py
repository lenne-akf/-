import asyncio
import csv
import json
import re
import os
from datetime import datetime
from urllib.parse import quote, parse_qs, urlparse
from playwright.async_api import async_playwright

# ==================== 配置区 ====================
KEYWORDS = [
    "李荣浩单依纯",
    "单依纯侵权",
    "李荣浩李白侵权",
    "单依纯李白",
    "单依纯歌手",
]
START_DATE = "2025-06-07"
END_DATE = "2026-05-30"
MAX_VIDEOS = 60
MAX_COMMENTS_PER_VIDEO = 1000
OUTPUT_FILE = "douyin_comments.csv"
STATE_FILE = "douyin_state.json"
MIN_LIKE_COUNT = 10000
MIN_COMMENT_COUNT = 2000
COLLECT_IF_STATS_UNAVAILABLE = True
# ================================================

VIDEO_ID_RE = re.compile(r"/video/(\d+)")


def parse_count(text) -> int:
    if text is None:
        return 0
    if isinstance(text, (int, float)):
        return int(text)
    text = str(text).strip().lower().replace(",", "").replace("万", "w")
    if "w" in text:
        try:
            return int(float(text.replace("w", "")) * 10000)
        except Exception:
            return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def parse_time(time_str: str):
    if not time_str:
        return None
    if isinstance(time_str, (int, float)):
        try:
            return datetime.fromtimestamp(time_str)
        except Exception:
            return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(time_str).strip(), fmt)
        except Exception:
            continue
    return None


def within_date_range(ts, start, end):
    t = parse_time(ts)
    if not t:
        return True
    return start <= t <= end


def aweme_id_from_url(url: str) -> str:
    m = VIDEO_ID_RE.search(url)
    return m.group(1) if m else ""


class DouyinApiSniffer:
    """监听抖音 Web 端 XHR，从 JSON 取点赞/评论"""

    DETAIL_KEYS = ("aweme/detail", "aweme/v1/web/aweme/detail")
    COMMENT_KEYS = ("comment/list", "comment/list/")

    def __init__(self):
        self.video_detail = {}
        self.comments = {}

    def attach(self, page):
        page.on("response", self._on_response)

    def reset_video(self, aweme_id: str):
        self.comments[aweme_id] = []

    async def _on_response(self, response):
        if response.status != 200:
            return
        url = response.url
        ctype = (response.headers.get("content-type") or "").lower()
        if "json" not in ctype and "javascript" not in ctype:
            return
        try:
            body = await response.json()
        except Exception:
            return

        if any(k in url for k in self.DETAIL_KEYS):
            detail = body.get("aweme_detail") or body.get("aweme_info") or {}
            aid = str(detail.get("aweme_id") or "")
            if aid:
                self.video_detail[aid] = detail
            return

        if any(k in url for k in self.COMMENT_KEYS):
            qs = parse_qs(urlparse(url).query)
            aid = str((qs.get("aweme_id") or qs.get("item_id") or [""])[0])
            if not aid:
                return
            items = body.get("comments") or []
            if not items:
                return
            bucket = self.comments.setdefault(aid, [])
            seen = {c.get("cid") for c in bucket}
            for c in items:
                cid = c.get("cid")
                if cid and cid not in seen:
                    bucket.append(c)
                    seen.add(cid)

    async def wait_detail(self, aweme_id: str, timeout=25):
        for _ in range(timeout * 2):
            if aweme_id in self.video_detail:
                return self.video_detail[aweme_id]
            await asyncio.sleep(0.5)
        return None

    def get_comments(self, aweme_id: str):
        return self.comments.get(aweme_id, [])


async def extract_render_data(page, aweme_id: str):
    try:
        raw = await page.evaluate(
            """() => {
                const el = document.querySelector('#RENDER_DATA');
                if (el && el.textContent) return el.textContent;
                for (const s of document.querySelectorAll('script')) {
                    const t = s.textContent || '';
                    if (t.includes('aweme_detail') || t.includes('awemeId')) return t;
                }
                return '';
            }"""
        )
        if not raw:
            return None
        text = raw.strip()
        if text.startswith("%"):
            from urllib.parse import unquote
            text = unquote(text)
        data = json.loads(text)

        def find_detail(obj):
            if isinstance(obj, dict):
                if obj.get("aweme_id") and str(obj.get("aweme_id")) == aweme_id:
                    if "statistics" in obj or "author" in obj:
                        return obj
                for v in obj.values():
                    r = find_detail(v)
                    if r:
                        return r
            elif isinstance(obj, list):
                for i in obj:
                    r = find_detail(i)
                    if r:
                        return r
            return None

        return find_detail(data)
    except Exception:
        return None


async def scroll_to_bottom(page, selector, max_scrolls=12, wait_ms=1200):
    prev = 0
    for _ in range(max_scrolls):
        items = await page.query_selector_all(selector)
        if len(items) == prev:
            break
        prev = len(items)
        if items:
            await items[-1].scroll_into_view_if_needed()
        await page.wait_for_timeout(wait_ms)


async def collect_video_urls(page, max_count):
    urls, seen = [], set()
    for a in await page.query_selector_all("a[href*='/video/']"):
        href = await a.get_attribute("href") or ""
        m = VIDEO_ID_RE.search(href)
        if not m:
            continue
        vid = m.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        urls.append(f"https://www.douyin.com/video/{vid}")
        if len(urls) >= max_count:
            break
    return urls


async def trigger_comment_load(page):
    for sel in (
        "[data-e2e='comment-icon']",
        "[data-e2e='feed-comment-icon']",
        "div[class*='comment']",
    ):
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                await loc.click(timeout=2000)
                await page.wait_for_timeout(800)
                break
        except Exception:
            pass
    for _ in range(20):
        await page.mouse.wheel(0, 900)
        await page.wait_for_timeout(800)


def rows_from_api(detail, comments, video_url, source_keyword: str):
    author = detail.get("author") or {}
    stats = detail.get("statistics") or {}
    create_time = detail.get("create_time", 0)
    pub = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M") if create_time else ""

    tags = []
    for t in detail.get("text_extra") or []:
        name = t.get("hashtag_name") or t.get("cha_name")
        if name:
            tags.append(f"#{name}" if not name.startswith("#") else name)
    for t in detail.get("cha_list") or []:
        name = t.get("cha_name")
        if name:
            tags.append(f"#{name}" if not name.startswith("#") else name)

    rows = []
    for c in comments:
        text = (c.get("text") or "").strip()
        if not text:
            continue
        cid = c.get("cid", "")
        user = c.get("user") or {}
        user_name = user.get("nickname") or user.get("unique_id") or ""
        rows.append({
            "来源类型": source_keyword,
            "视频链接": video_url,
            "作者ID": author.get("sec_uid") or author.get("uid") or "",
            "作者名字": author.get("nickname", ""),
            "视频发布时间": pub,
            "评论ID": f"\t{cid}" if cid else "",
            "评论者名字": user_name,
            "评论内容": text.replace("\n", " "),
            "话题标签": ",".join(tags),
            "点赞数": stats.get("digg_count", 0),
            "评论数": stats.get("comment_count", 0),
        })
    return rows


async def process_one_video(page, sniffer, video_url, start_dt, end_dt, source_keyword: str):
    aweme_id = aweme_id_from_url(video_url)
    if not aweme_id:
        return []

    sniffer.reset_video(aweme_id)
    print(f"  ▶ 进入视频: {video_url}")

    try:
        await page.goto(video_url, wait_until="commit", timeout=60000)
    except Exception as e:
        print(f"     ⚠️ 页面加载: {e}")
    await page.wait_for_timeout(3000)

    detail = await sniffer.wait_detail(aweme_id, timeout=20)
    if not detail:
        detail = await extract_render_data(page, aweme_id)
    if detail:
        sniffer.video_detail[aweme_id] = detail

    stats = (detail or {}).get("statistics") or {}
    like_count = parse_count(stats.get("digg_count", 0))
    comment_count = parse_count(stats.get("comment_count", 0))
    source = "接口" if stats else "未获取"
    print(f"     点赞: {like_count}  评论: {comment_count}  ({source})")

    stats_ok = bool(stats)
    if stats_ok and like_count < MIN_LIKE_COUNT:
        print("     ⏭️ 点赞未达门槛")
        return []
    if stats_ok and MIN_COMMENT_COUNT > 0 and comment_count < MIN_COMMENT_COUNT:
        print("     ⏭️ 评论未达门槛")
        return []
    if not stats_ok and not COLLECT_IF_STATS_UNAVAILABLE:
        print("     ⏭️ 未读到统计，跳过")
        return []

    create_time = (detail or {}).get("create_time")
    if create_time and not within_date_range(create_time, start_dt, end_dt):
        print("     ⏭️ 发布时间不在范围内")
        return []

    await trigger_comment_load(page)
    for _ in range(30):
        if len(sniffer.get_comments(aweme_id)) >= MAX_COMMENTS_PER_VIDEO:
            break
        await page.wait_for_timeout(1000)

    comments = sniffer.get_comments(aweme_id)[:MAX_COMMENTS_PER_VIDEO]
    print(f"     📝 接口采集评论: {len(comments)} 条")
    return rows_from_api(detail or {}, comments, video_url, source_keyword)


async def login_and_save_state(browser_context, page):
    print("\n" + "=" * 50)
    print("请在 Edge 中登录抖音，完成后回到终端按 Enter")
    print("=" * 50)
    await page.goto("https://www.douyin.com", wait_until="domcontentloaded")
    input(">>> 登录完成后按 Enter: ")
    await browser_context.storage_state(path=STATE_FILE)
    print(f"✅ 已保存 {STATE_FILE}")


async def main():
    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(END_DATE, "%Y-%m-%d")
    sniffer = DouyinApiSniffer()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        if os.path.exists(STATE_FILE):
            context = await browser.new_context(
                storage_state=STATE_FILE,
                viewport={"width": 1440, "height": 900},
                locale="zh-CN",
            )
        else:
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                locale="zh-CN",
            )

        page = await context.new_page()
        sniffer.attach(page)

        await page.goto("https://www.douyin.com", wait_until="domcontentloaded")
        try:
            await page.wait_for_selector("input[placeholder*='搜索']", timeout=8000)
            print("✅ 登录状态有效")
        except Exception:
            print("⚠️ 需要登录")
            await login_and_save_state(context, page)

        results = []
        for keyword in KEYWORDS:
            search_url = f"https://www.douyin.com/search/{quote(keyword)}?type=video"
            print(f"\n🔍 搜索词条: {keyword}")
            await page.goto(search_url, wait_until="commit", timeout=60000)
            await page.wait_for_timeout(5000)

            try:
                await page.wait_for_selector("a[href*='/video/']", timeout=15000)
                print("✅ 搜索结果已出现")
            except Exception:
                print(f"❌ 搜索页异常 URL={page.url}，跳过该词条")
                continue

            try:
                filter_btn = page.locator("div.search-filter >> text=筛选")
                if await filter_btn.count() > 0:
                    await filter_btn.first.click()
                    await page.wait_for_timeout(1000)
                    latest_btn = page.locator("text=最新发布")
                    if await latest_btn.count() > 0:
                        await latest_btn.first.click()
                        await page.wait_for_timeout(2000)
            except Exception:
                pass

            await scroll_to_bottom(page, "a[href*='/video/']", max_scrolls=10)
            video_urls = await collect_video_urls(page, MAX_VIDEOS)
            print(f"📊 [{keyword}] 将处理 {len(video_urls)} 个视频（请勿关闭浏览器）")

            for idx, video_url in enumerate(video_urls):
                print(f"\n[{keyword}] [{idx + 1}/{len(video_urls)}]")
                try:
                    rows = await process_one_video(
                        page, sniffer, video_url, start_dt, end_dt, keyword
                    )
                    results.extend(rows)
                except Exception as e:
                    print(f"  ❌ 出错: {e}")
                await asyncio.sleep(1)

        if results:
            keys = [
                "来源类型", "视频链接", "作者ID", "作者名字", "视频发布时间",
                "评论ID", "评论者名字", "评论内容", "话题标签", "点赞数", "评论数",
            ]
            with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                w.writeheader()
                w.writerows(results)
            print(f"\n✅ 保存 {len(results)} 条评论 → {OUTPUT_FILE}")
        else:
            print("\n⚠️ 未采集到数据。可删除 douyin_state.json 重登，或将 MIN_LIKE_COUNT 调小测试")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

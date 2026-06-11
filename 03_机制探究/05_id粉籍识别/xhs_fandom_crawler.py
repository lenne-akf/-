"""小红书用户粉籍识别：复用微博情感推断逻辑，合规限速抓取公开主页与笔记。"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import pandas as pd
import requests
from playwright.sync_api import sync_playwright
from xhshow import Xhshow

from weibo_fandom_crawler import (
    CONFIDENCE_THRESHOLD,
    append_record,
    classify_user,
    is_weibo_uid,
    load_all_records,
    load_checkpoint,
    normalize_id_column,
    save_checkpoint,
)
from xhs_xyw_sign import sign_headers_get_xyw

BASE_DIR = Path(__file__).resolve().parent
COOKIE_FILE = BASE_DIR / "cookie_xhs"
STORAGE_STATE = BASE_DIR / "xhs_storage_state.json"
DEFAULT_INPUT = BASE_DIR / "xhs_ids_deduped.xlsx"

MIN_DELAY = 2.0
MAX_DELAY = 3.5
MAX_NOTES = 50
MAX_NOTE_PAGES = 3


def load_cookie() -> str:
    return COOKIE_FILE.read_text(encoding="utf-8").strip()


def parse_cookie_dict(cookie_str: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def make_api_session(cookie_str: str, uid: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://www.xiaohongshu.com/user/profile/{uid}",
            "Origin": "https://www.xiaohongshu.com",
            "Cookie": cookie_str,
        }
    )
    return session


def build_xhs_input() -> pd.DataFrame:
    """从四批去重文件汇总非微博 ID（含 origin）。"""
    rows: list[dict] = []
    for f in ["id_deduped.xlsx", "id2_deduped.xlsx", "id3_deduped.xlsx", "id4_deduped.xlsx"]:
        path = BASE_DIR / f
        if not path.exists():
            continue
        df = normalize_id_column(pd.read_excel(path))
        batch = f.replace("_deduped.xlsx", "")
        for _, row in df.iterrows():
            uid = str(row["user_id"]).strip()
            if not uid or uid.lower() == "nan" or is_weibo_uid(uid):
                continue
            origin = str(row["origin"]).strip() if "origin" in df.columns else batch
            rows.append({"user_id": uid, "origin": origin})
    out = pd.DataFrame(rows).drop_duplicates(subset=["user_id"], keep="first")
    out.to_excel(DEFAULT_INPUT, index=False)
    print(f"Built XHS input: {len(out)} unique IDs -> {DEFAULT_INPUT.name}")
    return out


def note_to_text(note: dict) -> str:
    parts: list[str] = []
    card = note.get("note_card") or note.get("noteCard") or note
    if not isinstance(card, dict):
        return ""
    for key in ("display_title", "title", "desc", "description"):
        val = card.get(key)
        if val:
            parts.append(str(val))
    tags = card.get("tag_list") or card.get("tagList") or []
    for tag in tags:
        if isinstance(tag, dict):
            name = tag.get("name") or tag.get("tag_name") or ""
            if name:
                parts.append(f"#{name}#")
        elif isinstance(tag, str):
            parts.append(f"#{tag}#")
    return " ".join(parts).strip()


def parse_profile_payload(data: dict) -> dict:
    basic = data.get("basic_info") or data.get("basicInfo") or {}
    interactions = data.get("interactions") or []
    fans = follows = notes_count = 0
    for item in interactions:
        itype = (item.get("type") or item.get("name") or "").lower()
        count = item.get("count") or item.get("value") or 0
        try:
            count = int(str(count).replace(",", ""))
        except ValueError:
            count = 0
        if "fan" in itype or itype == "fans":
            fans = count
        elif "follow" in itype:
            follows = count
        elif "note" in itype or "发布" in itype:
            notes_count = count
    return {
        "screen_name": basic.get("nickname") or basic.get("nick_name") or "",
        "description": basic.get("desc") or basic.get("description") or "",
        "red_id": basic.get("red_id") or basic.get("redId") or "",
        "gender": basic.get("gender", ""),
        "ip_location": basic.get("ip_location") or basic.get("ipLocation") or "",
        "followers_count": fans,
        "friends_count": follows,
        "statuses_count": notes_count,
    }


def parse_notes_payload(data: dict) -> tuple[list[str], str | None]:
    notes = data.get("notes") or data.get("note_list") or []
    texts: list[str] = []
    for note in notes:
        text = note_to_text(note)
        if text:
            texts.append(text)
    cursor = data.get("cursor") or data.get("next_cursor")
    return texts, cursor


def check_logged_in(cookie_str: str, client: Xhshow | None = None) -> bool:
    client = client or Xhshow()
    cookies = parse_cookie_dict(cookie_str)
    sign_headers = client.sign_headers_get(uri="/api/sns/web/v2/user/me", cookies=cookies)
    resp = requests.get(
        "https://edith.xiaohongshu.com/api/sns/web/v2/user/me",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.xiaohongshu.com/",
            "Origin": "https://www.xiaohongshu.com",
            "Cookie": cookie_str,
            **sign_headers,
        },
        timeout=20,
    )
    if resp.status_code != 200:
        return False
    data = resp.json().get("data") or {}
    return bool(data.get("user_id")) and not data.get("guest", True)


def fetch_user(cookie_str: str, uid: str, client: Xhshow | None = None) -> tuple[dict, list[str], str | None]:
    client = client or Xhshow()
    cookies = parse_cookie_dict(cookie_str)
    if not cookies.get("a1"):
        return {}, [], "missing a1 cookie"

    session = make_api_session(cookie_str, uid)

    profile_uri = "/api/sns/web/v1/user/otherinfo"
    profile_params = {"target_user_id": uid}
    sign_headers = sign_headers_get_xyw(client, profile_uri, cookies, profile_params)
    resp = session.get(
        "https://edith.xiaohongshu.com" + profile_uri,
        params=profile_params,
        headers=sign_headers,
        timeout=20,
    )
    if resp.status_code == 461:
        try:
            body = resp.json()
            code = body.get("code")
            msg = body.get("msg") or ""
            if code in (300011, 300015):
                return {}, [], (
                    f"账号安全限制(code={code}): {msg}。"
                    "请先在浏览器打开小红书完成扫码/安全验证，再重新复制 cookie。"
                )
        except Exception:
            pass
        return {}, [], f"profile http 461"
    if resp.status_code != 200:
        return {}, [], f"profile http {resp.status_code}"
    body = resp.json()
    if body.get("code") != 0 or not body.get("success"):
        return {}, [], body.get("msg") or f"profile api code {body.get('code')}"

    profile = parse_profile_payload(body.get("data") or {})

    posts: list[str] = []
    cursor = ""
    for _ in range(MAX_NOTE_PAGES):
        note_uri = "/api/sns/web/v1/user_posted"
        note_params = {
            "num": "30",
            "cursor": cursor,
            "user_id": uid,
            "image_formats": "jpg,webp,avif",
        }
        sign_headers = sign_headers_get_xyw(client, note_uri, cookies, note_params)
        resp = session.get(
            "https://edith.xiaohongshu.com" + note_uri,
            params=note_params,
            headers=sign_headers,
            timeout=20,
        )
        if resp.status_code != 200:
            break
        note_body = resp.json()
        if note_body.get("code") != 0:
            break
        page_texts, cursor = parse_notes_payload(note_body.get("data") or {})
        posts.extend(page_texts)
        if len(posts) >= MAX_NOTES or not cursor:
            break
        time.sleep(random.uniform(0.4, 0.8))

    return profile, posts[:MAX_NOTES], None


class BrowserFetcher:
    """用 Playwright 保存的浏览器会话抓取（绕过 cookie 复制不完整问题）。"""

    def __init__(self, state_file: Path):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True, channel="msedge")
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=str(state_file),
        )

    def close(self) -> None:
        self._context.close()
        self._browser.close()
        self._pw.stop()

    def fetch(self, uid: str) -> tuple[dict, list[str], str | None]:
        profile_data: dict | None = None
        note_pages: list[dict] = []
        page = self._context.new_page()

        def on_response(resp):
            nonlocal profile_data
            url = resp.url
            if resp.status != 200 or "edith.xiaohongshu.com/api/sns/web/" not in url:
                return
            try:
                body = resp.json()
            except Exception:
                return
            if "/user/otherinfo" in url and uid in url:
                if body.get("code") == 0:
                    profile_data = body.get("data") or {}
            elif "/user_posted" in url and uid in url:
                if body.get("code") == 0:
                    note_pages.append(body.get("data") or {})

        page.on("response", on_response)
        page.goto(
            f"https://www.xiaohongshu.com/user/profile/{uid}",
            wait_until="commit",
            timeout=120_000,
        )
        page.wait_for_timeout(4000)
        for _ in range(MAX_NOTE_PAGES - 1):
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(1500)

        body_text = page.inner_text("body")
        page.close()

        if ("扫码" in body_text or "验证" in body_text) and not profile_data and not note_pages:
            return {}, [], "浏览器会话仍要求扫码验证，请重新运行 xhs_save_session.py"

        if not profile_data and not note_pages:
            return {}, [], "未获取到用户数据（可能私密账号或不存在）"

        profile = parse_profile_payload(profile_data or {})
        posts: list[str] = []
        for pdata in note_pages:
            texts, _ = parse_notes_payload(pdata)
            posts.extend(texts)
            if len(posts) >= MAX_NOTES:
                break
        return profile, posts[:MAX_NOTES], None


def crawl_all(
    input_file: Path,
    output_file: Path,
    checkpoint_file: Path,
    resume: bool = False,
    use_browser: bool = False,
) -> pd.DataFrame:
    if not input_file.exists():
        df = build_xhs_input()
    else:
        df = normalize_id_column(pd.read_excel(input_file))
        df = df[~df["user_id"].astype(str).str.lower().eq("nan")]

    origin_map = {}
    if "origin" in df.columns:
        origin_map = dict(zip(df["user_id"].astype(str), df["origin"].astype(str)))

    all_ids = df["user_id"].astype(str).tolist()
    print(f"XHS IDs to crawl: {len(all_ids)}")

    checkpoint = load_checkpoint(checkpoint_file) if resume else {"version": 3, "done": [], "records": []}
    records_file = checkpoint_file.with_suffix(".jsonl")
    done = set(checkpoint["done"])

    cookie_str = load_cookie()
    client = Xhshow()
    browser_fetcher: BrowserFetcher | None = None

    if use_browser or STORAGE_STATE.exists():
        state_file = STORAGE_STATE
        if not state_file.exists():
            raise RuntimeError("未找到 xhs_storage_state.json，请先运行: python xhs_save_session.py")
        browser_fetcher = BrowserFetcher(state_file)
        test_profile, test_posts, err = browser_fetcher.fetch(all_ids[0])
        if err or not test_profile.get("screen_name"):
            browser_fetcher.close()
            raise RuntimeError(f"浏览器会话测试失败: {err or '无用户数据'}")
        print(f"浏览器模式: {test_profile.get('screen_name')}，笔记 {len(test_posts)} 条")
    else:
        if not check_logged_in(cookie_str, client):
            raise RuntimeError("cookie_xhs 未登录或已过期，请更新后重试")
        print("Cookie 校验通过：已登录")
        test_profile, test_posts, err = fetch_user(cookie_str, all_ids[0], client)
        if err or not test_profile.get("screen_name"):
            raise RuntimeError(
                f"API 测试失败: {err or '无用户数据'}。"
                "建议运行 python xhs_save_session.py 后加 --browser 参数爬取"
            )
        print(f"API 测试成功: {test_profile.get('screen_name')}，笔记 {len(test_posts)} 条")

    pending = [uid for uid in all_ids if uid not in done]
    try:
        for idx, uid in enumerate(pending, 1):
            print(f"[{idx}/{len(pending)}] XHS {uid}...", flush=True)
            row = {
                "user_id": uid,
                "origin": origin_map.get(uid, ""),
                "platform": "小红书",
                "screen_name": "",
                "description": "",
                "red_id": "",
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
                if browser_fetcher:
                    profile, posts, err = browser_fetcher.fetch(uid)
                else:
                    profile, posts, err = fetch_user(cookie_str, uid, client)
                if err and not profile.get("screen_name") and not posts:
                    raise RuntimeError(err)

                result = classify_user(profile, posts)
                row.update(
                    {
                        "screen_name": profile.get("screen_name", ""),
                        "description": profile.get("description", ""),
                        "red_id": profile.get("red_id", ""),
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
                if err:
                    row["posts_sample"] = (row["posts_sample"] + f" | warn: {err}")[:500]

                print(
                    f"  -> {row['screen_name'] or '(无昵称)'} | {row['fandom_label']} "
                    f"(conf={row['confidence']:.0%}, score={row['fan_score']})",
                    flush=True,
                )
            except Exception as exc:
                row["status"] = "error"
                row["fandom_label"] = "抓取失败"
                row["posts_sample"] = f"error: {exc}"
                print(f"  -> ERROR: {exc}", flush=True)

            done.add(uid)
            checkpoint["done"] = list(done)
            append_record(row, records_file)
            save_checkpoint(checkpoint, checkpoint_file, records_file)

            if idx < len(pending):
                time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    finally:
        if browser_fetcher:
            browser_fetcher.close()

    result_df = pd.DataFrame(load_all_records(records_file))
    result_df.to_excel(output_file, index=False)
    print_summary(result_df, output_file)
    return result_df


def print_summary(df: pd.DataFrame, output_file: Path) -> None:
    print("\n=== XHS Summary ===")
    print(f"Total records: {len(df)}")
    if "fandom_label" in df.columns:
        print("\nFandom labels (top 15):")
        print(df["fandom_label"].value_counts().head(15).to_string())
    pool_label = f"不在conf{int(CONFIDENCE_THRESHOLD * 100)}池"
    conf = (
        df["fandom_label"].notna()
        & ~df["fandom_label"].isin([pool_label, "无法判断", "抓取失败"])
    ).sum()
    print(f"\nIn conf{int(CONFIDENCE_THRESHOLD * 100)} pool: {conf} ({conf / max(len(df), 1) * 100:.1f}%)")
    print(f"Output: {output_file}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="小红书粉籍爬取与推断（conf70）")
    p.add_argument("--input", default="xhs_ids_deduped.xlsx", help="输入 xlsx")
    p.add_argument("--output", default="xhs_fandom_result.xlsx", help="结果 xlsx")
    p.add_argument("--checkpoint", default="crawl_checkpoint_xhs.json", help="断点 json")
    p.add_argument("--resume", action="store_true", help="断点续爬")
    p.add_argument("--browser", action="store_true", help="使用 xhs_storage_state.json 浏览器会话")
    p.add_argument("--rebuild-input", action="store_true", help="从四批 deduped 重建输入")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.rebuild_input:
        build_xhs_input()
    crawl_all(
        BASE_DIR / args.input,
        BASE_DIR / args.output,
        BASE_DIR / args.checkpoint,
        resume=args.resume,
        use_browser=args.browser,
    )

"""在真实浏览器中登录小红书并保存会话，供爬虫使用。"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE = BASE_DIR / "xhs_storage_state.json"


def save_session(state_file: Path, profile_url: str) -> None:
    print("将打开 Edge 浏览器，请在小红书网页中完成登录与安全验证。")
    print("确认能正常浏览用户主页后，回到终端按 Enter 保存会话。")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="msedge")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded", timeout=120_000)
        input("\n>>> 登录并打开任意用户主页确认正常后，按 Enter 保存会话...\n")
        page.goto(profile_url, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(3000)
        context.storage_state(path=str(state_file))
        browser.close()
    print(f"会话已保存: {state_file}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="保存小红书浏览器登录态")
    p.add_argument("--state", default=str(DEFAULT_STATE), help="输出 json 路径")
    p.add_argument(
        "--profile",
        default="https://www.xiaohongshu.com/user/profile/64fdfe220000000005001727",
        help="用于验证的 profile 链接",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    save_session(Path(args.state), args.profile)

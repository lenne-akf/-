# -*- coding: utf-8 -*-
"""小红书爬虫配置（A 组事件向关键词）。"""
from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import DATA, PKG_XHS, XHS_COOKIE  # noqa: E402

PKG_DIR = Path(__file__).resolve().parent

# A 组 · 事件向（与论文检索口径一致）
KEYWORDS: list[str] = [
    "单依纯 李荣浩",
    "单依纯 侵权",
    "单依纯 李白",
    "如何呢 又能怎",
    "李荣浩 版权",
]

MAX_NOTES_PER_KEYWORD = 80
MAX_COMMENTS_PER_NOTE = 200
MAX_SCROLL_ROUNDS = 12
HEADLESS = False

SLEEP_BETWEEN_KEYWORDS = 3.0
SLEEP_BETWEEN_NOTES = 2.0
SLEEP_AFTER_SCROLL = 1.2

EVENT_NAME = "单依纯李荣浩版权争议"
PLATFORM = "xiaohongshu"

PROJECT_DIR = PKG_XHS.parent  # 概览分析/
OUTPUT_DIR = DATA
COOKIE_FILE = XHS_COOKIE

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

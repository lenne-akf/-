# -*- coding: utf-8 -*-
"""掩码词云：按 explore 阶段生成 PNG，供 dispute_dashboard 动画展示。"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage
from wordcloud import WordCloud

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import OUT, OVERVIEW  # noqa: E402

MASK_PATH = OVERVIEW / "mask.png"
OUT_WC = OUT / "wordcloud"
OUT_WC_PLAT = OUT / "wordcloud_platform"
PLAT_IDS = [
    ("weibo", "微博"),
    ("douyin", "抖音"),
    ("xiaohongshu", "小红书"),
]

# 偏深酒红/金，少浅色，词云更饱满显眼
WC_COLORS = (
    "#2a0a12", "#3d1218", "#4a0e0e", "#5c1a28", "#6b1d35",
    "#722f37", "#8b2332", "#9a3050", "#a07d3a", "#8b6914",
)
WC_WEIGHTS = (4, 4, 5, 4, 5, 5, 5, 4, 2, 2)


def find_cjk_font() -> str | None:
    for p in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ):
        if p.exists():
            return str(p)
    return None


def load_mask_array(threshold: int = 200) -> np.ndarray:
    """
    mask.png：黑色麦克风 + 白色背景。

    WordCloud 约定（与 PIL 相反）：
      - 数组值 0（黑）→ 可填词（主体）
      - 数组值 255（白）→ 不填词（背景）
    """
    if not MASK_PATH.exists():
        raise FileNotFoundError(f"未找到掩码图: {MASK_PATH}")
    gray = np.array(Image.open(MASK_PATH).convert("L"))

    # 黑色区域 = 麦克风主体
    subject = gray < threshold

    labeled, n = ndimage.label(subject)
    if n > 1:
        sizes = ndimage.sum(subject, labeled, range(1, n + 1))
        subject = labeled == (int(np.argmax(sizes)) + 1)

    subject = ndimage.binary_fill_holes(subject)
    subject = ndimage.binary_opening(subject, iterations=1)

    coords = np.argwhere(subject)
    if coords.size:
        h, w = gray.shape
        pad = 16
        y0 = max(0, int(coords[:, 0].min()) - pad)
        y1 = min(h, int(coords[:, 0].max()) + pad + 1)
        x0 = max(0, int(coords[:, 1].min()) - pad)
        x1 = min(w, int(coords[:, 1].max()) + pad + 1)
        subject = subject[y0:y1, x0:x1]

    ratio = float(subject.mean())
    if ratio < 0.02 or ratio > 0.88:
        raise ValueError(
            f"主体区域占比 {ratio:.1%} 异常；请使用黑形白底 mask.png（仅麦克风涂黑）"
        )

    # 主体=0 可填词，背景=255 留白
    wc_mask = np.where(subject, 0, 255).astype(np.uint8)
    return wc_mask


def _resize_mask(mask: np.ndarray, max_side: int = 1100) -> np.ndarray:
    h, w = mask.shape
    if max(h, w) <= max_side:
        return mask
    scale = max_side / max(h, w)
    nw, nh = int(w * scale), int(h * scale)
    # 最近邻保持 0/255 边界清晰
    return np.array(
        Image.fromarray(mask).resize((nw, nh), Image.Resampling.NEAREST)
    )


def _color_func(word, font_size, position, orientation, random_state=None, **kwargs):
    rng = random_state or random.Random()
    return rng.choices(WC_COLORS, weights=WC_WEIGHTS, k=1)[0]


def build_wordcloud_timeline(
    df: pd.DataFrame,
    phases: list[dict],
    tokenize_fn,
    parse_date_fn,
    top_n: int = 120,
) -> dict:
    """与屏1阶段条对齐的词频序列。"""
    work = df.copy()
    work["_date"] = work["created_at"].map(parse_date_fn)
    frames: list[dict] = []
    for i, ph in enumerate(phases):
        d0, d1 = ph.get("date_start", ""), ph.get("date_end", "")
        if d0 and d1:
            sub = work[work["_date"].between(d0, d1)]
        else:
            sub = work[work["_date"].notna()]
        words = tokenize_fn(sub["content"].tolist(), top_n)
        frames.append({
            "phase_index": i,
            "label": ph.get("label", f"阶段{i + 1}"),
            "label_en": ph.get("label_en", ""),
            "date_start": d0,
            "date_end": d1,
            "count": int(len(sub)),
            "words": words,
            "image": "",
        })
    return {
        "mask_image": "mask.png",
        "top_n": top_n,
        "frames": frames,
    }


def render_wordcloud_frames(
    timeline: dict,
    out_dir: Path | None = None,
    max_side: int = 1100,
) -> dict:
    """为每个阶段渲染掩码词云 PNG。"""
    out_dir = out_dir or OUT_WC
    out_dir.mkdir(parents=True, exist_ok=True)
    font = find_cjk_font()
    if not font:
        print("[警告] 未找到中文字体，跳过词云 PNG 生成")
        return timeline

    wc_mask = _resize_mask(load_mask_array(), max_side=max_side)
    th, tw = wc_mask.shape

    for fr in timeline.get("frames", []):
        freq = {item["word"]: item["count"] for item in fr.get("words", []) if item.get("count", 0) > 0}
        idx = fr.get("phase_index", 0)
        fname = f"wordcloud_phase_{idx}.png"
        out_path = out_dir / fname
        if not freq:
            fr["image"] = ""
            continue

        wc = WordCloud(
            font_path=font,
            width=tw,
            height=th,
            mask=wc_mask,
            background_color=None,
            mode="RGBA",
            max_words=min(200, max(100, len(freq) * 2)),
            min_font_size=9,
            max_font_size=64,
            font_step=1,
            scale=2,
            repeat=True,
            prefer_horizontal=0.5,
            relative_scaling=0.55,
            margin=0,
            contour_width=0,
            color_func=_color_func,
            random_state=42 + idx,
        )
        wc.grid_size = 1
        wc.generate_from_frequencies(freq)
        wc.to_file(str(out_path))
        fr["image"] = fname
        print(f"[词云] {fr.get('label', idx)} → output/wordcloud/{fname}")

    timeline["output_dir"] = "output/wordcloud"
    return timeline


def build_platform_wordcloud(
    df: pd.DataFrame,
    phases: list[dict],
    tokenize_fn,
    parse_date_fn,
    top_n: int = 100,
) -> dict:
    """与屏1阶段对齐：每阶段 × 每平台一张掩码词云。"""
    work = df.copy()
    work["_date"] = work["created_at"].map(parse_date_fn)
    frames: list[dict] = []
    for i, ph in enumerate(phases):
        d0, d1 = ph.get("date_start", ""), ph.get("date_end", "")
        if d0 and d1:
            phase_sub = work[work["_date"].between(d0, d1)]
        else:
            phase_sub = work[work["_date"].notna()]
        for pid, plabel in PLAT_IDS:
            sub = phase_sub[phase_sub["platform"].astype(str) == pid]
            words = tokenize_fn(sub["content"].tolist(), top_n)
            frames.append({
                "phase_index": i,
                "phase_label": ph.get("label", f"阶段{i + 1}"),
                "date_start": d0,
                "date_end": d1,
                "platform": pid,
                "platform_label": plabel,
                "count": int(len(sub)),
                "words": words,
                "image": "",
            })
    return {
        "mask_image": "mask.png",
        "top_n": top_n,
        "platforms": [{"platform": p, "label": l} for p, l in PLAT_IDS],
        "frames": frames,
    }


def render_platform_wordcloud_frames(
    timeline: dict,
    out_dir: Path | None = None,
    max_side: int = 900,
) -> dict:
    out_dir = out_dir or OUT_WC_PLAT
    out_dir.mkdir(parents=True, exist_ok=True)
    font = find_cjk_font()
    if not font:
        print("[警告] 未找到中文字体，跳过分平台词云 PNG")
        return timeline

    wc_mask = _resize_mask(load_mask_array(), max_side=max_side)
    th, tw = wc_mask.shape

    for fr in timeline.get("frames", []):
        freq = {
            item["word"]: item["count"]
            for item in fr.get("words", [])
            if item.get("count", 0) > 0
        }
        pi = fr.get("phase_index", 0)
        pid = fr.get("platform", "weibo")
        fname = f"wordcloud_{pid}_phase_{pi}.png"
        out_path = out_dir / fname
        if not freq:
            fr["image"] = ""
            continue

        wc = WordCloud(
            font_path=font,
            width=tw,
            height=th,
            mask=wc_mask,
            background_color=None,
            mode="RGBA",
            max_words=min(160, max(80, len(freq) * 2)),
            min_font_size=10,
            max_font_size=64,
            font_step=1,
            scale=2,
            repeat=True,
            prefer_horizontal=0.5,
            relative_scaling=0.55,
            margin=0,
            contour_width=0,
            color_func=_color_func,
            random_state=100 + pi * 3 + hash(pid) % 17,
        )
        wc.grid_size = 1
        wc.generate_from_frequencies(freq)
        wc.to_file(str(out_path))
        fr["image"] = fname
        print(
            f"[词云·平台] {fr.get('platform_label', pid)} · {fr.get('phase_label', pi)} "
            f"→ output/wordcloud_platform/{fname}"
        )

    timeline["output_dir"] = "output/wordcloud_platform"
    return timeline

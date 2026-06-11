# -*- coding: utf-8 -*-
"""若缺少 mask.png，生成简易麦克风轮廓（黑形白底）供词云使用。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import OVERVIEW


def main() -> None:
    path = OVERVIEW / "mask.png"
    if path.exists():
        print(f"mask 已存在: {path}")
        return

    w, h = 640, 900
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    # 麦头
    draw.ellipse((170, 80, 470, 380), fill=0)
    # 杆
    draw.rounded_rectangle((285, 360, 355, 760), radius=28, fill=0)
    # 底座
    draw.rounded_rectangle((200, 740, 440, 820), radius=24, fill=0)

    arr = np.array(img)
    if (arr < 128).mean() < 0.02:
        raise RuntimeError("生成的 mask 主体区域过小")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print(f"已生成默认 mask: {path}")


if __name__ == "__main__":
    main()

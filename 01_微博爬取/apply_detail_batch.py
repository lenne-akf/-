# -*- coding: utf-8 -*-
"""将 detail_batches/batch_XX.txt 写入 MediaCrawler/config/weibo_config.py。"""

from __future__ import annotations
import argparse
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=1, help="批次号，如 1 对应 batch_01.txt")
    parser.add_argument(
        "--batch-dir",
        default="detail_batches",
        help="相对 output/ 的子目录，如 detail_batches_engagement",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    batch_file = base / "output" / args.batch_dir / f"batch_{args.batch:02d}.txt"
    if not batch_file.exists():
        raise FileNotFoundError(batch_file)

    ids = [ln.strip() for ln in batch_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    cfg = PROJECT_ROOT / "MediaCrawler" / "config" / "weibo_config.py"
    text = cfg.read_text(encoding="utf-8")
    lines = [f'    "{nid}",' for nid in ids]
    block = "WEIBO_SPECIFIED_ID_LIST = [\n" + "\n".join(lines) + "\n]"
    text, n = re.subn(
        r"WEIBO_SPECIFIED_ID_LIST\s*=\s*\[[^\]]*\]",
        block,
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n != 1:
        raise RuntimeError("未能更新 WEIBO_SPECIFIED_ID_LIST")
    cfg.write_text(text, encoding="utf-8")
    print(f"已写入 batch_{args.batch:02d}，共 {len(ids)} 个 note_id → {cfg}")


if __name__ == "__main__":
    main()

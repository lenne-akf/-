# -*- coding: utf-8 -*-
"""
Search 帖子：按 note_id 去重 → 事件相关性筛选 → 生成 detail 待爬 note_id 列表。

输入（默认）：
  MediaCrawler/data/weibo/csv/search_contents_*.csv

输出（weibo_crawl/output/）：
  search_posts_deduped.csv       — 去重后全部 search 帖
  search_posts_event_related.csv — 与事件相关的帖（建议用于分析 / detail）
  search_posts_excluded.csv      — 被剔除的帖及原因
  detail_note_ids.txt            — 按互动量排序的 note_id（供 detail 爬取）
  detail_batches/batch_01.txt …  — 每批 N 个 id（默认 200）
  search_posts_event_related_full.csv — 去重全量（含曾误剔除帖，带 is_event_related 标记）

用法：
  python prepare_search_for_detail.py --top-detail 200 --batch-size 200
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OFFICIAL_UIDS = {
    "1739046981",  # 李荣浩
    "5598574734",  # 单依纯
    "6026098745",  # 工作室
    "6898463374",  # 百沐
}

EVENT_TERMS = [
    "侵权",
    "版权",
    "道歉",
    "赔偿",
    "停唱",
    "强行侵权",
    "音著协",
    "退票",
    "演唱会",
    "歌手2025",
    "歌手 2025",
    "如何呢",
    "魔改",
    "打野",
    "工作室",
    "维护第一枪",
    "巡演",
    "百沐",
    "李白",
]

# 分析主时间窗（仅打标，不强制剔除窗外帖）
EVENT_WINDOW_START = "2025-06-01"
EVENT_WINDOW_END = "2026-04-30 23:59:59"


def _post_text(row: pd.Series) -> str:
    return str(row.get("content") or "")


def classify_relevance(row: pd.Series) -> tuple[bool, str]:
    text = _post_text(row)
    uid = str(row.get("user_id") or "").strip()

    if uid in OFFICIAL_UIDS:
        return True, "official_account"

    has_lr = "李荣浩" in text
    has_syc = "单依纯" in text
    has_event = any(t in text for t in EVENT_TERMS if t != "李白")

    libai_in_event = "李白" in text and (
        has_lr
        or has_syc
        or "侵权" in text
        or "版权" in text
        or "道歉" in text
        or "演唱会" in text
        or "歌手" in text
    )

    if has_lr and has_syc:
        return True, "both_stars"
    if "侵权" in text or "强行侵权" in text:
        return True, "infringement"
    if libai_in_event:
        return True, "libai_event"
    if has_lr and (has_event or "李白" in text):
        return True, "li_with_event"
    if has_syc and (has_event or "李白" in text):
        return True, "shan_with_event"
    if "百沐" in text:
        return True, "baimu"

    if "李白" in text and not has_lr and not has_syc:
        return False, "libai_poetry_or_unrelated"
    if has_lr and not has_syc and "李白" not in text and not has_event:
        return False, "li_fan_or_concert_only"
    if has_syc and not has_lr and "李白" not in text and not has_event:
        return False, "shan_fan_only"
    if not has_lr and not has_syc:
        return False, "no_core_entity"

    return False, "weak_match"


def engagement_score(row: pd.Series) -> int:
    def _n(col: str) -> int:
        try:
            return int(float(row.get(col) or 0))
        except (TypeError, ValueError):
            return 0

    return _n("liked_count") + _n("comments_count") + _n("shared_count")


def load_search_csvs(raw_dir: Path) -> pd.DataFrame:
    files = sorted(raw_dir.glob("search_contents_*.csv"))
    if not files:
        raise FileNotFoundError(f"未找到 search_contents_*.csv: {raw_dir}")
    df = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files], ignore_index=True)
    df["note_id"] = df["note_id"].astype(str)
    return df


def dedupe_posts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("last_modify_ts", ascending=False, na_position="last")
    deduped = df.drop_duplicates(subset=["note_id"], keep="first").copy()
    if "source_keyword" in df.columns:
        kw_map = (
            df.groupby("note_id")["source_keyword"]
            .apply(lambda s: "|".join(sorted({str(x).strip() for x in s if str(x).strip()})))
        )
        deduped["source_keywords_merged"] = deduped["note_id"].map(kw_map)
    return deduped


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
    parser.add_argument("--top-detail", type=int, default=200, help="detail 爬取热帖数量上限")
    parser.add_argument("--batch-size", type=int, default=200, help="detail 分批文件每批条数")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    batch_dir = out_dir / "detail_batches"
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_dir.mkdir(parents=True, exist_ok=True)

    raw = load_search_csvs(raw_dir)
    deduped = dedupe_posts(raw)

    rel = deduped.apply(classify_relevance, axis=1, result_type="expand")
    deduped["is_event_related"] = rel[0]
    deduped["exclude_reason"] = rel[1].where(~rel[0], "")

    deduped["publish_time"] = pd.to_datetime(deduped["create_date_time"], errors="coerce")
    deduped["in_event_window"] = (
        deduped["publish_time"] >= EVENT_WINDOW_START
    ) & (deduped["publish_time"] <= EVENT_WINDOW_END)

    deduped["engagement"] = deduped.apply(engagement_score, axis=1)

    related = deduped.loc[deduped["is_event_related"]].copy()
    excluded = deduped.loc[~deduped["is_event_related"]].copy()

    related = related.sort_values("engagement", ascending=False)
    top_ids = related["note_id"].head(args.top_detail).tolist()

    # 完整版：去重全量，误剔除帖恢复收录（带筛选标记）
    full = deduped.copy()
    full["restored_from_excluded"] = ~full["is_event_related"]
    full = full.sort_values("engagement", ascending=False)

    paths = {
        "deduped": out_dir / "search_posts_deduped.csv",
        "related": out_dir / "search_posts_event_related.csv",
        "excluded": out_dir / "search_posts_excluded.csv",
        "full": out_dir / "search_posts_event_related_full.csv",
        "id_list": out_dir / "detail_note_ids.txt",
    }
    deduped.to_csv(paths["deduped"], index=False, encoding="utf-8-sig")
    related.to_csv(paths["related"], index=False, encoding="utf-8-sig")
    excluded.to_csv(paths["excluded"], index=False, encoding="utf-8-sig")
    full.to_csv(paths["full"], index=False, encoding="utf-8-sig")
    paths["id_list"].write_text("\n".join(top_ids) + ("\n" if top_ids else ""), encoding="utf-8")

    # 清空旧分批，按 batch_size 重写
    for old in batch_dir.glob("batch_*.txt"):
        old.unlink()
    batch_count = 0
    for i in range(0, len(top_ids), args.batch_size):
        chunk = top_ids[i : i + args.batch_size]
        batch_no = i // args.batch_size + 1
        batch_count = batch_no
        (batch_dir / f"batch_{batch_no:02d}.txt").write_text(
            "\n".join(chunk) + "\n", encoding="utf-8"
        )

    _write_weibo_config_ids(top_ids[: args.batch_size])

    print("=== Search 去重与筛选 ===")
    print(f"原始行数（含重复）: {len(raw)}")
    print(f"去重后 note_id: {len(deduped)}")
    print(f"事件相关: {len(related)}")
    print(f"已剔除(仍收录于 full): {len(excluded)}")
    print(f"完整版 full: {len(full)} 行 → {paths['full']}")
    print(f"事件窗内(2025-06~2026-04): {related['in_event_window'].sum()} / {len(related)}")
    print("\n剔除原因分布:")
    print(excluded["exclude_reason"].value_counts().to_string())
    print(f"\n输出:\n  {paths['full']}\n  {paths['related']}\n  {paths['excluded']}")
    print(f"detail Top{args.top_detail} → {paths['id_list']}（共 {batch_count} 轮，每轮最多 {args.batch_size} 条）")
    print(f"已写入 weibo_config 第 1 轮 {min(args.batch_size, len(top_ids))} 个 note_id")


def _write_weibo_config_ids(note_ids: list[str]) -> None:
    cfg = PROJECT_ROOT / "MediaCrawler" / "config" / "weibo_config.py"
    text = cfg.read_text(encoding="utf-8")
    lines = [f'    "{nid}",' for nid in note_ids]
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


if __name__ == "__main__":
    main()

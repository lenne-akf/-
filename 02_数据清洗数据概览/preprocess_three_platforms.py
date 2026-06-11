from __future__ import annotations
# -*- coding: utf-8 -*-
"""
三平台评论数据预处理：合并 → 清洗 → jieba 分词 → 去停用词

输入：
  - 小红书：../output/original_data_*.csv 或本目录 original_data_*.csv
  - 微博（两路合并，均保留）：
      · 微博数据2/detail_comments.csv（队员新交付，热评流）
      · weibo_posts_全部.csv / weibo_posts_超话.csv（帖内评论 JSON）
  - 抖音：douyin_comments.csv（或 douyin_comments*.csv）

输出（本目录 output/）：
  - cleaned_comments.csv
  - cleaned_with_tokens.csv
  - tokenized_comments.txt
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import json
import re
from pathlib import Path

import emoji
import jieba
import pandas as pd

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
OUT_DIR = OUT

STOPWORD_FILES = [
    ROOT / "hit_stopwords.txt",
    ROOT / "stopwords_baidu.txt",
    ROOT / "stopwords_scu.txt",
]

OUT_CLEANED = OUT_DIR / "cleaned_comments.csv"
OUT_WITH_TOKENS = OUT_DIR / "cleaned_with_tokens.csv"
OUT_TOKENIZED_TXT = OUT_DIR / "tokenized_comments.txt"
WEIBO_V2_COMMENTS = DATA / "微博数据2" / "detail_comments.csv"

MIN_CHINESE_CHARS = 2
MIN_TOTAL_CHARS = 4

SPAM_KEYWORDS = (
    "[广告]", "加微信", "加vx", "加V", "加v", "刷赞", "刷粉", "代刷",
    "私信领取", "点击链接", "优惠券", "兼职", "招代理", "免费领取",
    "扫码关注", "推广", "代购", "引流", "领券", "限时优惠",
)

PURE_SYMBOL_RE = re.compile(r"^[\s\d\W]+$", re.UNICODE)
URL_ONLY_RE = re.compile(
    r"^(?:https?://|www\.)[^\s]+$",
    re.IGNORECASE,
)


def load_stopwords(paths: list[Path]) -> set[str]:
    words: set[str] = set()
    for path in paths:
        if not path.exists():
            print(f"[警告] 停用词文件不存在: {path}")
            continue
        for enc in ("utf-8", "utf-8-sig", "gbk"):
            try:
                raw = path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                raw = None
        if raw is None:
            print(f"[警告] 无法解码停用词: {path}")
            continue
        for line in raw.splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                words.add(w)
    return words


def strip_emoji(text: str) -> str:
    return emoji.replace_emoji(text, replace="")


def count_chinese(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def basic_normalize(text: str) -> str:
    t = str(text)
    t = re.sub(r"http\S+", "", t)
    t = re.sub(r"www\.\S+", "", t)
    t = re.sub(r"\[.*?\]", "", t)
    t = re.sub(r"@[^\s\u4e00-\u9fff]+", "", t)
    t = re.sub(r"#([^#]+)#", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_pure_invalid(text: str) -> bool:
    t = str(text).strip()
    if not t:
        return True
    if URL_ONLY_RE.match(t):
        return True
    if PURE_SYMBOL_RE.match(t):
        return True
    no_emoji = strip_emoji(t).strip()
    if not no_emoji:
        return True
    if PURE_SYMBOL_RE.match(no_emoji):
        return True
    if count_chinese(no_emoji) == 0 and not re.search(r"[A-Za-z]{3,}", no_emoji):
        return True
    return False


def is_spam(text: str) -> bool:
    t = str(text)
    tl = t.lower()
    return any(k.lower() in tl for k in SPAM_KEYWORDS)


def is_too_short(text: str) -> bool:
    t = str(text).strip()
    return count_chinese(t) < MIN_CHINESE_CHARS or len(t) < MIN_TOTAL_CHARS


def _empty_series() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "platform", "content", "user_id", "post_id", "created_at",
            "comment_id", "user_name", "like_count", "keyword", "data_source",
        ]
    )


def _row(
    platform: str,
    content: str,
    user_id: str = "",
    post_id: str = "",
    created_at: str = "",
    comment_id: str = "",
    user_name: str = "",
    like_count: str = "",
    keyword: str = "",
    data_source: str = "",
) -> dict:
    return {
        "platform": platform,
        "content": str(content).strip(),
        "user_id": str(user_id).strip(),
        "post_id": str(post_id).strip(),
        "created_at": str(created_at).strip(),
        "comment_id": str(comment_id).strip(),
        "user_name": str(user_name).strip(),
        "like_count": str(like_count).strip(),
        "keyword": str(keyword).strip(),
        "data_source": str(data_source).strip(),
    }


def find_xhs_files() -> list[Path]:
    patterns = [
        OUT / "original_data_*.csv",
        DATA / "original_data_*.csv",
    ]
    found: list[Path] = []
    for pat in patterns:
        found.extend(sorted(pat.parent.glob(pat.name)))
    # 去重路径、按修改时间取最新一份（避免多份时间戳重复合并）
    unique = sorted({p.resolve() for p in found}, key=lambda p: p.stat().st_mtime, reverse=True)
    if not unique:
        return []
    return [unique[0]]


def load_xhs_comments() -> pd.DataFrame:
    paths = find_xhs_files()
    if not paths:
        print("[警告] 未找到小红书 original_data_*.csv")
        return _empty_series()
    path = paths[0]
    print(f"[信息] 小红书: {path.name}")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    rows = []
    for _, r in df.iterrows():
        content = str(r.get("content", "")).strip()
        if not content:
            continue
        created = r.get("created_at") or r.get("comment_time") or ""
        plat = str(r.get("platform", "xiaohongshu")).strip() or "xiaohongshu"
        rows.append(
            _row(
                platform=plat,
                content=content,
                user_id=r.get("user_id", ""),
                post_id=r.get("post_id", ""),
                created_at=created,
                comment_id=r.get("comment_id", ""),
                user_name=r.get("user_name", ""),
                like_count=r.get("like_count", ""),
                keyword=r.get("keyword", ""),
            )
        )
    return pd.DataFrame(rows)


def _normalize_weibo_datetime(raw: str) -> str:
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return ""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1) + s[10:] if len(s) > 10 else m.group(1)
    return s


def load_weibo_comments_v2() -> pd.DataFrame:
    path = WEIBO_V2_COMMENTS
    if not path.exists():
        return _empty_series()
    print(f"[信息] 微博(新): {path.relative_to(DATA)}")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]
    rows = []
    skip = {"转发微博", "转发", ""}
    for _, r in df.iterrows():
        content = str(r.get("content", "")).strip()
        if not content or content in skip:
            continue
        note_id = str(r.get("note_id", "")).strip()
        if not note_id:
            continue
        cid = str(r.get("comment_id", "")).strip() or f"wb_{note_id}_{len(rows)}"
        created = _normalize_weibo_datetime(
            r.get("create_date_time") or r.get("create_time") or ""
        )
        rows.append(
            _row(
                platform="weibo",
                content=content,
                user_id=str(r.get("user_id", "")).strip(),
                post_id=note_id,
                created_at=created,
                comment_id=cid,
                user_name=str(r.get("nickname", "")).strip(),
                like_count=str(r.get("comment_like_count", "")).strip(),
                keyword="微博数据2",
                data_source="微博数据2",
            )
        )
    print(f"       原始评论行: {len(df):,} → 有效: {len(rows):,}")
    return pd.DataFrame(rows) if rows else _empty_series()


def load_weibo_comments_legacy() -> pd.DataFrame:
    rows = []
    for fname in ("weibo_posts_全部.csv", "weibo_posts_超话.csv"):
        path = DATA / fname
        if not path.exists():
            print(f"[警告] 微博文件不存在: {fname}")
            continue
        print(f"[信息] 微博: {fname}")
        df = pd.read_csv(path, encoding="utf-8-sig", on_bad_lines="skip", dtype=str)
        df.columns = [c.strip() for c in df.columns]
        for _, post in df.iterrows():
            pid = str(post.get("帖子ID", "")).strip()
            if not pid:
                continue
            raw = post.get("评论列表(JSON)")
            if pd.isna(raw) or not str(raw).strip():
                continue
            try:
                items = json.loads(str(raw))
            except json.JSONDecodeError:
                continue
            if not isinstance(items, list):
                continue
            for i, c in enumerate(items):
                if not isinstance(c, dict):
                    continue
                content = str(c.get("text", c.get("content", ""))).strip()
                if not content or content == "转发微博":
                    continue
                uid = str(c.get("user_id", c.get("uid", c.get("user_uid", "")))).strip()
                rows.append(
                    _row(
                        platform="weibo",
                        content=content,
                        user_id=uid,
                        post_id=pid,
                        created_at=str(c.get("time", c.get("created_at", ""))),
                        comment_id=f"wb_legacy_{pid}_{i}",
                        user_name=str(c.get("user", c.get("user_name", ""))),
                        like_count=str(c.get("likes", c.get("like_count", ""))),
                        keyword=str(post.get("来源类型", "")),
                        data_source=fname,
                    )
                )
    return pd.DataFrame(rows) if rows else _empty_series()


def load_weibo_comments() -> pd.DataFrame:
    """合并两路微博评论，清洗阶段再按 user_id+post_id+content 去重。"""
    parts: list[pd.DataFrame] = []
    leg = load_weibo_comments_legacy()
    if not leg.empty:
        parts.append(leg)
    v2 = load_weibo_comments_v2()
    if not v2.empty:
        parts.append(v2)
    if not parts:
        print("[警告] 未找到任何微博评论数据（微博数据2 与 weibo_posts_*.csv 均不可用）")
        return _empty_series()
    combined = pd.concat(parts, ignore_index=True)
    print(
        f"[信息] 微博两路合并(清洗前): "
        f"weibo_posts={len(leg):,} + 微博数据2={len(v2):,} → 合计 {len(combined):,}"
    )
    return combined


def find_douyin_file() -> Path | None:
    for name in ("douyin_comments.csv", "douyin_comments(1).csv"):
        p = DATA / name
        if p.exists():
            return p
    matches = sorted(ROOT.glob("douyin_comments*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def extract_douyin_post_id(url: str) -> str:
    m = re.search(r"/video/(\d+)", str(url))
    return m.group(1) if m else str(url).strip()


def load_douyin_comments() -> pd.DataFrame:
    path = find_douyin_file()
    if path is None:
        print("[警告] 未找到抖音 douyin_comments*.csv")
        return _empty_series()
    print(f"[信息] 抖音: {path.name}")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        "content": ["评论内容", "content", "评论文本"],
        "comment_id": ["评论ID", "comment_id"],
        "post_id": ["视频ID", "post_id", "aweme_id"],
        "video_url": ["视频链接", "video_url"],
        "created_at": ["评论时间", "created_at", "视频发布时间", "发布时间"],
        "user_id": ["评论用户ID", "user_id", "用户ID"],
        "user_name": ["评论用户", "user_name", "作者名字", "昵称"],
        "like_count": ["点赞数", "like_count"],
        "keyword": ["来源类型", "keyword", "搜索词"],
    }

    def pick(row, keys: list[str]) -> str:
        for k in keys:
            if k in row.index and pd.notna(row.get(k)):
                v = str(row.get(k)).strip()
                if v:
                    return v
        return ""

    rows = []
    for _, r in df.iterrows():
        content = pick(r, col_map["content"])
        if not content:
            continue
        post_id = pick(r, col_map["post_id"])
        if not post_id:
            post_id = extract_douyin_post_id(pick(r, col_map["video_url"]))
        cid = pick(r, col_map["comment_id"]).lstrip("\t").strip()
        rows.append(
            _row(
                platform="douyin",
                content=content,
                user_id=pick(r, col_map["user_id"]),
                post_id=post_id,
                created_at=pick(r, col_map["created_at"]),
                comment_id=cid,
                user_name=pick(r, col_map["user_name"]),
                like_count=pick(r, col_map["like_count"]),
                keyword=pick(r, col_map["keyword"]),
            )
        )
    return pd.DataFrame(rows)


def merge_all() -> tuple[pd.DataFrame, pd.Series]:
    parts = [load_xhs_comments(), load_weibo_comments(), load_douyin_comments()]
    parts = [p for p in parts if not p.empty]
    if not parts:
        raise SystemExit("未找到任何平台评论数据，请检查输入文件。")
    merged = pd.concat(parts, ignore_index=True)
    src_counts = merged["data_source"].fillna("").replace("", "未标注").value_counts()
    return merged, src_counts


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats = {
        "empty_removed": 0,
        "short_removed": 0,
        "invalid_removed": 0,
        "spam_removed": 0,
        "dup_removed": 0,
    }
    work = df.copy()
    if "data_source" not in work.columns:
        work["data_source"] = ""
    work["content_raw"] = work["content"].astype(str)
    work["content"] = work["content_raw"].map(basic_normalize)

    # 去重时优先保留「微博数据2」（含真实 comment_id / 点赞 / 时间更完整）
    def _source_priority(src: str) -> int:
        s = str(src)
        if "微博数据2" in s:
            return 0
        if "weibo_posts" in s:
            return 1
        return 2

    work["_dedup_prio"] = work["data_source"].map(_source_priority)
    work = work.sort_values("_dedup_prio").reset_index(drop=True)

    def _merge_sources(series: pd.Series) -> str:
        parts: set[str] = set()
        for s in series:
            for x in str(s).replace("|", "+").split("+"):
                x = x.strip()
                if x:
                    parts.add(x)
        return "+".join(sorted(parts))

    # 仅当 user_id、post_id、content 三字段全部相同才视为重复；
    # 同一用户在同一帖的多条不同正文会全部保留。
    n_before_dedup = len(work)
    dedup_cols = ["user_id", "post_id", "content"]
    work["data_source"] = work.groupby(dedup_cols, sort=False)["data_source"].transform(
        _merge_sources
    )
    work = work.drop_duplicates(subset=dedup_cols, keep="first")
    work = work.drop(columns=["_dedup_prio"], errors="ignore")
    stats["dup_removed"] = n_before_dedup - len(work)

    mask_empty = work["content"].str.len() == 0
    stats["empty_removed"] = int(mask_empty.sum())
    work = work[~mask_empty]

    mask_short = work["content"].map(is_too_short)
    stats["short_removed"] = int(mask_short.sum())
    work = work[~mask_short]

    mask_invalid = work["content"].map(is_pure_invalid)
    stats["invalid_removed"] = int(mask_invalid.sum())
    work = work[~mask_invalid]

    mask_spam = work["content"].map(is_spam)
    stats["spam_removed"] = int(mask_spam.sum())
    work = work[~mask_spam]

    return work.reset_index(drop=True), stats


def tokenize_text(text: str, stopwords: set[str]) -> list[str]:
    words = jieba.lcut(str(text), cut_all=False)
    out = []
    for w in words:
        w = w.strip()
        if not w or len(w) < 2:
            continue
        if w in stopwords:
            continue
        if re.fullmatch(r"\d+", w):
            continue
        if re.fullmatch(r"[\W_]+", w) and not re.search(r"[\u4e00-\u9fff]", w):
            continue
        out.append(w)
    return out


def tokenize_dataframe(df: pd.DataFrame, stopwords: set[str]) -> pd.DataFrame:
    tokens_list = [tokenize_text(t, stopwords) for t in df["content"]]
    out = df.copy()
    out["tokens"] = [" ".join(ts) for ts in tokens_list]
    return out


def print_report(
    n_raw: int,
    raw_by_platform: pd.Series,
    stats: dict,
    n_final: int,
    final_by_platform: pd.Series,
    stopword_count: int,
) -> None:
    removed = (
        stats["empty_removed"]
        + stats["short_removed"]
        + stats["invalid_removed"]
        + stats["spam_removed"]
        + stats["dup_removed"]
    )
    lines = [
        "",
        "=" * 76,
        "三平台评论数据清洗报告",
        "=" * 76,
        f"原始合并条数: {n_raw}",
        "各平台原始数量:",
    ]
    for plat, cnt in raw_by_platform.items():
        lines.append(f"  - {plat}: {cnt}")
    lines.extend([
        "-" * 76,
        f"去重删除 (user_id+post_id+content 三字段完全相同): {stats['dup_removed']}",
        f"空 content 删除: {stats['empty_removed']}",
        f"过短删除 (<{MIN_CHINESE_CHARS} 汉字 或 <{MIN_TOTAL_CHARS} 字符): {stats['short_removed']}",
        f"纯符号/表情/数字/URL 删除: {stats['invalid_removed']}",
        f"广告/灌水删除: {stats['spam_removed']}",
        f"合计删除: {removed}",
        "-" * 76,
        f"最终有效条数: {n_final}",
        "各平台清洗后数量:",
    ])
    for plat, cnt in final_by_platform.items():
        lines.append(f"  - {plat}: {cnt}")
    lines.extend([
        f"停用词表合并: {stopword_count} 个",
        "=" * 76,
    ])
    print("\n".join(lines))


def print_source_report(src_counts: pd.Series) -> None:
    if src_counts.empty:
        return
    print("\n各数据来源条数（合并后、清洗前）:")
    for name, cnt in src_counts.items():
        print(f"  - {name}: {cnt}")


def main() -> None:
    jieba.setLogLevel(jieba.logging.INFO)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    merged, src_counts = merge_all()
    n_raw = len(merged)
    raw_plat = merged["platform"].value_counts()
    print_source_report(src_counts)

    cleaned, stats = clean_dataframe(merged)
    n_final = len(cleaned)

    # 主表列：统一字段 + 元信息（不含 token）
    core_cols = [
        "platform", "content", "user_id", "post_id", "created_at",
        "comment_id", "user_name", "like_count", "keyword", "data_source", "content_raw",
    ]
    cleaned_out = cleaned[[c for c in core_cols if c in cleaned.columns]]
    cleaned_out.to_csv(OUT_CLEANED, index=False, encoding="utf-8-sig")

    stopwords = load_stopwords(STOPWORD_FILES)
    with_tokens = tokenize_dataframe(cleaned_out, stopwords)
    with_tokens.to_csv(OUT_WITH_TOKENS, index=False, encoding="utf-8-sig")

    OUT_TOKENIZED_TXT.write_text(
        "\n".join(with_tokens["tokens"].tolist()) + ("\n" if n_final else ""),
        encoding="utf-8",
    )

    final_plat = cleaned["platform"].value_counts()
    print_report(n_raw, raw_plat, stats, n_final, final_plat, len(stopwords))

    # 验收：CSV 行数与报告一致；txt 行数与 CSV 一致（含分词结果为空的行）
    verify = len(pd.read_csv(OUT_WITH_TOKENS, encoding="utf-8-sig"))
    txt_raw = OUT_TOKENIZED_TXT.read_text(encoding="utf-8")
    txt_lines = len(txt_raw.splitlines()) if txt_raw else 0
    nonempty_tokens = int((with_tokens["tokens"].str.strip() != "").sum())
    ok = verify == n_final and txt_lines == n_final
    print(f"\n已保存:\n  - {OUT_CLEANED}\n  - {OUT_WITH_TOKENS}\n  - {OUT_TOKENIZED_TXT}")
    print(
        f"\n验收: cleaned_with_tokens.csv 行数={verify}, 报告最终={n_final}, "
        f"tokenized_comments.txt 行数={txt_lines}, 有效分词行={nonempty_tokens} "
        f"→ {'通过' if ok else '不一致，请检查'}"
    )


if __name__ == "__main__":
    main()

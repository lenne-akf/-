from __future__ import annotations
# -*- coding: utf-8 -*-
"""导出 v5 escalator 全池 user_id 列表。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import OUT, COMMENTS_TOPICS, SENTIMENT, TOPIC_NAMING, V5_USER_IDS, bootstrap_sys_path

bootstrap_sys_path()
from build_topic_escalator import build_topic_escalator  # noqa: E402
from build_web_json import parse_date_yyyy_mm_dd  # noqa: E402


def export_v5_user_ids(out_path: Path = V5_USER_IDS) -> int:
    sentiment = pd.read_csv(SENTIMENT, encoding="utf-8-sig")
    topics = pd.read_csv(COMMENTS_TOPICS, encoding="utf-8-sig")
    naming = pd.read_csv(TOPIC_NAMING, encoding="utf-8-sig")
    merged = sentiment.merge(topics[["comment_id", "topic_id"]], on="comment_id", how="left")

    esc = build_topic_escalator(
        merged,
        naming,
        parse_date_yyyy_mm_dd,
        source_topic_id=0,
        target_topic_id=4,
        min_comments=1,
        min_target_share=0.02,
        min_drift_gain=0.02,
        top_users=99999,
    )
    uids = sorted({str(u["user_id"]) for u in esc.get("top_users", []) if u.get("user_id")})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(uids) + ("\n" if uids else ""), encoding="utf-8")
    meta = OUT / "v5_pool_meta.json"
    meta.write_text(
        json.dumps({"count": len(uids), "source": "build_topic_escalator v5 full pool"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(uids)


def main() -> None:
    n = export_v5_user_ids()
    print(f"已导出 v5 池 {n} 人 -> {V5_USER_IDS}")


if __name__ == "__main__":
    main()

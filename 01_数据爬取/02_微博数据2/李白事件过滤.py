import sys
from pathlib import Path as _Path
_R = _Path(__file__).resolve().parent.parent
if str(_R) not in sys.path:
    sys.path.insert(0, str(_R))
import 项目路径 as P

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""筛选李白版权事件相关帖子（含吴向飞支线）。"""

import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = P.微博帖子
SOURCE_CSV = P.微博帖子全部
SUPERTOPIC_CSV = P.微博超话


def is_super_topic_post(text: str, topics: str = "", source_type: str = "") -> bool:
    """判断是否为超话内发布的帖子。"""
    blob = text + " " + topics + " " + source_type
    if source_type.startswith("超话:"):
        return True
    return bool(re.search(r"#[^#\n]+?\[超话\]#", blob))


def is_libai_copyright_event(text: str, topics: str = "", author: str = "") -> bool:
    """判断帖子是否属于单依纯 × 李荣浩 × 《李白》版权争议事件（含吴向飞支线）。"""
    blob = text + " " + topics

    if author == "李荣浩":
        if "吴向飞" in blob:
            return True
        if any(k in blob for k in ["李白", "单依纯", "强行侵权", "翻唱《李白》", "翻唱李白"]):
            return True
        if "侵权" in blob and "没有授权" in blob:
            return True
        if "单依纯" in blob:
            return True
        return False

    if author == "单依纯":
        return any(k in blob for k in ["李白", "李荣浩", "侵权", "版权", "授权", "道歉", "著作权", "李老师"])

    if author == "单依纯官方工作室":
        return any(k in blob for k in ["李白", "侵权", "版权", "授权", "李荣浩", "道歉", "致歉", "著作权", "版权工作"])

    if author == "百沐娱乐":
        return any(k in blob for k in ["李白", "侵权", "版权", "授权", "李荣浩", "道歉", "致歉", "著作权"])

    # 吴向飞支线
    if "吴向飞" in blob and any(k in blob for k in ["李荣浩", "路一直都在", "版权", "授权", "单依纯", "李白", "侵权"]):
        return True

    if "路一直都在" in blob and any(k in blob for k in ["李荣浩", "吴向飞", "版权", "授权", "单依纯"]):
        return True

    # 粉丝 / 媒体
    if "李白" in blob:
        if any(k in blob for k in ["单依纯", "单伊纯", "李荣浩", "侵权", "版权", "授权", "翻唱", "强行", "道歉"]):
            return True

    if ("单依纯" in blob or "单伊纯" in blob) and "李荣浩" in blob:
        if any(k in blob for k in ["李白", "侵权", "版权", "授权", "道歉", "强行", "翻唱", "深圳", "著作权", "喊话", "吴向飞"]):
            return True

    if any(k in blob for k in ["强行侵权", "翻唱李白", "未经授权"]):
        return True

    if any(k in blob for k in ["音著协", "著作权协"]) and any(k in blob for k in ["单依纯", "李荣浩", "李白"]):
        return True

    return False


def row_passes(row: dict) -> bool:
    return is_libai_copyright_event(row["帖子内容"], row["话题标签"], row["作者"])


def export_main(source: Path, output: Path):
    with open(source, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    kept = [r for r in rows if row_passes(r)]
    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(kept)
    return len(rows), len(kept)


def export_supertopic(rows: list[dict], output: Path):
    kept = [
        r for r in rows
        if row_passes(r) and is_super_topic_post(r["帖子内容"], r["话题标签"], r["来源类型"])
    ]
    if not kept:
        return 0
    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=kept[0].keys())
        writer.writeheader()
        writer.writerows(kept)
    return len(kept)


def main():
    source = SOURCE_CSV if SOURCE_CSV.exists() else INPUT_CSV
    if not source.exists():
        print(f"未找到 {source}")
        return

    with open(source, encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))

    total, main_count = export_main(source, INPUT_CSV)
    st_count = export_supertopic(all_rows, SUPERTOPIC_CSV)

    print(f"主 CSV: {total} -> {main_count} 条（含吴向飞支线）-> {INPUT_CSV}")
    print(f"超话 CSV: {st_count} 条 -> {SUPERTOPIC_CSV}")


if __name__ == "__main__":
    main()

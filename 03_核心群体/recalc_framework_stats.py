# -*- coding: utf-8 -*-
"""修正立场编码后，重算指责取向 / 护主取向统计。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

DIR = Path(__file__).resolve().parent
CSV = DIR / "comments_单李粉.csv"
OUT = DIR / "framework_stats_corrected.json"

PERSON = re.compile(
    r"网暴|辱骂|造谣|人品|道德|凌霸|小作文|攻击|双标|引导舆论|抹黑|撒谎|抄袭|人身攻击"
)


def layer(text: str) -> str:
    t = str(text)
    if re.search(r"版权|侵权|授权|维权|强行侵权|音著协|音协", t):
        return "版权议题"
    if re.search(r"难听|唱功|唱得|毁歌|改编|审美|音色|咖位", t):
        return "职业评价"
    if PERSON.search(t):
        return "人身指责"
    return "其他"


def stance_corrected(text: str) -> str:
    """修正误判：「强行退票」≠侵权；「支持维权」 alone 不算护李。"""
    t = str(text)

    if re.search(r"李荣浩.*(双标|抄袭|撒谎|引导|网暴|小作文|资本|凌霸)|#李荣浩抄袭#", t):
        return "护单/贬李"
    if re.search(r"支持单依纯|知错就改|护单|小单.*(担当|负责|道歉)", t):
        return "护单/贬李"

    if re.search(r"支持李荣浩|李荣浩全肯定|@李荣浩", t):
        return "护李/贬单"
    if re.search(r"单依纯侵权在先|强行侵权就是不尊重", t):
        return "护李/贬单"
    if re.search(r"支持维权|支持这个李荣浩", t) and "李荣浩" in t:
        return "护李/贬单"
    # 「支持维权」无明确对象 → 中性
    if t.strip() in ("支持维权", "支持维权！", "支持维权！！"):
        return "中性/其他"

    if "单依纯" in t and "李荣浩" not in t:
        return "聚焦单"
    if "李荣浩" in t and "单依纯" not in t:
        return "聚焦李"
    return "中性/其他"


def main():
    df = pd.read_csv(CSV)
    df["content_layer_v2"] = df["content"].map(layer)
    df["stance_v2"] = df["content"].map(stance_corrected)

    stats = {}
    for gkey, label in [("单粉", "单依纯粉"), ("李粉", "李荣浩粉")]:
        sub = df[df["core_group"] == gkey]
        n = len(sub)
        accuse = (sub["content_layer_v2"] == "人身指责").sum()
        protect_key = "护单/贬李" if gkey == "单粉" else "护李/贬单"
        protect = (sub["stance_v2"] == protect_key).sum()
        false_pro_li = (sub["stance_v2"] == "护李/贬单").sum() if gkey == "单粉" else 0
        stats[gkey] = {
            "n": int(n),
            "指责取向_n": int(accuse),
            "指责取向_pct": round(accuse / n * 100, 1),
            "护主取向_n": int(protect),
            "护主取向_pct": round(protect / n * 100, 1),
            "单粉误判护李_n": int(false_pro_li) if gkey == "单粉" else 0,
        }

    result = {
        "note": "护主取向：单粉仅计护单/贬李，李粉仅计护李/贬单；已剔除单粉2条误判",
        "rows": [
            {
                "label": "指责取向",
                "单粉": stats["单粉"]["指责取向_pct"],
                "李粉": stats["李粉"]["指责取向_pct"],
            },
            {
                "label": "护主取向",
                "单粉": stats["单粉"]["护主取向_pct"],
                "李粉": stats["李粉"]["护主取向_pct"],
            },
        ],
        "detail": stats,
    }

    df.to_csv(DIR / "comments_单李粉_corrected.csv", index=False, encoding="utf-8-sig")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

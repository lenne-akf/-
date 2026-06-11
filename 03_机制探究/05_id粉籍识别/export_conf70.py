"""从爬取结果按 conf70 导出粉籍整合表。"""

import argparse
from pathlib import Path

import pandas as pd

from filter_conf80 import ARTIST_INFO, NOT_ARTIST

TH = 0.7
MIN_SCORE = 2.0
SKIP = {"跳过-非微博ID", "抓取失败", "无法判断"}


def export(input_file: Path, output_file: Path, origin: str | None = None) -> None:
    df = pd.read_excel(input_file)
    if origin and "origin" in df.columns:
        df = df[df["origin"] == origin].copy()

    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0)
    df["fan_score"] = pd.to_numeric(df["fan_score"], errors="coerce").fillna(0)

    def relabel(row):
        if row["fandom_label"] in SKIP:
            return row["fandom_label"]
        if row["confidence"] >= TH and row["fan_score"] >= MIN_SCORE:
            return row["predicted_fandom"]
        if row["fan_score"] >= MIN_SCORE:
            return f"不在conf{int(TH * 100)}池"
        return "无法判断"

    df["粉籍"] = df.apply(relabel, axis=1)
    pool = df[~df["粉籍"].isin(SKIP | {f"不在conf{int(TH * 100)}池"})].copy()
    pool["艺人说明"] = pool["粉籍"].map(lambda x: ARTIST_INFO.get(x, ""))
    pool["是否确认艺人"] = pool["粉籍"].apply(
        lambda x: "是" if x in ARTIST_INFO else ("否-误识别" if x in NOT_ARTIST else "待核实")
    )

    simple = pool[
        ["user_id", "粉籍", "confidence", "screen_name", "艺人说明", "是否确认艺人"]
        + (["origin"] if "origin" in pool.columns else [])
    ].rename(columns={"confidence": "置信度"})

    with pd.ExcelWriter(output_file, engine="openpyxl") as w:
        simple.sort_values(["粉籍", "user_id"]).to_excel(w, sheet_name="id对应粉籍", index=False)
        simple[simple["是否确认艺人"] == "是"].to_excel(w, sheet_name="确认艺人", index=False)
        simple[simple["是否确认艺人"] == "待核实"].to_excel(w, sheet_name="待核实", index=False)
        pool.groupby("粉籍").size().reset_index(name="人数").sort_values("人数", ascending=False).to_excel(
            w, sheet_name="粉籍汇总", index=False
        )

    print(f"{output_file.name}: 达标 {len(pool)}, 确认艺人 {(pool['是否确认艺人']=='是').sum()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--origin", default=None)
    args = ap.parse_args()
    export(Path(args.input), Path(args.output), args.origin)

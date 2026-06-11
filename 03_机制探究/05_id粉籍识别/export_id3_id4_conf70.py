"""爬取完成后：按 conf70 导出 id3 / id4 分文件整合表。"""

from pathlib import Path

import pandas as pd

from export_conf70 import TH, MIN_SCORE, SKIP, export
from filter_conf80 import ARTIST_INFO, NOT_ARTIST

BASE = Path(__file__).resolve().parent
RAW = BASE / "weibo_fandom_result_id3_id4.xlsx"
ORIGIN = BASE / "id3_id4_deduped.xlsx"


def main() -> None:
    if not RAW.exists():
        raise SystemExit(f"请先完成爬取: {RAW}")

    df = pd.read_excel(RAW)
    origin = pd.read_excel(ORIGIN)[["user_id", "origin"]]
    origin["user_id"] = origin["user_id"].astype(str)
    df["user_id"] = df["user_id"].astype(str)
    df = df.merge(origin, on="user_id", how="left")

    df.to_excel(BASE / "weibo_fandom_result_id3_id4.xlsx", index=False)

    export(RAW, BASE / "id_粉籍整合_conf70_id3_id4.xlsx")
    for tag, out in [
        ("id3.xlsx", "id_粉籍整合_conf70_id3.xlsx"),
        ("id4.csv", "id_粉籍整合_conf70_id4.xlsx"),
    ]:
        export(RAW, BASE / out, origin=tag)

    # 汇总
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0)
    df["fan_score"] = pd.to_numeric(df["fan_score"], errors="coerce").fillna(0)
    ok = df[
        (df["confidence"] >= TH)
        & (df["fan_score"] >= MIN_SCORE)
        & (~df["fandom_label"].isin(SKIP))
    ]
    print("\n=== 汇总 ===")
    print("总记录", len(df))
    print("conf70达标", len(ok))
    for tag in ["id3.xlsx", "id4.csv"]:
        sub = ok[ok["origin"] == tag]
        confirmed = sub["predicted_fandom"].isin(ARTIST_INFO).sum()
        print(f"  {tag}: 达标 {len(sub)}, 确认艺人 {confirmed}")


if __name__ == "__main__":
    main()

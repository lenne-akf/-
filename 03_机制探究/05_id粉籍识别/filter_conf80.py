"""从爬取结果中筛选「明确艺人粉籍」，并附艺人说明。"""

import argparse
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent

# 真实艺人/团体及简要说明
ARTIST_INFO = {
    "单依纯": "内地歌手（《永不失联的爱》）",
    "陈楚生": "内地歌手（0713快男冠军）",
    "李荣浩": "内地歌手、音乐人",
    "aespa": "韩国女子偶像组合",
    "林俊杰": "新加坡华语歌手",
    "周深": "内地歌手",
    "摩登兄弟": "刘宇宁及其粉丝团常用称呼",
    "周杰伦": "华语流行歌手",
    "赵英俊": "内地音乐人（已故）",
    "王一博": "演员、歌手、舞者",
    "方大同": "华语 R&B 歌手（已故）",
    "丁禹兮": "内地演员",
    "邓超": "内地演员",
    "成毅": "内地演员（《莲花楼》等）",
    "张靓颖": "内地歌手",
    "侯明昊": "内地演员",
    "苏醒AllenSu": "内地歌手（0713快男）",
    "苏醒": "内地歌手（0713快男）",
    "袁一琦": "SNH48 成员、歌手",
    "罗云熙": "内地演员",
    "贺峻霖": "时代少年团成员",
    "时代少年团": "内地男子偶像组合",
    "杨旭文": "内地演员",
    "蔡依林": "台湾流行歌手",
    "吴尊": "演员、歌手（飞轮海）",
    "张杰": "内地歌手",
    "周兴哲": "马来西亚华语歌手",
    "易烊千玺": "演员、歌手（TFBOYS）",
    "TaylorSwift": "美国流行歌手（泰勒·斯威夫特）",
    "张颂文": "内地演员",
    "李宇春": "内地歌手",
    "黄霄云": "内地歌手",
    "赵丽颖": "内地演员",
    "张凌赫": "内地演员",
    "杨超越": "演员、前火箭少女101成员",
    "en王翊恩": "网络红人/博主",
    "邹若男": "短剧/网络红人",
    "李煜东": "待核实（小众艺人或角色名）",
    "陈飞宇": "内地演员",
    "田栩宁": "内地演员",
    "孙燕姿": "新加坡华语歌手",
    "鹿晗": "演员、歌手",
    "汪苏泷": "内地歌手",
    "毛不易": "内地歌手",
    "汪峰": "内地歌手",
    "angelababy": "杨颖，演员",
    "Angelababy": "杨颖，演员",
    "谢可寅": "歌手、THE9成员",
    "OrmKornnaphat": "泰国演员（Orm）",
    "展轩": "内地演员",
    "汪顺": "游泳运动员（体育明星）",
    "耀耀": "待核实（昵称/角色名）",
}

# 明显非艺人：平台、活动、游戏、话题、CP杂项等
NOT_ARTIST = {
    "DeepSeek", "豆瓣App", "签到领红包", "超级红人节", "国庆阅兵", "生活手记",
    "电子日记薄", "阴阳师手游", "高考加油", "微信式恋爱", "热点", "茶颜悦色",
    "社保", "网球", "巴萨", "柔美的细胞君3", "人世间大结局", "歌手2025",
    "单依纯含金量", "王橹杰付彬言", "海口惊现神兽", "育才仙宗", "浩多物料",
    "投行泰山", "红颜中老", "希朝相伴", "哈哈昂", "李晋晔张典娜", "灵魂摆渡",
    "恋与制作人", "微信式恋爱", "超级红人节", "抑郁症",
    "新龙人力", "APEX英雄", "王者荣耀", "blg", "BLG", "TOP_ESPORTS",
    "北京大学", "浙江大学", "微博之夜", "炉石传说", "药王谷", "趣味运动会",
    "可爱鼠鼠原", "宇宙探索", "univu5", "kudoo", "pitd定义", "全红婵",
    "梅奔", "夜神月", "长篇", "真实生活", "热爱可抵漫长",
}


def main(input_file: Path, output_file: Path) -> None:
    df = pd.read_excel(input_file)
    exclude = {"不在conf80池", "无法判断", "跳过-非微博ID", "抓取失败"}
    conf = df[~df["fandom_label"].isin(exclude)].copy()

    conf["是否艺人"] = conf["fandom_label"].apply(
        lambda x: "是" if x in ARTIST_INFO else ("否-误识别" if x in NOT_ARTIST else "待核实")
    )
    conf["艺人说明"] = conf["fandom_label"].map(
        lambda x: ARTIST_INFO.get(x, "未能自动识别，请结合 evidence 人工确认")
    )

    artists = conf[conf["是否艺人"] == "是"].copy()
    pending = conf[conf["是否艺人"] == "待核实"].copy()
    false_pos = conf[conf["是否艺人"] == "否-误识别"].copy()

    cols = [
        "user_id", "screen_name", "description", "fandom_label", "艺人说明",
        "confidence", "fan_score", "evidence", "posts_sample",
        "followers_count", "statuses_count",
    ]
    cols = [c for c in cols if c in artists.columns]

    artists = artists.sort_values(["fandom_label", "confidence"], ascending=[True, False])
    artists_out = artists[cols]
    pending_out = pending[cols + ["是否艺人"]] if len(pending) else pending
    false_out = false_pos[["user_id", "screen_name", "fandom_label", "evidence"]]

    summary = (
        artists.groupby("fandom_label", as_index=False)
        .agg(粉丝数=("user_id", "count"), 说明=("艺人说明", "first"))
        .sort_values("粉丝数", ascending=False)
    )

    with pd.ExcelWriter(output_file, engine="openpyxl") as w:
        artists_out.to_excel(w, sheet_name="明确艺人粉籍", index=False)
        summary.to_excel(w, sheet_name="艺人汇总", index=False)
        if len(pending_out):
            pending_out.to_excel(w, sheet_name="待核实", index=False)
        false_out.to_excel(w, sheet_name="已剔除误识别", index=False)

    print(f"conf80 原始: {len(conf)}")
    print(f"明确艺人粉籍: {len(artists_out)}")
    print(f"待核实: {len(pending_out)}")
    print(f"误识别剔除: {len(false_out)}")
    print(f"输出: {output_file}")
    print("\n艺人汇总:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="weibo_fandom_result.xlsx")
    ap.add_argument("--output", default=None)
    args = ap.parse_args()
    stem = Path(args.input).stem.replace("weibo_fandom_result_", "").replace("weibo_fandom_result", "id")
    out = BASE / (args.output or f"conf80_艺人粉籍明细_{stem}.xlsx")
    main(BASE / args.input, out)

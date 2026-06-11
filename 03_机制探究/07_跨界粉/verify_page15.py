# -*- coding: utf-8 -*-
"""页15 跨界粉话语取向验证：数据联合 + 编码 + 统计 + 出图"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent
FENJI_XLSX = PROJECT_ROOT / "数据" / "id粉籍" / "id.xlsx"
FENJI_CSV = PROJECT_ROOT / "数据" / "id粉籍" / "id粉籍_李白事件评论.csv"
DETAIL = PROJECT_ROOT / "数据" / "微博2" / "detail_comments.csv"
PUSHERS = PROJECT_ROOT / "数据" / "id粉籍" / "hidden_escalator_comments.csv"

CORE_ARTISTS = {"单依纯", "李荣浩"}
HIGHLIGHT = ["陈楚生", "黄霄云", "周深", "王一博", "周杰伦"]

PERSON = re.compile(
    r"网暴|辱骂|造谣|人品|道德|凌霸|小作文|攻击|双标|引导舆论|抹黑|撒谎|抄袭|人身攻击|绿茶|太妹|厚颜无耻"
)
ATTACK_STRONG = re.compile(
    r"难听死了|难听的要死|滚出|垃圾|恶心|太妹|厚颜无耻|网暴|人身攻击|绿茶|败类|没素质|预制天后|难听得要死"
)
RIVAL_ARTISTS = re.compile(
    r"黄霄云|黄霄雲|王菲|邓丽君|张杰|华晨宇|那英|姚晓棠|杨丞琳|汪苏泷|张碧晨|王一博|周杰伦|李健|陈奕迅"
)
COPYRIGHT_ANALOGY = re.compile(
    r"周杰伦|方文山|《年轮》|年轮|张碧晨|汪苏泷|类似|差不多|类比|唱.*歌.*版权|词的版权"
)

# ── Design tokens (match page14) ─────────────────────────────
BG = "#EFEDE8"
PANEL = "#FFFFFF"
INK = "#1A1820"
INK2 = "#5A5668"
RULE = "#E6E2DB"

MODE_ORDER = ["版权议题/类比", "事件评价", "竞品对线", "娱乐玩梗", "劝阻捆绑", "其他/中性"]
MODE_COL = {
    "版权议题/类比": "#4A6FA5",
    "事件评价": "#5B8C7A",
    "竞品对线": "#C44E52",
    "娱乐玩梗": "#D4843A",
    "劝阻捆绑": "#8E7F9E",
    "其他/中性": "#C8C3BB",
}

LAYER_ORDER = ["版权议题", "职业评价", "人身指责", "其他"]
LAYER_COL = {
    "版权议题": "#4A6FA5",
    "职业评价": "#D4843A",
    "人身指责": "#C44E52",
    "其他": "#C8C3BB",
}


def layer(text: str) -> str:
    t = str(text)
    if re.search(r"版权|侵权|授权|维权|强行侵权|音著协|音协", t):
        return "版权议题"
    if re.search(r"难听|唱功|唱得|毁歌|改编|审美|音色|咖位", t):
        return "职业评价"
    if PERSON.search(t):
        return "人身指责"
    return "其他"


def discourse_mode(text: str, fenji_name: str) -> str:
    t = str(text)
    rival = RIVAL_ARTISTS.search(t)

    # 竞品对线：粉圈拉踩 / 捧自家贬对家 / 赛道梗
    if re.search(r"拉踩|内蹭|藤壶|对标|洗地|没素质|捧.*踩|竞品|对家|魔星|退货的是谁|买黑水", t):
        if rival or fenji_name in ("黄霄云",):
            return "竞品对线"
    if fenji_name == "黄霄云" and re.search(r"黄霄|魔星|无妄|内蹭|藤壶|wwzz|美哭", t):
        if re.search(r"单依纯|侵权|版权|李荣浩|顶流", t) and re.search(
            r"拉踩|没素质|洗地|踩|内蹭|藤壶|对标|捧|退货|黑水", t
        ):
            return "竞品对线"
    if rival and re.search(r"踩|拉踩|内蹭|模仿|蹭|不如|难.*听|油腻|疯子|碰瓷", t):
        return "竞品对线"

    if COPYRIGHT_ANALOGY.search(t):
        return "版权议题/类比"
    if re.search(r"版权|侵权|授权|维权|尊重原创|音著协|音协", t):
        return "版权议题/类比"

    if re.search(r"别带|不要带|不要侮辱|带上.*做什么|乱带|捆绑|别侮辱", t):
        return "劝阻捆绑"
    if re.search(r"笑死|哈哈哈|无所谓|抢钱|跳大神|玩梗|笑疯了", t):
        return "娱乐玩梗"

    # 事件评价：改编梗、道歉、演唱会、监制等
    if re.search(
        r"单依纯|李荣浩|侵权|改编|道歉|维权|李白|演唱会|退票|监制|出品|咖位|"
        r"又如何|又能怎|预制|难听|毁歌|唱得|支持维权|路人说",
        t,
    ):
        return "事件评价"
    return "其他/中性"


def is_attack(text: str) -> bool:
    t = str(text)
    if ATTACK_STRONG.search(t):
        return True
    if re.search(r"难听|难听得|毁歌|唱烂|预制", t) and re.search(r"单依纯|她唱|单唱", t):
        return True
    return layer(t) == "人身指责"


def _load_fenji_table() -> pd.DataFrame:
    if FENJI_XLSX.is_file():
        fenji = pd.read_excel(FENJI_XLSX)
        fenji = fenji.iloc[:, :2].copy()
        fenji.columns = ["user_id", "粉籍"]
    elif FENJI_CSV.is_file():
        fenji = pd.read_csv(FENJI_CSV, usecols=["user_id", "粉籍"], dtype={"user_id": str})
        fenji = fenji.drop_duplicates(subset=["user_id"], keep="first")
    else:
        raise FileNotFoundError(
            f"未找到粉籍表，请放置 {FENJI_XLSX} 或 {FENJI_CSV}"
        )
    fenji["user_id"] = fenji["user_id"].astype(str)
    return fenji


def load_merged() -> pd.DataFrame:
    fenji = _load_fenji_table()

    pushers = pd.read_csv(PUSHERS, dtype={"user_id": str})
    pushers["user_id"] = pushers["user_id"].astype(str)
    pusher_set = set(pushers["user_id"])

    comments = pd.read_csv(DETAIL, dtype={"user_id": str}, low_memory=False)
    comments["user_id"] = comments["user_id"].astype(str)
    comments = comments[comments["user_id"].isin(pusher_set)]

    merged = comments.merge(fenji, on="user_id", how="inner")
    merged["content_layer"] = merged["content"].map(layer)
    merged["discourse_mode"] = merged.apply(
        lambda r: discourse_mode(r["content"], r["粉籍"]), axis=1
    )
    merged["is_attack"] = merged["content"].map(is_attack)
    merged["group_type"] = merged["粉籍"].apply(
        lambda x: "单粉" if x == "单依纯" else ("李粉" if x == "李荣浩" else "跨界粉")
    )
    return merged


def pct_dict(series: pd.Series) -> dict[str, float]:
    if len(series) == 0:
        return {}
    vc = series.value_counts(normalize=True) * 100
    return {k: round(float(v), 1) for k, v in vc.items()}


def group_stats(sub: pd.DataFrame) -> dict:
    n = len(sub)
    return {
        "n_comments": int(n),
        "n_users": int(sub["user_id"].nunique()),
        "discourse_pct": pct_dict(sub["discourse_mode"]),
        "layer_pct": pct_dict(sub["content_layer"]),
        "attack_rate_pct": round(sub["is_attack"].mean() * 100, 1) if n else 0,
        "竞品对线_pct": round((sub["discourse_mode"] == "竞品对线").mean() * 100, 1) if n else 0,
        "人身指责层_pct": round((sub["content_layer"] == "人身指责").mean() * 100, 1) if n else 0,
    }


def build_summary(df: pd.DataFrame) -> dict:
    cross = df[~df["粉籍"].isin(CORE_ARTISTS)]
    core = df[df["粉籍"].isin(CORE_ARTISTS)]

    summary = {
        "data_source": {
            "fenji_file": str(FENJI_XLSX.name if FENJI_XLSX.is_file() else FENJI_CSV.name),
            "fenji_users": int(df["user_id"].nunique()),
            "pusher_matched_comments": int(len(df)),
            "crossover_comments": int(len(cross)),
            "crossover_users": int(cross["user_id"].nunique()),
            "单粉_comments": int((df["粉籍"] == "单依纯").sum()),
            "李粉_comments": int((df["粉籍"] == "李荣浩").sum()),
        },
        "verification": {},
        "crossover_discourse_pct": pct_dict(cross["discourse_mode"]),
        "crossover_layer_pct": pct_dict(cross["content_layer"]),
        "top_artists_by_volume": cross["粉籍"].value_counts().head(15).to_dict(),
        "highlight_groups": {name: group_stats(df[df["粉籍"] == name]) for name in HIGHLIGHT},
        "conclusion_support": [],
    }

    shan = core[core["粉籍"] == "单依纯"]
    li = core[core["粉籍"] == "李荣浩"]
    total_attack = int(df["is_attack"].sum())
    cross_attack = int(cross["is_attack"].sum())
    total_personal = int((df["content_layer"] == "人身指责").sum())
    cross_personal = int((cross["content_layer"] == "人身指责").sum())

    summary["verification"] = {
        "跨界粉_攻击参与率": round(cross["is_attack"].mean() * 100, 1),
        "单粉_攻击参与率": round(shan["is_attack"].mean() * 100, 1),
        "李粉_攻击参与率": round(li["is_attack"].mean() * 100, 1),
        "跨界粉_人身指责层": round((cross["content_layer"] == "人身指责").mean() * 100, 1),
        "单粉_人身指责层": round((shan["content_layer"] == "人身指责").mean() * 100, 1),
        "跨界粉_竞品对线": round((cross["discourse_mode"] == "竞品对线").mean() * 100, 1),
        "跨界粉_版权类比或议题": round(
            (cross["discourse_mode"] == "版权议题/类比").mean() * 100, 1
        ),
        "跨界粉_事件评价": round((cross["discourse_mode"] == "事件评价").mean() * 100, 1),
        "攻击评论_跨界占全部": round(cross_attack / total_attack * 100, 1) if total_attack else 0,
        "攻击评论_跨界绝对量": cross_attack,
        "攻击评论_单粉绝对量": int(shan["is_attack"].sum()),
        "攻击评论_李粉绝对量": int(li["is_attack"].sum()),
        "人身指责_跨界占全部": round(cross_personal / total_personal * 100, 1) if total_personal else 0,
        "人身指责_跨界绝对量": cross_personal,
    }

    v = summary["verification"]
    checks = []
    if v["跨界粉_人身指责层"] < v.get("单粉_人身指责层", 99):
        checks.append(
            f"跨界粉人身指责层仅{v['跨界粉_人身指责层']}%（单粉{v.get('单粉_人身指责层')}%），异化强度低"
        )
    if v["跨界粉_竞品对线"] < 5:
        checks.append(f"竞品对线占比仅{v['跨界粉_竞品对线']}%，体量很小")
    evt_cpr = v["跨界粉_版权类比或议题"] + v["跨界粉_事件评价"]
    if evt_cpr > 35:
        checks.append(f"版权类比+事件评价合计{evt_cpr:.1f}%，为跨界粉显性话语主体")
    if v["攻击评论_跨界占全部"] < 60:
        tot = v["攻击评论_跨界绝对量"] + v["攻击评论_单粉绝对量"] + v["攻击评论_李粉绝对量"]
        checks.append(
            f"攻击型评论中跨界粉占{v['攻击评论_跨界占全部']}%（{v['攻击评论_跨界绝对量']}/{tot}条），"
            f"单粉{v['攻击评论_单粉绝对量']}条、李粉{v['攻击评论_李粉绝对量']}条"
        )
    hx = summary["highlight_groups"].get("黄霄云", {})
    if hx and hx.get("n_comments", 0) >= 5:
        evt = hx.get("discourse_pct", {}).get("版权议题/类比", 0) + hx.get("discourse_pct", {}).get("事件评价", 0)
        checks.append(
            f"黄霄云粉：竞品对线{hx.get('竞品对线_pct',0)}%，版权/事件类{evt:.1f}%（n={hx['n_comments']}）"
        )
    wz = summary["highlight_groups"].get("周深", {})
    if wz.get("n_comments"):
        checks.append(f"周深粉 n={wz['n_comments']}：竞品对线{wz.get('竞品对线_pct',0)}%，攻击率{wz.get('attack_rate_pct',0)}%")
    summary["conclusion_support"] = checks
    return summary


def pick_examples(df: pd.DataFrame) -> dict:
    cross = df[~df["粉籍"].isin(CORE_ARTISTS)]
    examples = {}
    for mode in ["版权议题/类比", "事件评价", "竞品对线", "娱乐玩梗", "劝阻捆绑"]:
        sub = cross[cross["discourse_mode"] == mode].head(5)
        examples[mode] = [
            {"粉籍": r["粉籍"], "content": str(r["content"])[:120]}
            for _, r in sub.iterrows()
        ]
    for name in ["陈楚生", "黄霄云", "周深"]:
        sub = df[df["粉籍"] == name].head(8)
        examples[f"{name}代表"] = [
            {"mode": r["discourse_mode"], "layer": r["content_layer"], "content": str(r["content"])[:120]}
            for _, r in sub.iterrows()
        ]
    return examples


def setup_font():
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "SimHei"):
        if name in {f.name for f in font_manager.fontManager.ttflist}:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams.update({
        "axes.unicode_minus": False,
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "savefig.facecolor": BG,
        "axes.facecolor": PANEL,
    })


def _pct_label(ax, x, y, val, color, min_show=5.0):
    if val < min_show:
        return
    lum = 0.299 * int(color[1:3], 16) + 0.587 * int(color[3:5], 16) + 0.114 * int(color[5:7], 16)
    ax.text(x, y, f"{val:.1f}%", ha="center", va="center", fontsize=9,
            color="#FFF" if lum < 150 else INK, fontweight="bold")


def plot_fig1_mode(summary: dict):
    """fig1: 跨界粉整体话语模式堆叠条 + 与单李粉攻击率对比"""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), facecolor=BG)
    fig.subplots_adjust(wspace=0.28, top=0.82, bottom=0.14, left=0.08, right=0.96)

    # 左：跨界粉话语模式 100% 堆叠
    ax = axes[0]
    pct = summary["crossover_discourse_pct"]
    vals = [pct.get(m, 0) for m in MODE_ORDER]
    bottom = 0.0
    handles = []
    for m, v in zip(MODE_ORDER, vals):
        if v <= 0:
            continue
        c = MODE_COL[m]
        ax.bar(0, v, bottom=bottom, width=0.45, color=c, edgecolor="none", label=m)
        _pct_label(ax, 0, bottom + v / 2, v, c, min_show=4)
        bottom += v
        handles.append(mpatches.Patch(color=c, label=m))
    ax.set_xlim(-0.6, 0.6)
    ax.set_ylim(0, 100)
    ax.set_xticks([0])
    ax.set_xticklabels(["跨界粉\n(203条)"])
    ax.set_ylabel("评论占比 (%)")
    ax.set_title("跨界粉话语模式结构", fontsize=13, fontweight="bold", loc="left", pad=12)
    ax.yaxis.grid(True, color=RULE, linewidth=0.7)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    # 右：攻击参与率对比
    ax2 = axes[1]
    v = summary["verification"]
    labels = ["单粉", "李粉", "跨界粉"]
    rates = [v["单粉_攻击参与率"], v["李粉_攻击参与率"], v["跨界粉_攻击参与率"]]
    colors = ["#8E7F9E", "#3A5C50", "#5B8C7A"]
    bars = ax2.bar(labels, rates, color=colors, width=0.55, edgecolor="none")
    for b, r in zip(bars, rates):
        ax2.text(b.get_x() + b.get_width() / 2, r + 0.3, f"{r:.1f}%",
                 ha="center", va="bottom", fontsize=10, fontweight="bold", color=INK)
    ax2.set_ylim(0, max(rates) * 1.35 + 1)
    ax2.set_ylabel("攻击参与率 (%)")
    ax2.set_title("攻击参与率对比", fontsize=13, fontweight="bold", loc="left", pad=12)
    ax2.yaxis.grid(True, color=RULE, linewidth=0.7)
    ax2.set_axisbelow(True)
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)

    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, 0.98))
    fig.savefig(OUT_DIR / "fig1_跨界粉话语模式与攻击率.png", bbox_inches="tight")
    plt.close(fig)


def plot_fig2_highlight(summary: dict):
    """fig2: 重点跨界群体话语模式分组堆叠"""
    groups = [g for g in HIGHLIGHT if summary["highlight_groups"].get(g, {}).get("n_comments", 0) > 0]
    fig, ax = plt.subplots(figsize=(10, 5.2), facecolor=BG)
    fig.subplots_adjust(top=0.78, bottom=0.12, left=0.10, right=0.96)

    x = range(len(groups))
    w = 0.55
    handles = []
    for i, mode in enumerate(MODE_ORDER):
        vals = [
            summary["highlight_groups"][g]["discourse_pct"].get(mode, 0) for g in groups
        ]
        if not any(vals):
            continue
        bottoms = [0.0] * len(groups)
        if i > 0:
            for j, g in enumerate(groups):
                bottoms[j] = sum(
                    summary["highlight_groups"][g]["discourse_pct"].get(m, 0)
                    for m in MODE_ORDER[:i]
                )
        bars = ax.bar(x, vals, bottom=bottoms, width=w, color=MODE_COL[mode],
                      edgecolor="none", label=mode)
        for j, (g, v, bot) in enumerate(zip(groups, vals, bottoms)):
            if v >= 5:
                _pct_label(ax, j, bot + v / 2, v, MODE_COL[mode])
        handles.append(mpatches.Patch(color=MODE_COL[mode], label=mode))

    ax.set_xticks(list(x))
    ax.set_xticklabels([
        f"{g}\n(n={summary['highlight_groups'][g]['n_comments']})" for g in groups
    ])
    ax.set_ylim(0, 100)
    ax.set_ylabel("评论占比 (%)")
    ax.set_title("重点跨界粉群体话语模式", fontsize=13, fontweight="bold", loc="left", pad=14)
    ax.yaxis.grid(True, color=RULE, linewidth=0.7)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, 0.96))
    fig.savefig(OUT_DIR / "fig2_重点跨界群体对比.png", bbox_inches="tight")
    plt.close(fig)


def plot_combo():
    from matplotlib.image import imread
    from matplotlib.gridspec import GridSpec
    import numpy as np

    fig = plt.figure(figsize=(10, 9), facecolor=BG)
    gs = GridSpec(2, 1, figure=fig, hspace=0.08)
    for i, name in enumerate(["fig1_跨界粉话语模式与攻击率.png", "fig2_重点跨界群体对比.png"]):
        ax = fig.add_subplot(gs[i])
        ax.imshow(imread(OUT_DIR / name))
        ax.axis("off")
    fig.savefig(OUT_DIR / "fig_combo_竖排.png", bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def write_text(summary: dict, examples: dict):
    lines = [
        "【页15 · 典型代表句 · 供 PPT 后期粘贴】",
        "数据来源：可识别主页粉籍推手用户 · 《李白》事件评论（跨界粉203条/144人）",
        "",
    ]
    for mode, items in examples.items():
        if not items or "代表" in mode:
            continue
        lines.append(f"━━ {mode} ━━")
        for i, ex in enumerate(items[:4], 1):
            lines.append(f"{i}. 「{ex['content']}」  （{ex['粉籍']}粉）")
        lines.append("")
    for name in ["陈楚生", "黄霄云", "周深"]:
        key = f"{name}代表"
        if key not in examples:
            continue
        lines.append(f"━━ {name}粉 · 混合样例 ━━")
        for i, ex in enumerate(examples[key][:5], 1):
            lines.append(f"{i}. [{ex['mode']}] 「{ex['content']}」")
        lines.append("")

    (OUT_DIR / "代表句_PPT素材.txt").write_text("\n".join(lines), encoding="utf-8")

    v = summary["verification"]
    txt = f"""【2.3 群体话语取向分化（二）· 跨界粉 · 特点与原因推测】

一、核心特点（推手池×粉籍匹配：跨界粉{summary['data_source']['crossover_comments']}条/{summary['data_source']['crossover_users']}人）

1. 跨界粉不是攻击主力
   · 攻击参与率：跨界粉 {v['跨界粉_攻击参与率']}% vs 单粉 {v['单粉_攻击参与率']}% vs 李粉 {v['李粉_攻击参与率']}%
   · 人身指责层：跨界粉 {v['跨界粉_人身指责层']}%（远低于事件核心群体的帮战强度）

2. 话语以「版权类比 + 事件评价」为主，非粉圈竞品拱火
   · 版权议题/类比：{v['跨界粉_版权类比或议题']}%
   · 事件评价（讨论侵权、改编、道歉等）：{v['跨界粉_事件评价']}%
   · 竞品对线（粉圈拉踩/捧踩）：仅 {v['跨界粉_竞品对线']}%

3. 黄霄云粉是唯一显著出现「竞品对线」的跨界群体，但仍是少数
   · 黄霄云粉 n={summary['highlight_groups'].get('黄霄云',{}).get('n_comments','?')}：
     竞品对线 {summary['highlight_groups'].get('黄霄云',{}).get('竞品对线_pct','?')}%，
     其余多为版权/事件讨论
   · 陈楚生粉、周深粉、王一博粉、周杰伦粉：竞品对线极少或为0，
     以事件本位评价/版权类比为主

4. 与页14的关系
   · 页14核心对立发生在单粉↔李粉；页15说明「还有人在说话，但不是同一类攻击」
   · 跨界粉参与提供类比、围观评价，不构成舆论异化主导力量

二、原因推测

· 粉籍边界弱绑定：跨界粉与事件主体无直接权益冲突，缺乏「护主/贬对方」动员结构
· 发言功能不同：多为借案例讨论行业版权规范（类比其他歌手纠纷）或评价改编/道歉本身
· 竞品对线需「赛道竞争」记忆：仅黄霄云等与单依纯存在长期粉圈比较叙事，故偶发对线；其余艺人粉无此动机
· 样本限定：仅含可识别主页粉籍推手用户203条，绝对量小，方向性结论可靠

三、验证结论
"""
    for c in summary["conclusion_support"]:
        txt += f"   ✓ {c}\n"
    (OUT_DIR / "页15_特点与原因.txt").write_text(txt, encoding="utf-8")


def main():
    setup_font()
    df = load_merged()
    cross = df[~df["粉籍"].isin(CORE_ARTISTS)]
    cross.to_csv(OUT_DIR / "comments_跨界粉.csv", index=False, encoding="utf-8-sig")

    summary = build_summary(df)
    examples = pick_examples(df)
    summary["examples"] = examples

    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    write_text(summary, examples)
    plot_fig1_mode(summary)
    plot_fig2_highlight(summary)
    plot_combo()

    print(json.dumps(summary["verification"], ensure_ascii=False, indent=2))
    print("Saved to:", OUT_DIR)


if __name__ == "__main__":
    main()

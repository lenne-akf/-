from __future__ import annotations
# -*- coding: utf-8 -*-
"""
Step 4：BERTopic 主题建模

输入：output/cleaned_comments.csv（content 列）
输出：topic_distribution.csv、topic_model.pkl、topic_viz*.png、
      topic_representative_docs.txt、topic_naming.csv（人工命名模板）
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import os
import pickle
import random
import re
import tempfile
import textwrap
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from matplotlib import patheffects as pe
from matplotlib.colors import LinearSegmentedColormap

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
OUT_DIR = OUT

INPUT_CSV = OUT_DIR / "cleaned_comments.csv"
OUT_MODEL = OUT_DIR / "topic_model.pkl"
OUT_DIST = OUT_DIR / "topic_distribution.csv"
OUT_NAMING = OUT_DIR / "topic_naming.csv"
OUT_REP_DOCS = OUT_DIR / "topic_representative_docs.txt"
OUT_VIZ_BAR = OUT_DIR / "topic_viz.png"
OUT_VIZ_INTER = OUT_DIR / "topic_viz_intertopic.png"
OUT_COMMENTS_TOPICS = OUT_DIR / "comments_with_topics.csv"
EMB_CACHE = OUT_DIR / "bertopic_embeddings.npy"

EMBED_MODEL = "all-MiniLM-L6-v2"
EMBED_FALLBACK = "paraphrase-multilingual-MiniLM-L12-v2"  # 本地缓存，中文更稳
EMBED_BATCH = 128
TOP_N_KEYWORDS = 10
TOP_N_REP_IN_CSV = 3
RANDOM_SAMPLES_PER_TOPIC = 5
TARGET_TOPIC_RANGE = (5, 12)
TARGET_TOPICS = 7
MIN_TOPIC_DOCS_REPORT = 80
# BERTopic 自动切出的碎屑簇（与议题无关），合并回离群
BERTOPIC_MICRO_NOISE_IDS = frozenset({4, 5})
# 叙事补强 topic_id（屏2 展示顺序 4/5）
NARRATIVE_TOPIC_IDS = frozenset({4, 5})
NARRATIVE_KEYWORDS = {
    0: "李白,改编,翻唱,又能怎,听感,侵权,舆论,音乐",
    4: "人身攻击,网暴,辱骂,去死,滚,贱,丑,恶心,垃圾,不要脸",
    5: "总监制,人设,人品,态度,没教养,墙倒,mean,拽,白眼",
}
# 并入主议题，不再单独占一个簇（屏2 控制在约 6 个）
TOPIC_MERGE_MAP = {8: 1, 9: 0, 10: 0}
MIN_CHINESE_FOR_TRAIN = 8
RNG = random.Random(42)

STOP = set(
    "的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 "
    "自己 这 那 吗 吧 啊 呢 哦 嗯 哈 呀 还 把 被 让 给 对 从 而 已 以 及 与 或 但 如果 "
    "什么 怎么 为什么 可以 这个 那个 真的 感觉 觉得 就是 不是 我们 他们 你们 她 他 它".split()
)
# 人名/应援高频词：进入 c-TF-IDF 停用，避免「单依纯+李荣浩」占满关键词
DOMAIN_STOP = set(
    "单依纯 李荣浩 李白 工作室 官方 粉丝 宝宝 期待 支持 喜欢 爱了 好美 好棒 好听 加油 "
    "单姐 纯妹妹 妹妹 歌手 明星 艺人 偶像 评论 回复 转发 微博 视频 抖音 小红书".split()
)
NOISE_PHRASES = (
    "亮甲", "灰指甲", "一个传染俩", "得了灰指甲", "马上用亮", "怎么办用亮",
    "http", "www.", "加微信", "加V", "刷赞",
)
LOW_INFO_FAN = re.compile(
    r"^[\s\d\W]*(?:好美|好棒|好厉害|期待|爱了|支持|666|nb|yyds)[\s\d\W]*$",
    re.I,
)


def count_chinese(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", str(text)))


def is_noise_document(text: str) -> bool:
    t = str(text).strip()
    if not t:
        return True
    if any(p in t for p in NOISE_PHRASES):
        return True
    if LOW_INFO_FAN.match(t):
        return True
    if count_chinese(t) < MIN_CHINESE_FOR_TRAIN:
        return True
    return False


def should_train_document(text: str) -> bool:
    """用于聚类训练：去掉梗刷屏、纯应援短句，保留可解释议题文本。"""
    if is_noise_document(text):
        return False
    t = str(text).strip()
    # 极短且几乎只有艺人名
    chars = re.sub(r"[\u4e00-\u9fff]", "", t)
    names_only = (
        count_chinese(t) <= 12
        and sum(1 for n in ("单依纯", "李荣浩", "李白", "syc", "lrh") if n in t) >= 1
        and len(chars.strip()) < 8
    )
    return not names_only


def setup_font() -> None:
    for name in ("Microsoft YaHei", "SimHei", "PingFang SC"):
        plt.rcParams["font.sans-serif"] = [name]
        plt.rcParams["axes.unicode_minus"] = False
        return


def tokenize_zh(text: str) -> list[str]:
    import jieba
    skip = STOP | DOMAIN_STOP
    return [
        w for w in jieba.lcut(str(text))
        if len(w) >= 2 and w not in skip and not w.isdigit()
    ]


class JiebaVectorizer:
    """中文 c-TF-IDF 用词袋向量器。"""

    def __init__(self):
        self._cv = None

    def fit(self, docs):
        from sklearn.feature_extraction.text import CountVectorizer
        self._cv = CountVectorizer(tokenizer=tokenize_zh, max_features=6000, min_df=5)
        self._cv.fit(docs)
        return self

    def transform(self, docs):
        if self._cv is None:
            self.fit(docs)
        return self._cv.transform(docs)

    def fit_transform(self, docs):
        from sklearn.feature_extraction.text import CountVectorizer
        self._cv = CountVectorizer(tokenizer=tokenize_zh, max_features=6000, min_df=5)
        return self._cv.fit_transform(docs)

    def get_feature_names_out(self):
        return self._cv.get_feature_names_out() if self._cv is not None else []


def get_embedder() -> tuple[object, str]:
    """返回 (模型, 实际使用的模型名)。优先离线加载，避免 HuggingFace 超时。"""
    from sentence_transformers import SentenceTransformer

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    for name in (EMBED_MODEL, EMBED_FALLBACK):
        try:
            print(f"尝试离线加载: {name}")
            return SentenceTransformer(name, local_files_only=True), name
        except Exception as e:
            print(f"  跳过 ({e})")
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    print(f"离线不可用，尝试在线下载: {EMBED_FALLBACK}")
    return SentenceTransformer(EMBED_FALLBACK), EMBED_FALLBACK


def keywords_csv(topic_model, topic_id: int) -> str:
    if topic_id == -1:
        return ""
    if topic_id in NARRATIVE_KEYWORDS:
        return NARRATIVE_KEYWORDS[topic_id]
    tw = topic_model.get_topic(topic_id) or []
    return ",".join(w for w, _ in tw[:TOP_N_KEYWORDS])


_RE_PERSONAL_ATTACK = re.compile(
    r"人身攻击|网暴|去死|滚[开吧]?|贱[人货]?|婊|丑[死鬼]?|恶心|垃圾|不要脸|败类|蠢货|傻[逼逼叉]|"
    r"没[脸皮]|骂[死娘]|喷[子粪]|攻击[性]|侮辱|羞辱|人渣|下头|恶臭|滚出",
    re.I,
)
_RE_PERSONA = re.compile(
    r"总监制|人设|人品|墙倒众人推|mean|拽[吗么]?|没教养|没素质|白眼|态度[有]?问题|"
    r"大牌|耍大牌|不尊重|没礼貌|傲慢|嚣张|恶心[人]?的?艺人",
    re.I,
)
# 可从这些 BERTopic 簇中「拉回」叙事主题（不含道歉维权簇 1）
_OVERRIDE_SOURCE_IDS = frozenset({-1, 0, 2, 3, 4, 5})


def consolidate_topics(topics: list[int]) -> tuple[list[int], int]:
    """将碎屑/子簇并入主议题，减少驾驶舱主题个数。"""
    merged = 0
    out = list(topics)
    for i, tid in enumerate(out):
        t = int(tid)
        if t in TOPIC_MERGE_MAP:
            out[i] = TOPIC_MERGE_MAP[t]
            merged += 1
    return out, merged


def apply_topic_refinements(topics: list[int], documents: list[str]) -> tuple[list[int], dict]:
    """去掉无意义微簇；从 0/-1 仅拆出人身攻击、人设两类，其余并入主议题。"""
    stats = {
        "noise_to_outlier": 0,
        "narrative_4": 0,
        "narrative_5": 0,
        "merged_subtopics": 0,
    }
    refined = list(topics)
    for i, doc in enumerate(documents):
        tid = int(refined[i])
        if tid in BERTOPIC_MICRO_NOISE_IDS:
            refined[i] = -1
            stats["noise_to_outlier"] += 1
            tid = -1
        if tid not in _OVERRIDE_SOURCE_IDS:
            continue
        text = str(doc)
        if _RE_PERSONA.search(text):
            refined[i] = 5
            stats["narrative_5"] += 1
        elif _RE_PERSONAL_ATTACK.search(text):
            refined[i] = 4
            stats["narrative_4"] += 1
    refined, n_merge = consolidate_topics(refined)
    stats["merged_subtopics"] = n_merge
    return refined, stats


def get_rep_comments(
    topic_model,
    topic_id: int,
    documents: list[str],
    topics: list[int],
    n: int,
) -> list[str]:
    try:
        reps = topic_model.get_representative_docs(topic_id) or []
    except Exception:
        reps = []
    if not reps:
        idx = [i for i, t in enumerate(topics) if t == topic_id]
        reps = [documents[i] for i in idx]
    out = []
    for s in reps:
        s = re.sub(r"\s+", " ", str(s)).strip()
        if s and s not in out:
            out.append(s[:300])
        if len(out) >= n:
            break
    return out


def random_comments(
    documents: list[str],
    topics: list[int],
    topic_id: int,
    n: int,
) -> list[str]:
    idx = [i for i, t in enumerate(topics) if t == topic_id]
    if not idx:
        return []
    pick = RNG.sample(idx, min(n, len(idx)))
    return [re.sub(r"\s+", " ", documents[i]).strip()[:300] for i in pick]


CHART_SIZE = (1200, 800)

_THEME = {
    "bg": "#f4f0f2",
    "card": "#ffffff",
    "ink": "#2a1a22",
    "ink_muted": "#6b5560",
    "ink_soft": "#9a8490",
    "accent": "#6b1d35",
    "accent_light": "#a83256",
    "line": "#e8dce1",
    "grid": "#efe6ea",
}
_TOPIC_COLORS = [
    {"color": "#6b1d35", "light": "#d4738f", "dark": "#3d1524"},
    {"color": "#8b2942", "light": "#e8a0b0", "dark": "#5a2033"},
    {"color": "#2d6a8f", "light": "#7eb8d8", "dark": "#1a4258"},
    {"color": "#2d9a78", "light": "#7fd4b8", "dark": "#1e6b55"},
    {"color": "#7a5c8a", "light": "#c4b0d0", "dark": "#4a3856"},
    {"color": "#b8860b", "light": "#e8c96a", "dark": "#7a5208"},
]


def _save_figure(fig: plt.Figure, out_path: Path) -> None:
    fig.savefig(out_path, dpi=100, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    try:
        from PIL import Image
        with Image.open(out_path) as im:
            if im.size != CHART_SIZE:
                im.resize(CHART_SIZE, Image.Resampling.LANCZOS).save(out_path)
    except ImportError:
        pass


def _topic_display_name(row: pd.Series) -> str:
    from topic_labels import label_from_keywords

    name = str(row.get("chinese_name", "") or "").strip()
    if name:
        return name
    return label_from_keywords(int(row["topic_id"]), str(row.get("keywords", "")))


def _load_dist_with_names() -> pd.DataFrame:
    dist = pd.read_csv(OUT_DIST, encoding="utf-8-sig")
    if OUT_NAMING.exists():
        naming = pd.read_csv(OUT_NAMING, encoding="utf-8-sig")
        if "chinese_name" in naming.columns:
            dist = dist.merge(
                naming[["topic_id", "chinese_name"]],
                on="topic_id",
                how="left",
                suffixes=("", "_n"),
            )
    dist = dist.sort_values("doc_count", ascending=False).reset_index(drop=True)
    dist["display_name"] = dist.apply(_topic_display_name, axis=1)
    return dist


def plot_premium_topic_dashboard(
    dist_df: pd.DataFrame,
    out_path: Path,
    total_n: int,
    outlier_n: int,
) -> None:
    """1200×800 主题洞察信息图（主图 topic_viz.png）。"""
    setup_font()
    if dist_df.empty:
        return

    df = dist_df.sort_values("doc_count", ascending=True).copy()
    if "display_name" not in df.columns:
        df["display_name"] = df.apply(_topic_display_name, axis=1)

    counts = df["doc_count"].astype(int).tolist()
    names = df["display_name"].tolist()
    ids = df["topic_id"].astype(int).tolist()
    total_topics = sum(counts) or 1
    pcts = [c / total_topics * 100 for c in counts]
    assigned_n = total_n - outlier_n

    fig = plt.figure(figsize=(12, 8), facecolor=_THEME["bg"])
    gs = gridspec.GridSpec(
        4, 12, figure=fig,
        height_ratios=[0.78, 0.95, 2.55, 1.0],
        hspace=0.4, wspace=0.48,
        left=0.06, right=0.96, top=0.92, bottom=0.07,
    )

    ax_title = fig.add_subplot(gs[0, :])
    ax_title.set_axis_off()
    ax_title.text(
        0, 0.75, "评论主题结构洞察",
        fontsize=26, fontweight=700, color=_THEME["ink"],
        transform=ax_title.transAxes, ha="left", va="center",
    )
    ax_title.text(
        0, 0.28,
        f"BERTopic · 主报告主题 {len(df)} 个 · 已归类 {assigned_n:,} 条 · 离群 {outlier_n:,} 条",
        fontsize=12, color=_THEME["ink_muted"],
        transform=ax_title.transAxes, ha="left", va="center",
    )
    ax_title.text(
        0, 0.02,
        "已过滤亮甲梗/纯应援短句；关键词已去艺人名。主题名请结合 topic_naming.csv 人工校对。",
        fontsize=9.2, color=_THEME["ink_soft"], style="italic",
        transform=ax_title.transAxes, ha="left", va="bottom",
    )

    # KPI：Top3 主题
    top3 = df.sort_values("doc_count", ascending=False).head(3)
    for i, (_, row) in enumerate(top3.iterrows()):
        ax_k = fig.add_subplot(gs[1, i * 4 : i * 4 + 4])
        ax_k.set_axis_off()
        pal = _TOPIC_COLORS[i % len(_TOPIC_COLORS)]
        ax_k.add_patch(mpatches.FancyBboxPatch(
            (0.02, 0.06), 0.96, 0.88,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=_THEME["card"], edgecolor=_THEME["line"], linewidth=1.2,
            transform=ax_k.transAxes,
        ))
        ax_k.add_patch(mpatches.FancyBboxPatch(
            (0.02, 0.78), 0.96, 0.16,
            boxstyle="round,pad=0.01,rounding_size=0.05",
            facecolor=pal["color"], transform=ax_k.transAxes,
        ))
        title = textwrap.shorten(str(row["display_name"]), 14, placeholder="…")
        ax_k.text(0.08, 0.86, f"#{i+1} {title}", fontsize=11, fontweight=700,
                  color="white", transform=ax_k.transAxes, va="center")
        ax_k.text(0.08, 0.48, f"{int(row['doc_count']):,}", fontsize=22, fontweight=700,
                  color=_THEME["ink"], transform=ax_k.transAxes, va="center")
        ax_k.text(0.08, 0.22, f"占已归类 {int(row['doc_count'])/assigned_n*100:.1f}%",
                  fontsize=10, color=_THEME["ink_muted"], transform=ax_k.transAxes, va="center")

    # 横向条形图
    ax_bar = fig.add_subplot(gs[2, 0:7])
    ax_bar.set_facecolor(_THEME["card"])
    for spine in ax_bar.spines.values():
        spine.set_visible(False)
    y = np.arange(len(df))
    xmax = max(counts) * 1.22
    for i, (cnt, pct, tid) in enumerate(zip(counts, pcts, ids)):
        pal = _TOPIC_COLORS[tid % len(_TOPIC_COLORS)]
        grad = LinearSegmentedColormap.from_list("g", [pal["light"], pal["color"], pal["dark"]], N=48)
        seg = max(cnt // 40, 1)
        w = cnt / seg
        for s in range(seg):
            ax_bar.barh(y[i], w, left=s * w, height=0.58, color=grad(s / max(seg - 1, 1)), edgecolor="none")
        ax_bar.barh(y[i], cnt, height=0.58, facecolor="none", edgecolor="white", linewidth=1.4)
        kw_short = " · ".join(str(df.iloc[i]["keywords"]).split(",")[:4])
        ax_bar.text(
            -xmax * 0.01, y[i], f"T{tid}",
            va="center", ha="right", fontsize=9, color=_THEME["ink_soft"],
        )
        lbl = ax_bar.text(
            cnt + xmax * 0.015, y[i],
            f"{cnt:,}  ({pct:.1f}%)",
            va="center", ha="left", fontsize=10.5, fontweight=600, color=_THEME["ink"],
        )
        lbl.set_path_effects([pe.withStroke(linewidth=3, foreground=_THEME["card"])])
        ax_bar.text(
            cnt * 0.02, y[i] - 0.32, kw_short,
            va="top", ha="left", fontsize=8, color=_THEME["ink_muted"], clip_on=True,
        )

    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(
        [textwrap.shorten(n, 16, placeholder="…") for n in names],
        fontsize=12, fontweight=600,
    )
    ax_bar.invert_yaxis()
    ax_bar.set_xlim(0, xmax)
    ax_bar.set_xlabel("评论数", fontsize=11, color=_THEME["ink_muted"])
    ax_bar.xaxis.grid(True, linestyle="-", linewidth=0.6, color=_THEME["grid"], zorder=0)
    ax_bar.set_axisbelow(True)
    ax_bar.text(-0.02, 1.05, "主题规模与关键词", fontsize=13, fontweight=700,
                color=_THEME["ink"], transform=ax_bar.transAxes)

    # 环形图
    ax_donut = fig.add_subplot(gs[2, 7:12])
    ax_donut.set_facecolor(_THEME["card"])
    pie_colors = [_TOPIC_COLORS[tid % len(_TOPIC_COLORS)]["color"] for tid in ids]
    ax_donut.pie(
        counts, colors=pie_colors, startangle=90, counterclock=False,
        wedgeprops=dict(width=0.44, edgecolor=_THEME["card"], linewidth=2.5),
        autopct=lambda p: f"{p:.0f}%" if p >= 4 else "",
        pctdistance=0.78,
        textprops=dict(fontsize=10, fontweight=700, color="white"),
    )
    ax_donut.text(
        0, 0, f"{len(df)}\n个主题\n\n{assigned_n:,}\n条已归类",
        ha="center", va="center", fontsize=11, fontweight=700, color=_THEME["ink"], linespacing=1.3,
    )
    leg_handles = [
        mpatches.Patch(facecolor=_TOPIC_COLORS[tid % len(_TOPIC_COLORS)]["color"], label=n)
        for tid, n in zip(ids, names)
    ]
    ax_donut.legend(
        handles=leg_handles,
        loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=1, frameon=False,
        fontsize=9, labelcolor=_THEME["ink_muted"],
    )
    ax_donut.text(0, 1.08, "占比结构", fontsize=13, fontweight=700,
                  ha="center", transform=ax_donut.transAxes, color=_THEME["ink"])

    # 底部：关键词热力条
    ax_kw = fig.add_subplot(gs[3, :])
    ax_kw.set_facecolor(_THEME["card"])
    ax_kw.set_axis_off()
    ax_kw.text(0, 1.05, "核心关键词（Top5）", fontsize=11, fontweight=600,
               color=_THEME["ink_muted"], transform=ax_kw.transAxes)
    y0 = 0.82
    for i, (_, row) in enumerate(df.sort_values("doc_count", ascending=False).iterrows()):
        tid = int(row["topic_id"])
        pal = _TOPIC_COLORS[tid % len(_TOPIC_COLORS)]
        kws = [k.strip() for k in str(row["keywords"]).split(",")[:5]]
        ax_kw.text(0, y0 - i * 0.19, textwrap.shorten(str(row["display_name"]), 12, placeholder="…"),
                   fontsize=10, fontweight=700, color=pal["dark"], transform=ax_kw.transAxes, va="center")
        x = 0.22
        for kw in kws:
            ax_kw.add_patch(mpatches.FancyBboxPatch(
                (x, y0 - i * 0.19 - 0.06), 0.11, 0.12,
                boxstyle="round,pad=0.01,rounding_size=0.15",
                facecolor=pal["light"], alpha=0.55, edgecolor=pal["color"], linewidth=0.8,
                transform=ax_kw.transAxes,
            ))
            ax_kw.text(x + 0.055, y0 - i * 0.19, kw, ha="center", va="center",
                       fontsize=8.5, color=_THEME["ink"], transform=ax_kw.transAxes)
            x += 0.125

    _save_figure(fig, out_path)


def _keyword_sets(keywords: str) -> set[str]:
    return {k.strip() for k in str(keywords).split(",") if k.strip()}


def plot_premium_intertopic(dist_df: pd.DataFrame, out_path: Path) -> None:
    """主题相似度气泡图（基于关键词 Jaccard + MDS）。"""
    setup_font()
    if len(dist_df) < 2:
        return

    df = dist_df.sort_values("doc_count", ascending=False).reset_index(drop=True)
    if "display_name" not in df.columns:
        df["display_name"] = df.apply(_topic_display_name, axis=1)

    sets = [_keyword_sets(k) for k in df["keywords"]]
    n = len(sets)
    sim = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            inter = len(sets[i] & sets[j])
            union = len(sets[i] | sets[j]) or 1
            sim[i, j] = sim[j, i] = inter / union
    dist_mat = 1 - sim

    from sklearn.manifold import MDS
    coords = MDS(n_components=2, dissimilarity="precomputed", random_state=42).fit_transform(dist_mat)

    fig, ax = plt.subplots(figsize=(12, 8), facecolor=_THEME["bg"])
    ax.set_facecolor(_THEME["card"])
    sizes = df["doc_count"].astype(float).values
    sizes = sizes / max(sizes.max(), 1) * 2200 + 380
    for i, (_, row) in enumerate(df.iterrows()):
        tid = int(row["topic_id"])
        pal = _TOPIC_COLORS[tid % len(_TOPIC_COLORS)]
        ax.scatter(
            coords[i, 0], coords[i, 1], s=sizes[i], c=pal["color"], alpha=0.72,
            edgecolors="white", linewidths=2.5, zorder=3,
        )
        ax.text(
            coords[i, 0], coords[i, 1],
            textwrap.shorten(str(row["display_name"]), 10, placeholder="…"),
            ha="center", va="center", fontsize=10, fontweight=700, color="white", zorder=4,
        )

    ax.set_title("主题语义邻近图（关键词相似度 · MDS）", fontsize=16, fontweight=700,
                 color=_THEME["ink"], pad=16)
    ax.text(
        0.5, 1.02,
        "气泡越大 → 评论越多；相距越近 → 关键词越像（非 BERTopic 官方距离，仅供叙事参考）",
        transform=ax.transAxes, ha="center", fontsize=10, color=_THEME["ink_soft"], style="italic",
    )
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(True, linestyle=":", linewidth=0.5, color=_THEME["grid"], alpha=0.8)
    plt.tight_layout()
    _save_figure(fig, out_path)


def render_topic_figures(total_n: int, outlier_n: int) -> None:
    dist_df = _load_dist_with_names()
    plot_premium_topic_dashboard(dist_df, OUT_VIZ_BAR, total_n, outlier_n)
    plot_premium_intertopic(dist_df, OUT_VIZ_INTER)
    print(f"已保存: {OUT_VIZ_BAR}")
    print(f"已保存: {OUT_VIZ_INTER}")


def build_topic_distribution(
    topic_model,
    documents: list[str],
    topics: list[int],
) -> pd.DataFrame:
    """按最终 topic 赋值统计（含叙事补强后的 4/5）。"""
    from collections import Counter

    counts = Counter(int(t) for t in topics if int(t) >= 0)
    rows = []
    for tid in sorted(counts.keys()):
        reps = get_rep_comments(topic_model, tid, documents, topics, TOP_N_REP_IN_CSV)
        if len(reps) < TOP_N_REP_IN_CSV:
            extra = random_comments(documents, topics, tid, TOP_N_REP_IN_CSV)
            for s in extra:
                if s not in reps:
                    reps.append(s)
                if len(reps) >= TOP_N_REP_IN_CSV:
                    break
        row = {
            "topic_id": tid,
            "doc_count": counts[tid],
            "keywords": keywords_csv(topic_model, tid),
        }
        for j in range(TOP_N_REP_IN_CSV):
            row[f"representative_comment_{j + 1}"] = reps[j] if j < len(reps) else ""
        rows.append(row)
    return pd.DataFrame(rows)


def build_topic_naming(dist_df: pd.DataFrame) -> pd.DataFrame:
    from topic_labels import label_from_keywords

    names = [
        label_from_keywords(int(r["topic_id"]), str(r["keywords"]))
        for _, r in dist_df.iterrows()
    ]
    return pd.DataFrame({
        "topic_id": dist_df["topic_id"],
        "doc_count": dist_df["doc_count"],
        "keywords": dist_df["keywords"],
        "chinese_name": names,
        "命名参考": names,
        "命名说明": "由关键词自动生成；可在 chinese_name 列手工覆盖",
    })


def write_representative_docs(
    topic_model,
    documents: list[str],
    topics: list[int],
    outlier_n: int,
    out_path: Path,
    topic_ids: list[int] | None = None,
) -> None:
    lines = [
        "BERTopic 主题代表评论（每主题随机 5 条）",
        "=" * 60,
        f"离群主题 topic_id=-1 评论数: {outlier_n}（未列入主题表，见 topic_distribution.csv 说明）",
        "",
    ]
    if topic_ids is None:
        topic_ids = sorted(t for t in set(topics) if t != -1)
    else:
        topic_ids = sorted(topic_ids)
    for tid in topic_ids:
        kw = keywords_csv(topic_model, tid)
        n = sum(1 for t in topics if t == tid)
        lines.append(f"【主题 {tid}】文档数: {n}")
        lines.append(f"关键词: {kw.replace(',', ' · ')}")
        lines.append("-" * 48)
        for j, s in enumerate(
            random_comments(documents, topics, tid, RANDOM_SAMPLES_PER_TOPIC), 1
        ):
            lines.append(f"  {j}. {s}")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _setup_joblib_ascii_tmp() -> Path:
    """Windows + 中文项目路径时，HDBSCAN/joblib 需 ASCII 临时目录。"""
    tmp = Path(tempfile.gettempdir()) / "bertopic_joblib_cache"
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ["JOBLIB_TEMP_FOLDER"] = str(tmp)
    return tmp


def main() -> None:
    if not INPUT_CSV.exists():
        raise SystemExit(f"未找到 {INPUT_CSV}，请先运行 preprocess_three_platforms.py")

    _setup_joblib_ascii_tmp()

    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from umap import UMAP

    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    if "content" not in df.columns:
        raise SystemExit("cleaned_comments.csv 缺少 content 列")

    documents = df["content"].astype(str).tolist()
    n = len(documents)
    train_mask = np.array([should_train_document(d) for d in documents], dtype=bool)
    n_train = int(train_mask.sum())
    print(f"全量 {n} 条；参与聚类训练 {n_train} 条（已剔除短句/应援/亮甲梗等）")

    embedder, embed_name = get_embedder()
    print(f"实际嵌入模型: {embed_name}")
    if EMB_CACHE.exists() and len(np.load(EMB_CACHE)) == n:
        print(f"加载缓存嵌入: {EMB_CACHE.name}")
        embeddings = np.load(EMB_CACHE)
    else:
        print("计算句向量…")
        embeddings = embedder.encode(documents, batch_size=EMBED_BATCH, show_progress_bar=True)
        np.save(EMB_CACHE, embeddings)
        print(f"嵌入已缓存: {EMB_CACHE}")

    docs_train = [documents[i] for i in range(n) if train_mask[i]]
    emb_train = embeddings[train_mask]

    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=42,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=25,
        min_samples=7,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
        core_dist_n_jobs=1,
    )
    topic_model = BERTopic(
        embedding_model=embedder,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=JiebaVectorizer(),
        top_n_words=TOP_N_KEYWORDS,
        calculate_probabilities=False,
        verbose=True,
    )

    print("训练 BERTopic（仅议题向评论）…")
    topic_model.fit(docs_train, emb_train)
    topic_model.reduce_topics(docs_train, nr_topics=TARGET_TOPICS)
    print("为全量评论分配主题…")
    topics, _ = topic_model.transform(documents, embeddings)
    topics, refine_stats = apply_topic_refinements(list(topics), documents)
    print(
        "主题整理: "
        f"碎屑→离群 {refine_stats['noise_to_outlier']} · "
        f"人身攻击 {refine_stats['narrative_4']} · "
        f"总监制/人设 {refine_stats['narrative_5']} · "
        f"子簇并入主议题 {refine_stats['merged_subtopics']}"
    )

    n_topics = len({t for t in topics if t != -1})
    outlier_n = sum(1 for t in topics if t == -1)

    with open(OUT_MODEL, "wb") as f:
        pickle.dump({
            "model": topic_model,
            "topics": topics,
            "embed_model": embed_name,
            "umap": "n_neighbors=15,min_dist=0.0,metric=cosine",
            "hdbscan": "min_cluster_size=25,min_samples=7",
            "train_docs": n_train,
        }, f)
    print(f"模型已保存: {OUT_MODEL}")

    dist_all = build_topic_distribution(topic_model, documents, topics)
    dist_df = dist_all[dist_all["doc_count"] >= MIN_TOPIC_DOCS_REPORT].copy()
    dist_minor = dist_all[dist_all["doc_count"] < MIN_TOPIC_DOCS_REPORT].copy()
    dist_df.to_csv(OUT_DIST, index=False, encoding="utf-8-sig")
    if not dist_minor.empty:
        dist_minor.to_csv(OUT_DIR / "topic_minor_clusters.csv", index=False, encoding="utf-8-sig")
        print(f"碎屑主题（<{MIN_TOPIC_DOCS_REPORT} 条）已另存: topic_minor_clusters.csv")
    (OUT_DIR / "topic_outlier_stats.txt").write_text(
        f"离群主题 topic_id=-1\n评论数: {outlier_n}\n占比: {outlier_n/n*100:.2f}%\n"
        f"说明: 未纳入 topic_distribution.csv\n",
        encoding="utf-8",
    )
    print(f"主题分布表: {OUT_DIST}（{len(dist_df)} 个主题，已排除 -1；离群 {outlier_n} 条）")

    naming_df = build_topic_naming(dist_df)
    naming_df.to_csv(OUT_NAMING, index=False, encoding="utf-8-sig")
    print(f"命名模板: {OUT_NAMING}")

    write_representative_docs(
        topic_model, documents, topics, outlier_n, OUT_REP_DOCS,
        topic_ids=dist_df["topic_id"].tolist(),
    )
    print(f"代表评论: {OUT_REP_DOCS}")

    df_out = df.copy()
    df_out["topic_id"] = topics
    df_out.to_csv(OUT_COMMENTS_TOPICS, index=False, encoding="utf-8-sig")

    render_topic_figures(n, outlier_n)

    # 验收报告
    summary_path = OUT_DIR / "topic_modeling_report.txt"
    summary_lines = [
        "BERTopic 主题建模报告",
        "=" * 50,
        f"嵌入模型: {embed_name}",
        f"目标模型(若离线失败则回退): {EMBED_MODEL} → {EMBED_FALLBACK}",
        f"总评论数: {n}",
        f"训练样本数: {n_train}",
        f"离群 (-1): {outlier_n} ({outlier_n/n*100:.2f}%)",
        f"有效主题数: {n_topics}",
        f"报告主题数(≥{MIN_TOPIC_DOCS_REPORT}条): {len(dist_df)}",
        "说明: 已剔除亮甲梗/纯应援短句后再聚类；艺人名进入停用词表。",
    ]
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("\n" + "=" * 60)
    print("BERTopic 训练报告")
    print("=" * 60)
    print(f"嵌入模型: {embed_name}")
    print(f"总评论数: {n}")
    print(f"离群 (-1) 评论数: {outlier_n} ({outlier_n/n*100:.2f}%)")
    print(f"有效主题数 (不含 -1): {n_topics}")
    lo, hi = TARGET_TOPIC_RANGE
    if lo <= n_topics <= hi:
        print(f"主题数量验收: 通过（{lo}~{hi}）")
    else:
        print(f"主题数量验收: 未通过 — 当前 {n_topics} 个，请调整 TARGET_TOPICS 或 min_cluster_size")
    print("\n主题概览（topic_id · 文档数 · 关键词）:")
    for _, row in dist_df.head(25).iterrows():
        kw_short = textwrap.shorten(str(row["keywords"]), width=50, placeholder="…")
        print(f"  [{row['topic_id']}] {row['doc_count']:>5} 条  {kw_short}")
    print("=" * 60)
    print("请在 topic_naming.csv 中填写 chinese_name 后用于可视化看板。")


def refine_only() -> None:
    """不重训：在现有 topic 赋值上做碎屑剔除 + 叙事补强，并刷新 CSV/图。"""
    if not OUT_COMMENTS_TOPICS.exists():
        raise SystemExit(f"未找到 {OUT_COMMENTS_TOPICS}，请先运行完整 BERTopic。")
    with open(OUT_MODEL, "rb") as f:
        bundle = pickle.load(f)
    topic_model = bundle["model"]

    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    documents = df["content"].astype(str).tolist()
    n = len(documents)
    topics = pd.read_csv(OUT_COMMENTS_TOPICS, encoding="utf-8-sig")["topic_id"].astype(int).tolist()
    if len(topics) != n:
        raise SystemExit("comments_with_topics 行数与 cleaned_comments 不一致")

    topics, refine_stats = apply_topic_refinements(topics, documents)
    print(
        "主题整理: "
        f"碎屑→离群 {refine_stats['noise_to_outlier']} · "
        f"人身攻击 {refine_stats['narrative_4']} · "
        f"总监制/人设 {refine_stats['narrative_5']} · "
        f"子簇并入主议题 {refine_stats['merged_subtopics']}"
    )

    outlier_n = sum(1 for t in topics if t == -1)
    dist_all = build_topic_distribution(topic_model, documents, topics)
    dist_df = dist_all[dist_all["doc_count"] >= MIN_TOPIC_DOCS_REPORT].copy()
    dist_minor = dist_all[dist_all["doc_count"] < MIN_TOPIC_DOCS_REPORT].copy()
    dist_df.to_csv(OUT_DIST, index=False, encoding="utf-8-sig")
    if not dist_minor.empty:
        dist_minor.to_csv(OUT_DIR / "topic_minor_clusters.csv", index=False, encoding="utf-8-sig")
    else:
        minor_path = OUT_DIR / "topic_minor_clusters.csv"
        if minor_path.exists():
            minor_path.unlink()
    (OUT_DIR / "topic_outlier_stats.txt").write_text(
        f"离群主题 topic_id=-1\n评论数: {outlier_n}\n占比: {outlier_n/n*100:.2f}%\n"
        f"说明: 未纳入 topic_distribution.csv；含 BERTopic 碎屑簇 4/5 并入离群\n",
        encoding="utf-8",
    )
    build_topic_naming(dist_df).to_csv(OUT_NAMING, index=False, encoding="utf-8-sig")
    write_representative_docs(
        topic_model, documents, topics, outlier_n, OUT_REP_DOCS,
        topic_ids=dist_df["topic_id"].tolist(),
    )
    df_out = df.copy()
    df_out["topic_id"] = topics
    df_out.to_csv(OUT_COMMENTS_TOPICS, index=False, encoding="utf-8-sig")
    render_topic_figures(n, outlier_n)
    print(f"已刷新主报告主题 {len(dist_df)} 个 → {OUT_DIST}")


def viz_only() -> None:
    """仅根据 topic_distribution.csv 重绘可视化（无需重训模型）。"""
    if not OUT_DIST.exists():
        raise SystemExit(f"未找到 {OUT_DIST}")
    n = len(pd.read_csv(INPUT_CSV, encoding="utf-8-sig"))
    outlier_n = 0
    stats = OUT_DIR / "topic_outlier_stats.txt"
    if stats.exists():
        for line in stats.read_text(encoding="utf-8").splitlines():
            if line.startswith("评论数:"):
                outlier_n = int(line.split(":")[1].strip())
                break
    render_topic_figures(n, outlier_n)
    print("可视化已更新。")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("--viz-only", "--viz"):
        viz_only()
    elif len(sys.argv) > 1 and sys.argv[1] in ("--refine-only", "--refine"):
        refine_only()
    else:
        main()

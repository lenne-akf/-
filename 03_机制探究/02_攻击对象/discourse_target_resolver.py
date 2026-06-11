from __future__ import annotations
# -*- coding: utf-8 -*-
"""基于专名、代词窗口与负面语境的攻击对象解析。"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import re
from dataclasses import dataclass, field

from topic4_subsplit import (
    _RE_COPYRIGHT,
    _RE_DEFEND_OR_CONDEMN,
    _RE_LI,
    _RE_PROFESSIONAL,
    _RE_SHAN,
    is_personal_attack_on_shan,
)

RE_SHAN_ALIAS = re.compile(r"单依纯|单姐|纯妹妹|小单|依依|依纯|纯子|单妹妹|单依杶", re.I)
RE_LI_ALIAS = re.compile(r"李荣浩|李老师|浩哥|老李|李哥|lrh|小眼睛", re.I)

# 攻击对象 · 专名识别（示例列表供参考，按类别归并展示；越具体越靠前）
ENTITY_RULES: list[tuple[str, str, re.Pattern]] = [
    ("单依纯工作室", "工作室/经纪公司", re.compile(r"单依纯工作室|单依纯官方", re.I)),
    ("李荣浩工作室", "工作室/经纪公司", re.compile(r"李荣浩工作室", re.I)),
    ("华晨宇工作室", "工作室/经纪公司", re.compile(r"华晨宇工作室", re.I)),
    ("单依纯粉丝", "粉丝/营销号", re.compile(r"单依纯的?粉丝|单粉|纯牛奶|单依纯粉丝后援会", re.I)),
    ("李荣浩粉丝", "粉丝/营销号", re.compile(r"李荣浩的?粉丝|浩粉|李荣浩大粉", re.I)),
    ("营销号", "粉丝/营销号", re.compile(r"营销号|水军|黑粉组织|通稿号", re.I)),
    ("时代少年团", "组合/团体", re.compile(r"时代少年团|TNT|马嘉祺|丁程鑫", re.I)),
    ("硬糖少女303", "组合/团体", re.compile(r"硬糖少女303|硬糖", re.I)),
    ("INTO1", "组合/团体", re.compile(r"INTO1", re.I)),
    ("SNH48", "组合/团体", re.compile(r"SNH48", re.I)),
    ("周深", "其他艺人", re.compile(r"周深|深深|生米", re.I)),
    ("华晨宇", "其他艺人", re.compile(r"华晨宇|花花|火星人", re.I)),
    ("张靓颖", "其他艺人", re.compile(r"张靓颖|珍姐|凉粉", re.I)),
    ("邓紫棋", "其他艺人", re.compile(r"邓紫棋|GEM|棋士", re.I)),
    ("毛不易", "其他艺人", re.compile(r"毛不易|毛毛", re.I)),
    ("刘柏辛", "其他艺人", re.compile(r"刘柏辛", re.I)),
    ("黄霄雲", "其他艺人", re.compile(r"黄霄雲|黄霄云", re.I)),
    ("吉克隽逸", "其他艺人", re.compile(r"吉克隽逸", re.I)),
    ("哇唧唧哇", "工作室/经纪公司", re.compile(r"哇唧唧哇", re.I)),
    ("乐华娱乐", "工作室/经纪公司", re.compile(r"乐华娱乐|乐华", re.I)),
    ("时代峰峻", "工作室/经纪公司", re.compile(r"时代峰峻", re.I)),
    ("天娱传媒", "工作室/经纪公司", re.compile(r"天娱传媒|天娱", re.I)),
    ("声生不息", "综艺/节目", re.compile(r"声生不息", re.I)),
    ("天赐的声音", "综艺/节目", re.compile(r"天赐的声音", re.I)),
    ("我们的歌", "综艺/节目", re.compile(r"我们的歌", re.I)),
    ("歌手2024", "综艺/节目", re.compile(r"歌手\s*2024|歌手2024", re.I)),
    ("中国好声音", "综艺/节目", re.compile(r"中国好声音|好声音", re.I)),
    ("说唱听我的", "综艺/节目", re.compile(r"说唱听我的", re.I)),
    ("纯甄", "品牌/商务", re.compile(r"纯甄", re.I)),
    ("伊利", "品牌/商务", re.compile(r"伊利", re.I)),
    ("vivo", "品牌/商务", re.compile(r"vivo", re.I)),
    ("欧莱雅", "品牌/商务", re.compile(r"欧莱雅", re.I)),
    ("华伦天奴", "品牌/商务", re.compile(r"华伦天奴", re.I)),
    ("百事可乐", "品牌/商务", re.compile(r"百事可乐", re.I)),
    ("微博", "平台/媒体", re.compile(r"微博|wb|围脖", re.I)),
    ("豆瓣", "平台/媒体", re.compile(r"豆瓣", re.I)),
    ("抖音", "平台/媒体", re.compile(r"抖音|dy", re.I)),
    ("哔哩哔哩", "平台/媒体", re.compile(r"哔哩哔哩|b站|B站", re.I)),
    ("腾讯视频", "平台/媒体", re.compile(r"腾讯视频", re.I)),
    ("芒果TV", "平台/媒体", re.compile(r"芒果TV|芒果tv", re.I)),
    ("网易云音乐", "平台/媒体", re.compile(r"网易云音乐|网易云", re.I)),
    ("单依纯", "单依纯", RE_SHAN_ALIAS),
    ("李荣浩", "李荣浩", RE_LI_ALIAS),
]

LEGACY_TO_GROUP = {
    "单依纯本人": ("单依纯", "单依纯"),
    "李荣浩": ("李荣浩", "李荣浩"),
    "团队": ("工作室/经纪公司", "工作室/经纪公司"),
    "其他/事件": ("其他/事件", "其他/事件"),
}

RE_TEAM = re.compile(
    r"团队|工作室|公司|经纪|后援|粉丝团|常石磊|班子|公关|运营|"
    r"厂牌|唱片|官方工作室",
    re.I,
)
TARGET_ORDER = ("单依纯本人", "李荣浩", "团队", "其他/事件")

RE_NEG = re.compile(
    r"骂|攻击|诋毁|黑|辱|恶心|讨厌|失望|难评|离谱|抄袭|甩锅|装|洗|护短|"
    r"难看|难听|改得|毁|不负责|傲慢|狂|飘|塌|伪|贱|滚|去死|垃圾|废物|"
    r"不要脸|下头|心机|绿茶|又当又立|双标|恶心|缺德|过分|气|怒|"
    r"围剿|恶意|伤害|推.*浪|污蔑|造谣|甩|糊弄|买热搜|捂嘴|"
    r"活人感|道貌岸然|伪君子|小作文|十年抄袭|眼|心胸",
    re.I,
)
RE_DEFEND_SHAN = re.compile(
    r"心疼单依纯|维护单|挺单|支持单|单依纯.*(冤枉|无辜|不该|不应)|"
    r"别.*黑单|不要.*骂单|停止.*攻击单|"
    r"单依纯值得|恶意围剿|都在害怕她|"
    r"单依纯.*(道歉|担责|体面)|"
    r"用作品和实力说话",
    re.I,
)
RE_DEFEND_LI = re.compile(
    r"心疼.*李荣浩|维护李|挺李|李.*(冤枉|无辜|体面|太体面)|"
    r"别.*黑李|不要.*骂李|老李.*体面",
    re.I,
)
RE_ATTACK_CYBER = re.compile(
    r"网暴|人身攻击|恶意|围剿|黑子|喷子|水军|媒体|热搜|词条|"
    r"对立|煽动|引战|吃人血|吃.*流量",
    re.I,
)
RE_EVENT = re.compile(
    r"版权|抄袭|改编|侵权|下架|李白|旋律|授权|维权|举证|"
    r"听感|毁歌|著作权|采样|洗稿|乌龙|凌霸|音协",
    re.I,
)
RE_FEM_PRON = re.compile(r"她|此女|这姑娘|这女孩|这位女")
RE_MALE_PRON = re.compile(r"他|此男|这男的|这位男|浩哥(?!粉)")


@dataclass
class TargetAnnotation:
    attack_target: str
    attack_target_display: str = ""
    attack_target_group: str = ""
    target_scores: dict[str, float] = field(default_factory=dict)
    target_evidence: str = ""
    is_mixed: bool = False
    secondary_target: str | None = None


def _match_entity(text: str) -> tuple[str, str] | None:
    for display, group, pat in ENTITY_RULES:
        if pat.search(text):
            return display, group
    return None


def _display_from_legacy(primary: str) -> tuple[str, str]:
    return LEGACY_TO_GROUP.get(primary, ("其他/事件", "其他/事件"))


def _window(text: str, start: int, end: int, before: int = 50, after: int = 50) -> str:
    return text[max(0, start - before) : min(len(text), end + after)]


def _add_score(scores: dict[str, float], key: str, val: float, evidence: list[str], note: str) -> None:
    scores[key] = scores.get(key, 0.0) + val
    if val >= 2 and note:
        evidence.append(note)


def _score_named_entities(text: str, scores: dict[str, float], evidence: list[str]) -> None:
    for m in RE_SHAN_ALIAS.finditer(text):
        w = _window(text, m.start(), m.end())
        if _RE_DEFEND_OR_CONDEMN.search(w) or RE_DEFEND_SHAN.search(w):
            _add_score(scores, "其他/事件", 1.5, evidence, f"维护单:{m.group()}")
            continue
        if is_personal_attack_on_shan(text) or is_personal_attack_on_shan(w):
            _add_score(scores, "单依纯本人", 6.0, evidence, f"人身/品格:{m.group()}")
        elif RE_NEG.search(w) or _RE_PROFESSIONAL.search(w):
            _add_score(scores, "单依纯本人", 4.0, evidence, f"专名+批评:{m.group()}")
        elif _RE_SHAN.search(w):
            _add_score(scores, "单依纯本人", 2.0, evidence, f"提及单:{m.group()}")

    for m in RE_LI_ALIAS.finditer(text):
        w = _window(text, m.start(), m.end())
        if RE_DEFEND_LI.search(w):
            _add_score(scores, "其他/事件", 1.0, evidence, f"维护李:{m.group()}")
            continue
        if RE_NEG.search(w) or re.search(r"抄|侵权|甩锅|买|装|伪|眼|心胸|活人", w, re.I):
            _add_score(scores, "李荣浩", 4.5, evidence, f"专名+批评:{m.group()}")
        else:
            _add_score(scores, "李荣浩", 1.5, evidence, f"提及李:{m.group()}")

    for m in RE_TEAM.finditer(text):
        w = _window(text, m.start(), m.end())
        if RE_NEG.search(w) or re.search(r"不会|差|烂|甩|公关|摆明|搞你", w, re.I):
            _add_score(scores, "团队", 5.0, evidence, f"团队批评:{m.group()}")
        else:
            _add_score(scores, "团队", 2.0, evidence, f"提及团队:{m.group()}")


def _score_pronouns(text: str, scores: dict[str, float], evidence: list[str]) -> None:
    for m in RE_FEM_PRON.finditer(text):
        left = text[max(0, m.start() - 80) : m.start()]
        right = text[m.end() : min(len(text), m.end() + 40)]
        ctx = left + m.group() + right
        if RE_SHAN_ALIAS.search(left) or re.search(r"这姑娘|这女孩|此女", left):
            if RE_NEG.search(ctx):
                _add_score(scores, "单依纯本人", 3.5, evidence, "她→单(负面)")
            elif RE_DEFEND_SHAN.search(ctx):
                _add_score(scores, "其他/事件", 2.0, evidence, "她→单(维护)")

    for m in RE_MALE_PRON.finditer(text):
        left = text[max(0, m.start() - 80) : m.start()]
        right = text[m.end() : min(len(text), m.end() + 40)]
        ctx = left + m.group() + right
        if RE_LI_ALIAS.search(left) or "浩哥" in left:
            if RE_NEG.search(ctx) or re.search(r"抄|侵权|甩|买|装|活人|眼|心胸", ctx, re.I):
                _add_score(scores, "李荣浩", 3.5, evidence, "他→李(负面)")
            elif RE_DEFEND_LI.search(ctx):
                _add_score(scores, "其他/事件", 1.5, evidence, "他→李(维护)")


def _score_event_and_cyber(text: str, scores: dict[str, float], evidence: list[str]) -> None:
    if RE_EVENT.search(text) or _RE_COPYRIGHT.search(text):
        if not RE_SHAN_ALIAS.search(text) and not RE_LI_ALIAS.search(text):
            _add_score(scores, "其他/事件", 4.0, evidence, "纯事件/版权")
        else:
            _add_score(scores, "其他/事件", 2.0, evidence, "事件框架")
    if RE_ATTACK_CYBER.search(text):
        _add_score(scores, "其他/事件", 2.5, evidence, "网暴/媒体/对立")


def resolve_attack_target(text: str) -> TargetAnnotation:
    text = str(text or "").strip()
    scores: dict[str, float] = {k: 0.0 for k in TARGET_ORDER}
    evidence: list[str] = []

    if not text:
        return TargetAnnotation("其他/事件", "其他/事件", "其他/事件", scores, "空文本")

    _score_named_entities(text, scores, evidence)
    _score_pronouns(text, scores, evidence)
    _score_event_and_cyber(text, scores, evidence)

    # 粉丝/团队主体：「单依纯粉丝」攻击 → 团队或事件，非单本人
    if re.search(r"单依纯的?粉丝|单粉|纯牛奶", text, re.I) and RE_NEG.search(text):
        if not is_personal_attack_on_shan(text):
            scores["单依纯本人"] = max(0, scores.get("单依纯本人", 0) - 3)
            _add_score(scores, "团队", 2.0, evidence, "指向粉丝群体")

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    primary, top = ranked[0]
    secondary = ranked[1][0] if len(ranked) > 1 else None
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top <= 0:
        if RE_EVENT.search(text):
            primary = "其他/事件"
        elif RE_TEAM.search(text):
            primary = "团队"
        elif RE_LI_ALIAS.search(text):
            primary = "李荣浩"
        elif RE_SHAN_ALIAS.search(text):
            primary = "单依纯本人"
        else:
            primary = "其他/事件"
        evidence.append("低分兜底")

    is_mixed = second_score >= 2 and (top - second_score) <= 2.5
    ev_str = "；".join(evidence[:6]) if evidence else "语境推断"

    entity = _match_entity(text)
    if entity:
        display, group = entity
    else:
        display, group = _display_from_legacy(primary)

    return TargetAnnotation(
        attack_target=primary,
        attack_target_display=display,
        attack_target_group=group,
        target_scores={k: round(v, 2) for k, v in scores.items()},
        target_evidence=ev_str,
        is_mixed=is_mixed,
        secondary_target=secondary if is_mixed else None,
    )

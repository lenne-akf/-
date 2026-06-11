from __future__ import annotations
# -*- coding: utf-8 -*-
"""
用户主题网络 · 四阶段静态拼图（2×2）

从 topic_network 快照中选取 4 个代表阶段，输出：
  output/topic_network_four_phases.png

阶段叙事：版权集聚 → 偏移初现 → 混异化扩散 → 人攻倾向
"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# paths via _paths
ANALYSIS_JSON = OUT / "analysis_viz.json"
OUT_PNG = OUT / "topic_network_four_phases.png"

# 四阶段：2025 酝酿(人攻=0) → 2026 爆发期(03-28~04-05) → 混异化 → 人攻倾向
PHASE_PICKS: list[tuple[int, str]] = [
    (0, "阶段一 · 酝酿期 · 版权集聚"),
    (10, "阶段二 · 爆发期 · 偏移初现"),
    (11, "阶段三 · 混异化扩散"),
    (12, "阶段四 · 人攻倾向"),
]

_THEME = {
    "bg": "#0a0608",
    "bg_grad": "#1a1220",
    "ink": "#f5e6b8",
    "ink_muted": "#a89888",
    "link": "#64748b",
    "attack": "#9a3050",
}


def _load_topic_network() -> dict:
    if not ANALYSIS_JSON.exists():
        raise FileNotFoundError(f"缺少 {ANALYSIS_JSON}，请先运行 build_web_json.py")
    data = json.loads(ANALYSIS_JSON.read_text(encoding="utf-8"))
    spec = data.get("topic_network") or {}
    if not spec.get("snapshots"):
        raise ValueError("analysis_viz.json 中无 topic_network 快照")
    return spec


def _date_range_label(snap: dict) -> str:
    d0 = str(snap.get("date_start") or "")[:10]
    d1 = str(snap.get("date_end") or "")[:10]
    if d0 and d1 and d0 != d1:
        return f"{d0} ~ {d1}"
    return d0 if d0 else str(snap.get("label") or "")


def _network_attack_pct(snap: dict) -> float:
    """网络层面人攻强度：当周活跃用户评论向量中人攻权重均值（%）。"""
    active = [n for n in snap.get("nodes") or [] if int(n.get("count") or 0) > 0]
    if not active:
        return 0.0
    return float(sum(float(n.get("t4_share") or 0) for n in active) / len(active) * 100.0)


def _draw_panel(ax, spec: dict, phase_index: int, stage_title: str) -> None:
    snap = spec["snapshots"][str(phase_index)]
    layout = spec.get("topic_layout") or {}
    topics = {t["topic_id"]: t for t in spec.get("topics") or []}

    ax.set_facecolor(_THEME["bg"])
    ax.set_xlim(0, 1)
    ax.set_ylim(1, 0)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.add_patch(
        plt.Circle((0.5, 0.48), 0.42, fill=True, color=_THEME["bg_grad"], alpha=0.35, zorder=0)
    )

    for tid_str, pos in layout.items():
        tid = int(tid_str)
        tm = topics.get(tid, {})
        color = tm.get("color") or "#888"
        x, y = pos[0], pos[1]
        is_t4 = tid == 4
        ring_r = 0.038 if len(layout) >= 6 else 0.048
        ax.add_patch(
            plt.Circle(
                (x, y), ring_r * 1.15, fill=False, ec=color,
                lw=2.8 if is_t4 else 2.0, alpha=0.55 if is_t4 else 0.45, zorder=2,
            )
        )
        ax.add_patch(
            plt.Circle((x, y), ring_r, fill=True, fc=color, alpha=0.12, ec=color, lw=1.8, zorder=2)
        )
        name = tm.get("short_name") or tm.get("name") or f"主题{tid}"
        if len(name) > 7:
            name = name[:6] + "…"
        ax.text(
            x, y + ring_r + 0.035, f"{tid} {name}", ha="center", va="top",
            fontsize=7.5, color=_THEME["ink"], fontweight="bold", zorder=3,
        )

    node_map = {n["id"]: n for n in snap.get("nodes") or []}
    for lk in snap.get("links") or []:
        a = node_map.get(lk["source"])
        b = node_map.get(lk["target"])
        if not a or not b:
            continue
        w = float(lk.get("weight") or 0)
        alpha = min(0.75, 0.15 + w * 0.45)
        ax.plot(
            [a["tx"], b["tx"]], [a["ty"], b["ty"]], color=_THEME["link"],
            alpha=alpha, lw=0.6 + w * 1.2, zorder=1,
        )

    active = [n for n in snap.get("nodes") or [] if int(n.get("count") or 0) > 0]
    for n in active:
        r = max(0.008, min(0.022, float(n.get("r") or 8) / 520))
        alpha = float(n.get("opacity") or 0.85)
        ax.add_patch(
            plt.Circle(
                (n["tx"], n["ty"]), r, fc=n.get("color") or "#888",
                ec="white", lw=0.3, alpha=alpha, zorder=4,
            )
        )

    dom_name = snap.get("dominant_topic_name") or "—"
    dom_pct = snap.get("dominant_topic_pct") or 0
    t4_pct = _network_attack_pct(snap)
    dr = _date_range_label(snap)
    dom_short = dom_name if len(dom_name) <= 10 else dom_name[:9] + "…"

    ax.text(
        0.03, 0.04, stage_title, transform=ax.transAxes, fontsize=11.5,
        fontweight="bold", color=_THEME["ink"], va="bottom", ha="left", zorder=5,
    )
    ax.text(
        0.03, 0.10, dr, transform=ax.transAxes, fontsize=8.5,
        color=_THEME["ink_muted"], va="bottom", ha="left", zorder=5,
    )
    attack_label = f"人攻 {t4_pct:.1f}%" if t4_pct >= 0.05 else "人攻 0%"
    ax.text(
        0.97, 0.04,
        f"主导 {dom_short} {dom_pct:.0f}% · {attack_label}",
        transform=ax.transAxes, fontsize=8,
        color=_THEME["attack"] if t4_pct >= 0.5 else _THEME["ink_muted"],
        va="bottom", ha="right", zorder=5,
    )


def plot_four_phases(
    spec: dict | None = None,
    picks: list[tuple[int, str]] | None = None,
    out_path: Path = OUT_PNG,
) -> Path:
    spec = spec or _load_topic_network()
    picks = picks or PHASE_PICKS
    n_snap = len(spec.get("phases") or [])
    for idx, _ in picks:
        if idx >= n_snap:
            raise ValueError(f"阶段 index={idx} 超出快照范围 (0~{n_snap - 1})")

    fig, axes = plt.subplots(2, 2, figsize=(14, 12), facecolor=_THEME["bg"])
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.04, wspace=0.06, hspace=0.08)

    for ax, (phase_i, title) in zip(axes.flat, picks):
        _draw_panel(ax, spec, phase_i, title)

    fig.suptitle(
        "用户主题网络迁移 · 四阶段静态呈现",
        fontsize=16, fontweight="bold", color=_THEME["ink"], y=0.97,
    )
    fig.text(
        0.5, 0.935,
        "节点=用户 · 颜色=当周主导主题 · 位置偏移=人身攻击评论占比 · 边=主题向量相似",
        ha="center", fontsize=9.5, color=_THEME["ink_muted"],
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, facecolor=_THEME["bg"], bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "PingFang SC", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    spec = _load_topic_network()
    path = plot_four_phases(spec)
    print(f"已保存: {path}")
    for idx, title in PHASE_PICKS:
        snap = spec["snapshots"][str(idx)]
        print(f"  [{idx}] {title}  {_date_range_label(snap)}")


if __name__ == "__main__":
    main()

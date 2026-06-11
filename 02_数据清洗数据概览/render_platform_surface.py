# -*- coding: utf-8 -*-
"""
生成三平台「时间 × 评论量」层叠 3D 曲面静态图（科幻风 PNG）。

供 dispute_dashboard.html 展示；数据口径与 build_web_json.build_surface_3d 一致。
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import OUT  # noqa: E402

OUT_PNG = OUT / "platform_time_surface.png"

LAYER_CFG = [
    ("douyin", "抖音", "#ff6bcb", "#9b59b6", 2.0),
    ("weibo", "微博", "#00e5ff", "#0984e3", 7.0),
    ("xiaohongshu", "小红书", "#7fff7a", "#00b894", 12.0),
]


def _setup_font() -> None:
    for name in ("Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC"):
        try:
            font_manager.findfont(name, fallback_to_default=False)
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return
        except Exception:
            continue
    plt.rcParams["axes.unicode_minus"] = False


def _smooth(values: np.ndarray, window: int = 3) -> np.ndarray:
    if len(values) < 3:
        return values.astype(float)
    kernel = np.ones(window) / window
    return np.convolve(values.astype(float), kernel, mode="same")


def _layer_mesh(
    values: list[int],
    y_center: float,
    z_base: float,
    z_scale: float,
    n_y: int = 28,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(values)
    if n == 0:
        return np.zeros((2, 2)), np.zeros((2, 2)), np.zeros((2, 2))
    smoothed = _smooth(np.array(values, dtype=float))
    x_fine = np.linspace(0, max(n - 1, 1), max(n * 5, 48))
    yi = np.linspace(-1.15, 1.15, n_y)
    Xi, Yi = np.meshgrid(x_fine, y_center + yi * 1.35)
    Zi = np.zeros_like(Xi)
    for j, y_off in enumerate(yi):
        bump_row = np.exp(-(y_off**2) * 2.2)
        for i, x in enumerate(x_fine):
            idx = int(round(x))
            idx = min(max(idx, 0), len(smoothed) - 1)
            Zi[j, i] = z_base + smoothed[idx] * bump_row * z_scale
    return Xi, Yi, Zi


def render_surface_png(surface_spec: dict, out_path: Path | None = None) -> Path:
    """根据 surface_3d JSON 结构绘制并保存 PNG。"""
    out_path = out_path or OUT_PNG
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dates = surface_spec.get("dates") or []
    layers_raw = {x["platform"]: x for x in surface_spec.get("layers") or []}
    if not dates or not layers_raw:
        raise ValueError("surface_3d 无有效 dates/layers，跳过静态曲面图")

    _setup_font()
    fig = plt.figure(figsize=(16, 9), facecolor="#060d18")
    ax = fig.add_subplot(111, projection="3d", facecolor="#060d18")

    n = len(dates)
    peak_vals = [
        max(layer["values"])
        for layer in layers_raw.values()
        if layer.get("values")
    ]
    peak = max(peak_vals) if peak_vals else 1
    z_scale = max(0.015, 80.0 / max(peak, 1))
    z_cursor = 0.0
    z_gap = max(80, z_scale * 400)

    for pid, label, face, edge, y_center in LAYER_CFG:
        layer = layers_raw.get(pid)
        if not layer:
            continue
        values = layer.get("values") or [0] * n
        Xi, Yi, Zi = _layer_mesh(values, y_center, z_cursor, z_scale)
        ax.plot_surface(
            Xi,
            Yi,
            Zi,
            color=face,
            alpha=0.78,
            edgecolor=edge,
            linewidth=0.12,
            antialiased=True,
            shade=True,
            rcount=Zi.shape[0],
            ccount=Zi.shape[1],
        )
        z_cursor = float(Zi.max()) + z_gap

    # 底座网格
    gx = np.linspace(0, max(n - 1, 1), 24)
    gy = np.linspace(0, 14, 10)
    Gx, Gy = np.meshgrid(gx, gy)
    Gz = np.zeros_like(Gx)
    ax.plot_wireframe(
        Gx, Gy, Gz,
        color=(0, 0.9, 1, 0.12),
        linewidth=0.35,
        rstride=2,
        cstride=2,
    )

    ax.set_xlim(0, max(n - 1, 1))
    ax.set_ylim(0, 14)
    ax.set_zlim(0, z_cursor * 1.05)
    ax.set_xlabel("时间 →", color="#8ec8ff", fontsize=11, labelpad=10)
    ax.set_ylabel("", color="#8ec8ff")
    ax.set_zlabel("评论量", color="#8ec8ff", fontsize=11, labelpad=8)
    ax.tick_params(colors="#6a8aaa", labelsize=8)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.grid(True, color=(0, 0.85, 1, 0.08), linestyle="--", linewidth=0.4)
    ax.view_init(elev=26, azim=-58)

    step = max(1, n // 8)
    tick_idx = list(range(0, n, step))
    if tick_idx[-1] != n - 1:
        tick_idx.append(n - 1)
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(
        [dates[i][5:] if len(dates[i]) >= 10 else dates[i] for i in tick_idx],
        rotation=25,
        ha="right",
    )

    gran = "按周" if surface_spec.get("granularity") == "week" else "按日"
    title = f"三平台评论时空层叠曲面（{gran} · {n} 时点）"
    fig.suptitle(title, color="#e8f4ff", fontsize=15, fontweight="bold", y=0.96)
    leg_y = 0.88
    for i, (_, lab, face, _, _) in enumerate(LAYER_CFG):
        if layers_raw.get(LAYER_CFG[i][0]):
            fig.text(
                0.72 + (i % 3) * 0.09,
                leg_y - (i // 3) * 0.04,
                f"■ {lab}",
                color=face,
                fontsize=11,
                fontweight="bold",
            )

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out_path, dpi=200, facecolor="#060d18", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    print(f"[静态曲面] 已保存: {out_path}")
    return out_path


if __name__ == "__main__":
    import json
    from build_web_json import OUT_OVERVIEW

    spec = json.loads(OUT_OVERVIEW.read_text(encoding="utf-8"))["surface_3d"]
    render_surface_png(spec)

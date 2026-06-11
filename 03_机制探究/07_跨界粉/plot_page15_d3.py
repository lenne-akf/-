# -*- coding: utf-8 -*-
"""页15 D3 风格可视化：Sankey + 平行坐标，并导出 PNG 供 PPT。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT_DIR))
from verify_page15 import (  # noqa: E402
    CORE_ARTISTS,
    load_merged,
)

HTML_PATH = OUT_DIR / "page15_d3_viz.html"
DATA_PATH = OUT_DIR / "d3_viz_data.json"


def bucket_group(name: str) -> str:
    if name == "单依纯":
        return "单依纯粉"
    if name == "李荣浩":
        return "李荣浩粉"
    if name in ("陈楚生", "黄霄云", "周深"):
        return f"{name}粉"
    return "其他跨界粉"


def build_viz_data(df) -> dict:
    df = df.copy()
    df["viz_group"] = df["粉籍"].map(bucket_group)

    sankey_groups = ["单依纯粉", "李荣浩粉", "陈楚生粉", "黄霄云粉", "周深粉", "其他跨界粉"]
    mode_order = ["事件评价", "版权议题/类比", "竞品对线", "娱乐玩梗", "劝阻捆绑", "其他/中性"]

    links_raw = (
        df.groupby(["viz_group", "discourse_mode"])
        .size()
        .reset_index(name="value")
    )
    sankey_links = []
    for _, row in links_raw.iterrows():
        g, m, v = row["viz_group"], row["discourse_mode"], int(row["value"])
        if g not in sankey_groups or m not in mode_order or v <= 0:
            continue
        sankey_links.append({"source": g, "target": m, "value": v})

    # 平行坐标：核心对照群体
    parallel_groups = ["单依纯粉", "李荣浩粉", "陈楚生粉", "黄霄云粉", "周深粉", "跨界粉合计"]
    parallel_rows = []
    for g in parallel_groups:
        sub = df if g == "跨界粉合计" else df[df["viz_group"] == g]
        if g == "跨界粉合计":
            sub = df[~df["粉籍"].isin(CORE_ARTISTS)]
        n = len(sub)
        if n == 0:
            continue
        parallel_rows.append({
            "group": g,
            "n": n,
            "事件评价": round((sub["discourse_mode"] == "事件评价").mean() * 100, 1),
            "版权类比": round((sub["discourse_mode"] == "版权议题/类比").mean() * 100, 1),
            "竞品对线": round((sub["discourse_mode"] == "竞品对线").mean() * 100, 1),
            "人身指责": round((sub["content_layer"] == "人身指责").mean() * 100, 1),
            "攻击参与": round(sub["is_attack"].mean() * 100, 1),
        })

    return {
        "meta": {
            "title": "页15 · 跨界粉话语取向分化",
            "subtitle": "推手池 × 可识别粉籍 · 《李白》侵权舆情评论",
            "total_comments": int(len(df)),
        },
        "sankey": {
            "groups": sankey_groups,
            "modes": mode_order,
            "links": sankey_links,
        },
        "parallel": parallel_rows,
        "group_colors": {
            "单依纯粉": "#8B6B8E",
            "李荣浩粉": "#3A5C50",
            "陈楚生粉": "#7A6B7D",
            "黄霄云粉": "#B86B5C",
            "周深粉": "#5A7A8C",
            "其他跨界粉": "#A89F94",
            "跨界粉合计": "#6B8F71",
        },
        "mode_colors": {
            "事件评价": "#4E7C6A",
            "版权议题/类比": "#4A6FA5",
            "竞品对线": "#B54548",
            "娱乐玩梗": "#C4843A",
            "劝阻捆绑": "#8E7F9E",
            "其他/中性": "#C5C0B8",
        },
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>页15 D3 · 跨界粉话语取向</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Noto Sans SC", "Microsoft YaHei", sans-serif;
    background: #F7F5F2;
    color: #1C1A17;
    padding: 40px 48px 56px;
  }
  .page { max-width: 1280px; margin: 0 auto; }
  header { margin-bottom: 36px; }
  h1 {
    font-size: 26px; font-weight: 700; letter-spacing: -0.02em;
    color: #1C1A17; margin-bottom: 8px;
  }
  .subtitle { font-size: 13px; color: #6B6560; line-height: 1.6; }
  .subtitle span { font-family: "IBM Plex Mono", monospace; color: #8A8278; }
  .grid {
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 28px;
    align-items: start;
  }
  .panel {
    background: #FFFCF9;
    border: 1px solid #E8E3DC;
    border-radius: 12px;
    padding: 24px 20px 16px;
  }
  .panel-title {
    font-size: 14px; font-weight: 600; color: #3D3832;
    margin-bottom: 4px; padding-left: 2px;
  }
  .panel-desc {
    font-size: 11px; color: #8A8278; margin-bottom: 16px; padding-left: 2px;
    line-height: 1.5;
  }
  .caption {
    font-size: 10px; color: #A39E96; margin-top: 10px; padding-left: 2px;
    font-family: "IBM Plex Mono", monospace;
  }
  svg { display: block; width: 100%; overflow: visible; }
  .link { fill: none; stroke-opacity: 0.42; transition: stroke-opacity 0.2s; }
  .link:hover { stroke-opacity: 0.72; }
  .node rect { cursor: default; rx: 3; ry: 3; }
  .node-label {
    font-size: 11px; font-weight: 500; fill: #2A2724;
    pointer-events: none;
  }
  .node-value {
    font-size: 9px; fill: #8A8278;
    font-family: "IBM Plex Mono", monospace;
    pointer-events: none;
  }
  .axis-label { font-size: 10px; fill: #6B6560; }
  .par-line { fill: none; stroke-width: 2; stroke-linecap: round; opacity: 0.88; }
  .par-line.dim { opacity: 0.12; }
  .par-dot { stroke: #FFFCF9; stroke-width: 1.5; }
  .legend-item { font-size: 10px; fill: #5A554E; }
  .tooltip {
    position: fixed; pointer-events: none; opacity: 0;
    background: #1C1A17; color: #F7F5F2; font-size: 11px;
    padding: 8px 12px; border-radius: 6px; line-height: 1.5;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 99;
    max-width: 240px;
  }
  .tooltip strong { color: #fff; font-weight: 600; }
  @media (max-width: 960px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="page">
  <header>
    <h1 id="main-title"></h1>
    <p class="subtitle" id="main-sub"></p>
  </header>
  <div class="grid">
    <div class="panel">
      <div class="panel-title">Sankey · 粉籍群体 → 话语模式</div>
      <div class="panel-desc">D3 Sankey 布局：左为粉籍来源，右为话语编码；流带宽度 = 评论条数。可悬停查看具体流量。</div>
      <div id="sankey-wrap"></div>
      <p class="caption">Observable / D3.js sankey · 数据：可识别粉籍推手评论</p>
    </div>
    <div class="panel">
      <div class="panel-title">Parallel Coordinates · 话语指标对照</div>
      <div class="panel-desc">平行坐标：五维指标跨群体对比。跨界粉「竞品对线」「人身指责」轴明显偏低，与单粉形成形态差异。</div>
      <div id="parallel-wrap"></div>
      <p class="caption">D3 parallel coordinates · 悬停高亮单条轨迹</p>
    </div>
  </div>
</div>
<div class="tooltip" id="tip"></div>
<script>
const DATA = __DATA_JSON__;

document.getElementById("main-title").textContent = DATA.meta.title;
document.getElementById("main-sub").innerHTML =
  DATA.meta.subtitle + " · 合计 <span>" + DATA.meta.total_comments + "</span> 条匹配评论";

const tip = d3.select("#tip");
function showTip(html, ev) {
  tip.style("opacity", 1).html(html)
    .style("left", (ev.clientX + 14) + "px")
    .style("top", (ev.clientY - 10) + "px");
}
function hideTip() { tip.style("opacity", 0); }

// ── Sankey ──────────────────────────────────────────────
(function drawSankey() {
  const wrap = d3.select("#sankey-wrap");
  const W = 680, H = 520;
  const margin = { top: 12, right: 120, bottom: 12, left: 108 };
  const svg = wrap.append("svg").attr("viewBox", `0 0 ${W} ${H}`);

  const groups = DATA.sankey.groups;
  const modes = DATA.sankey.modes;
  const nodeNames = [...groups, ...modes];
  const nodeIndex = Object.fromEntries(nodeNames.map((d, i) => [d, i]));

  const sankey = d3.sankey()
    .nodeId(d => d.name)
    .nodeAlign(d3.sankeyJustify)
    .nodeWidth(14)
    .nodePadding(14)
    .extent([[margin.left, margin.top], [W - margin.right, H - margin.bottom]]);

  const graph = sankey({
    nodes: nodeNames.map(name => ({
      name,
      side: groups.includes(name) ? "left" : "right",
    })),
    links: DATA.sankey.links.map(d => ({
      source: d.source,
      target: d.target,
      value: d.value,
    })),
  });

  const gColors = DATA.group_colors;
  const mColors = DATA.mode_colors;
  function nodeColor(name) {
    return gColors[name] || mColors[name] || "#A89F94";
  }

  const linkG = svg.append("g");
  linkG.selectAll(".link")
    .data(graph.links)
    .join("path")
    .attr("class", "link")
    .attr("d", d3.sankeyLinkHorizontal())
    .attr("stroke", d => nodeColor(d.source.name))
    .attr("stroke-width", d => Math.max(1, d.width))
    .on("mousemove", (ev, d) => {
      showTip(`<strong>${d.source.name}</strong> → <strong>${d.target.name}</strong><br/>${d.value} 条评论`, ev);
      d3.selectAll(".link").classed("dim", true);
      d3.select(ev.currentTarget).classed("dim", false).style("stroke-opacity", 0.85);
    })
    .on("mouseleave", () => {
      hideTip();
      d3.selectAll(".link").classed("dim", false).style("stroke-opacity", null);
    });

  const nodeG = svg.append("g");
  nodeG.selectAll(".node")
    .data(graph.nodes)
    .join("g")
    .attr("class", "node")
    .attr("transform", d => `translate(${d.x0},${d.y0})`);

  nodeG.selectAll(".node").append("rect")
    .attr("height", d => Math.max(1, d.y1 - d.y0))
    .attr("width", d => d.x1 - d.x0)
    .attr("fill", d => nodeColor(d.name));

  nodeG.selectAll(".node").each(function(d) {
    const g = d3.select(this);
    const isLeft = d.side === "left";
    const x = isLeft ? -8 : (d.x1 - d.x0) + 8;
    const anchor = isLeft ? "end" : "start";
    g.append("text")
      .attr("class", "node-label")
      .attr("x", x).attr("y", (d.y1 - d.y0) / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", anchor)
      .text(d.name);
    g.append("text")
      .attr("class", "node-value")
      .attr("x", x).attr("y", (d.y1 - d.y0) / 2 + 13)
      .attr("text-anchor", anchor)
      .text(d.value + "条");
  });
})();

// ── Parallel Coordinates ────────────────────────────────
(function drawParallel() {
  const wrap = d3.select("#parallel-wrap");
  const W = 480, H = 420;
  const margin = { top: 28, right: 24, bottom: 36, left: 24 };
  const svg = wrap.append("svg").attr("viewBox", `0 0 ${W} ${H}`);

  const dims = [
    { key: "事件评价", label: "事件评价" },
    { key: "版权类比", label: "版权类比" },
    { key: "竞品对线", label: "竞品对线" },
    { key: "人身指责", label: "人身指责" },
    { key: "攻击参与", label: "攻击参与" },
  ];
  const rows = DATA.parallel;
  const x = d3.scalePoint().domain(dims.map(d => d.key)).range([margin.left, W - margin.right]);
  const y = {};
  dims.forEach(dim => {
    y[dim.key] = d3.scaleLinear().domain([0, 100]).range([H - margin.bottom, margin.top]);
  });

  // axes
  dims.forEach(dim => {
    const ax = svg.append("g").attr("transform", `translate(${x(dim.key)},0)`);
    ax.call(d3.axisLeft(y[dim.key]).ticks(4).tickSize(-W + margin.left + margin.right).tickFormat(d => d + "%"));
    ax.selectAll(".tick line").attr("stroke", "#EDE8E1").attr("stroke-dasharray", "2,3");
    ax.selectAll(".domain").remove();
    ax.selectAll(".tick text").attr("class", "axis-label").attr("x", -6);
    ax.append("text")
      .attr("class", "axis-label")
      .attr("y", margin.top - 12)
      .attr("text-anchor", "middle")
      .attr("font-weight", 600)
      .attr("fill", "#3D3832")
      .text(dim.label);
  });

  const line = d3.line().defined(d => d[1] != null).x(d => x(d[0])).y(d => y[d[0]](d[1]));
  const gColors = DATA.group_colors;

  const paths = svg.append("g").selectAll(".par-line")
    .data(rows)
    .join("path")
    .attr("class", "par-line")
    .attr("stroke", d => gColors[d.group] || "#6B6560")
    .attr("d", d => line(dims.map(dim => [dim.key, d[dim.key]])))
    .on("mousemove", (ev, d) => {
      showTip(`<strong>${d.group}</strong> (n=${d.n})<br/>` +
        dims.map(dim => `${dim.label}: ${d[dim.key]}%`).join("<br/>"), ev);
      paths.classed("dim", true);
      d3.select(ev.currentTarget).classed("dim", false).raise();
    })
    .on("mouseleave", () => { hideTip(); paths.classed("dim", false); });

  svg.append("g").selectAll(".par-dot")
    .data(rows.flatMap(d => dims.map(dim => ({ group: d.group, key: dim.key, val: d[dim.key], n: d.n }))))
    .join("circle")
    .attr("class", "par-dot")
    .attr("cx", d => x(d.key))
    .attr("cy", d => y[d.key](d.val))
    .attr("r", 3.5)
    .attr("fill", d => gColors[d.group] || "#6B6560");

  // legend
  const leg = svg.append("g").attr("transform", `translate(${margin.left}, ${H - 14})`);
  rows.forEach((d, i) => {
    const item = leg.append("g").attr("transform", `translate(${i * 72}, 0)`);
    item.append("line").attr("x1", 0).attr("x2", 14).attr("y1", 0).attr("y2", 0)
      .attr("stroke", gColors[d.group]).attr("stroke-width", 2);
    item.append("text").attr("class", "legend-item").attr("x", 18).attr("y", 4)
      .text(d.group.replace("粉", ""));
  });
})();
</script>
</body>
</html>
"""


def export_html(data: dict) -> None:
    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    HTML_PATH.write_text(html, encoding="utf-8")
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def export_png() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright 未安装，跳过 PNG。请直接打开 HTML 或使用浏览器截图。")
        return

    png_s = OUT_DIR / "fig_d3_sankey_parallel.png"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
            page.goto(HTML_PATH.as_uri())
            page.wait_for_timeout(1500)
            page.screenshot(path=str(png_s), full_page=True)
            browser.close()
        print("PNG:", png_s)
    except Exception as exc:
        print("PNG 导出失败:", exc)
        print("请打开 HTML 手动截图，或运行: playwright install chromium")


def export_plotly_png(data: dict) -> None:
    """Plotly 静态导出（D3 风格配色），供 PPT 直接使用。"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    g_colors = data["group_colors"]
    m_colors = data["mode_colors"]
    groups = data["sankey"]["groups"]
    modes = data["sankey"]["modes"]
    node_labels = groups + modes
    node_colors = [g_colors.get(n, m_colors.get(n, "#A89F94")) for n in node_labels]

    link = data["sankey"]["links"]
    source_idx = [node_labels.index(d["source"]) for d in link]
    target_idx = [node_labels.index(d["target"]) for d in link]
    values = [d["value"] for d in link]

    def to_rgba(hex_color: str, a: float = 0.38) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{a})"

    link_colors = [to_rgba(g_colors.get(d["source"], "#A89F94")) for d in link]

    sankey = go.Sankey(
        arrangement="snap",
        node=dict(
            pad=18,
            thickness=16,
            line=dict(color="#E8E3DC", width=0.5),
            label=node_labels,
            color=node_colors,
            hovertemplate="%{label}<br>%{value} 条<extra></extra>",
        ),
        link=dict(
            source=source_idx,
            target=target_idx,
            value=values,
            color=link_colors,
            hovertemplate="%{source.label} → %{target.label}<br>%{value} 条<extra></extra>",
        ),
    )

    fig1 = go.Figure(sankey)
    fig1.update_layout(
        title=dict(
            text="粉籍群体 → 话语模式",
            x=0.02,
            xanchor="left",
            font=dict(size=18, color="#1C1A17"),
        ),
        font=dict(family="Microsoft YaHei, Noto Sans SC, sans-serif", size=12, color="#3D3832"),
        paper_bgcolor="#F7F5F2",
        margin=dict(l=24, r=24, t=64, b=24),
        height=560,
        width=960,
    )
    p1 = OUT_DIR / "fig_d3_sankey.png"
    fig1.write_image(str(p1), scale=2)
    print("PNG:", p1)

    rows = data["parallel"]
    dims = ["事件评价", "版权类比", "竞品对线", "人身指责", "攻击参与"]
    x_pos = list(range(len(dims)))

    fig2 = go.Figure()
    for r in rows:
        y_vals = [r[d] for d in dims]
        color = g_colors.get(r["group"], "#6B6560")
        fig2.add_trace(
            go.Scatter(
                x=x_pos,
                y=y_vals,
                mode="lines+markers",
                name=r["group"].replace("粉", ""),
                line=dict(color=color, width=2.8),
                marker=dict(size=7, color=color, line=dict(width=1, color="#FFFCF9")),
                hovertemplate="%{fullData.name}<br>%{y:.1f}%<extra></extra>",
            )
        )
    fig2.update_layout(
        title=dict(
            text="话语指标平行坐标对照",
            x=0.02,
            xanchor="left",
            font=dict(size=18, color="#1C1A17"),
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=x_pos,
            ticktext=dims,
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            title="占比 (%)",
            range=[-2, 105],
            gridcolor="#EDE8E1",
            zeroline=False,
        ),
        paper_bgcolor="#F7F5F2",
        plot_bgcolor="#FFFCF9",
        font=dict(family="Microsoft YaHei, sans-serif", color="#3D3832"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=56, r=24, t=88, b=48),
        height=480,
        width=880,
    )
    p2 = OUT_DIR / "fig_d3_parallel.png"
    fig2.write_image(str(p2), scale=2)
    print("PNG:", p2)

    par_dims = [
        dict(range=[0, 100], label=d, values=[r[d] for r in rows], tickformat=".0f")
        for d in dims
    ]

    combo = make_subplots(
        rows=2,
        cols=1,
        specs=[[{"type": "sankey"}], [{"type": "xy"}]],
        row_heights=[0.58, 0.42],
        vertical_spacing=0.08,
    )
    combo.add_trace(sankey, row=1, col=1)
    for r in rows:
        color = g_colors.get(r["group"], "#6B6560")
        combo.add_trace(
            go.Scatter(
                x=x_pos,
                y=[r[d] for d in dims],
                mode="lines+markers",
                name=r["group"].replace("粉", ""),
                line=dict(color=color, width=2.2),
                marker=dict(size=6, color=color),
                showlegend=False,
            ),
            row=2,
            col=1,
        )
    combo.update_xaxes(tickmode="array", tickvals=x_pos, ticktext=dims, row=2, col=1)
    combo.update_yaxes(title="占比 (%)", range=[-2, 105], row=2, col=1)
    combo.update_layout(
        title=dict(text="页15 · 跨界粉话语取向分化", x=0.5, font=dict(size=20)),
        paper_bgcolor="#F7F5F2",
        font=dict(family="Microsoft YaHei, sans-serif"),
        height=980,
        width=960,
        margin=dict(t=72, b=24),
    )
    p3 = OUT_DIR / "fig_d3_combo_竖排.png"
    combo.write_image(str(p3), scale=2)
    print("PNG:", p3)


def main():
    df = load_merged()
    data = build_viz_data(df)
    export_html(data)
    export_plotly_png(data)
    export_png()
    print("HTML:", HTML_PATH)
    print("Data:", DATA_PATH)


if __name__ == "__main__":
    main()

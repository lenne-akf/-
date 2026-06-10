================================================================================
  传播学项目 · 代码提取说明
  路径：F:\可视化\传播学\代码
  更新：2026-06-10
================================================================================

本目录从原项目中提取了四类核心脚本，已去除硬编码 Cookie 与微信本地路径等私人信息。
运行前请先阅读「隐私与安全」一节。

--------------------------------------------------------------------------------
目录结构
--------------------------------------------------------------------------------

代码/
├── README.txt                 ← 本说明
├── cookies.txt                ← 微博 Cookie（需自行填写，已 .gitignore 不上传）
├── .gitignore                 ← 忽略 cookies.txt
│
├── 01_微博爬取/               ← Search + Detail + 快速评论爬取
│   ├── run_uv.bat
│   ├── prepare_search_for_detail.py
│   ├── apply_detail_batch.py
│   ├── export_detail_tables.py
│   └── fetch_comments_fast.py
│
├── 02_强度桑基图/
│   └── page11_sankey_intensity.py
│
├── 03_核心群体/
│   ├── recalc_framework_stats.py
│   └── plot_page14_charts.py
│
└── 04_跨界粉/
    ├── verify_page15.py
    └── plot_page15_d3.py

--------------------------------------------------------------------------------
隐私与安全（重要）
--------------------------------------------------------------------------------

【已在本提取包中处理】
  · fetch_comments_fast.py 原从 MediaCrawler/config/base_config.py 读 Cookie
    → 已改为 COOKIES = "cookies.txt"，运行时从 代码/cookies.txt 读取
  · verify_page15.py 原含微信本地路径（含 wxid）
    → 已改为项目内相对路径 数据/id粉籍/

【原项目中仍含私人信息、未复制到本目录的文件】
  文件名：MediaCrawler/config/base_config.py
    内容：变量 COOKIES = "..." 含完整微博登录凭证（SUB、SUBP、XSRF-TOKEN 等）
    建议：勿分享该文件；可清空 COOKIES 后改从 cookie.txt 手动同步

  文件名：数据/Cookie.txt
    内容：可能存有与 base_config 相同的 Cookie 备份
    建议：仅本地保留，勿上传

  文件名：weibo_crawl/fetch_comments_fast.py（原目录副本）
    内容：仍引用 base_config.py 中的 COOKIES（未更新）
    建议：以 代码/01_微博爬取/fetch_comments_fast.py 为准

  文件名：数据/id粉籍/merge_and_classify_fans.py（未提取）
    内容：引用 数据/Cookie.txt 爬用户主页判定粉籍
    建议：若使用需自行检查 Cookie 文件权限

【Cookie 配置方法】
  1. 编辑 代码/cookies.txt
  2. 浏览器登录 https://m.weibo.cn
  3. F12 → Network → 任意请求 → Request Headers → 复制 Cookie 整行
  4. 粘贴到 cookies.txt（保留一行即可，# 开头为注释）
  5. cookies.txt 已在 .gitignore 中，不会随 git 上传

--------------------------------------------------------------------------------
各 Python 文件功能说明
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
【01_微博爬取】Search → Detail 全流程 + 快速爬取
--------------------------------------------------------------------------------

  run_uv.bat
    MediaCrawler 启动脚本（依赖项目根目录 MediaCrawler 子项目，未整体复制）。
    支持：sync / playwright / login / search / detail / creator
    用法示例：
      cmd /c "F:\可视化\传播学\代码\01_微博爬取\run_uv.bat search"
      cmd /c "F:\可视化\传播学\代码\01_微博爬取\run_uv.bat detail"

  prepare_search_for_detail.py
    Search 结果后处理：
      · 按 note_id 去重
      · 事件相关性筛选（版权/侵权/双星等规则）
      · 按互动量排序，生成 detail 待爬列表
    输入：MediaCrawler/data/weibo/csv/search_contents_*.csv
    输出：01_微博爬取/output/
          - search_posts_deduped.csv
          - search_posts_event_related.csv
          - detail_note_ids.txt
          - detail_batches/batch_XX.txt

  apply_detail_batch.py
    将 output/detail_batches/batch_XX.txt 中的 note_id 写入
    MediaCrawler/config/weibo_config.py 的 WEIBO_SPECIFIED_ID_LIST，
    供 detail 模式按批爬取。
    用法：python apply_detail_batch.py --batch 1

  export_detail_tables.py
    detail 爬取完成后，合并 MediaCrawler 原始 CSV，输出整理表：
      - output/detail_posts.csv
      - output/detail_comments.csv

  fetch_comments_fast.py  ★ 快速爬取（评论）
    轻量评论爬取：Playwright 直接请求 m.weibo.cn/comments/hotflow API。
    比 MediaCrawler detail 模式更快，适合补抓评论。
    Cookie 来源：代码/cookies.txt（脚本内 COOKIES = "cookies.txt"）
    用法：
      python fetch_comments_fast.py
      python fetch_comments_fast.py --ids output/detail_note_ids.txt --max-comments 200
      python fetch_comments_fast.py --dry-run

  【推荐流程】
    1. 填写 代码/cookies.txt
    2. 配置 MediaCrawler/config/base_config.py（KEYWORDS、CRAWLER_TYPE 等）
    3. run_uv.bat search
    4. python prepare_search_for_detail.py
    5. python apply_detail_batch.py --batch 1
    6. run_uv.bat detail
    7. python export_detail_tables.py
    或：python fetch_comments_fast.py 快速补抓评论

--------------------------------------------------------------------------------
【02_强度桑基图】
--------------------------------------------------------------------------------

  page11_sankey_intensity.py
    绘制页11「强度分化桑基图」：
      · 方案 A：阶段 → 议题 → 低/高强度（主图，输出 PNG + HTML）
      · 方案 B：三阶段并行「议题·强度」池规模变化
    输入：02_强度桑基图/output/page11/page11_comments_scored.csv
          （需含 phase、content_layer、attack_score、excluded 等列；
           可从概览分析流水线生成后复制到该路径）
    输出：page11_sankey_intensity.png / .html
          page11_sankey_parallel.html
          page11_sankey_flows.csv
          page11_intensity_by_topic_phase.json
    依赖：pandas, plotly, kaleido（导出 PNG）

--------------------------------------------------------------------------------
【03_核心群体】页14 单粉 / 李粉话语取向
--------------------------------------------------------------------------------

  recalc_framework_stats.py
    对单依纯粉、李荣浩粉评论重新编码：
      · content_layer_v2（版权议题 / 职业评价 / 人身指责 / 其他）
      · stance_v2（护单/贬李、护李/贬单、中性等，含误判修正）
    统计「指责取向」「护主取向」占比。
    输入：03_核心群体/comments_单李粉.csv
    输出：comments_单李粉_corrected.csv
          framework_stats_corrected.json

  plot_page14_charts.py
    页14 可视化主脚本：堆叠条形图（话语层级）、发散条形图（框架取向）、
    竖排组合图等，自动调用 recalc_framework_stats.py。
    输入：summary_v2.json、comments_单李粉.csv（同目录）
    输出：fig1_话语层级.png、fig2_框架取向.png、fig_combo_竖排.png 等

--------------------------------------------------------------------------------
【04_跨界粉】页15 其他艺人粉籍话语分析
--------------------------------------------------------------------------------

  verify_page15.py
    页15 主脚本：联合粉籍表 + 推手评论 + 全量评论，编码并统计跨界粉话语特征。
    输入：
      - 数据/id粉籍/id.xlsx（优先）或 id粉籍_李白事件评论.csv
      - 数据/id粉籍/hidden_escalator_comments.csv
      - 数据/微博2/detail_comments.csv
    输出：comments_跨界粉.csv、summary.json、统计图 PNG、说明文本

  plot_page15_d3.py
    页15 D3 风格交互可视化（Sankey + 平行坐标），导出 HTML 与 PNG。
    依赖 verify_page15.load_merged() 加载数据。

  运行顺序建议：
    python verify_page15.py
    python plot_page15_d3.py

--------------------------------------------------------------------------------
环境与依赖（简要）
--------------------------------------------------------------------------------

  微博爬取：MediaCrawler/.venv_new、uv、Playwright Chromium
  可视化：pandas、matplotlib、plotly、kaleido、openpyxl（读 xlsx）

  分析脚本的数据文件需放在各子目录或 数据/ 下对应路径；
  首次运行前请确认输入 CSV 已就位。

================================================================================

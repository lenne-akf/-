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
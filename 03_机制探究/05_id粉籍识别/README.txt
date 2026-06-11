粉籍 ID 爬取与推断 — 使用说明
================================

一、环境依赖
------------
Python 3.10+，安装：

  pip install pandas openpyxl requests

微博爬取还需：在代码目录下放置 cookie 文件
小红书爬取：
  pip install xhshow pycryptodome playwright
  playwright install msedge


二、目录说明
------------
  data/                    四批原始 ID 输入
    id.xlsx                第 1 批
    id2.xlsx               第 2 批
    id3.xlsx               第 3 批
    id4.csv                第 4 批

  weibo_fandom_crawler.py  爬取 + 粉籍推断（核心）
  export_conf70.py         导出 conf70 整合表
  filter_conf80.py         艺人确认/误识别字典
  export_id3_id4_conf70.py id3、id4 分批导出


三、四批怎么跑（微博）
----------------------
在「粉籍id爬取」目录下打开终端，依次执行：

【第 1 批 id】
  python weibo_fandom_crawler.py --input data/id.xlsx
  python export_conf70.py --input weibo_fandom_result_id.xlsx --output id_粉籍整合_conf70_id.xlsx

【第 2 批 id2】
  python weibo_fandom_crawler.py --input data/id2.xlsx
  python export_conf70.py --input weibo_fandom_result_id2.xlsx --output id_粉籍整合_conf70_id2.xlsx

【第 3、4 批 id3 + id4】
  两批合并爬取时，需先准备带 origin 列的去重表 id3_id4_deduped.xlsx
  （可由 id3.xlsx、id4.csv 合并去重得到，origin 标注 id3.xlsx / id4.csv）。

  python weibo_fandom_crawler.py --input data/id3.xlsx --dedup id3_id4_deduped.xlsx --output weibo_fandom_result_id3_id4.xlsx --checkpoint crawl_checkpoint_id3_id4.json

  若 id3、id4 分两次爬，请将结果合并为 weibo_fandom_result_id3_id4.xlsx 后再导出。

  python export_id3_id4_conf70.py

  将生成：
    id_粉籍整合_conf70_id3.xlsx
    id_粉籍整合_conf70_id4.xlsx
    id_粉籍整合_conf70_id3_id4.xlsx

断点续爬：在 crawler 命令后加 --resume

判定规则：confidence >= 0.7 且 fan_score >= 2.0 进入 conf70 池；
从简介/微博中自动发现艺人名 + 情感词打分，不预设艺人名单。


四、最终四批怎么合并
--------------------
代码导出的是各批 conf70 表。
四批汇总步骤（Excel 手工，与本次作业最终成果一致）：
  1. 打开各批 id_粉籍整合_conf70_*.xlsx 的「确认艺人」或「id对应粉籍」sheet
  2. 追加 origin 列标注来源（id / id2 / id3 / id4）后纵向合并
  3. 人工复核：删除非艺人待核实行，修正明显误识别
  4. 保存为：id_粉籍整合_conf70_四批汇总_复核后.xlsx

（合并与复核为人工步骤，保证最终可视化用的是复核后表。）

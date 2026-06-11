# 数据清洗与数据概览

三平台评论合并清洗、情感分析、BERTopic、Web 驾驶舱 JSON 与静态图。

## 运行顺序

```powershell
cd 概览分析/数据清洗与数据概览
python preprocess_three_platforms.py
python sentiment_analysis.py
python bertopic_modeling.py
python build_web_json.py
```

## 主要产出

- `../output/cleaned_comments.csv`
- `../output/comments_with_topics.csv`
- `../output/overview_stats.json` · `analysis_viz.json`
- `../dispute_dashboard.html`

## 依赖

- 原始数据在 `../data/`（不含 Cookie）
- 停用词：`hit_stopwords.txt` 等（本目录）

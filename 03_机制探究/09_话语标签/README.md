# 话语标签

人身攻击话语的**标签化规则**与 **page14 可视化**（条形图 + 桑基 + 典型评论）。

## 脚本

| 文件 | 说明 |
|------|------|
| `discourse_label_features.py` | 18 类标签正则、攻击维度、`lbl_*` 特征（Logistic 复用） |
| `plot_page14_discourse_labeling.py` | 产出 `output/page14_discourse_labeling.png` |

## 运行

```powershell
cd 概览分析/话语标签
python plot_page14_discourse_labeling.py
```

前置：v5 池 user_id 列表、`output/comments_with_topics.csv`（见 `数据清洗与数据概览` 流水线）。

## 产出

- `../output/page14_discourse_labeling.png`
- `../output/page14_label_frequencies.csv`
- `../output/page14_label_sankey_links.csv`
- `../output/page14_label_example.csv`

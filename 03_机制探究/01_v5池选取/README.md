# v5 池的选取

版权轴扶梯（escalator）用户池：主导主题仍为版权类，话语向人身攻击（topic4）漂移。

## 脚本

| 文件 | 说明 |
|------|------|
| `build_topic_escalator.py` | 扶梯用户识别逻辑（供看板 JSON） |
| `export_v5_pool.py` | 导出全池 user_id → `../output/copyright_axis_escalator_v5_full_user_ids.txt` |
| `pool_filters.py` | 池内评论过滤（有效 user_id） |
| `plot_fandom_topic_stacked_bar.py` | 池内粉籍×主题构成图 |

```powershell
python export_v5_pool.py
```

## 前置

需先完成 `数据清洗与数据概览` 流水线。

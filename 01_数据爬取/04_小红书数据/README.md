# 小红书数据爬取

Playwright + Cookie 抓取笔记与评论。

## 准备

1. 复制 **`Cookie.example`** 为 **`Cookie`**（与本 README 同目录）
2. 浏览器登录 [xiaohongshu.com](https://www.xiaohongshu.com)，复制 Request Headers 中的 **Cookie** 整段，粘贴进 `Cookie`


3. 安装依赖：

```powershell
cd 概览分析/小红书数据爬取
pip install -r requirements.txt
python -m playwright install chromium
```

## 运行

```powershell
cd 概览分析/小红书数据爬取
python crawl_xhs.py              # 搜笔记 + 抓评论 → ../data/
python crawl_xhs.py --test       # 小规模测试 Cookie
python crawl_xhs.py --headless   # 无界面（Cookie 失效会直接报错）
python crawl_xhs.py --notes-only # 只搜笔记
python crawl_xhs.py --comments-only ../data/notes_xiaohongshu.csv
```

或使用 `run.ps1`（会自动安装 playwright）。

## 产出（`../data/`）

| 文件 | 说明 |
|------|------|
| `notes_{时间戳}.csv` | 笔记元数据 |
| `comments_{时间戳}.csv` | 评论明细 |
| `original_data_{时间戳}.csv` | 合并表，供 `preprocess_three_platforms.py` 读取 |

关键词见 `config.py`（默认 A 组事件向 5 个检索词）。

## 接入清洗

```powershell
cd ../数据清洗与数据概览
python preprocess_three_platforms.py
```

脚本会自动选用最新的 `original_data_*.csv`。

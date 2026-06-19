# 微博舆情数据交付包 — 单依纯 × 李荣浩《李白》侵权事件

**生成日期：** 2026-06-04  
**平台：** 新浪微博（移动站 m.weibo.cn）  
**采集工具：** MediaCrawler + 自研轻量评论脚本  
**编码：** UTF-8 with BOM（Excel 可直接打开）

---

## 一、本包包含哪些文件（交付清单 · 7 个 CSV + 本说明）

| 文件名 | 行数 | 用途 |
|--------|------|------|
| `search_posts_event_related.csv` | **1,406** | 关键词搜索 · **事件相关帖（分析主表）** |
| `search_posts_deduped.csv` | **1,511** | 关键词搜索 · 去重全量帖 |
| `search_posts_excluded.csv` | **105** | 关键词搜索 · 被剔除帖及原因 |
| `detail_posts.csv` | **200** | **第 1 批**评论爬取 · Top200 热帖元数据 |
| `search_posts_comments_gt20_extra.csv` | **68** | **第 2 批**评论爬取 · 评>20、非 Top200 帖元数据 |
| `search_posts_likes_gt20_extra.csv` | **157** | **第 3 批**评论爬取 · 赞>20 且评≤20、非 Top200 帖元数据 |
| `detail_comments.csv` | **20,792** | **三批帖评论合并**（每帖最多 200 条热评，非按批拆分） |
| `README.md` | — | 本说明文档 |

> **重要：** 增补两表（`search_posts_*_extra.csv`）存的是**原帖详情**，不是评论；评论全部在 **`detail_comments.csv`** 中，用 `note_id` 关联。

---

## 二、爬取说明

### 2.1 关键词搜索（Search）

- **模式：** `CRAWLER_TYPE = search`，`WEIBO_SEARCH_TYPE = default`（综合排序）
- **每关键词上限：** 约 200 条（`CRAWLER_MAX_NOTES_COUNT = 200`）
- **是否抓评论：** 否（Search 阶段只收帖，不收评论）
- **原始抓取：** 2,229 行（含跨关键词重复）→ 按 `note_id` 去重后 **1,511** 条

**使用的 12 个关键词（分 3 批完成）：**

| 批次 | 关键词 |
|------|--------|
| 1 | 李荣浩 单依纯；单依纯 侵权；强行侵权 李白；李荣浩 李白 |
| 2 | 单依纯 道歉；李荣浩 版权；单依纯 道歉 李白；李荣浩 赔偿 |
| 3 | 单依纯 停唱 李白；百沐 退票；单依纯 李荣浩 版权；李荣浩 打响 版权 |

**筛选逻辑（`search_posts_event_related.csv`）：**

- 保留：命中李荣浩/单依纯 + 事件词（侵权、版权、道歉、李白等），或官方账号帖
- 剔除：仅粉丝日常、纯古诗「李白」、与事件无关等 → 见 `search_posts_excluded.csv`
- 事件相关：**1,406** 条；剔除：**105** 条


### 2.2 热帖评论（三轮 Detail / 快爬）

评论接口：`comments/hotflow`（**热评流**），每帖目标 **200 条**；三批评论**合并写入** `detail_comments.csv`，**未**按批拆成多个评论文件。

| 批次 | 帖元数据文件 | 帖数 | 入选条件 | 约新增评论 |
|------|--------------|------|----------|------------|
| **第 1 批** | `detail_posts.csv` | 200 | 事件相关帖按 `engagement` 取 **Top200** | ~19,035 |
| **第 2 批** | `search_posts_comments_gt20_extra.csv` | 68 | 事件相关 + **评论数>20** + **不在 Top200** | 1,165 |
| **第 3 批** | `search_posts_likes_gt20_extra.csv` | 157 | 事件相关 + **点赞数>20 且评论数≤20** + **不在 Top200** | 592 |
| **合计** | 见上三表 + 评论合并表 | **425 帖有爬评** | — | **20,792 条**（`detail_comments.csv`） |

**说明：**

- Search 阶段**不抓评论**；所有评论仅在 `detail_comments.csv`。
- 增补帖的正文在 `search_posts_*_extra.csv`（字段与 `search_posts_event_related.csv` 相同），**不在** `detail_posts.csv`。
- 用 `note_id` 把帖元数据表与 `detail_comments.csv` 关联；表内无「批次」字段，需对照上表三个帖清单区分来源。

---

## 三、字段说明（按文件完整列出）

以下 **7 个 CSV** 均为 **UTF-8 with BOM**，可用 Excel 直接打开。除特别说明外，文本字段空值表示接口未返回或该场景不适用。

---

### 3.1 `search_posts_event_related.csv`（1,406 行 · 22 列）

**用途：** 关键词搜索后、经事件相关性筛选的**主分析表**；Top200 热帖从此表按 `engagement` 排序选取。

| 序号 | 字段名 | 类型 | 含义与说明 |
|------|--------|------|------------|
| 1 | `note_id` | 字符串 | 微博帖子唯一 ID，**主键**。例：`5281814849783031`。用于关联 detail 表、构造链接。 |
| 2 | `content` | 文本 | 帖子正文。已去除 HTML 标签（如 `<br>`、`<a>`）；微博「…全文」截断保留原样。 |
| 3 | `create_time` | 整数 | 帖子发布时间，**Unix 时间戳（秒，UTC 基准）**。 |
| 4 | `create_date_time` | 文本 | 帖子发布时间，**中国时区（UTC+8）** 可读格式。例：`2026-03-29 14:37:34+08:00`。 |
| 5 | `liked_count` | 整数 | 点赞数，**抓取时刻快照**，非实时值。 |
| 6 | `comments_count` | 整数 | 微博显示的评论总数，**抓取时刻快照**；不等于本包 `detail_comments.csv` 中的评论行数。 |
| 7 | `shared_count` | 整数 | 转发数，**抓取时刻快照**。 |
| 8 | `last_modify_ts` | 整数 | 本条记录写入本地 CSV 的时间戳，**毫秒**。 |
| 9 | `note_url` | 文本 | 移动站帖子链接。格式：`https://m.weibo.cn/detail/{note_id}`，可能含临时 query 参数。 |
| 10 | `ip_location` | 文本 | 发帖 IP 属地。例：`北京`、`浙江`；空表示未展示。 |
| 11 | `user_id` | 字符串 | 发帖用户 UID（微博数字 ID）。 |
| 12 | `nickname` | 文本 | 发帖用户昵称/显示名。 |
| 13 | `gender` | 文本 | 用户性别：`m` 男，`f` 女；可能为空。 |
| 14 | `profile_url` | 文本 | 用户移动站主页 URL。 |
| 15 | `avatar` | 文本 | 用户头像图片 URL（含 CDN 参数，可能过期）。 |
| 16 | `source_keyword` | 文本 | 该帖**首次/主要**被哪条搜索关键词召回。例：`李荣浩 单依纯`。 |
| 17 | `source_keywords_merged` | 文本 | 去重合并后，该帖被哪些关键词命中，**竖线 `\|` 分隔**。例：`李荣浩 单依纯\|李荣浩 版权`。 |
| 18 | `is_event_related` | 布尔 | 是否判为与本事件相关。本表恒为 **`True`**。 |
| 19 | `exclude_reason` | 文本 | 剔除原因代码。本表**恒为空**（已纳入相关表，不再携带剔除代码）。 |
| 20 | `publish_time` | 日期时间 | 由 `create_date_time` 解析的标准化发布时间，便于排序/筛选。 |
| 21 | `in_event_window` | 布尔 | 是否落在预设分析时间窗 **2025-06-01 ~ 2026-04-30 23:59:59** 内。 |
| 22 | `engagement` | 整数 | **互动量** = `liked_count` + `comments_count` + `shared_count`，用于热帖排序。 |

---

### 3.2 `search_posts_deduped.csv`（1,511 行 · 22 列）

**用途：** 12 个关键词搜索结果的**去重全量**（每个 `note_id` 一行），含事件相关与无关帖，便于审计搜索覆盖面。行集合 = 相关表（1,406）+ 剔除表（105）。

| 序号 | 字段名 | 类型 | 含义与说明 |
|------|--------|------|------------|
| 1 | `note_id` | 字符串 | 微博帖子唯一 ID，**主键**。例：`5281814849783031`。用于关联 detail 表、构造链接。 |
| 2 | `content` | 文本 | 帖子正文。已去除 HTML 标签（如 `<br>`、`<a>`）；微博「…全文」截断保留原样。 |
| 3 | `create_time` | 整数 | 帖子发布时间，**Unix 时间戳（秒，UTC 基准）**。 |
| 4 | `create_date_time` | 文本 | 帖子发布时间，**中国时区（UTC+8）** 可读格式。例：`2026-03-29 14:37:34+08:00`。 |
| 5 | `liked_count` | 整数 | 点赞数，**抓取时刻快照**，非实时值。 |
| 6 | `comments_count` | 整数 | 微博显示的评论总数，**抓取时刻快照**；不等于本包 `detail_comments.csv` 中的评论行数。 |
| 7 | `shared_count` | 整数 | 转发数，**抓取时刻快照**。 |
| 8 | `last_modify_ts` | 整数 | 本条记录写入本地 CSV 的时间戳，**毫秒**。 |
| 9 | `note_url` | 文本 | 移动站帖子链接。格式：`https://m.weibo.cn/detail/{note_id}`，可能含临时 query 参数。 |
| 10 | `ip_location` | 文本 | 发帖 IP 属地。例：`北京`、`浙江`；空表示未展示。 |
| 11 | `user_id` | 字符串 | 发帖用户 UID（微博数字 ID）。 |
| 12 | `nickname` | 文本 | 发帖用户昵称/显示名。 |
| 13 | `gender` | 文本 | 用户性别：`m` 男，`f` 女；可能为空。 |
| 14 | `profile_url` | 文本 | 用户移动站主页 URL。 |
| 15 | `avatar` | 文本 | 用户头像图片 URL（含 CDN 参数，可能过期）。 |
| 16 | `source_keyword` | 文本 | 该帖**首次/主要**被哪条搜索关键词召回。例：`李荣浩 单依纯`。 |
| 17 | `source_keywords_merged` | 文本 | 去重合并后，该帖被哪些关键词命中，**竖线 `\|` 分隔**。例：`李荣浩 单依纯\|李荣浩 版权`。 |
| 18 | `is_event_related` | 布尔 | 脚本自动判定是否与本事件相关：**`True`**（1,406 条，同相关表）或 **`False`**（105 条，同剔除表）。 |
| 19 | `exclude_reason` | 文本 | 剔除原因代码。若 `is_event_related=True` 则为**空**；若 `False` 则为非空，取值如 `no_core_entity`、`shan_fan_only`、`li_fan_or_concert_only`、`libai_poetry_or_unrelated`（含义见 `search_posts_excluded.csv` 字段 19 说明）。 |
| 20 | `publish_time` | 日期时间 | 由 `create_date_time` 解析的标准化发布时间，便于排序/筛选。 |
| 21 | `in_event_window` | 布尔 | 是否落在预设分析时间窗 **2025-06-01 ~ 2026-04-30 23:59:59** 内。 |
| 22 | `engagement` | 整数 | **互动量** = `liked_count` + `comments_count` + `shared_count`，用于热帖排序。 |

---

### 3.3 `search_posts_excluded.csv`（105 行 · 22 列）

**用途：** 从去重全量中**被自动剔除**、未进入相关表的帖子，附剔除原因供人工复核。2026-06-04 已将 49 条人工复核帖移回 `search_posts_event_related.csv`。

| 序号 | 字段名 | 类型 | 含义与说明 |
|------|--------|------|------------|
| 1 | `note_id` | 字符串 | 微博帖子唯一 ID，**主键**。例：`5281814849783031`。用于关联 detail 表、构造链接。 |
| 2 | `content` | 文本 | 帖子正文。已去除 HTML 标签（如 `<br>`、`<a>`）；微博「…全文」截断保留原样。 |
| 3 | `create_time` | 整数 | 帖子发布时间，**Unix 时间戳（秒，UTC 基准）**。 |
| 4 | `create_date_time` | 文本 | 帖子发布时间，**中国时区（UTC+8）** 可读格式。例：`2026-03-29 14:37:34+08:00`。 |
| 5 | `liked_count` | 整数 | 点赞数，**抓取时刻快照**，非实时值。 |
| 6 | `comments_count` | 整数 | 微博显示的评论总数，**抓取时刻快照**；不等于本包 `detail_comments.csv` 中的评论行数。 |
| 7 | `shared_count` | 整数 | 转发数，**抓取时刻快照**。 |
| 8 | `last_modify_ts` | 整数 | 本条记录写入本地 CSV 的时间戳，**毫秒**。 |
| 9 | `note_url` | 文本 | 移动站帖子链接。格式：`https://m.weibo.cn/detail/{note_id}`，可能含临时 query 参数。 |
| 10 | `ip_location` | 文本 | 发帖 IP 属地。例：`北京`、`浙江`；空表示未展示。 |
| 11 | `user_id` | 字符串 | 发帖用户 UID（微博数字 ID）。 |
| 12 | `nickname` | 文本 | 发帖用户昵称/显示名。 |
| 13 | `gender` | 文本 | 用户性别：`m` 男，`f` 女；可能为空。 |
| 14 | `profile_url` | 文本 | 用户移动站主页 URL。 |
| 15 | `avatar` | 文本 | 用户头像图片 URL（含 CDN 参数，可能过期）。 |
| 16 | `source_keyword` | 文本 | 该帖**首次/主要**被哪条搜索关键词召回。例：`李荣浩 单依纯`。 |
| 17 | `source_keywords_merged` | 文本 | 去重合并后，该帖被哪些关键词命中，**竖线 `\|` 分隔**。例：`李荣浩 单依纯\|李荣浩 版权`。 |
| 18 | `is_event_related` | 布尔 | 是否判为与本事件相关。本表恒为 **`False`**（均为被剔除帖）。 |
| 19 | `exclude_reason` | 文本 | 剔除原因代码，**非空**。本表当前取值分布：`no_core_entity`（48）、`shan_fan_only`（31）、`li_fan_or_concert_only`（19）、`libai_poetry_or_unrelated`（7）。各代码含义如下。 |
| 20 | `publish_time` | 日期时间 | 由 `create_date_time` 解析的标准化发布时间，便于排序/筛选。 |
| 21 | `in_event_window` | 布尔 | 是否落在预设分析时间窗 **2025-06-01 ~ 2026-04-30 23:59:59** 内。 |
| 22 | `engagement` | 整数 | **互动量** = `liked_count` + `comments_count` + `shared_count`，用于热帖排序。 |

**`exclude_reason` 代码说明（字段 19）：**

| 代码 | 含义 | 典型情况 |
|------|------|----------|
| `no_core_entity` | 未命中核心实体 | 正文未出现李荣浩、单依纯等当事人，仅因关键词误召回 |
| `shan_fan_only` | 仅单依纯粉丝向 | 提到单依纯但无侵权/李白/道歉等事件语境 |
| `li_fan_or_concert_only` | 仅李荣浩粉丝/演唱会向 | 提到李荣浩但无事件关键词（日常、演唱会官宣等） |
| `libai_poetry_or_unrelated` | 纯「李白」无当事人 | 古诗、梗图等与本次舆情无关的「李白」 |


---

### 3.4 `detail_posts.csv`（200 行 · 19 列）

**用途：** 从事件相关帖中按 `engagement` 取 **Top200** 的帖子元数据（detail 模式抓取）。

| 序号 | 字段名 | 类型 | 含义与说明 |
|------|--------|------|------------|
| 1 | `note_id` | 字符串 | 微博帖子唯一 ID，**主键**。与 `detail_comments.csv` 的 `note_id` 关联。例：`5281814849783031`。 |
| 2 | `content` | 文本 | 帖子正文。已去除 HTML 标签（如 `<br>`、`<a>`）；微博「…全文」截断保留原样。 |
| 3 | `create_time` | 整数 | 帖子发布时间，**Unix 时间戳（秒，UTC 基准）**。 |
| 4 | `create_date_time` | 文本 | 帖子发布时间，**中国时区（UTC+8）** 可读格式。例：`2026-03-29 14:37:34+08:00`。 |
| 5 | `liked_count` | 整数 | 点赞数，**detail 抓取时刻快照**，非实时值。 |
| 6 | `comments_count` | 整数 | 微博显示的评论总数，**抓取时刻快照**；**不等于**本表对应帖在 `detail_comments.csv` 中已爬行的条数。 |
| 7 | `shared_count` | 整数 | 转发数，**抓取时刻快照**。 |
| 8 | `last_modify_ts` | 整数 | 本条记录写入本地 CSV 的时间戳，**毫秒**。 |
| 9 | `note_url` | 文本 | 移动站帖子链接。格式：`https://m.weibo.cn/detail/{note_id}`，可能含临时 query 参数。 |
| 10 | `ip_location` | 文本 | 发帖 IP 属地。例：`北京`、`浙江`；空表示未展示。 |
| 11 | `user_id` | 字符串 | 发帖用户 UID（微博数字 ID）。 |
| 12 | `nickname` | 文本 | 发帖用户昵称/显示名。 |
| 13 | `gender` | 文本 | 用户性别：`m` 男，`f` 女；可能为空。 |
| 14 | `profile_url` | 文本 | 用户移动站主页 URL。 |
| 15 | `avatar` | 文本 | 用户头像图片 URL（含 CDN 参数，可能过期）。 |
| 16 | `source_keyword` | 文本 | Search 阶段召回该帖时使用的关键词；detail 单独补抓时**常为空**。 |
| 17 | `platform` | 文本 | 数据来源平台，固定值 **`weibo`**。 |
| 18 | `event` | 文本 | 研究事件名称，固定值 **`李白侵权舆情`**。 |
| 19 | `crawl_source` | 文本 | 采集模式标识，固定值 **`detail`**（热帖详情/评论配套帖元数据）。 |

---

### 3.5 `detail_comments.csv`（20,792 行 · 18 列）

**用途：** **三批**（Top200 + 评>20 增补 + 赞>20 增补）帖子的评论**合并表**；接口为 `comments/hotflow`（热评流），每帖目标最多 **200** 条，实际因删帖/关评/`ok=0` 等可能更少。

**关联：** `note_id` 可关联 `detail_posts.csv`（Top200）或 `search_posts_comments_gt20_extra.csv` / `search_posts_likes_gt20_extra.csv`（增补帖）。

| 序号 | 字段名 | 类型 | 含义与说明 |
|------|--------|------|------------|
| 1 | `comment_id` | 字符串 | 评论唯一 ID，**主键**。 |
| 2 | `create_time` | 整数 | 评论发布时间，**Unix 时间戳（秒，UTC 基准）**。 |
| 3 | `create_date_time` | 文本 | 评论发布时间，**中国时区（UTC+8）** 可读格式。例：`2026-03-29 14:48:52+08:00`。 |
| 4 | `note_id` | 字符串 | 所属帖子 ID，**外键** → 任一批次帖元数据表的 `note_id`。 |
| 5 | `content` | 文本 | 评论正文。已去除 HTML 标签；可能含 `@昵称` 文本、表情文字描述。 |
| 6 | `sub_comment_count` | 字符串 | 该评论下子评论（楼中楼）数量，取自微博接口，**以字符串存储**。 |
| 7 | `comment_like_count` | 字符串 | 该评论获得的点赞数，**以字符串存储**。 |
| 8 | `last_modify_ts` | 整数 | 本条记录写入本地 CSV 的时间戳，**毫秒**。 |
| 9 | `ip_location` | 文本 | 评论 IP 属地；由接口 `source` 字段去掉前缀「来自」得到。例：`北京`。 |
| 10 | `parent_comment_id` | 字符串 | 父评论 ID。一级热评通常 **等于自身 `comment_id`**；若为楼中楼回复则为被回复评论的 ID。 |
| 11 | `user_id` | 字符串 | 评论者 UID（微博数字 ID）。 |
| 12 | `nickname` | 文本 | 评论者昵称/显示名。 |
| 13 | `gender` | 文本 | 评论者性别：`m` 男，`f` 女；可能为空。 |
| 14 | `profile_url` | 文本 | 评论者移动站主页 URL。 |
| 15 | `avatar` | 文本 | 评论者头像图片 URL（含 CDN 参数，可能过期）。 |
| 16 | `platform` | 文本 | 数据来源平台，固定值 **`weibo`**。 |
| 17 | `event` | 文本 | 研究事件名称，固定值 **`李白侵权舆情`**。 |
| 18 | `crawl_source` | 文本 | 采集模式标识，固定值 **`detail`**。 |

---

### 3.6 `search_posts_comments_gt20_extra.csv`（68 行 · 22 列）

**用途：** **第 2 批**评论爬取对应的**原帖元数据**（不是评论表）。入选：来自 `search_posts_event_related.csv`，**评论数 > 20**，且 **不在 Top200**（`detail_posts.csv` 之外）。该 68 帖的评论在 `detail_comments.csv` 中，用 `note_id` 关联。

| 序号 | 字段名 | 类型 | 含义与说明 |
|------|--------|------|------------|
| 1 | `note_id` | 字符串 | 微博帖子唯一 ID，**主键**。例：`5283226341871143`。用于关联 `detail_comments.csv`。 |
| 2 | `content` | 文本 | 帖子正文。已去除 HTML 标签（如 `<br>`、`<a>`）；微博「…全文」截断保留原样。 |
| 3 | `create_time` | 整数 | 帖子发布时间，**Unix 时间戳（秒，UTC 基准）**。 |
| 4 | `create_date_time` | 文本 | 帖子发布时间，**中国时区（UTC+8）** 可读格式。例：`2026-03-29 14:37:34+08:00`。 |
| 5 | `liked_count` | 整数 | 点赞数，**Search 抓取时刻快照**，非实时值。 |
| 6 | `comments_count` | 整数 | 微博显示的评论总数，**快照**；本表入选条件为 **> 20**；不等于 `detail_comments.csv` 中实际爬到的行数。 |
| 7 | `shared_count` | 整数 | 转发数，**抓取时刻快照**。 |
| 8 | `last_modify_ts` | 整数 | 本条记录写入本地 CSV 的时间戳，**毫秒**。 |
| 9 | `note_url` | 文本 | 移动站帖子链接。格式：`https://m.weibo.cn/detail/{note_id}`，可能含临时 query 参数。 |
| 10 | `ip_location` | 文本 | 发帖 IP 属地。例：`北京`、`浙江`；空表示未展示。 |
| 11 | `user_id` | 字符串 | 发帖用户 UID（微博数字 ID）。 |
| 12 | `nickname` | 文本 | 发帖用户昵称/显示名。 |
| 13 | `gender` | 文本 | 用户性别：`m` 男，`f` 女；可能为空。 |
| 14 | `profile_url` | 文本 | 用户移动站主页 URL。 |
| 15 | `avatar` | 文本 | 用户头像图片 URL（含 CDN 参数，可能过期）。 |
| 16 | `source_keyword` | 文本 | 该帖**首次/主要**被哪条搜索关键词召回。例：`李荣浩 单依纯`。 |
| 17 | `source_keywords_merged` | 文本 | 去重合并后，该帖被哪些关键词命中，**竖线 `\|` 分隔**。 |
| 18 | `is_event_related` | 布尔 | 是否判为与本事件相关。本表恒为 **`True`**（均来自事件相关主表）。 |
| 19 | `exclude_reason` | 文本 | 剔除原因代码。本表**恒为空**。 |
| 20 | `publish_time` | 日期时间 | 由 `create_date_time` 解析的标准化发布时间，便于排序/筛选。 |
| 21 | `in_event_window` | 布尔 | 是否落在预设分析时间窗 **2025-06-01 ~ 2026-04-30 23:59:59** 内。 |
| 22 | `engagement` | 整数 | **互动量** = `liked_count` + `comments_count` + `shared_count`。 |

---

### 3.7 `search_posts_likes_gt20_extra.csv`（157 行 · 22 列）

**用途：** **第 3 批**评论爬取对应的**原帖元数据**（不是评论表）。入选：来自 `search_posts_event_related.csv`，**点赞数 > 20 且评论数 ≤ 20**，且 **不在 Top200**。该 157 帖的评论在 `detail_comments.csv` 中，用 `note_id` 关联。

| 序号 | 字段名 | 类型 | 含义与说明 |
|------|--------|------|------------|
| 1 | `note_id` | 字符串 | 微博帖子唯一 ID，**主键**。例：`5282661481317968`。用于关联 `detail_comments.csv`。 |
| 2 | `content` | 文本 | 帖子正文。已去除 HTML 标签（如 `<br>`、`<a>`）；微博「…全文」截断保留原样。 |
| 3 | `create_time` | 整数 | 帖子发布时间，**Unix 时间戳（秒，UTC 基准）**。 |
| 4 | `create_date_time` | 文本 | 帖子发布时间，**中国时区（UTC+8）** 可读格式。 |
| 5 | `liked_count` | 整数 | 点赞数，**Search 抓取时刻快照**；本表入选条件为 **> 20**。 |
| 6 | `comments_count` | 整数 | 微博显示的评论总数，**快照**；本表入选条件为 **≤ 20**（与第 2 批互补，不重叠）。 |
| 7 | `shared_count` | 整数 | 转发数，**抓取时刻快照**。 |
| 8 | `last_modify_ts` | 整数 | 本条记录写入本地 CSV 的时间戳，**毫秒**。 |
| 9 | `note_url` | 文本 | 移动站帖子链接。格式：`https://m.weibo.cn/detail/{note_id}`。 |
| 10 | `ip_location` | 文本 | 发帖 IP 属地。 |
| 11 | `user_id` | 字符串 | 发帖用户 UID（微博数字 ID）。 |
| 12 | `nickname` | 文本 | 发帖用户昵称/显示名。 |
| 13 | `gender` | 文本 | 用户性别：`m` 男，`f` 女；可能为空。 |
| 14 | `profile_url` | 文本 | 用户移动站主页 URL。 |
| 15 | `avatar` | 文本 | 用户头像图片 URL（含 CDN 参数，可能过期）。 |
| 16 | `source_keyword` | 文本 | 该帖**首次/主要**被哪条搜索关键词召回。 |
| 17 | `source_keywords_merged` | 文本 | 去重合并后，该帖被哪些关键词命中，**竖线 `\|` 分隔**。 |
| 18 | `is_event_related` | 布尔 | 是否判为与本事件相关。本表恒为 **`True`**。 |
| 19 | `exclude_reason` | 文本 | 剔除原因代码。本表**恒为空**。 |
| 20 | `publish_time` | 日期时间 | 由 `create_date_time` 解析的标准化发布时间。 |
| 21 | `in_event_window` | 布尔 | 是否落在预设分析时间窗 **2025-06-01 ~ 2026-04-30 23:59:59** 内。 |
| 22 | `engagement` | 整数 | **互动量** = `liked_count` + `comments_count` + `shared_count`。 |

---
---

## 四、表之间如何关联

```
search_posts_event_related.csv（1,406 帖，Search 主表）
         │
         ├── detail_posts.csv（Top200 帖元数据，200）
         ├── search_posts_comments_gt20_extra.csv（评>20 增补，68）
         ├── search_posts_likes_gt20_extra.csv（赞>20 评≤20 增补，157）
         │
         └── detail_comments.csv（三批评论合并，20,792 行）
                  ▲
                  └── 用 note_id 与上面三张「帖元数据」表关联
```

- **话题广度 / 时间线：** `search_posts_event_related.csv`
- **Top200 帖 + 评论：** `detail_posts.csv` + `detail_comments.csv`（`note_id` 过滤 Top200）
- **增补帖 + 评论：** `search_posts_comments_gt20_extra.csv` 或 `search_posts_likes_gt20_extra.csv` + `detail_comments.csv`
- **核对剔除原因：** `search_posts_excluded.csv`
- **审计搜索全量：** `search_posts_deduped.csv`

---

## 五、数据局限（交付时请一并说明）

1. 互动数为抓取时刻快照，非实时全量。
2. 评论为 **hotflow 热评**，非全量评论；每帖上限 200 条，实际因删帖/关评等可能更少。
3. Search 未采集评论；仅对 **425 帖**（Top200 + 两批增补）爬了评论，其余事件相关帖无评论数据。
4. 部分 UID/链接含微博临时参数，长期可能失效，分析建议以 `note_id` / `comment_id` 为主键。
5. 仅供学术研究使用，请遵守微博平台服务条款与相关法律法规。

---

## 六、原始文件位置（本包未包含，仅供备份）

| 路径 | 说明 |
|------|------|
| `MediaCrawler/data/weibo/csv/search_contents_2026-06-04.csv` | Search 原始 2,229 行 |
| `MediaCrawler/data/weibo/csv/detail_contents_2026-06-04.csv` | Detail 帖原始 |
| `MediaCrawler/data/weibo/csv/detail_comments_2026-06-04.csv` | Detail 评原始（与本包 `detail_comments.csv` 内容一致，已去重整理） |

---

*整理脚本：`weibo_crawl/prepare_search_for_detail.py`、`export_detail_tables.py`、`fetch_comments_fast.py`*

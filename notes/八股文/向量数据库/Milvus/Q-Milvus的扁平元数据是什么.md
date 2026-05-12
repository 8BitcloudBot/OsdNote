---
tags:
  - vector-database
  - milvus
  - schema
---

# Q: Milvus的扁平元数据是什么意思？

## 一句话答案

Milvus 的 Schema 是扁平的——所有标量字段（元数据）和向量字段定义在**同一层级**，不支持嵌套对象、子文档或关系模型。每条数据就是一个字段值的列表，和向量位置并列。

## 核心概念

以抖音视频为例，你在 Milvus 里存储一条视频数据的 Schema 是这样：

```python
from pymilvus import CollectionSchema, FieldSchema, DataType

fields = [
    # 主键
    FieldSchema(name="video_id", dtype=DataType.INT64, is_primary=True, auto_id=False),

    # 向量字段（跟其他字段平级）
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),

    # 标量字段——全部扁平，没有嵌套
    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
    FieldSchema(name="author", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="publish_date", dtype=DataType.INT64),    # 时间戳
    FieldSchema(name="duration", dtype=DataType.INT32),        # 时长（秒）
    FieldSchema(name="likes", dtype=DataType.INT64),           # 点赞数
    FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
    FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=1000),  # 逗号分隔
]

schema = CollectionSchema(fields, description="抖音视频库")
collection = Collection("douyin_videos", schema)
```

插入时就是**一维扁平数组**：

```python
collection.insert([
    [1],                         # video_id
    [[0.1, 0.2, ...]],           # embedding
    ["今天天气真好"],              # title
    ["科技频道"],                  # author
    [1715414400],                # publish_date
    [120],                       # duration
    [10000],                     # likes
    ["搞笑"],                     # category
    ["#vlog#life"],              # tags
])
```

**扁平与非扁平对比（以 Elasticsearch 为例）：**

```json
// ES — 支持嵌套对象
{
  "video_id": 1,
  "title": "...",
  "author": {
    "name": "科技频道",
    "uid": 12345,
    "level": "gold"        // ← 嵌套在 author 里
  },
  "comments": [             // ← 数组嵌套对象
    {"user": "A", "text": "hh"},
    {"user": "B", "text": "kk"}
  ]
}

// Milvus — 全部拍平
{
  "video_id": 1,
  "title": "...",
  "author_name": "科技频道",    // ← 拍平
  "author_uid": 12345,          // ← 拍平
  "author_level": "gold",       // ← 拍平
  // comments 无法存储嵌套结构
}
```

## 面试追问

> [!question] 追问详析
>
> **Q1: 为什么 Milvus 要设计成扁平的？**
>
> 三个原因：
>
> 1. **分布式数据分布。** 向量+标量必须存在同一个 shard 里才能做混合检索（搜向量 + 标量过滤）。如果支持嵌套对象，嵌套结构会大幅增加数据分布和序列化的复杂度，shard 分裂/迁移时成本极高。
>
> 2. **查询路径简单。** 扁平 Schema 的过滤直接走对应的 Field，查询路径是 O(1) 的字段名 → 倒排索引 → 位图。嵌套对象需要先展开、再合并位图，性能不可预测。
>
> 3. **向量优先的设计哲学。** Milvus 是向量数据库，标量过滤是"辅助"能力。它不承诺对标量做复杂查询（如 JOIN、子查询），只承诺最基础的等值/范围/IN/NOT IN。扁平结构是以最小复杂度换取基本过滤能力的妥协。
>
> **Q2: 那如果我的数据天然有嵌套结构怎么办？**
>
> 你必须在业务层"预拍平"：
>
> ```python
> # 原始数据（嵌套）
> video = {
>     "author": {"name": "科技频道", "uid": 12345, "level": "gold"},
>     "comments": [{"user": "A", "text": "..."}, {"user": "B", "text": "..."}]
> }
>
> # 拍平后写入 Milvus
> flat = {
>     "author_name": video["author"]["name"],
>     "author_uid": video["author"]["uid"],
>     "author_level": video["author"]["level"],
>     "comment_count": len(video["comments"]),  # 只存统计值
>     "comment_users": "A,B",  # 逗号拼成字符串，用 LIKE 模糊匹配
> }
> ```
>
> 如果必须保留评论做搜索，要么把评论文本拼成字段用 `expr='comments like "%keyword%"'`，要么单独存到 ES。
>
> **Q3: 那 Milvus 的 expr 过滤能力到底到哪个级别？**
>
> ```python
> # ✅ 支持的
> expr = 'likes > 10000'
> expr = 'category in ["搞笑", "科技"]'
> expr = 'author == "科技频道" and publish_date > 1715414400'
> expr = 'tags like "%vlog%"'          # 模糊匹配
> expr = 'likes > 10000 and likes < 100000'
> expr = 'video_id not in [1, 2, 3]'
>
> # ❌ 不支持的
> expr = 'author.name == "xx"'     # 无嵌套
> expr = 'likes > avg(likes)'      # 无聚合函数
> expr = 'comments[0].user == "A"' # 无数组索引
> ```
>
> 注意：`like` 的性能取决于字段是否建立了 index（Milvus 3.0+ 支持标量字段索引）。
>
> **Q4: 扁平设计对查询性能的具体影响？**
>
> Milvus 的混合检索流程：
> ```
> 用户请求: search vector + expr filter
>           ↓
>   1. 向量检索 → 取 top-KNN 候选集 (N个)
>           ↓
>   2. 标量过滤 → 用 expr 从候选集筛选 (用位图/倒排)
>           ↓
>   3. 返回命中的结果
> ```
> - 如果 filter 是范围查询（如 `likes > 10000`），是在**候选集上做过滤**，不是全量过滤
> - 如果候选集不够大（N 太小），即使有满足条件的数据也被排除了
> - 所以调参关键是：**先保证候选集召回率**，再考虑 filter
>
> **经验值：** 当 filter 的筛选率 > 90%（即过滤掉大部分数据时），建议调大 `search_params.limit` 的 N 值，否则最终结果可能为空。
>
> **Q5: Milvus 2.x 和 3.x 对标量过滤有什么改进？**
>
> | 版本 | 标量索引 | filter 执行 |
> |------|---------|------------|
> | 2.1 | 无标准标量索引 | 扫描候选集，O(N) |
> | 2.2 | 内存索引（bitset） | bitset 加速 |
> | 2.3+ | 倒排索引（inverted index） | 支持 `like`，大幅提升 |
> | 3.0 | 全自动索引 | 自动选择 scalars index 类型 |
>
> Milvus 3.0 的标量过滤能力已经接近 ES 的简单查询，但复杂嵌套仍然不行。

## 避坑

> [!warning] 常见坑点
>
> **坑1：误以为 Milvus 支持 JSON 字段**
>
> ```python
> # ❌ 错误
> FieldSchema(name="metadata", dtype=DataType.JSON)  # 2.x 不存在 JSON 类型
>
> # ✅ 或者用 Milvus 3.0 的 JSON 支持（有限）
> FieldSchema(name="metadata", dtype=DataType.JSON)
> # 但 3.0 的 JSON 字段只能做简单检索，不支持深层次嵌套
> # expr = 'metadata["title"] == "xxx"'  # 2.x 不可用
> ```
> Milvus 2.x 没有 JSON 类型。3.0 引入了有限 JSON 支持，但能力远不及 ES。
>
> **坑2：VARCHAR 长度设太小导致数据截断**
> ```python
> # ❌ title 设 100，实际标题 200 字 — 插入静默截断！
> FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=100)
>
> # ✅ title 设 500 以上
> FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500)
> ```
> VARCHAR 超长不会抛错，而是静默截断，检索时查不到完整内容。
>
> **坑3：忘记标量字段也可以建索引**
> ```python
> # 默认没 index，filter 走全量扫描
> collection.create_index("likes", {"index_type": "INVERTED"})
> collection.create_index("author", {"index_type": "BITMAP"})
> ```
> 频繁过滤的字段一定要建标量索引，否则 `1亿条数据 * likes > 10000` 的过滤 = 几十秒。
>
> **坑4：FILTER 和 SEARCH 的语义混淆**
> ```python
> # search — 搜向量后 filter
> collection.search(data=query_vec, anns_field="embedding",
>                    expr="likes > 10000", limit=10)
>
> # query — 纯标量查询，不搜向量
> collection.query(expr="likes > 10000", limit=10, output_fields=["title"])
> ```
> 如果不需要向量检索（只查标量），用 `query()` 而不是 `search()`，性能好得多。

## 相关笔记

- [[Q-Milvus查询流程和参数调优]]
- [[Q-向量数据库的Schema设计原则]]
- [[Q-FAISS的索引构建和搜索配置]]

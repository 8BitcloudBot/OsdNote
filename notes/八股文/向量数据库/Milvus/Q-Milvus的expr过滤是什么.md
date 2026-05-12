---
tags:
  - vector-database
  - milvus
  - query
---

# Q: Milvus 的 expr 过滤是什么？

## 一句话答案

`expr` 是 Milvus 在向量搜索时对标量字段做二次过滤的表达式，相当于 SQL 的 `WHERE`，但只在向量检索的候选集上执行，不是全量过滤。

## 执行流程

```
用户请求: search(vector=[0.1,0.2,...], expr="likes > 10000", limit=10)
                      ↓
  Step 1 — 向量检索：在向量空间里搜出 top-N（N由limit决定）
                      ↓
  Step 2 — expr过滤：从这N条里筛出满足 "likes > 10000" 的
                      ↓
  Step 3 — 返回结果：≤ N 条结果（可能为空）
```

**关键理解：** expr 不是 SQL WHERE，后者是全表扫描后过滤。expr 是在**向量检索的结果集上**做过滤。如果向量检索的 top-N 里没有符合 expr 的数据，最终结果就是空的——即使全库有满足条件的数据。

## 用法

```python
from pymilvus import Collection, connections

connections.connect("default", host="localhost", port="19530")
collection = Collection("douyin_videos")

# 基本查询 — 搜向量 + 过滤
results = collection.search(
    data=[query_vector],                     # 输入向量
    anns_field="embedding",                  # 向量字段名
    param={"metric_type": "L2", "params": {"nprobe": 10}},
    limit=100,                               # 先取100个候选
    expr="likes > 10000",                   # 从100里筛
    output_fields=["title", "author", "likes"]
)

# 等式 + 范围组合
results = collection.search(
    data=[query_vector],
    anns_field="embedding",
    param={"metric_type": "IP", "params": {"nprobe": 16}},
    limit=50,
    expr='category == "搞笑" and publish_date > 1715414400 and likes > 5000'
)

# IN 和 NOT IN
expr = 'video_id in [1001, 1002, 1003]'
expr = 'author not in ["黑名单用户1", "黑名单用户2"]'

# LIKE 模糊匹配
expr = 'title like "%旅行%"'     # 包含"旅行"
expr = 'tags like "#vlog%"'     # 以#vlog开头

# 纯标量查询（不用向量检索）
results = collection.query(
    expr="likes > 10000",
    limit=10,
    output_fields=["title", "author", "publish_date"]
)
```

## 支持的运算符一览

| 运算符 | 示例 | 说明 |
|--------|------|------|
| `==`, `!=` | `author == "科技频道"` | 等值/不等值 |
| `>`, `<`, `>=`, `<=` | `likes > 10000` | 数值比较 |
| `in`, `not in` | `category in ["A","B"]` | 集合包含 |
| `like` | `title like "%关键字%"` | 模糊匹配 |
| `and`, `or` | `A and B or C` | 逻辑组合 |

**不支持：** 嵌套路径（`author.name`）、聚合函数（`count`、`avg`）、子查询、JOIN、正则。

## expr + 向量检索的参数联动

面试考察重点：**`limit` 和 `expr` 的配合关系**

```python
# ❌ 典型错误
results = collection.search(
    limit=5,                     # 候选集只取5条
    expr="likes > 100000",       # 过滤条件非常严格
)
# 结果：很可能为空 — 5条里很难刚好有likes > 100000的

# ✅ 正确做法
results = collection.search(
    limit=500,                   # 候选集放大到500条
    expr="likes > 100000",
)
# 结果：500条里大概率能筛出几条
```

**经验公式：**

```
当 expr 筛选率 = 90% 时（即筛掉90%的数据）：
  需要 limit = 预期结果数 / (1 - 筛选率) = 10 / 0.1 = 100

当 expr 筛选率 = 99% 时：
  需要 limit = 10 / 0.01 = 1000 （候选集大幅膨胀）
```

所以严格过滤 + 小 limit = 空结果，这是最高频的错误。

## 面试追问

> [!question] 追问详析
>
> **Q1: 如果我想做"先过滤再向量检索"怎么做？**
>
> Milvus search 默认是"先搜向量再 filter"。如果你需要"先 filter 再搜向量"（比如只搜今天发布的视频），用 **IVF_FLAT + expr 配合索引**：
>
> 实际上 Milvus 2.3+ 支持 **iterator search** 模式：
> ```python
> from pymilvus import RangeSearchResult
> # 用更大的候选集 + 严格过滤来达到类似效果
> ```
>
> 更精确的方式是用 `query()` 先拿到 ID 列表，再用 `search()` 限定范围：
> ```python
> # 1. 先用标量过滤拿到符合条件的 ID
> valid_ids = collection.query(
>     expr="publish_date > 1715414400",
>     output_fields=["video_id"]
> )
> ids = [r["video_id"] for r in valid_ids]
>
> # 2. 搜向量时用 expr 限定在这些ID内
> results = collection.search(
>     expr=f"video_id in {ids}",
>     ...
> )
> ```
> 但这样做在 IDs 大量时性能很差。更好的方式是在业务层做时间分片（按日期建多个 collection）。
>
> **Q2: expr 对标量索引的依赖？**
>
> 如果标量字段没有索引：
> - 等值/范围过滤：走**全量扫描**（慢）
> - 建了倒排索引 `INVERTED`：走**倒排链**（快）
>
> ```python
> # 必须手动建标量索引
> collection.create_index("likes", {
>     "index_type": "INVERTED",
>     "params": {"nlist": 128}
> })
> collection.create_index("author", {
>     "index_type": "BITMAP"
> })
> ```
>
> | 过滤列 | 无索引 | 有 INVERTED | 有 BITMAP |
> |--------|-------|-------------|-----------|
> | `likes > 10000` | 扫描所有行，O(N) | 跳过不满足的范围块 | 位图与运算 |
> | `author == "张三"` | O(N) | 倒排链快速定位 | 位图 |
> | `title like "%x%"` | O(N) | 倒排词元匹配 | 不支持 |
>
> Milvus 3.0 新增了**自动标量索引**，不需要手动创建。
>
> **Q3: expr 和 SQL 的 WHERE 有什么本质区别？**
>
> | 维度 | SQL WHERE | Milvus expr |
> |------|-----------|-------------|
> | 执行范围 | 全表扫描 | 向量检索的候选集 |
> | 过滤时机 | 先筛再算 | 先向量搜再筛 |
> | 数据量 | 百万~亿级 | 候选集大小（通常 ≤ 1000） |
> | 索引依赖 | B+Tree/Hash | 倒排/Bitmap |
> | 嵌套支持 | 完整 | 无 |
>
> 本质区别：Milvus 的搜索流程决定了 **expr 是"向量检索的辅助修饰"**，不是独立过滤工具。需要纯标量过滤时应该用 `query()`。
>
> **Q4: 为什么 expr 不能先过滤再向量检索？**
>
> 因为 Milvus 的索引结构是围绕向量构建的（HNSW/IVF），向量检索必须从头开始遍历。
>
> 如果要实现"先过滤再向量检索"，理论上需要：
> 1. 用标量索引（如 B+Tree）先定位满足条件的行
> 2. 对定位到的行做向量检索
>
> 但这要求向量索引必须支持"增删部分行"（不在索引里的就不搜），FAISS 和 HNSW 都不原生支持。Milvus 3.0 通过 **Sparse + Dense 混合搜索** 部分解决了这个问题（先标量过滤得到候选ID列表，再局部构建向量检索），但性能仍然不如原生的向量优先搜索。

## 避坑

> [!warning] 常见坑点
>
> **坑1：limit 太小 + expr 太严格 = 空结果**
> ```python
> # ❌ 结果总是空的
> results = collection.search(limit=5, expr="likes > 1000000")
> # 5条候选中极大概率没有百万点赞的数据
>
> # ✅ limit 放大到合理值
> results = collection.search(limit=500, expr="likes > 1000000")
> ```
> 这是 Milvus 搜索中最常见的"没数据"原因。
>
> **坑2：expr 字段名写错**
> ```python
> # ❌ Schema 里定义的字段名是 "author_name"，不是 "author"
> expr = 'author == "张三"'     # 静默不报错，但结果为空
>
> # ✅ 用 Schema 里的真实字段名
> expr = 'author_name == "张三"'
> ```
> expr 里字段名写错也不报错，只是永远匹配不到数据。排查时很难发现。
>
> **坑3：用 `query()` 做纯标量查询但忘记 `output_fields`**
> ```python
> # ❌ query 返回空数据（仅返回主键）
> results = collection.query(expr="likes > 10000")
>
> # ✅ 指定要返回的字段
> results = collection.query(expr="likes > 10000", output_fields=["title", "likes"])
> ```
> `query()` 默认只返回主键字段，不指定 `output_fields` 只能拿到 ID。
>
> **坑4：String/VARCHAR 的 like 条件性能差**
> ```python
> # ❌ like "%%" 前缀模糊匹配 = 全表扫描
> expr = 'title like "%旅行%"'
>
> # ✅ 尽量用前缀匹配
> expr = 'title like "旅行%"'  # 前缀匹配可以用倒排
> ```
> `like "%keyword%"` 无法利用倒排索引的前缀优化，性能差。Milvus 3.0 引入了分词器（tokenizer）来优化全文搜索。
>
> **坑5：误以为 expr 能做 JOIN 或子查询**
> ```python
> # ❌ 不存在
> expr = 'video_id in (select id from hot_table)'
>
> # ✅ 业务层自己做
> hot_ids = [1, 2, 3]  # 业务层查询
> expr = f'video_id in {hot_ids}'
> ```

## 相关笔记

- [[Q-Milvus的扁平元数据是什么]]
- [[Q-Milvus查询流程和参数调优]]
- [[Q-Milvus标量索引类型和选择]]
- [[Q-向量混合检索策略]]

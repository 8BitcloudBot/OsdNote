---
tags:
  - vector-database
  - chroma
  - milvus
  - comparison
---

# Q: Chroma 和 Milvus 怎么选？

## 一句话答案

Chroma 是轻量嵌入式，pip install 即用，适合原型验证和个人项目；Milvus 是分布式生产系统，适合大规模、高可用场景。**Demo 用 Chroma，上线用 Milvus。**

## 核心对比

| 维度 | Chroma | Milvus |
|------|--------|--------|
| 定位 | 嵌入式向量数据库 | 分布式向量数据库 |
| 部署方式 | `pip install chromadb`，本地文件存储 | 分布式集群，支持 K8s/Docker Compose |
| 数据规模 | 百万级（全内存） | 十亿级 |
| 持久化 | 本地文件（sqlite + parquet） | etcd（元数据）+ MinIO/S3（数据） |
| 标量过滤 | 无索引，全量扫描 | INVERTED/BITMAP 索引 |
| expr 能力 | 支持基本 filter，性能随数据量线性下降 | 完整 expr + 倒排加速 |
| 分布式 | 无 | 原生支持，多 shard + 多副本 |
| 高可用 | 无（单进程崩溃即丢失） | 多副本 + 故障恢复 |
| 客户端 | Python 优先 | Python/Java/Go/Node/REST |
| 运维成本 | 几乎为零 | 较高（etcd + MinIO + K8s） |
| 社区 | 开源，活跃 | 开源 + Zilliz 商业支持 |
| 适用阶段 | 原型、Demo、个人项目 | 生产环境、企业级 |

## 代码对比

```python
# ============= Chroma =============
import chromadb

# 启动客户端（数据存本地）
client = chromadb.PersistentClient(path="./chroma_data")

# 创建集合
collection = client.create_collection(
    name="douyin_videos",
    metadata={"hnsw:space": "cosine"}
)

# 插入
collection.add(
    ids=["1", "2"],
    embeddings=[[0.1, 0.2], [0.3, 0.4]],
    metadatas=[
        {"title": "视频A", "author": "张三", "likes": 10000},
        {"title": "视频B", "author": "李四", "likes": 20000},
    ],
    documents=["视频A的文本", "视频B的文本"]
)

# 搜索
results = collection.query(
    query_embeddings=[[0.15, 0.25]],
    n_results=5,
    where={"likes": {"$gte": 10000}},   # 标量过滤
    where_document={"$contains": "视频"}  # 全文搜索
)

# ============= Milvus =============
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections

connections.connect("default", host="localhost", port="19530")

fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
    FieldSchema(name="author", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="likes", dtype=DataType.INT64),
]
schema = CollectionSchema(fields)
collection = Collection("douyin_videos", schema)

# 建索引
collection.create_index("embedding", {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 128}})
collection.create_index("likes", {"index_type": "INVERTED"})
collection.load()

# 搜索
results = collection.search(
    data=[[0.1, 0.2, ...]],
    anns_field="embedding",
    param={"metric_type": "L2"},
    limit=5,
    expr="likes >= 10000",
    output_fields=["title", "author", "likes"]
)
```

## 选型决策树

```
数据量多少？
├── < 100万 → 是否需要分布式？
│   ├── 否 → Chroma ✅
│   └── 是 → 是否需要标量过滤？
│       ├── 简单过滤 → Chroma | Qdrant
│       └── 复杂过滤 → Milvus
├── 100万~1000万 → 是否需要高可用？
│   ├── 否 → Qdrant / Milvus Standalone
│   └── 是 → Milvus ✅
└── > 1000万 → Milvus ✅
```

## 面试追问

> [!question] 追问详析
>
> **Q1: Chroma 的持久化可靠吗？**
>
> 有限可靠。Chroma 用 sqlite 存元数据 + parquet 存向量，单进程写入。
>
> 问题：
> - 多个 Python 进程同时写同一个 PersistentClient → sqlite 锁冲突
> - 进程 crash → 未 flush 的数据丢失（Chroma 没有 WAL）
> - 没有多副本，数据存本地，机器挂了就没了
>
> ```python
> # ❌ 多进程写入 Chroma — sqlite 锁冲突
> # Process 1
> chromadb.PersistentClient(path="./data")
> # Process 2 — OperationalError: database is locked
> chromadb.PersistentClient(path="./data")
>
> # ✅ 单进程 + 读写分离（但 Chroma 原生不支持）
> ```
>
> 所以 Chroma 不适合生产环境做写密集型。
>
> **Q2: 为什么面试官喜欢问这种对比？**
>
> 因为**选型能力 = 工程经验的浓缩表现**。能选对的人：
> - 知道每种工具的适用边界
> - 理解"运维成本"、"数据规模"、"一致性"这些非功能需求
> - 不会拿锤子看什么都像钉子
>
> 回答时一定要给出**分阶段的选型演进策略**：不是"我用 Milvus"，而是"初期 Chroma 快速验证 → 数据百万级且需要多服务共享 → 迁 Milvus"。
>
> **Q3: Chroma 的 metadata filter 和 Milvus expr 的根本差距？**
>
> Chroma filter 是在 Python 层面用 dict 条件匹配，数据全在内存里遍历：
> ```python
> # Chroma — 内存遍历式过滤
> where = {"likes": {"$gte": 10000}, "author": "张三"}
> # 等价于 Python: [x for x in data if x.likes >= 10000 and x.author == "张三"]
> ```
>
> Milvus expr 是在 C++ 层面用倒排索引做：
> ```python
> # Milvus — 倒排索引式过滤
> expr = "likes >= 10000 and author == '张三'"
> # 用预建的 INVERTED 索引 + BITMAP 加速，O(logN)
> ```
>
| 数据量 | Chroma filter | Milvus expr |
|--------|--------------|-------------|
| 1万 | <1ms | <1ms |
| 10万 | 5-10ms | <1ms |
| 100万 | 50-100ms | 1-2ms |
| 1000万 | 卡死 | 5-10ms |
>
> Chroma 数据量到百万级后 filter 会明显变慢，Milvus 有索引所以几乎不受数据量影响。
>
> **Q4: 有没有替代方案？**
>
> | 工具 | 适合场景 | 定位 |
> |------|---------|------|
> | Chroma | 原型、个人项目 | 最轻量 |
> | Milvus | 大规模生产 | 最重型 |
> | Qdrant | 数据量中等+需要分布式 | 中间态 |
> | Weaviate | 需要集成 NLP 能力 | 自带推理 |
> | Pinecone | 不想运维 | 全托管 |
> | FAISS | 只需要向量检索 | 纯索引库 |
>
> 如果你的数据在 100万~1000万 之间，又不想上 K8s，**Qdrant** 是最佳平衡点。单二进制文件启动，有分布式能力，性能接近 Milvus。

## 避坑

> [!warning] 常见坑点
>
> **坑1：Chroma 的 embeddings 参数和 documents 参数**
> ```python
> # Chroma 支持两种搜索方式
>
> # 方式一：自己算 embedding
> collection.query(query_embeddings=[[...]], ...)
>
> # 方式二：让 Chroma 用默认模型算
> collection.query(query_texts=["视频A"], ...)  # 默认用 all-MiniLM-L6-v2
>
> # ❌ 混合用两个参数会报错
> collection.query(query_embeddings=[[...]], query_texts=["视频A"])
> # ValueError: can't use both
> ```
>
> **坑2：Chroma 的 PersistentClient 路径冲突**
> ```python
> # ❌ 两个客户端用同一个路径
> c1 = chromadb.PersistentClient(path="./data")
> c2 = chromadb.PersistentClient(path="./data")  # 锁住
>
> # ✅ 不同项目用不同路径
> c1 = chromadb.PersistentClient(path="./project_a_data")
> c2 = chromadb.PersistentClient(path="./project_b_data")
> ```
>
> **坑3：Chroma 的 hnsw 参数在 create_collection 时设**
> ```python
> # ❌ 建完 collection 后再改就晚了
> collection = client.create_collection("videos")
>
> # ✅ 创建时指定
> collection = client.create_collection(
>     "videos",
>     metadata={"hnsw:space": "cosine", "hnsw:construction_ef": 200}
> )
> ```
> 标量过滤的 where 条件里，key 必须是 metadata dict 里的键，不能嵌套。
>
> **坑4：Milvus 的运维负担被低估**
> ```bash
> # 启动 Milvus 需要至少：
> # etcd + MinIO/S3 + Milvus Proxy/QueryNode/DataNode/IndexNode
> # docker-compose.yml 至少 6 个 service
>
> # 对比 Chroma：
> pip install chromadb
> python -c "import chromadb; chromadb.PersistentClient()"
> ```
> 面试官问"为什么选 Chroma"时，除了性能还应该提**运维成本**：一个 10 人的小团队扛不起 Milvus 集群。
>
> **坑5：数据迁移成本**
> ```python
> # Chroma → Milvus 没有官方迁移工具，需要自己写脚本
>
> # 1. 从 Chroma 读出所有数据
> all_data = collection.get(include=["embeddings", "metadatas", "documents"])
>
> # 2. 格式化
> entities = [
>     all_data["ids"],
>     all_data["embeddings"],
>     [m["title"] for m in all_data["metadatas"]],
>     ...
> ]
>
> # 3. 写入 Milvus
> milvus_collection.insert(entities)
> ```
> 选型时一定要考虑迁移成本，Chroma → Milvus = 自己写脚本，Milvus → Chroma = 几乎不可逆（Milvus 的索引和分区概念 Chroma 没有）。

## 相关笔记

- [[Q-Milvus的扁平元数据是什么]]
- [[Q-Milvus的expr过滤是什么]]
- [[Q-FAISS和Milvus怎么选]]
- [[Q-向量数据库选型全景]]

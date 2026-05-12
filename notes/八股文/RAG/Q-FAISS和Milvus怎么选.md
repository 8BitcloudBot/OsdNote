---
tags:
  - RAG
  - 向量数据库
---

# Q: FAISS和Milvus怎么选？

## 一句话答案

小规模（<100万向量）用FAISS快速验证，大规模生产用Milvus。

## 核心对比

| 维度 | FAISS | Milvus |
|------|-------|--------|
| 部署方式 | 内存索引，单机 | 分布式，支持K8s |
| 数据规模 | 百万级 | 十亿级 |
| 持久化 | 需手动 `write_index()` | 自动持久化，基于etcd+minio |
| 索引类型 | IVF/HNSW/PQ/Flat | 11种+原生索引，支持混合索引 |
| 一致性 | N/A | 支持Strong/Bounded/Session/Eventually |
| 生态 | Meta开源，社区大 | 国产，中文文档好，有Zilliz Cloud |
| 动态增删 | 需重建索引 | 支持增量insert/delete |
| 过滤查询 | 需自行实现 | 原生支持标量过滤+向量检索 |
| 多租户 | 无 | 原生Partition机制 |

## 代码

```python
# ============= FAISS =============
import faiss
import numpy as np

dim = 768

# 暴力检索 — 小数据精确搜索
index = faiss.IndexFlatL2(dim)
index.add(vectors)            # shape: (N, 768)

# IVF倒排索引 — 大数据量
quantizer = faiss.IndexFlatL2(dim)
index = faiss.IndexIVFFlat(quantizer, dim, nlist=100)
index.train(vectors)          # 必须train！否则报错
index.add(vectors)

# HNSW图索引 — 高召回场景
index = faiss.IndexHNSWFlat(dim, M=32)  # M越大召回越高，内存越大
index.add(vectors)

# GPU加速
res = faiss.StandardGpuResources()
gpu_index = faiss.index_cpu_to_gpu(res, 0, index)

# 搜索
D, I = index.search(query, k=10)  # D=distance, I=indices

# 持久化
faiss.write_index(index, "index.faiss")
index = faiss.read_index("index.faiss")

# ============= Milvus =============
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType

connections.connect("default", host="localhost", port="19530")

# 定义Schema
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=768),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=500),
    FieldSchema(name="created_at", dtype=DataType.INT64),
]
schema = CollectionSchema(fields, description="文档向量库")

# 创建Collection
collection = Collection("docs", schema)

# 创建索引（必须在insert之前！）
index_params = {
    "index_type": "IVF_FLAT",
    "metric_type": "L2",
    "params": {"nlist": 128}
}
collection.create_index("vector", index_params)

# 加载到内存（必须load才能搜）
collection.load()

# 插入数据
import random
entities = [
    [i for i in range(1000)],                          # id
    [[random.random() for _ in range(768)] for _ in range(1000)],  # vector
    [f"text_{i}" for i in range(1000)],                # text
    [i for i in range(1000)],                          # created_at
]
collection.insert(entities)

# 向量检索 + 标量过滤
search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
results = collection.search(
    data=[query_vector],
    anns_field="vector",
    param=search_params,
    limit=10,
    expr="created_at > 1700000000",  # 标量过滤表达式
    output_fields=["text", "created_at"]
)
```

## 面试追问

> [!question] 追问详析
> 
> **Q1: 为什么FAISS检索这么快？**
> 
> 三个原因：
> 1. **纯内存计算** — 向量全在RAM，不经过网络IO，单机延迟 <1ms
> 2. **GPU加速** — `faiss.StandardGpuResources()` 把 FAISS index 推到GPU，批量检索比CPU快10-100倍，底层用CUDA矩阵运算
> 3. **无序列化开销** — 不像Milvus要走gRPC + protobuf序列化/反序列化
> 
> 代价也很明显：数据量超过内存就OOM，且单机无高可用。
> 
> **Q2: Milvus怎么保证高可用？**
> 
> ```
> 客户端 → Proxy(负载均衡) → Query Node(查询) / Data Node(写入)
>                                ↓
>                etcd(元数据) + MinIO/S3(持久化)
> ```
> - **etcd** — 存储Collection的schema、索引配置等元数据，3节点Raft保证一致性
> - **MinIO/S3** — 向量数据落盘，Data Node异步刷盘，崩溃后从对象存储恢复
> - **多副本** — Query Node和Data Node都可以水平扩展，无单点
> - **读写分离** — Query Node只读，Data Node只写，互不影响
> 
> **Q3: IVF和HNSW怎么选？**
> 
> | 维度 | IVF | HNSW |
> |------|-----|------|
> | 原理 | K-means聚类 + 只搜最近n个簇 | 多层图 + 贪心搜索 |
> | 召回率 | 调nprobe可提升，通常90-95% | 默认95-99%，接近精确 |
> | 构建速度 | 需要train，但训练快 | 构建图慢，O(N·M·logN) |
> | 内存占用 | 只存聚类中心，内存小 | 存多层图结构，内存大（M=32时约1.5x原数据） |
> | 适用场景 | 数据量大、内存有限 | 召回要求高、内存充足 |
> | 增量插入 | 需重建索引 | 天然支持增量（图动态插入） |
> 
> **Q4: 你们项目里怎么选的？这个过程是怎样的？**
> 
> 这是一个非常好展示工程思维的面试问题，标准回答路径：
> 
> 1. **MVP阶段** — 用FAISS FlatIndex快速验证RAG可行性，几百个文档不需要复杂索引
> 2. **数据增长到万级** — 换FAISS IVF，nlist=128，nprobe=16，召回 >95%
> 3. **数据到百万级 + 需要多服务共享** — 迁Milvus，因为FAISS单机内存已经扛不住了，且多服务需要共享同一个向量库
> 4. **上线后** — Milvus配一致性=Strong保证读写一致，开Partition做租户隔离
> 
> 面试官想听到的是"技术选型的演进过程"，而不是"我用了Milvus"。
> 
> **Q5: Milvus的nlist和nprobe怎么调？**
> 
> - **nlist（聚类中心数）** — 和 `sqrt(N)` 同数量级，`nlist = 4*sqrt(N)` 是经验公式
>   - nlist太小 → 每个簇太大，搜索慢
>   - nlist太大 → 聚类中心过多，build慢
> - **nprobe（搜索时扫描的簇数）** — 越大召回越高但越慢
>   - nprobe=1 最快但召回可能不到50%
>   - nprobe=nlist 等价于暴力搜索
>   - 经验值 nprobe = nlist/10 ~ nlist/5
> - **关键**：nprobe调大只能在"已创建的索引"里提高召回，不能突破索引本身的上限。如果nlist设得太大导致每个簇太少，nprobe调满也救不回来

## 避坑

> [!warning] 常见坑点
> 
> **坑1：FAISS IVF不调用train()直接add**
> ```python
> # ❌ 错误 — 必报错
> index = faiss.IndexIVFFlat(quantizer, dim, nlist)
> index.add(vectors)  # RuntimeError: IndexIVF not trained
> 
> # ✅ 正确
> index.train(vectors)  # 先train，聚类中心
> index.add(vectors)    # 再add
> ```
> 原因：IVF需要先聚类得到nlist个中心点，train就是做K-means。FlatIndex不需要train。
> 
> **坑2：Milvus先insert再create_index**
> ```python
> # ❌ 错误 — index已经存在的segment不会建索引
> collection.insert(data)
> collection.create_index("vector", index_params)  # 只对新数据生效
> 
> # ✅ 正确 — 先建索引再插数据
> collection.create_index("vector", index_params)
> collection.insert(data)
> collection.load()
> ```
> 如果已经插了数据：
> ```python
> collection.create_index("vector", index_params)
> collection.flush()  # 刷盘
> collection.compact()  # 触发索引重建
> ```
> 
> **坑3：Milvus忘记load()**
> ```python
> # ❌ 错误
> collection.search(...)  # CollectionNotLoadedException
> 
> # ✅ 任何search之前必须load
> collection.load()
> ```
> load() 把索引和数据从磁盘加载到内存，不load就搜是最高频错误。
> 
> **坑4：FAISS HNSW的M值乱设**
> - M=4~64，默认16。M越大图越密，召回越高但内存翻倍
> - M=32时索引内存 ≈ 原始数据的 1.5x
> - M=64时索引内存 ≈ 原始数据的 3x
> - 无脑设64然后OOM是非常经典的事故
> 
> **坑5：FAISS不同index搜出来的距离不可比**
> - `IndexFlatL2` 返回的是欧氏距离
> - `IndexIVFPQ` 返回的是近似距离（量化后的），和真实距离有偏差
> - 不要把不同index的distance混在一起排序比较
> 
> **坑6：Milvus的expr过滤语法**
> ```python
> # ✅ 正确
> expr = 'age > 20 and name like "张%"'
> 
> # ❌ 错误 — 不能有空格在比较符里
> expr = 'age > 20'  # 正确
> expr = 'age>20'    # 也可以
> ```
> expr 本质是布尔表达式，字段要用Schema中定义的名称，不是Python变量名。

## 相关笔记

- [[Q-IVF和HNSW底层原理对比]]
- [[Q-Milvus架构和组件详解]]
- [[Q-向量检索的ANN算法全景]]
- [[Q-RAG中向量库如何做多租户隔离]]

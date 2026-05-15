---
tags:
  - rag
  - optimization
  - embedding
  - reranker
  - prompt-engineering
---

# Q: RAG 系统"很笨"怎么优化？

## 一句话答案

RAG 优化四大方向：检索质量（嵌入模型 + Reranker）、查询理解（改写 + 路由）、上下文管理（压缩 + 预算）、生成质量（Prompt 工程）。优先优化检索质量，这是最直接提升效果的方向。

## 优化方向全景图

| 方向 | 具体技术 | 优先级 | 效果 | 复杂度 |
|------|---------|--------|------|--------|
| **检索质量** | 换大嵌入模型、加 Reranker | 🔴 高 | 直接提升检索精度 | 低 |
| **查询理解** | 查询改写、Multi-Query、HyDE | 🟡 中 | 提升召回率 | 中 |
| **上下文管理** | 上下文压缩、Token 预算 | 🟡 中 | 减少噪声，降低成本 | 中 |
| **生成质量** | Prompt 工程、Few-shot | 🟡 中 | 提升回答质量 | 低 |
| **评估体系** | RAGAS、人工评估 | 🔴 高 | 指导优化方向 | 中 |

## 详细优化方案

### 1. 检索质量优化（最高优先级）

#### 1.1 嵌入模型选择

嵌入模型是检索质量的基础。模型太小会导致语义理解能力不足。

| 模型 | 维度 | 中文效果 | 速度 | 推荐场景 |
|------|------|---------|------|---------|
| `bge-small-zh-v1.5` | 512 | 一般 | 快 | 原型验证 |
| `bge-large-zh-v1.5` | 1024 | 好 | 中 | **生产推荐** |
| `m3e-large` | 1024 | 好 | 中 | 中文场景 |
| `text-embedding-3-small` | 1536 | 好 | API | 有预算 |
| `text-embedding-3-large` | 3072 | 很好 | API | 高质量需求 |

```python
# ❌ 错误：使用太小的模型
from langchain_huggingface import HuggingFaceEmbeddings
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5")

# ✅ 正确：使用更大的模型
from langchain_huggingface import HuggingFaceEmbeddings
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-large-zh-v1.5")
```

#### 1.2 Reranker 加持

Reranker 是检索质量的第二道保障。它对初步检索结果进行精细排序，比向量相似度更准确。

| Reranker 模型 | 中文效果 | 速度 | 推荐场景 |
|---------------|---------|------|---------|
| `bge-reranker-v2-m3` | 很好 | 中 | **中文首选** |
| `bge-reranker-large` | 好 | 慢 | 高质量需求 |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | 一般 | 快 | 英文场景 |

```python
# 实现 Reranker
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

# 初始化 Reranker
reranker = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-v2-m3")
compressor = CrossEncoderReranker(model=reranker, top_n=5)

# 创建带 Reranker 的检索器
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vector_retriever
)
```

#### 1.3 混合检索策略

单一检索方式有局限性，混合检索可以结合语义检索和关键词检索的优势。

```python
# 混合检索实现
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

# 向量检索器
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

# BM25 检索器
bm25_retriever = BM25Retriever.from_documents(documents, k=10)

# RRF 融合
ensemble_retriever = EnsembleRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    weights=[0.6, 0.4]  # 可调权重
)
```

### 2. 查询理解优化

#### 2.1 查询改写

将用户模糊的查询改写为更适合检索的形式。

```python
# 查询改写示例
query_rewrite_prompt = """
请将以下用户查询改写为更适合向量检索的形式：
- 保持核心语义
- 去除口语化表达
- 补充关键上下文

用户查询：{query}
改写后：
"""
```

#### 2.2 Multi-Query（多查询生成）

生成多个查询变体，分别检索后合并结果，提升召回率。

```python
# Multi-Query 实现
multi_query_prompt = """
请为以下查询生成 3 个不同的表述方式，用于向量检索：

原始查询：{query}

请生成：
1. 更正式的表述
2. 更具体的表述
3. 更通用的表述

返回 JSON 格式：
["表述1", "表述2", "表述3"]
"""
```

#### 2.3 HyDE（假设性文档嵌入）

先让 LLM 生成一个假设性答案，用答案的嵌入进行检索（因为答案和文档的风格更接近）。

```python
# HyDE 实现
hyde_prompt = """
请根据以下查询，生成一个假设性的答案（不需要准确，只需要风格和格式）：

查询：{query}

假设性答案：
"""

# 用假设性答案的嵌入进行检索
hypothetical_answer = llm.invoke(hyde_prompt)
hyde_embedding = embeddings.embed_query(hypothetical_answer)
results = vectorstore.search_by_vector(hyde_embedding)
```

### 3. 上下文管理优化

#### 3.1 上下文压缩

对检索到的文档进行压缩，只保留与查询相关的部分。

```python
# 上下文压缩
from langchain.retrievers.document_compressors import LLMChainExtractor

compressor = LLMChainExtractor.from_llm(llm)
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=base_retriever
)
```

#### 3.2 Token 预算管理

限制送入 LLM 的总 token 数，优先保留高相关性内容。

```python
# Token 预算管理
class ContextBudgetManager:
    def __init__(self, max_tokens=10000):
        self.max_tokens = max_tokens

    def fit_context(self, documents, query):
        # 按相关性排序
        scored_docs = [(doc, self.score(doc, query)) for doc in documents]
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # 贪心填充
        selected = []
        current_tokens = 0
        for doc, score in scored_docs:
            doc_tokens = self.count_tokens(doc.page_content)
            if current_tokens + doc_tokens <= self.max_tokens:
                selected.append(doc)
                current_tokens += doc_tokens
            else:
                # 尝试截取关键部分
                truncated = self.extract_key_parts(doc, self.max_tokens - current_tokens)
                if truncated:
                    selected.append(truncated)
                break

        return selected
```

### 4. 生成质量优化

#### 4.1 Prompt 工程

系统提示词的质量直接影响生成效果。

```python
# 优化的系统提示词
system_prompt = """
你是一个专业的问答助手。请根据以下检索到的文档内容回答用户的问题。

规则：
1. 只基于提供的文档内容回答，不要编造信息
2. 如果文档中没有相关信息，请明确说明"根据提供的文档，无法回答这个问题"
3. 引用具体的文档来源
4. 回答要简洁、准确、有条理

检索到的文档：
{context}

用户问题：{query}
"""
```

#### 4.2 Few-shot 示例

在提示词中加入示例，指导 LLM 生成符合期望的回答。

```python
# Few-shot 示例
few_shot_prompt = """
请根据文档回答问题。以下是回答示例：

示例 1：
问题：红烧肉需要哪些食材？
答案：根据菜谱文档，红烧肉需要以下食材：
- 五花肉 500g
- 冰糖 30g
- 生抽 2勺
- 老抽 1勺
- 料酒 2勺
- 葱姜适量

示例 2：
问题：这道菜的烹饪步骤是什么？
答案：根据菜谱文档，烹饪步骤如下：
1. 五花肉切块，冷水下锅焯水
2. 锅中放油，加冰糖炒糖色
3. 放入五花肉翻炒上色
4. 加入调料和适量水，小火炖 1 小时
5. 大火收汁即可

现在请回答：
问题：{query}
答案：
"""
```

## 优化效果评估

### 评估指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| **检索精度** | Top-K 结果中相关文档的比例 | > 0.8 |
| **检索召回率** | 相关文档被检索到的比例 | > 0.7 |
| **答案正确性** | 生成答案的 factual accuracy | > 0.9 |
| **答案完整性** | 答案覆盖问题所有方面 | > 0.8 |
| **用户满意度** | 用户正面反馈比例 | > 0.85 |

### 评估方法

```python
# RAGAS 评估框架
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

# 准备评估数据
eval_data = {
    "question": ["红烧肉怎么做？", "需要哪些食材？"],
    "answer": ["...", "..."],  # RAG 生成的答案
    "contexts": [["..."], ["..."]],  # 检索到的文档
    "ground_truth": ["...", "..."],  # 标准答案
}

# 运行评估
result = evaluate(
    dataset=eval_data,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
)
print(result)
```

## 优化路径建议

```
阶段 1：快速见效（1-2 天）
├── 换更大的嵌入模型（bge-large-zh-v1.5）
├── 加 Reranker（bge-reranker-v2-m3）
└── 优化系统提示词

阶段 2：深度优化（1-2 周）
├── 实现混合检索（向量 + BM25）
├── 加入查询改写
├── 实现上下文压缩
└── 建立评估体系

阶段 3：持续迭代（长期）
├── 基于评估结果调优参数
├── 收集用户反馈优化
├── 尝试 HyDE、Multi-Query 等高级技术
└── 监控和维护
```

## 面试追问

> [!question] 追问详析
>
> **Q1: 嵌入模型越大越好吗？**
>
> 不是绝对的。需要权衡：
> - **质量**：大模型语义理解能力更强
> - **速度**：大模型推理更慢
> - **成本**：大模型需要更多计算资源
> - **数据量**：小数据集用大模型可能过拟合
>
> 建议：先用小模型验证流程，再用大模型提升质量。生产环境推荐 `bge-large-zh-v1.5` 或 `m3e-large`。
>
> **Q2: Reranker 和 RRF 重排有什么区别？**
>
> | 维度 | Reranker | RRF |
> |------|----------|-----|
> | **原理** | Cross-encoder 精细打分 | 多路检索结果融合 |
> | **输入** | query + 单个文档 | 多个检索器的排序结果 |
> | **精度** | 高（精细比较） | 中（简单融合） |
> | **速度** | 慢（需要逐对计算） | 快（简单排序） |
> | **使用场景** | 精排阶段 | 粗排阶段 |
>
> 最佳实践：先用 RRF 融合多路检索结果（粗排），再用 Reranker 精细排序（精排）。
>
> **Q3: 如何评估 RAG 系统的优化效果？**
>
> 推荐使用 RAGAS 框架，包含四个核心指标：
> 1. **Faithfulness**：答案是否基于检索到的文档（防幻觉）
> 2. **Answer Relevancy**：答案是否回答了问题
> 3. **Context Precision**：检索到的文档是否相关
> 4. **Context Recall**：相关文档是否被检索到
>
> 除了自动化评估，还需要人工评估：随机抽样 100 个查询，人工判断答案质量。

## 避坑

> [!warning] 常见坑点
>
> **坑1：只优化检索，不优化 Prompt**
>
> ```python
> # ❌ 错误：检索优化了，但 Prompt 太简单
> prompt = f"根据以下内容回答：{context}\n问题：{query}"
>
> # ✅ 正确：Prompt 需要明确规则
> prompt = f"""你是一个专业的问答助手。请根据以下文档回答问题。
>
> 规则：
> 1. 只基于文档内容回答，不要编造
> 2. 如果文档中没有相关信息，明确说明
> 3. 引用具体来源
>
> 文档：{context}
> 问题：{query}
> """
> ```
>
> 原因：Prompt 是 LLM 的"指令"，不清晰的指令会导致 LLM 行为不可控。
>
> **坑2：忽略评估，盲目优化**
>
> ```python
> # ❌ 错误：凭感觉优化
> # "我觉得换大模型效果好了"
>
> # ✅ 正确：用数据说话
> # 优化前：RAGAS faithfulness = 0.72
> # 优化后：RAGAS faithfulness = 0.85
> # 提升：+13%
> ```
>
> 原因：没有评估，就无法知道优化是否有效，也无法比较不同方案的优劣。
>
> **坑3：过度优化单一指标**
>
> ```python
> # ❌ 错误：只追求检索精度，忽略召回率
> # top_k=1，精度高但可能漏掉相关文档
>
> # ✅ 正确：平衡多个指标
> # top_k=5，配合 Reranker 精排
> ```
>
> 原因：RAG 系统需要平衡精度和召回率。过度追求精度会导致信息遗漏，过度追求召回率会引入噪声。

## 相关笔记

- [[Q-RAG和Agent的区别与选择]]
- [[Q-FAISS和Milvus怎么选]]
- [[Q-Query-Routing和Skills机制对比]]
- [[响应合成模式]]
- [[查询重构与分发]]

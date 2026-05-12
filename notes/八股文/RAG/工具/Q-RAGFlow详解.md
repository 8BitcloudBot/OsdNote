---
tags:
  - rag
  - ragflow
  - document-parsing
---

# Q: RAGFlow 是什么？

## 一句话答案

RAGFlow 是一个**深度文档理解**的 RAG 引擎，在 RAG 的"解析"环节做了差异化：用版面分析（Layout Analysis）+ OCR + 表格识别来理解文档结构，而不是 Naive RAG 那样用 text splitter 暴力截断。

## 核心架构

```
用户上传文档（PDF/Word/Excel/PPT/图片）
              ↓
    ┌─────────────────────┐
    │   DeepDoc Parser    │ ← 核心差异点
    │  - 版面分析(Layout) │
    │  - OCR (PaddleOCR)  │
    │  - 表格识别(Table)  │
    │  - 公式识别(LaTeX)  │
    │  - 图片理解(ViT)    │
    └─────────┬───────────┘
              ↓ 结构化 chunks
    ┌─────────────────────┐
    │   Chunk Template    │ ← 用户可配置分块策略
    │  - 按标题层级合并   │
    │  - 按语义分段       │
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │   Embedding + 入库  │ ← 主流模型（BGE/GTE/text2vec）
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │   Rerank（重排序）  │ ← 可选
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │   LLM 生成回答      │ ← 支持主流 LLM
    └─────────────────────┘
```

## 与 Naive RAG 的对比

| 维度 | Naive RAG（LangChain） | RAGFlow |
|------|----------------------|---------|
| 文档解析 | `PyPDFLoader` + `RecursiveCharacterTextSplitter` | DeepDoc: 版面分析 + OCR + 表格识别 |
| PDF 处理 | 按页提取文字，无法处理扫描件 | 支持扫描件 OCR，保留原始版面 |
| 表格 | 被拆成文字丢失结构 | 识别为表格，可能转 Markdown 保留 |
| 图片 | 丢弃 | OCR + ViT 理解 |
| 公式 | 乱码 | LaTeX 还原 |
| 分块 | 固定字数截断 | 按文档结构（标题层级、段落边界） |
| 知识库管理 | 无 | 内置知识库 + 权限 + 版本管理 |
| 部署 | 自搭建 | Docker Compose 一键部署 |

## 效果差异

```
原始 PDF（两栏布局，左栏正文，右栏表格）：
┌─────────────────┬──────────────┐
│ 文本段落...      │ 价格表        │
│ 文本段落...      │ ┌───┬───┐   │
│ 文本段落...      │ │A │10 │   │
│                  │ │B │20 │   │
│                  │ └───┴───┘   │
└─────────────────┴──────────────┘

Naive RAG 的结果：从左到右逐行拼接
"文本段落... 文本段落... 价格表 ┌───┬───┐ A │10"

RAGFlow 的结果：结构化分块
Chunk 1: "文本段落... 文本段落..."
Chunk 2: "价格表\n| A | 10 |\n| B | 20 |"
```

## 部署

```bash
# Docker Compose 一键部署
git clone https://github.com/infiniflow/ragflow.git
cd ragflow/docker
docker compose up -d

# 访问 http://localhost:9380
# 默认账号: ragflow 密码: ragflow
```

## 产品层功能

- **知识库管理** — 创建多个知识库，每个知识库可配置不同的解析策略
- **Chunk 模板** — 自定义分块策略（按标题、按字数、按段落）
- **手动修正** — 解析结果可视化，支持手动调整分块边界
- **Rerank 配置** — 可对接 BGE-Reranker 等重排序模型
- **LLM 对接** — OpenAI / DeepSeek / Qwen / Ollama / 本地模型
- **检索测试** — 内置检索质量测试面板
- **API** — RESTful API 可集成到业务系统

## 面试追问

> [!question] 追问详析
>
> **Q1: RAGFlow 的 DeepDoc Parser 具体怎么工作？**
>
> 三阶段流水线：
>
> **阶段一：版面分析（Layout Detection）**
> 用基于 Detectron2 / PP-OCRv4 的版面分析模型，识别页面上每个区域的类型：
> - Text（正文文本）
> - Title（标题）
> - Table（表格）
> - Figure（图片/图表）
> - Header/Footer（页眉页脚）
> - Equation（公式）
>
> 输出：每个区域的位置（bbox）+ 类型 + 置信度
>
> **阶段二：内容提取**
> - 文本区域 → OCR 或直接提取
> - 表格区域 → OCR + 表格结构识别（提取行列结构，转 Markdown/HTML）
> - 图片区域 → ViT 模型做图文理解（可选）
> - 公式区域 → LaTeX 识别
>
> **阶段三：语义重组**
> 按文档的标题层级（H1→H2→H3...）重新组织成树状结构，同一层级下的内容合并为 Chunk，保证 Chunk 的语义完整性。
>
> **Q2: RAGFlow 跟 Dify 的区别是什么？**
>
> | 维度 | RAGFlow | Dify |
> |------|---------|------|
> | 核心定位 | RAG 引擎 | LLM 应用平台 |
> | 文档解析 | 深度（DeepDoc） | 轻量（普通 text split） |
> | 工作流 | RAG 专有 | 通用 LLM 编排 |
> | Agent 支持 | 有限 | 完整（Tool/Agent/Workflow） |
> | 整体范围 | 聚焦 RAG 质量 | 全栈 AI 应用平台 |
>
> Dify 什么都做（Chatbot/Agent/Workflow/RAG），RAGFlow 只在 RAG 这一个点上做深。可以**组合使用**：RAGFlow 做文档解析，Dify 做上层编排。
>
> **Q3: RAGFlow 的检索质量怎么样？实际 RAG 评测？**
>
> RAGFlow 的强项在**文档解析**，不是检索算法。检索层面它用的是常规 Embedding + Rerank，没有像 Jina ColBERT 那样的交互式检索或 Late Interaction 机制。
>
> 评测角度：
> - 文档解析准确率：比 Naive RAG 高很多（尤其 PDF、扫描件）
> - 检索召回率：取决于 Embedding 模型和 Rerank 配置，跟 LangChain 没本质区别
> - 整体回答质量：解析好 → 分块好 → 检索命中率高 → 回答质量高
>
> 关键结论：**RAGFlow 解决的是"给 LLM 喂进去的是什么"的问题，不是"怎么找到最相关内容"的问题。**
>
> **Q4: RAGFlow 什么时候不适用？**
>
> - 数据是纯文本/无格式的（log、代码、JSON）→ DeepDoc 优势不发挥
> - 不需要知识库管理功能 → 太重了，LangChain 几行代码够用
> - 需要与现有系统深度集成 → RAGFlow 是独立服务，API 集成有适配成本
> - 实时检索/高频写入 → RAGFlow 偏批量导入，动态更新体验不如向量库原生
> - 已经有成熟的文档预处理 Pipeline → 没必要再加一层

## 避坑

> [!warning] 常见坑点
>
> **坑1：把所有文档都丢进 RAGFlow 期望奇迹**
>
> RAGFlow 改善的是文档解析质量，不是检索魔法。如果源文档质量差（低分辨率扫描件、手写笔记），DeepDoc 也救不了。
>
> **坑2：RAGFlow 解析慢**
> ```python
> # 一个 100 页的 PDF + OCR + 表格识别
> # 处理时间 = 几十秒到几分钟
> # 不适合实时上传解析
> ```
> 它是离线批处理设计，别当在线 API 用（除非自己加队列）。
>
> **坑3：把 RAGFlow 当向量数据库用**
>
> RAGFlow 内置了 ES/FAISS 做向量存储，但它不是通用向量数据库。不要绕过 RAGFlow 的 API 直接操作底层存储，版本升级会挂。
>
> **坑4：忽略 Rerank 环节**
> ```python
> # RAGFlow 默认不开启 Rerank
> # 没开 Rerank 时，检索质量 = Embedding 的 recall@top-k
> # 开了 Rerank 后，检索质量 = Rerank 的 precision@top-k
> # 差距通常在 10-20% 的准确率提升
> ```
> 生产环境一定配 Rerank，否则浪费了 DeepDoc 解析出来的高质量 Chunk。
>
> **坑5：多语言文档的 OCR 问题**
>
> RAGFlow 的 OCR 基于 PaddleOCR，对中文支持极好，但小语种（阿拉伯语、泰语、越南语）的 OCR 质量取决于 PaddleOCR 模型对该语言的支持程度。

## 相关笔记

- [[Q-Naive RAG 到 Advanced RAG 演进]]
- [[Q-Dify 和 RAGFlow 对比]]
- [[Q-RAG 检索质量评估方法]]
- [[Q-文档解析在 RAG 中的重要性]]

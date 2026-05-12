---
tags:
  - rag
  - query-routing
  - agent
  - architecture
  - skill
---

# Q: Query Routing 的 Prompt Template Routing 和 Skills 机制本质相同？

## 一句话答案

对。两者共享同一个核心模式：**分类 → 匹配 → 分支分发**。Query Routing 说的是路由这个概念本身，Skills 是这个模式在 Agent 工程中的一种具体实现。

## 两种机制对照

```
Query Routing (概念层):
用户输入 → 分析器(LLM/分类器/Embedding相似度) → 选择路由分支 → 执行分支逻辑

Skills (工程实现层):
用户输入 → LLM 判断技能匹配 → 加载对应 SKILL.md → 注入指令到上下文 → 执行
```

||Query Routing - Prompt Template Routing|Skills 机制|
|--|--|--|
|**输入**|用户查询|用户指令/问题|
|**分类器**|LLM 分类 / Embedding 相似度 / 规则匹配|LLM 意图判断（隐式或显式分类）|
|**匹配对象**|Prompt 模板（指令+格式）|SKILL.md（指令+规则+参考）|
|**分发动作**|注入对应模板到 LLM 上下文|注入对应 SKILL.md 到 LLM 上下文|
|**分支粒度**|粗到细均可（领域→场景→动作）|通常是领域/任务级|
|**回退机制**|默认路由 / 兜底模板|无匹配时直接回答（不使用 skill）|

## Query Routing 全景

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────┐
│            Query Router                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │LLM Classi-│  │Embedding │  │Rule-based│  │
│  │fier      │  │Similarity│  │Regex/Key │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└────────────────┬────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
Prompt     Retriever      Agent
Template   Route          Route
(RAG)      (多知识库)     (多工具)
```

**三种路由类型：**

| 类型 | 核心逻辑 | 典型工具 |
|------|---------|---------|
| **Prompt Template Routing** | 不同查询走不同 Prompt | RAGFlow 的 Prompt 配置、LangChain Hub |
| **Retriever Routing** | 不同查询走不同知识库 | LangChain RouterRetriever、LlamaIndex Router |
| **Agent Routing** | 不同查询走不同 Tool/Agent | Skills 机制、OpenAI Function Calling 的路由选择 |

## 为什么说 Skills 就是 Prompt Template Routing 的具体实现

以 OpenCode 为例，一个用户说"帮我优化数据库设计"：

```
Without Skills:
用户输入 → LLM 直接回答 → 没有领域约束 → 输出通用答案

With Skills (Prompt Template Routing 的实现):
用户输入 → LLM 判断"这跟数据库有关" 
    → 加载 database-designer 的 SKILL.md（相当于选了一个 prompt 模板）
    → SKILL.md 注入到上下文：你可以用这些工具、按这个流程、关注这些指标
    → LLM 在约束下回答 → 输出有领域深度的答案
```

本质上就是：
```python
# 路由函数
router = {
    "database": {"skill": "database-designer", "prompt": "...数据库规范..."},
    "api":      {"skill": "mcp-server-builder", "prompt": "...API设计规范..."},
    "rag":      {"skill": "rag-architect",      "prompt": "...RAG设计规范..."},
}

user_input = "帮我设计用户表"
route = classifier(user_input)  # → "database"
context_inject(router[route]["prompt"])
# LLM 在 database 的 prompt 约束下回答
```

**Prompt Template Routing = 概念，Skills = 这个概念的工程化封装。** 区别只在于 Skills 还附加了文件管理（SKILL.md）、自动发现、版本管理等工程特性。

## 面试追问

> [!question] 追问详析
>
> **Q1: 为什么需要 Query Routing？直接用一个大 Prompt 不行吗？**
>
> 大 Prompt 的问题：
> 1. **上下文窗口限制** — 把所有分支的指令都塞进去，太长会丢掉关键信息（Lost in the Middle）
> 2. **指令冲突** — "当你回答数据库问题时，要用 ER 图"和"当你回答前端问题时，要用 JSX"，两条指令在同一个 Context 里互相干扰
> 3. **Token 浪费** — 用户只问一个简单问题，但 Prompt 里包含了所有领域的指令
> 4. **维护困难** — 一个巨型 Prompt 改了数据库部分，可能影响前端部分
>
> ```python
> # ❌ 大 Prompt 模式
> SYSTEM_PROMPT = """
> 你是数据库专家...
> 你是前端专家...
> 你是运维专家...
> """  # 越长越难用
>
> # ✅ 路由模式
> route = classify(user_input)
> prompt = load_skill(route)  # 只加载需要的
> ```
>
> **Q2: Skills 和 Function Calling 的区别？**
>
> | 维度 | Skills | Function Calling |
> |------|--------|----------------|
> | 本质 | **注入指令**到上下文 | **调用外部功能** |
> | 执行方式 | 修改 LLM 的 System Prompt | 触发外部 API/函数 |
> | 输出 | 仍由 LLM 生成文本 | 工具返回结构化数据 |
> | 控制粒度 | 约束回答方向和风格 | 执行具体操作 |
> | 典型场景 | "用 SQL 专家的方式来回答" | "查询数据库返回结果" |
>
> Skills 和 Function Calling 可以**组合使用**：Skill 告诉 LLM "你应该用 SQL 专家的方式思考"，然后 LLM 调用 `query_database` Function 获取数据。
>
> **Q3: Query Routing 的实现方式有哪些？**
>
> | 方式 | 原理 | 优点 | 缺点 |
> |------|------|------|------|
> | LLM 分类 | LLM 判断"这属于哪个路由" | 灵活、理解语义 | 延迟高、有误判 |
> | Embedding 相似度 | 把路由描述和 query 都向量化，算相似度 | 速度快、确定性 | 需要预定义描述、兜底差 |
> | 规则匹配 | 关键词/正则匹配 | 零延迟、可解释 | 不灵活、维护成本高 |
> | 混合 | LLM 先粗分类，规则做精匹配 | 兼顾灵活和稳定 | 实现复杂 |
>
> ```python
> # Embedding-based Routing — 效率最高
> from sentence_transformers import SentenceTransformer
> model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
>
> routes = {
>     "database": "数据库设计、SQL优化、表结构问题",
>     "rag": "RAG系统、向量检索、文档问答",
>     "agent": "Agent架构、Tool Calling、多Agent协作",
> }
>
> # 算 query 和每个路由描述的相似度
> query_vec = model.encode(user_input)
> route_vecs = model.encode(list(routes.values()))
> best_route = list(routes.keys())[np.argmax(query_vec @ route_vecs.T)]
> ```
>
> **Q4: Skills 机制的局限性？**
>
> 1. **路由粒度不够细** — Skills 通常是领域级（"数据库"），不能细到"这个具体数据库问题用什么思维方式回答"
> 2. **静态匹配** — SKILL.md 是固定的，不会根据用户历史动态调整
> 3. **覆盖盲区** — 如果没有匹配合适的 Skill，Fallback 表现取决于默认行为
> 4. **Skill 冲突** — 如果用户问的是"用 RAG 为数据库设计知识库"，RAG Skill 和 Database Skill 都可能触发，需要优先级仲裁

## 避坑

> [!warning] 常见坑点
>
> **坑1：路由分类器误判**
> ```python
> # 用户问："向量数据库的索引类型有哪些？"
> # 误判："这是在问数据库 → 走 database 路由 → 用 SQL 思维回答"
> # 实际上应该走 vector-database 或 rag 路由
> ```
> Embedding 路由需要精心设计 route description，LLM 路由需要给 few-shot 示例。
>
> **坑2：多层路由嵌套导致延迟叠加**
> ```python
> # 路由1: LLM 分类 → 200ms
> # 路由2: 再LLM分类 → 200ms  
> # 路由3: 再LLM路由 → 200ms
> # 还没开始回答就 600ms 了
> ```
> 多级路由用 Embedding 或规则在浅层，LLM 只做最后一级决策。
>
> **坑3：Skill 的回退策略不清晰**
>
> 当没有 skill 匹配时，是报错还是走默认回答？Skill 机制通常缺乏明确的 "no match" 处理策略，导致用户的边界问题得不到好结果。

## 相关笔记

- [[Q-RAGFlow详解]]
- [[Q-Agent架构中的路由策略]]
- [[Q-RAG 系统的 Query Routing 设计]]
- [[Q-Skills 机制和 Function Calling 对比]]

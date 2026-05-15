---
tags:
  - agent
  - architecture
  - decision-making
  - tool-calling
---

# Q: 什么时候需要引入 Agent？

## 一句话答案

当你需要 LLM 自主规划、调用外部工具、执行多步任务时才需要 Agent；单步知识问答用 RAG 就够了，Agent 只会增加复杂度和延迟。

## Agent 的核心能力

Agent 有三个核心能力，缺一不可：

| 能力 | 说明 | 是否需要 Agent |
|------|------|---------------|
| **多步推理** | 将复杂任务拆解为多个步骤 | ✅ 需要 |
| **工具调用** | 调用 API、数据库、代码执行器 | ✅ 需要 |
| **自主决策** | 根据中间结果调整策略 | ✅ 需要 |
| **记忆管理** | 维护长期和短期记忆 | ✅ 需要（可选） |
| **知识检索** | 从外部知识库获取信息 | ❌ 用 RAG 就够 |

## 需要 Agent 的典型场景

### 场景 1：多步任务编排

```
用户目标：帮我做一顿完整的晚餐

Agent 规划：
├── 步骤 1：查询冰箱食材 → 调用库存 API
├── 步骤 2：检索适合的菜谱 → 调用 RAG
├── 步骤 3：检查是否有过敏食材 → 调用用户偏好数据库
├── 步骤 4：生成购物清单 → 调用计算工具
└── 步骤 5：输出完整方案 → 综合所有结果
```

### 场景 2：工具调用

```
用户目标：查一下今天的天气，推荐适合的菜

Agent 执行：
├── 调用天气 API → 获取天气信息
├── 分析天气特点 → LLM 推理
├── 调用 RAG 检索 → 适合的菜谱
└── 综合推荐 → 生成答案
```

### 场景 3：复杂决策

```
用户目标：如果推荐的菜用户不满意，自动调整策略

Agent 执行：
├── 首次推荐 → 调用 RAG
├── 用户反馈 → 解析意图
├── 分析不满意原因 → LLM 推理
├── 调整策略 → 修改推荐参数
└── 重新推荐 → 调用 RAG
```

### 场景 4：数据处理

```
用户目标：分析这个 CSV 文件，生成可视化报告

Agent 执行：
├── 读取文件 → 调用文件系统
├── 数据清洗 → 调用 Python 代码执行器
├── 统计分析 → 调用 Python 代码执行器
├── 生成图表 → 调用 matplotlib
└── 输出报告 → 综合所有结果
```

## 不需要 Agent 的场景

### 场景 1：单步问答

```
用户问题：红烧肉怎么做？

直接用 RAG：
├── 检索菜谱 → 向量检索
└── 生成答案 → LLM 生成

不需要 Agent 的理由：
- 只需要一次检索和一次生成
- 没有工具调用需求
- 没有多步推理需求
```

### 场景 2：信息检索

```
用户问题：Python 的 sorted 函数怎么用？

直接用 RAG：
├── 检索文档 → 向量检索
└── 生成答案 → LLM 生成

不需要 Agent 的理由：
- 单步知识问答
- 答案在文档中直接可得
```

### 场景 3：简单生成

```
用户问题：帮我写一封邮件

直接用 LLM：
└── 生成邮件 → LLM 生成

不需要 Agent 的理由：
- 不需要外部信息
- 不需要工具调用
- 单步生成任务
```

## 决策流程图

```
你的场景需要什么？
│
├─ 需要访问外部知识（文档、数据库、API）
│   │
│   ├─ 只需要检索和回答（单步）
│   │   └─ ✅ 用 RAG
│   │
│   └─ 需要检索 + 其他操作（多步）
│       └─ ✅ 用 Agent（RAG 作为工具）
│
├─ 需要调用外部工具（API、代码执行、文件操作）
│   └─ ✅ 用 Agent
│
├─ 需要多步推理和决策
│   └─ ✅ 用 Agent
│
├─ 需要维护对话状态和记忆
│   └─ ✅ 用 Agent（可选）
│
└─ 只是简单对话，不需要外部信息
    └─ ✅ 直接用 LLM
```

## Agent vs Chain vs RAG 对比

| 维度 | RAG | Chain | Agent |
|------|-----|-------|-------|
| **流程** | 固定（检索→生成） | 固定（预定义步骤） | 动态（LLM 决策） |
| **灵活性** | 低 | 中 | 高 |
| **可控性** | 高 | 高 | 中 |
| **延迟** | 低 | 中 | 高 |
| **适用场景** | 知识问答 | 流程固定的多步任务 | 流程不确定的任务 |

### 选择建议

```
任务流程是否确定？
│
├─ 是 → 用 Chain（预定义步骤）
│   └─ 例如：文档处理流水线
│
└─ 否 → 流程是否复杂？
    │
    ├─ 简单（单步） → 用 RAG
    │   └─ 例如：知识问答
    │
    └─ 复杂（多步） → 用 Agent
        └─ 例如：复杂任务编排
```

## Agent 的实现方式

### 1. Function Calling（推荐）

最主流的方式，通过 LLM 的 Function Calling 能力调用工具。

```python
# Function Calling 实现
from openai import OpenAI

client = OpenAI()

# 定义工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_recipe",
            "description": "搜索菜谱",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "category": {"type": "string", "description": "菜系分类"}
                },
                "required": ["query"]
            }
        }
    }
]

# 调用 LLM
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "帮我做一顿晚餐"}],
    tools=tools,
    tool_choice="auto"
)

# 处理工具调用
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    # 执行工具...
```

### 2. LangChain Agent

使用 LangChain 框架实现 Agent。

```python
# LangChain Agent 实现
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.tools import Tool

# 定义工具
tools = [
    Tool(name="SearchRecipe", func=search_recipe, description="搜索菜谱"),
    Tool(name="GetWeather", func=get_weather, description="获取天气"),
]

# 创建 Agent
llm = ChatOpenAI(model="gpt-4")
agent = create_openai_tools_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 运行
result = agent_executor.invoke({"input": "帮我做一顿晚餐"})
```

### 3. LangGraph（推荐用于复杂 Agent）

使用 LangGraph 实现更复杂的 Agent 工作流。

```python
# LangGraph 实现
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

# 定义状态
class AgentState(TypedDict):
    messages: list
    next_step: str

# 定义节点
def planner(state: AgentState):
    # 规划下一步
    ...

def tool_executor(state: AgentState):
    # 执行工具
    ...

def should_continue(state: AgentState):
    # 判断是否继续
    ...

# 构建图
workflow = StateGraph(AgentState)
workflow.add_node("planner", planner)
workflow.add_node("tool_executor", tool_executor)
workflow.add_conditional_edges("planner", should_continue)
workflow.add_edge("tool_executor", "planner")

# 编译运行
app = workflow.compile()
result = app.invoke({"messages": [...]})
```

## 面试追问

> [!question] 追问详析
>
> **Q1: Agent 的核心组件有哪些？**
>
> Agent 有三个核心组件：
>
> 1. **规划（Planning）**
>    - 任务拆解：将复杂任务分解为可执行的子任务
>    - 执行顺序：决定子任务的执行顺序
>    - 动态调整：根据中间结果调整后续计划
>
> 2. **工具调用（Tool Use）**
>    - 工具选择：根据任务选择合适的工具
>    - 参数构造：为工具构造正确的输入参数
>    - 结果解析：解析工具返回的结果
>
> 3. **记忆（Memory）**
>    - 短期记忆：当前对话的上下文
>    - 长期记忆：历史交互的经验
>    - 工作记忆：当前任务的中间状态
>
> **Q2: Agent 和 Chain 有什么区别？**
>
> | 维度 | Chain | Agent |
> |------|-------|-------|
> | **流程** | 固定，预定义 | 动态，LLM 决策 |
> | **灵活性** | 低 | 高 |
> | **可控性** | 高 | 中 |
> | **调试** | 容易 | 困难 |
> | **适用场景** | 流程确定的任务 | 流程不确定的任务 |
>
> 选择建议：
> - 如果任务流程可以预定义，用 Chain（更可控）
> - 如果任务流程需要 LLM 动态决策，用 Agent（更灵活）
>
> **Q3: 如何设计一个可靠的 Agent？**
>
> 可靠的 Agent 需要：
>
> 1. **明确的工具定义**
>    - 工具描述清晰准确
>    - 参数类型和约束明确
>    - 返回格式标准化
>
> 2. **合理的规划策略**
>    - 设置最大步数限制（防止无限循环）
>    - 设置超时机制（防止卡死）
>    - 提供回退策略（工具调用失败时）
>
> 3. **完善的错误处理**
>    - 工具调用失败的重试机制
>    - 参数错误的修正引导
>    - 超时的优雅降级
>
> 4. **可观测性**
>    - 记录每一步的决策和执行
>    - 提供调试日志
>    - 支持中断和恢复

## 避坑

> [!warning] 常见坑点
>
> **坑1：所有场景都用 Agent**
>
> ```python
> # ❌ 错误：单步问答也用 Agent
> agent = Agent(tools=[rag_tool, search_tool, ...])
> result = agent.run("红烧肉怎么做？")  # 太慢，太复杂
>
> # ✅ 正确：单步问答直接用 RAG
> rag = RAGSystem()
> result = rag.query("红烧肉怎么做？")  # 快速，直接
> ```
>
> 原因：Agent 的规划和工具调用会增加 2-5 秒延迟，对于单步问答这是不必要的开销。
>
> **坑2：Agent 没有兜底机制**
>
> ```python
> # ❌ 错误：Agent 没有最大步数限制
> agent = Agent(tools=[...], max_steps=None)  # 可能无限循环
>
> # ✅ 正确：设置最大步数和超时
> agent = Agent(tools=[...], max_steps=10, timeout=60)
> ```
>
> 原因：LLM 的自主决策可能陷入循环或偏离目标，必须有兜底机制。
>
> **坑3：工具定义不清晰**
>
> ```python
> # ❌ 错误：工具描述模糊
> tools = [
>     {"name": "search", "description": "搜索"}  # 搜索什么？
> ]
>
> # ✅ 正确：工具描述清晰
> tools = [
>     {
>         "name": "search_recipe",
>         "description": "根据关键词搜索菜谱，返回菜名、食材、步骤",
>         "parameters": {
>             "query": {"type": "string", "description": "搜索关键词，如'红烧肉'"},
>             "category": {"type": "string", "enum": ["荤菜", "素菜", "汤品"]}
>         }
>     }
> ]
> ```
>
> 原因：LLM 根据工具描述选择工具，描述不清晰会导致选择错误。
>
> **坑4：忽略 Agent 的局限性**
>
> Agent 的能力边界：
> - ✅ 有明确工具可调用的任务
> - ✅ 可以拆解为明确步骤的任务
> - ❌ 需要创造性思维的任务（没有标准答案）
> - ❌ 需要实时感知环境的任务（没有对应工具）
> - ❌ 需要精确计算的任务（LLM 计算不可靠）
>
> 原因：Agent 的能力取决于工具集和 LLM 的推理能力，不是万能的。

## 相关笔记

- [[Q-RAG和Agent的区别与选择]]
- [[Q-RAG系统优化方向全解析]]
- [[Function Calling 深度解析]]
- [[Q-Query-Routing和Skills机制对比]]
- [[路由在RAG与Agent系统中的作用]]

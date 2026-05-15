# Function Calling 深度解析

> 与 MCP、Skill 的对比 + 全能 AI 助手的可行性边界

---

## 一、Function Calling 的本质

Function Calling（又称 Tool Calling）是现代 LLM 的关键能力，但常被误解。其核心不是"模型执行函数"，而是**模型输出函数调用的指令，你的代码负责执行**。

### 1.1 tools 到底是什么

tools 在技术上就是**一个 JSON Schema 格式的函数声明**，不是可执行代码：

```python
tool_definition = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "获取天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "城市名称"}
            },
            "required": ["location"]
        }
    }
}
```

模型看到这个声明后，如果认为用户问题匹配，返回一个特殊响应 `tool_calls`：

```json
{
  "tool_calls": [{
    "id": "call_xxx",
    "function": {
      "name": "get_weather",
      "arguments": "{\"location\": \"杭州\"}"
    }
  }]
}
```

你的代码解析这个指令，找到对应的 Python 函数，传入参数执行，把结果塞回对话。模型自始至终只负责"决策调哪个工具"和"生成参数"，实际干活的一直是你的代码。

### 1.2 执行位置

```
客户端/服务端
    │
    ├─ LLM API 调用（传 tools 声明 + 用户问题）
    │      │
    │      ▼
    ├─ LLM 返回 tool_calls（模型只决策，不执行）
    │      │
    │      ▼
    ├─ 本地代码解析 tool_calls，执行实际函数（发 HTTP、读文件、查 DB）
    │      │
    │      ▼
    ├─ 将结果以 role: tool 发回 LLM
    │      │
    │      ▼
    └─ LLM 组织最终自然语言回答
```

工具执行永远在你的进程里。LLM 服务商的服务器只参与"决策调哪个工具 + 生成参数"和"看到工具结果后生成最终回答"两个环节。实际的查天气 API 调用、文件读写、数据库查询全都发生在你自己控制的执行环境中。这也是 Function Calling 安全性的基础——你控制哪些函数暴露、何时调用、如何兜底。

---

## 二、Function Calling vs MCP vs Skill

| 维度 | Function Calling | MCP | Skill |
|------|-----------------|-----|-------|
| 本质 | 底层交互机制 | 标准化协议 | 指令/工作流文档 |
| 载体 | JSON Schema 函数声明 | 通过 MCP 协议暴露的工具列表 | Markdown 文件 |
| 谁消费 | LLM 的 tool_calls 机制 | LLM（通过宿主） | AI Agent（作为上下文指令） |
| 执行者 | 宿主代码 | MCP Server | AI 自身 + 工具 |
| 通信 | 进程内绑定 | 跨进程/跨机器（SSE/stdio） | 不涉及通信 |

- **Function Calling**: LLM 输出 tool_calls 后宿主代码自己实现逻辑
- **MCP**: LLM 输出 tool_calls 后宿主通过 MCP 协议调用远端 Server 的实现。MCP 的 tool 定义和 Function Calling 一一对应：`name`=`name`、`description`=`description`、`inputSchema`=`parameters`。MCP 把"本进程内硬编码的函数"升级为"通过标准化协议发现和调用的远程服务"
- **Skill**: 给 AI 的指令文档，定义"怎么做"而非"调什么接口"。在更高层编排能力和思考流程

**关系链**: Function Calling(基础机制) → MCP(标准化为协议) → Skill(高层编排)

---

## 三、全能 AI 助手的可行性

### 成立的部分

每个 tool 就是一项能力——排列组合可覆盖几乎任何人类通过电脑完成的操作：

| 能力 | 对应 tool |
|------|----------|
| 查天气 | `get_weather` |
| 操作文件 | `read_file` / `write_file` |
| 执行代码 | `run_python` |
| 控制浏览器 | `navigate` / `click` / `type` |
| 调用 API | `call_third_party_api` |
| 搜索 | `search_web` |

理论上注册足够多、足够完备的 tool，就能让 AI 助手具备任意能力。这就是 Anthropic Computer Use、OpenAI Operator、各种 Agent 框架的基本思路。

### 现实约束

| 约束 | 原因 | 应对 |
|------|------|------|
| 上下文天花板 | 注册 1000 个 tool 的描述就把上下文撑爆 | 分层路由 + 动态注入 |
| 决策不可靠 | 复杂场景下 LLM 选错工具、生成错误参数 | 不做全自动，保留人工确认环 |
| 错误链式放大 | 一个 tool 返回异常，后续依赖的全跑偏 | 每次调用做验证 + 设回滚点 |
| 顺序依赖隐性 | "先登录才能发帖"，LLM 不一定能推导出 | 显式声明 tool 的前置条件 |
| 长尾衰减 | 越少调用的 tool 越容易被遗忘或误用 | 缓存命中率统计 + 不活跃 tool 自动降级 |

### 实际架构

全能助手不是"一个模型 + 一万个 tool"，而是**多层架构**：

```
用户输入 → 意图路由层（判断领域）→ 动态注入层（只加载最相关 10-20 个 tool）
         → 执行+验证层（调用、校验、重试）→ 兜底层（置信度低时走人工/拒绝）
```

## 相关笔记

- [[Q-RAG和Agent的区别与选择]]
- [[Q-什么时候需要Agent]]
- [[Q-Query-Routing和Skills机制对比]]
```

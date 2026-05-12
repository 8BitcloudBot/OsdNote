# OsdNote

AI 面试八股 + 项目技术栈知识库。

## 结构

```
notes/
├── 八股文/
│   ├── LLM原理/
│   ├── Prompt工程/
│   ├── RAG/
│   ├── Agent/
│   ├── 向量数据库/
│   └── 推理部署/
└── 项目技术栈/
    ├── LangChain/
    ├── LangGraph/
    ├── FastAPI/
    └── Docker/
```

每张卡片格式：**Q → 一句话答案 → 对比 → 代码 → 追问详析 → 避坑 → 相关笔记**

## 工作流

1. 在 `notes/` 下写 Markdown 卡片
2. 同步到 Obsidian：`python3 scripts/sync_to_obsidian.py`（每日 00:00 自动）
3. 推送 GitHub：`git add -A && git commit -m "kb: add Q-xxx" && git push`

## 同步

```bash
python3 scripts/sync_to_obsidian.py
```

将 `notes/` 的内容镜像到 Obsidian vault `/Users/wxhu/Documents/Obsidian_workspace/OpencodeDev`。

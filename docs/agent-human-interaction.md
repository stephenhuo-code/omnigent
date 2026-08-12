# Agent 与人的交互机制：横向调研

调研开源 agent 框架在「agent 需要人介入」这件事上的做法，为 omnigent 的交互设计提供对照。

重点回答两个问题：**谁有 inbox 机制**，以及**人机交互有哪些典型模式**。

> 关于名字：本文的 Hermes 指 **Nous Research** 的 Hermes Agent
> （`hermes-agent.nousresearch.com`，即 `omnigent/inner/hermes_executor.py` 对接的那个）。
> 网上有若干同名产品，结论不适用于它们。

---

## 一、inbox 机制的有无

| 框架 | inbox | 形态 |
|---|---|---|
| **LangChain Agent Inbox** | ✅ 独立产品 | Gmail 式界面，跨 agent 汇总所有被 `interrupt()` 挂起的线程 |
| **Multica** | ✅ | 「agent 需要你时才通知，不是每一步」 |
| **omnigent** | ✅ ×2 | `/inbox` 页面（给人）+ `sys_read_inbox`（给 agent） |
| **Hermes** | ⚠️ 近似 | Mission control 看板 + 审批，未叫 inbox |
| **LangGraph** | 底层原语 | `interrupt()` + checkpointer；Agent Inbox 是它的 UI 层 |
| **CrewAI** | ❌ | `human_input=True` 的任务级 gate |
| **AutoGen** | ❌ | `UserProxyAgent` 把人建模成对话图里的一个节点 |
| **OpenJarvis** | ❌ | 本地优先、能效导向（Watt / FLOPs / 延迟 / 成本），交互不是重点 |

**规律**：inbox 只在「**多会话并发 + 异步执行**」的平台上出现。单会话同步对话不需要它——人本来就盯着那一个流。它解决的是**注意力分配**问题，不是机制问题。

---

## 二、九种典型交互模式

### 1. 同步阻塞审批

agent 停下等人回答。Claude Code 默认模式、MCP elicitation 都是这个。

MCP 把它标准化成 `ElicitationRequest`，两种子模式：

- **Form** —— 带 JSON Schema 的结构化表单，客户端应允许用户查看、修改、拒绝或取消
- **URL** —— 敏感操作跳转外部页面，凭据不经过 MCP 客户端

### 2. 策略预设替代逐次询问

用规则一次性表达意图。Claude Code 的五档权限模式是最完整的实现：

| 模式 | 行为 |
|---|---|
| `default` | 改状态的操作都问，只读不问 |
| `acceptEdits` | 文件操作自动批，命令仍问 |
| `plan` | 只读探索，所有写入挂起到退出该模式 |
| `dontAsk` | 自动化场景 |
| `bypassPermissions` | 全放开，仅限隔离环境 |

再叠加 allowlist 规则和 `PreToolUse` hook——后者在权限系统**之前**运行，可在运行时批准、拒绝或改写工具调用。

### 3. 计划先行

先出完整方案 → 人批准整体 → 再执行。把 N 次微观审批压缩成一次宏观决策。

### 4. 中断-检查点-恢复

LangGraph 的核心贡献。`interrupt()` 暂停时把**完整状态快照**持久化：哪个节点在跑、每个 state key 的值、节点体内停在哪。人可以隔几小时再回答。

生产环境要求持久化 checkpointer（Postgres / Mongo）。**这是「长时间等待」能成立的技术前提**——没有 checkpoint，进程一重启待办就丢了。

### 5. 收件箱汇总

把散落在各会话的待办拉到一处。你开了 10 个会话，不点进去就不知道哪个在等你。

### 6. 看板 / 工单

Multica 和 Hermes 都用。agent「领取 issue、汇报进度、提出阻塞、交回评审」——把 agent 当队友而非工具。适合异步委派。

### 7. 评审门禁

Multica 的表述很精准：**Work lands in review, not in main. You decide what ships.** agent 不能直接合并，产物必须过人工评审。

### 8. 人作为 Agent

AutoGen 的 `UserProxyAgent`——不把「人」当特例，而是当成对话图里的一个节点。审批点因此是结构自带的，而非事后补的。

### 9. Agent 自己的异步收件箱

**这一种是 agent-to-agent，与前八种不同。** omnigent 的 `sys_call_async` / `sys_read_inbox` / `sys_cancel_async`：派发后台任务、稍后取回结果，替代轮询。

见 `omnigent/tools/builtins/async_inbox.py`。三个工具由 agent 的 `async:` 开关统一控制，**默认开启**；写 `async: false` 会一并移除。

> 该模块的注释引用了 `designs/SERVER_HARNESS_CONTRACT.md`，但这份文件不在本仓库里
> —— 是上游留下的悬空引用，协议细节只能从代码读。

---

## 三、四种响应动作已成事实标准

LangGraph、Agent Inbox、MCP 三方独立收敛到同一组：

| 动作 | 含义 |
|---|---|
| **Accept** | 原样批准 |
| **Edit** | 改参数后再执行 |
| **Respond** | 文字回复（「ask user」类工具） |
| **Ignore / Reject** | 拒绝，可带理由 |

MCP 用的是三值 `accept` / `decline` / `cancel`，多出一层区分：**「明确拒绝」和「没作选择就关掉了」不是一回事**。omnigent 沿用了这个三分（`ElicitationResult`），在审计上有意义——超时不该被记成拒绝。

---

## 四、对 omnigent 的观察

### 两种 inbox 并存，在框架里少见

大多数框架只有其中一种。omnigent 的 `/inbox`（人的待办汇总）和 `sys_read_inbox`（agent 的异步结果回收）语义完全不同，共用一个词容易混。**文档和 UI 措辞里值得明确区分。**

### 已经踩在标准上

`ElicitationResult` 的注释写明「Field names + semantics mirror MCP's `ElicitResult` verbatim」，`ElicitationRequestParams` 同样对齐 MCP 的 `ElicitRequestFormParams` / `ElicitRequestUrlParams`。

采用既有线格式而非自造协议，意味着将来接任何 MCP 客户端都省事。

### 缺的是策略层的表达力

Claude Code 有五档权限模式 + allowlist + `PreToolUse` hook；omnigent 目前主要靠 policy engine 加逐次 elicitation。

从「每次问」演进到「**预设策略 + 只上报例外**」是明确的方向，也正是 Multica 那句「agent needs a call, not every step」的意思。这不是要抄五档模式，而是要让常见意图能被一次性表达。

### `/inbox` 刻意不做已读/未读，这个克制是对的

`web/src/pages/InboxPage.tsx` 的注释说明了原因：服务端没有已读、忽略、@提及这些概念，审批只有「解决」和「超时」两种终态。

Agent Inbox 做了已读状态，代价是要维护一套独立的状态机——**多一个可能与真实状态不同步的地方**。

---

## 来源

- [Hermes Agent — Nous Research](https://hermes-agent.io/) · [awesome-hermes-agent](https://github.com/0xNyk/awesome-hermes-agent)
- [OpenJarvis — Stanford Scaling Intelligence Lab](https://scalingintelligence.stanford.edu/blogs/openjarvis) · [仓库](https://github.com/open-jarvis/OpenJarvis)
- [Multica](https://github.com/multica-ai/multica)
- [LangChain Agent Inbox](https://github.com/langchain-ai/agent-inbox) · [文档](https://deepwiki.com/langchain-ai/open-agent-platform/7-agent-inbox)
- [LangGraph Human-in-the-Loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [MCP Elicitation 规范](https://modelcontextprotocol.io/specification/draft/client/elicitation) · [解析](https://workos.com/blog/mcp-elicitation)
- [Claude Code 权限模式](https://code.claude.com/docs/en/permission-modes) · [Agent SDK permissions](https://platform.claude.com/docs/en/agent-sdk/permissions)
- [CrewAI vs AutoGen 对比](https://www.zenml.io/blog/crewai-vs-autogen)

调研时间：2026 年 8 月。框架演进很快，结论有时效性。

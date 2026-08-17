# 契约 · 策略函数

自写策略是本特性**唯一的硬强制载体**。策略由运行时在六个触发点上**无条件求值**,模型没有选择权,也绕不过。

## 声明形态

```yaml
guardrails:
  ask_timeout: 86400            # 全局审批等待上限(秒);G2 需支持天级
  policies:
    <name>:
      type: function
      function:                 # 工厂形式:arguments 是工厂 kwargs
        path: omnigent.policies.pipely.<module>.<callable>
        arguments: {}
      on: [tool_call, tool_result]      # 可窄化到单个工具:tool_call:<tool_name>
      condition: {}                     # 标签门:空/缺省=始终匹配
      ask_timeout: 3600                 # 可覆盖全局
```

**短形式**(可调用对象本身即求值器)也可用:`function: omnigent.policies.pipely.<module>.<callable>`。

## 求值契约

策略是一个 `fn(event, config) -> decision`。工厂形式下,`path` 指向的是**工厂**,在流程开始时调用一次,其返回值才是求值器。

**入参 `event`**:
- `event["type"]` —— 触发点(`tool_call` / `tool_result` / `request` / `response` / `llm_request` / `llm_response`)
- `event["data"]` —— 该触发点的负载。`tool_call` 含工具名与入参;`tool_result` 含**工具的真实返回值**
- `event["context"]["labels"]` —— 会话标签的**只读快照**

**返回 `decision`**:
- `{"action": "allow"}` —— 放行
- `{"action": "deny", "reason": "<给人看的原因>"}` —— 拒绝
- `{"action": "ask", ...}` —— 请求人工批准,经收件箱送达
- `{"set_labels": {...}, "state_updates": [...]}` —— 写状态,可与上述并存
- 返回 `None` —— 弃权(该策略不适用于此事件)

**审批语义**:超时、拒绝、取消**一律按未批准处理,且不留任何副作用**——`set_labels` 与 `state_updates` 仅在批准时才落。

## 本特性的策略清单

### `gates.py` —— 闸门状态机(FR-090、FR-099)

| 求值器 | 触发点 | 职责 |
| --- | --- | --- |
| `record_gate_passage` | `tool_result:<各闸门对应工具>` | 读**工具真实返回值**,满足条件才写 `pipely.gate` |
| `require_gate` | `tool_call:<受控操作>` | 读标签,当前闸门不满足则 deny,并说明缺哪一步 |
| `bind_flow_instance` | `tool_call`(首次) | 写 `pipely.flow.*`;检测到不同 pipeline 值时 deny(一会话一实例) |

**硬约束**:`g2_passed` 只能由核验工具的真实返回值触发。模型声称"我已核验"不会写出标签,后续操作照样被 `require_gate` 拒绝。

### `preflight.py` —— 前置条件校验(FR-091、FR-060)

| 求值器 | 触发点 | 职责 |
| --- | --- | --- |
| `require_preflight` | `tool_call` | 未通过校验则 deny 一切操作 |
| `run_preflight` | `tool_result:bot_selfcheck` | 汇总凭证、共享、审批权、bot 权限四类校验结果,写 `pipely.preflight.*` |

**为什么落在策略而非启动钩子**:运行时**没有 Agent 启动自检钩子**。现有范例的"首轮预检"写在 prompt 里靠模型自觉,是弱强制。

**报错要求**:缺失项必须**一次性列全**(FR-060),且"未共享"与"共享了但未委派审批权"要**分别报告**——前者看不到待办,后者看得到点不动,处置方式不同。

### `handoff.py` —— 交接与部署约束(FR-023、FR-056)

| 求值器 | 触发点 | 职责 |
| --- | --- | --- |
| `artifact_ref_only` | `tool_call`(运维侧作业部署) | 入参含分支名、工作区路径或可写源码位置时 deny |
| `deploy_within_ref` | `tool_call`(作业部署) | 部署的作业定义不在制品引用范围内时 deny |

### `identity.py` —— 凭证边界(FR-074、FR-062、FR-105)

| 求值器 | 触发点 | 职责 |
| --- | --- | --- |
| `deny_cross_pipeline_write` | `tool_call`(目录写) | 运维发布 bot 试图改其他管线资产时 deny |
| `sandbox_scope_only` | `tool_call`(目录写) | 架构开发 bot 试图写沙箱 Domain 之外时 deny |

## 复用的内置策略

先用现成的,不重复造:

| 内置策略 | 用途 | 挂在哪 |
| --- | --- | --- |
| `blast_radius` | 强推/硬重置/根删除恒 DENY;推送、合并、部署 ASK | 架构开发子 Agent |
| `worktree_guard` | 写入限制在工作区子树内 | 架构开发子 Agent |
| `read_only_os` | 拒绝一切改文件的调用 | 三个无 shell 子 Agent(兜底) |
| `spawn_bounds` | 每轮派发上限 | 编排者 |
| `headless_subagent_purpose_guard` | 子 Agent 用途白名单 | 编排者 |
| `cel_policy` | 简单条件判定,免写 Python | 视需要 |

## 测试契约

策略是纯函数,单测直接构造 `event` 断言 `decision`。**每条禁止类需求都必须有一个"构造违规场景 → 断言被拒"的用例**(FR-106)——"次数为 0"用统计证明是弱证明,用测试证明"必然被拒"才是强证明。

测试落 `tests/policies/pipely/`,与 `omnigent/policies/pipely/` 逐目录对应。

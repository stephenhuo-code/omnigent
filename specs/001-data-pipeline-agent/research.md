# Phase 0 · 研究结论

本文件记录 plan 阶段需要拍板的技术决策。所有"运行时能力"类结论均在本仓库源码中核实过,并附出处;凡未能核实的,明确标注。

---

## R1 · 强制载体的选择规则

**决策**:按需求性质选载体,四档强制力不可混用。

| 需求性质 | 载体 | 强制力 |
| --- | --- | --- |
| 压根不该有这个能力 | 不授予该工具(不声明 `os_env`;MCP `tools:` 白名单) | 强 |
| 不能做某事 | 策略在 `tool_call` 返回 deny | 强 |
| 做之前要人批准 | 策略返回 ask → 经收件箱送达 | 强 |
| **必须做且必须做成** | **确定性工具 + `tool_result` 策略写标签 + `tool_call` 策略门控** | 强 |
| 做的时候按确定逻辑 | Python 函数工具 | 中(调不调用由模型决定) |
| 怎么做的知识 | skill / prompt | 弱 |

**理由**:`Phase` 枚举定义了六个触发点,其中 `TOOL_CALL` 在"派发之前"、`TOOL_RESULT` 在"结果回给模型之前"(`omnigent/spec/types.py:1097` 起)。后者能读到**工具的真实返回值**,因此策略据此写标签时,模型无法通过自述伪造。这是把"必须做成"变成硬约束的唯一途径。

**已否决的替代**:
- *全部写进 prompt / skill* —— 运行时**没有强制加载 skill 的机制**(检索 `auto_load` / `always_load` / `mandatory` 均无结果),skill 是模型主动调用加载工具才读到的。把约束写进 skill 等于写进提示词。
- *只用函数工具不配策略* —— 函数工具保证"做的时候按代码做",保证不了"一定会做"。

---

## R2 · 交付位置:定义与代码分放两处

**决策**:Agent 定义(YAML、skills)放 `examples/pipely/`;策略与工具函数放 `omnigent/policies/pipely/` 与 `omnigent/tools/pipely/`。

**理由**(三条硬证据,均已核实):
1. `examples/` 与 `examples/polly/` **都没有 `__init__.py`** —— 不是 Python 包。
2. 已有 Agent 目录名含连字符(`deep-research`)—— 连字符不是合法 Python 标识符,无法 `import`。
3. 打包时 `examples/` 作**资源**处理(`omnigent/_platform.py:287` 说明 `omnigent/resources/examples/polly` 是指向真实目录的 stub 文件),资源目录不在导入路径上。

而 `FunctionRef.path` 的定义是"Dotted import path to the callable"(`omnigent/spec/types.py:1265` 起)。放错位置,FR-090、FR-091 会**静默失效**——不报错,只是策略从未生效。

**已否决的替代**:
- *并入 `omnigent/policies/builtins/`* —— 那是上游内置策略的地盘,混入既模糊职责,又扩大变基冲突面。新建子包是纯新增,不触碰上游任何文件。
- *做成独立可安装包* —— 可行且更解耦,但要额外建包与配置安装;Q1 已定为同仓。将来若需独立演进,挪出目录加 `pyproject.toml` 即可,迁移成本低。

---

## R3 · 闸门状态机的实现形态

**决策**:用会话级 guardrails 标签做状态,自写策略函数读写;`condition` 标签门用于声明式地限定策略生效范围。

**理由**:
- 策略结果支持 `set_labels` 与 `state_updates`(`omnigent/policies/types.py:237` 起),且审批场景下**仅在批准时**才落状态(`omnigent/runtime/policies/approval.py:23`),被拒或超时不留副作用——正是闸门语义所需。
- `PolicySpec.condition` 是标签门,"Empty/absent = always-match",支持 `{"role": ["admin","ops"]}` 这类取值,可把"仅在某闸门已通过时才允许某操作"部分地声明式表达。
- `PhaseSelector` 支持窄化到单个工具(`on: [tool_call:promote_release]`),仅 `TOOL_CALL` / `TOOL_RESULT` 阶段可用。

**关键约束**:标签是**会话级**的。因此一个会话只能承载一次流程实例(FR-099),否则多条管线的闸门状态会互相覆盖。

---

## R4 · 前置条件校验的落点

**决策**:自写策略函数,在**首个工具调用**上拦截,校验凭证齐备、会话共享、审批权委派、bot 权限。

**理由**:运行时**没有 Agent 启动自检钩子**(检索 `preflight` / `startup_check` / `on_start` / `required_env` 于 `omnigent/spec/types.py` 均无结果)。现有范例的"首轮预检"写在 prompt 里,靠模型自觉——那是弱强制,不满足 FR-091。

**注意**:校验本身需要真实探测(如只读 bot 的写探测必须被拒),这属于"确定性逻辑",应做成函数工具由策略调用或由策略直接执行;判定结果写标签,后续操作凭标签放行。

---

## R5 · 人机交互的送达路径

**决策**:闸门与审批统一经**收件箱**送达;跨用户送达靠会话共享 + 审批权委派。

**理由**(链路四环均已核实):
1. `sys_session_share` 按邮箱授予具名用户访问权,级别 read/edit/manage,经 `PUT /v1/sessions/{id}/permissions`(`omnigent/tools/builtins/spawn.py:674` 起)。
2. 会话列表以 `accessible_by=user_id` 过滤,语义为"该用户有权限记录的会话";源码注释明确 *shared sessions still surface for the "Shared with me" tab*(`omnigent/server/routes/sessions/routes_core.py`)。
3. 收件箱由各会话快照的 `pending_elicitations` 跨会话聚合而成(`web/src/lib/inbox.ts`)。
4. 子 Agent 的请求被服务端**镜像到父会话**(同上文件中 `resolveSessionId` 的注释)。

**三条落地约束**:
- **审批权 Agent 授不了**:`sys_session_share` 参数只有 `user_id` 与 `level`,无审批权字段;权限库中该字段默认关闭。必须由会话所有者单独委派。这是刻意的——Agent 不能自己给自己指定批准人。
- **共享能力默认关闭**:`agent_session_sharing` 是 `sys_session_share` 的唯一开关(`omnigent/spec/types.py:1003` 起),默认 `none`。本特性设 `non-public`,**不得设 `public`**(那会让整份会话记录匿名只读可见)。
- **权限是会话级**:为让某人批一条审批,必须共享整个会话。无更细粒度,已作为已知的权限放大接受。

---

## R6 · 凭证注入与隔离强度

**决策**:凭证优先经 MCP 声明注入;有 shell 的 Agent 环境中只放模型访问与代码托管两项。

**理由**:MCP 配置中的 `${VAR}` 在**解析期从进程环境展开**(`omnigent/spec/parser.py:349`)。因此:
- **无 shell 的 Agent**:没有读取环境的手段,"工具层注入"构成真隔离。
- **有 shell 的 Agent**:能直接读那个环境变量,**工具层注入不构成隔离**。仓库自身的告诫与此一致:*Do not pass secrets through the environment unless the tool genuinely needs them*(`docs/AGENT_YAML_SPEC.md:220`)。

这直接决定架构开发 bot 的权限划法:它必须能访问 OpenMetadata,但写权限由 OM 侧角色**限定在开发沙箱 Domain**,对正式资产只读。

**运行时不解析配置文件**:环境变量须由启动命令注入(如 `uv run --env-file .env`),运行时自身不读(`omnigent/cli.py:9338-9340`)。变量名支持 `OMNIGENT_<NAME>` 前缀别名以避免与宿主变量冲突(`omnigent/env_credentials.py`)。

**更强隔离的备选**:沙箱 + `credential_proxy` 可让明文根本不进沙箱(`docs/AGENT_YAML_SPEC.md:228` 起),但需网络隔离型后端;**不在 v1 范围**。

---

## R7 · git 接入

**决策**:不自建托管,使用 GitHub;认证复用运行时内置的 git 凭证助手。

**理由**:主机镜像内置凭证助手,从 `GIT_TOKEN` / `GIT_USERNAME` 应答凭证请求(`deploy/docker/Dockerfile:224-234`)。四条性质:**凭证不落盘**;`--system` 安装对沙箱内任何用户生效;**同时覆盖启动时克隆与后续 fetch/push**;未配置时公共仓库匿名克隆不受影响。`GIT_USERNAME` 默认 `x-access-token`,正是 GitHub 令牌认证所用,GitHub 场景无需额外设置。

**需另配的能力**:变更请求(Pull Request)的创建与状态查询**不能**复用 git 凭证,需独立的 GitHub 令牌与命令行工具。且该令牌**不应具备合并权限**——使 FR-045("Agent 不合并")从提示词约定升级为凭证层强制。

---

## R8 · 模型与 harness 分配

**决策**:

| Agent | Provider / Harness | 依据 |
| --- | --- | --- |
| 架构开发 | codex(`codex-native`) | 用户指定;需 shell、worktree、跑测试、开 PR |
| 编排者 | deepseek + 编排型 harness | 只做拆解与分派,不写代码 |
| 治理审计 / 运维发布 / 服务验证 | deepseek + 编排型 harness | 无 shell,工作是读、判定、出报告 |

**理由**:现有编排型范例(`examples/polly/config.yaml`)的大脑即 `harness: openai-agents` 配 `auth: {type: provider, name: deepseek}`,是本仓库已验证的非编码类组合。

**注意**:仓库中已有 `examples/deepseek/`,那是 provider 示例,与本 Agent 命名不冲突。

---

## R9 · 未解决与显式排除

| 项 | 状态 | 说明 |
| --- | --- | --- |
| OpenMetadata 的接口细节与版本 | **未核实** | 本仓库无任何 OpenMetadata 代码可供查证。MCP 接入的具体工具名、bot 与角色的创建方式、Domain 的划分接口,均须对照部署的实际版本确认。**这是实现阶段的第一个风险点。** |
| OpenMetadata 是否为身份提供方 | **未核实,判断为否** | 据既有认识它是 OIDC 客户端而非授权服务端,自身签发的是 bot 与个人访问令牌。该判断影响将来统一登录的路径选择,不影响 v1。 |
| 运行期合规监控 | **显式排除** | 合规指标以测试用例验收(FR-106);运行期可见性是运营诉求,另立需求。 |
| 统一登录 | **显式排除** | 两侧用户体系保持独立(FR-079)。已知代价是审计链断裂,已在 spec 中作为主动取舍记录。 |
| 变更执行人的自动记录 | **显式排除** | 用户决定暂不读取目录变更历史。 |
| 沙箱 + 凭证代理 | **显式排除** | v1 用"环境里不放多余凭证"约束有 shell 的 Agent;更强隔离留待后续。 |
| 多环境治理 | **显式排除** | 单一目标环境;开发期隔离靠沙箱 Domain 而非独立实例。 |

# Tasks: pipely — 数据管线生命周期 Agent

**Input**: Design documents from `/specs/001-data-pipeline-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **必须生成**。spec 的 FR-106 要求每条成功标准都有测试用例作为验收证据;项目宪法原则 I「测试先行」标注为不可协商。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行(不同文件、无未完成依赖)
- **[Story]**: 所属用户故事(US1–US5)

## Path Conventions

本特性交付的是 **Agent 定义包**,不是应用程序,因此是双落点结构:

| 路径 | 内容 | 可 import |
| --- | --- | --- |
| `examples/pipely/` | Agent 定义(YAML、skills) | **否**(资源目录) |
| `omnigent/policies/pipely/` | 策略函数 —— 唯一硬强制载体 | 是 |
| `omnigent/tools/pipely/` | 确定性工具 —— 无 shell 的 Agent 唯一可用形式 | 是 |
| `tests/{policies,tools,integration}/pipely/` | 与上两者逐目录对应 | — |

⚠️ **跑套件请用** `.specify/memory/pytest-known.sh --compare <目标>`,**不要对照零**——后端基线是 red(`tests/cli` 有 8 个失败在 CI 上同样红)。

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 创建 Agent 定义目录骨架 `examples/pipely/{agents,tools/mcp,skills}/`
- [ ] T002 [P] 创建策略子包 `omnigent/policies/pipely/__init__.py`
- [ ] T003 [P] 创建工具子包 `omnigent/tools/pipely/__init__.py`
- [ ] T004 [P] 创建测试目录 `tests/policies/pipely/__init__.py`、`tests/tools/pipely/__init__.py`、`tests/integration/pipely/__init__.py`
- [ ] T005 [P] [U67][U68] 编写 `examples/pipely/.env.example`,逐项注释每个凭证的用途、归属 Agent、是否必需(FR-066)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ 本阶段必须全部完成,五个用户故事才能开始。** 这里放的是所有故事共用的骨架与两处硬强制载体。

### Agent 声明骨架

- [ ] T006 [U63][U64] 编写编排者 `examples/pipely/config.yaml`:`executor`(deepseek + 编排型 harness)、`tools.agents` 声明四个子 Agent、`agent_session_sharing: non-public`、`guardrails.ask_timeout` 设为天级(FR-052)
- [ ] T007 [P] [U62] 编写 `examples/pipely/agents/architect/config.yaml`:codex harness、**声明 `os_env`**(唯一有 shell 者)、挂 `blast_radius` 与 `worktree_guard`
- [ ] T008 [P] [U61] 编写 `examples/pipely/agents/governance/config.yaml`:deepseek、**不声明 `os_env`**、挂 `read_only_os` 兜底
- [ ] T009 [P] [U61] 编写 `examples/pipely/agents/operations/config.yaml`:deepseek、**不声明 `os_env`**
- [ ] T010 [P] [U61] 编写 `examples/pipely/agents/consumer/config.yaml`:deepseek、**不声明 `os_env`**
- [ ] T011 [P] [U65][U66] 编写 `examples/pipely/tools/mcp/openmetadata.yaml`:HTTP 接入、`headers` 用变量引用注入各 Agent 的 bot 令牌、`tools:` 白名单按职责裁剪
- [ ] T012 [P] [U65] 编写 `examples/pipely/tools/mcp/airflow.yaml`:仅运维发布 Agent 可用,凭证与目录写入分离(FR-057)

### 硬强制载体(两处必须写 Python)

- [ ] T013 [P] [U33][U34][U35][U36][U37][U38][U39][A11][A12] 编写 `tests/tools/pipely/test_bot_selfcheck.py`:先落**负向探测**用例——只读 bot 的写探测**未被拒**时,`passed` 必须为 False 且该 bot 进入 `over_privileged`(FR-074、SC-025)
- [ ] T014 [U33][U34][U35][U36][U37][U38][U39] 实现 `omnigent/tools/pipely/bot_selfcheck.py`,使 T013 转绿;返回结构按 `contracts/tools.md`
- [X] T015 [P] [U1][U2][U3][U4][U5][U6][U7] 编写 `tests/policies/pipely/test_preflight.py`:三类失败必须**分别报告**——缺凭证、未共享、已共享但未委派审批权(FR-060、US1 场景 8/9)
- [X] T016 [U1][U2][U3][U4][U5][U6][U7] 实现 `omnigent/policies/pipely/preflight.py`,在**首个工具调用**上拦截并写 `pipely.preflight.*` 标签(FR-091;运行时无启动自检钩子)
- [ ] T017 [P] [U8][U9][U10][U11][U12][U13][U14][U15][U16][U17][U18][U19][U20][U21] 编写 `tests/policies/pipely/test_gates.py`:覆盖越序被拒、一会话一实例、以及**模型自述不写标签**(FR-090、FR-097、FR-099、SC-033)
- [ ] T018 [U8][U9][U10][U11][U12][U13][U14][U15][U16][U17][U18][U19][U20][U21] 实现 `omnigent/policies/pipely/gates.py`:`bind_flow_instance`、`require_gate`、`record_gate_passage`;标签模型按 `data-model.md`
- [ ] T019 [P] [U27][U28][U29][U30][U31][U32] 编写 `tests/policies/pipely/test_identity.py`:跨管线写入被拒、沙箱 Domain 外写入被拒(FR-105、SC-040)
- [ ] T020 [U27][U28][U29][U30][U31][U32] 实现 `omnigent/policies/pipely/identity.py`
- [ ] T021 [A5][A6] 在编排者与各子 Agent 的 `guardrails.policies` 中挂载上述策略,按 `contracts/policies.md` 配置 `on` 与 `condition`

- [ ] T085 [P] [U61][U62][U63][U64][U65][U66][U67][U68] 编写 `tests/policies/pipely/test_agent_declarations.py`:断言三个无 shell 子 Agent 的定义**不含** `os_env`、共享档为具名用户而非匿名公开、`ask_timeout` 覆盖天级、各 MCP 工具白名单无越权、**平台管理凭证不出现在任何 Agent 配置中**

**Checkpoint**: 前置校验、闸门状态机、凭证边界三道硬强制就位,可以开始故事。

---

## Phase 3: User Story 1 - 从模糊需求到可评审的 Spec (Priority: P1) 🎯 MVP

**Goal**: 用户用自然语言提出数据需求,产出一份条目齐备、可评审的统一 Spec,并停在 G1。

**Independent Test**: 给一个自然语言需求和可读的数据源样本,检查产出 Spec 的九类条目全部非空、质量阈值可量化、验收用例可执行、权限申请清单覆盖每个需授权动作;全程不创建任何治理资产。

### Tests for User Story 1

- [ ] T022 [P] [US1] [A5] `tests/policies/pipely/test_gates_g1.py`:Spec 未齐备时 G1 不通过;齐备且评审为"可实施"时才停在 G1 等人确认(spec US1 场景 5)
- [ ] T023 [P] [US1] [A1][A2][A3][A4] `tests/integration/pipely/test_spec_planning.py`:关键信息缺失时**提问而非静默取默认值**(FR-008、US1 场景 2)
- [ ] T024 [P] [US1] [A6][A8][A9][A10] `tests/policies/pipely/test_preflight_gate.py`:前置校验未过时,**在派发第一个任务之前**报出全部缺失项并停止(US1 场景 6)
- [ ] T025 [P] [US1] [A7] `tests/policies/pipely/test_env_scope.py`:架构开发 Agent 的进程环境只含模型访问与代码托管两项凭证(FR-062、SC-022、US1 场景 7)

### Implementation for User Story 1

- [ ] T026 [US1] [A1][A2] 编写 `examples/pipely/skills/plan-spec/SKILL.md`:从需求到统一 Spec 的九类条目产出流程与追问要点
- [ ] T027 [US1] [A2][A28] 在 `examples/pipely/agents/architect/config.yaml` 中补 prompt:Spec 规划职责、缺信息必须提问、**不得在 Spec 未更新时改实现**(FR-024)
- [ ] T028 [US1] [A3] 在 `examples/pipely/agents/governance/config.yaml` 中补 prompt:以只读读取目录现状、给出"可实施 / 需修改"的明确结论(FR-009)
- [ ] T029 [US1] [A5] 在 `examples/pipely/config.yaml` 的 prompt 中接入 G1:停在闸门、出示 Spec 与权限申请清单、**确认前不生成变更请求包**
- [ ] T030 [US1] [A5] 挂载 `require_gate` 于阶段 2 的入口操作,`condition` 限定 `pipely.gate` 未达 `g1_passed` 时拒绝

- [ ] T087 [US1] [A1][A2][A3][A4][A5][A6][A7][A8][A9][A10][A11][A12] 确认本故事的全部外层行为在 `tests/integration/pipely/` 中**已绿**,故事方可判定完成

**Checkpoint**: US1 可独立演示——能把一句话需求变成可评审的 Spec,并正确停在 G1。

---

## Phase 4: User Story 2 - 治理变更由人执行,Agent 只出手册与核验 (Priority: P2)

**Goal**: 治理审计 Agent 出变更请求包,平台管理员亲手执行,Agent 只读核验;核验通过才过 G2。

**Independent Test**: 给一份已冻结 Spec,检查三件产物齐备、手册每步含核验方式与回滚步骤、断言机器可判定;人为漏做一步,核验必须准确指出缺失并阻止 G2;全程验证该 Agent 未发起任何写操作。

### Tests for User Story 2

- [ ] T031 [P] [US2] [U40][U41][U42][U46] `tests/tools/pipely/test_verify_governance.py`:断言不满足时 `passed=False` 且 `missing_steps` 非空,失败项含期望值与实际值(FR-017、FR-018)
- [ ] T032 [P] [US2] [U43][U44] `tests/tools/pipely/test_verify_idempotent.py`:重复核验结果一致且无副作用(FR-019、US2 场景 8)
- [ ] T033 [P] [US2] [U13][U14][U15][U16] `tests/policies/pipely/test_gate_g2_from_tool_result.py`:**模型声称"已核验"不写 `g2_passed`;只有工具真实返回 `passed=True` 才写**(FR-097、SC-036)——本特性最关键的一条
- [ ] T034 [P] [US2] [U45][A19] `tests/policies/pipely/test_governance_readonly.py`:治理审计 Agent 的任何写入尝试被拒(FR-011、US2 场景 7)
- [ ] T035 [P] [US2] [A13][A14][A17] `tests/integration/pipely/test_change_request_package.py`:三件产物齐备,手册基于**实时状态**生成并标出命名冲突(FR-012~014、US2 场景 1/2)
- [ ] T036 [P] [US2] [A21] `tests/policies/pipely/test_repo_review_precondition.py`:平台管理员无仓库评审权限时,**在生成变更请求包之前**报错(FR-020、US2 场景 9)

### Implementation for User Story 2

- [ ] T037 [US2] [U40][U41][U42][U43][U44][U46][A16][A18][A20] 实现 `omnigent/tools/pipely/verify_governance.py`,返回结构按 `contracts/tools.md`,使 T031/T032 转绿
- [ ] T038 [US2] [A13][A14] 编写 `examples/pipely/skills/governance-change/SKILL.md`:变更请求包的产出规范(手册每步五要素、断言须机器可判定)
- [ ] T039 [US2] [A16] 在治理审计 Agent 的 `tools` 中注册 `verify_governance`,并挂 `record_gate_passage` 于 `tool_result:verify_governance`
- [ ] T040 [US2] [A15] 在编排者 prompt 中接入 G2:提交变更请求包后**结束回合、不阻塞会话**;由人在收件箱确认后触发核验(FR-016、US2 场景 3/4)
- [ ] T041 [US2] [A17] 在 `examples/pipely/skills/governance-change/SKILL.md` 的手册模板中纳入**第 1 批 bot 与开发沙箱 Domain 的创建步骤**(FR-077、FR-103)
- [ ] T042 [US2] [A8][A9] 在 `examples/pipely/.env.example` 中补齐会话共享与审批权委派的说明(前置配置,非包内)

- [ ] T088 [US2] [A13][A14][A15][A16][A17][A18][A19][A20][A21] 确认本故事的全部外层行为在 `tests/integration/pipely/` 中**已绿**,故事方可判定完成

**Checkpoint**: US2 可独立演示——能出手册、人执行后能准确核验、模型无法伪造通过。

---

## Phase 5: User Story 3 - 管线实现、质量门禁与交接 (Priority: P3)

**Goal**: 架构开发 Agent 按 Spec 实现代码、测试与调度作业定义,开变更请求;人合并打标签后产出不可变制品引用。

**Independent Test**: 验证每条验收用例都有自动化测试且全绿;子 Agent 写入未越出工作区;Agent 未自行合并;产出的制品引用可独立解析且不含任何指向源码工作区的路径。

### Tests for User Story 3

- [ ] T043 [P] [US3] [A24] `tests/policies/pipely/test_worktree_scope.py`:写入越出工作区被拒,且不影响该 Agent 的其他在途任务(FR-042、US3 场景 3)
- [ ] T044 [P] [US3] [U22][U23][U24] `tests/policies/pipely/test_handoff_artifact_ref.py`:交接物含分支名/工作区路径时被拒(FR-023、SC-012)
- [ ] T045 [P] [US3] [A30] `tests/policies/pipely/test_no_merge_by_agent.py`:Agent 发起合并被拒——由**凭证层**强制而非提示词(FR-045、FR-070、US3 场景 9)
- [ ] T046 [P] [US3] [A29] `tests/integration/pipely/test_git_credentials.py`:私有仓库的克隆、拉取、推送三个动作都认证成功,且磁盘上不留凭证文件(FR-068、FR-069、US3 场景 8)
- [ ] T047 [P] [US3] [A31] `tests/integration/pipely/test_anonymous_clone.py`:未配置 git 凭证时公共仓库匿名克隆正常(FR-068、US3 场景 10)
- [ ] T048 [P] [US3] [U29][U30][A32] `tests/policies/pipely/test_sandbox_domain_scope.py`:架构开发 bot 写沙箱 Domain 内成功、写正式资产被拒(FR-103、SC-038、US3 场景 11)
- [ ] T049 [P] [US3] [A26][A27] `tests/policies/pipely/test_gate_g3.py`:测试未全绿或变更请求未开时 G3 不通过;通过后交接物为不可变制品引用

- [ ] T083 [P] [US3] [U54][U55][U56][U57] 编写 `tests/tools/pipely/test_artifact_ref.py`:制品引用含四项、**不含任何可写源码位置**、已存在时拒绝修改、同标签重复产出幂等
- [ ] T086 [P] [US3] [A22][A23][A25][A28] 编写 `tests/integration/pipely/test_dev_workflow.py`:验收用例都有对应测试且全绿、调度作业定义纳入同一变更请求、推送开 PR 走交互式审批、**Spec 未更新时拒绝改实现**

### Implementation for User Story 3

- [ ] T050 [US3] [U22][U23][U24][U25][U26] 实现 `omnigent/policies/pipely/handoff.py`:`artifact_ref_only` 与 `deploy_within_ref`,使 T044 转绿
- [ ] T051 [US3] [A22][A23][A28] 编写 `examples/pipely/skills/build-release/SKILL.md`:开发、测试、调度作业定义、开变更请求的流程,含**先改 Spec 再改实现**的硬规矩
- [ ] T052 [US3] [A23][A25] 在 `examples/pipely/agents/architect/config.yaml` 的 prompt 中写明:调度作业**定义**属其职责、**Agent 不合并变更请求**、提交须带协作署名(FR-022、FR-045、FR-046)
- [ ] T053 [US3] [U54][U55][U56][U57][A27] 在 `omnigent/tools/pipely/artifact_ref.py` 中实现制品引用的产出:代码标签 + 制品标签 + **冻结的质量阈值与验收断言**,写入 OpenMetadata 管线资产(FR-101、FR-102)
- [ ] T054 [US3] [A26] 在 `examples/pipely/config.yaml` 的 prompt 中接入 G3:汇总测试与门禁结果、结束回合等人确认、**不自行合并**

- [ ] T089 [US3] [A22][A23][A24][A25][A26][A27][A28][A29][A30][A31][A32] 确认本故事的全部外层行为在 `tests/integration/pipely/` 中**已绿**,故事方可判定完成

**Checkpoint**: US3 可独立演示——能开发到绿、开 PR、人合并后产出完整的制品引用。

---

## Phase 6: User Story 4 - 上线、质量门禁与运维 (Priority: P4)

**Goal**: 运维发布 Agent 按制品引用触发 Airflow,执行质量门禁,获批后切换线上指向;失败保持旧版本。

**Independent Test**: 验证新快照未覆盖旧快照;门禁每项都有实际值与阈值对比;人为制造一项门禁失败时线上指向不变;上线切换确经独立审批;回滚后指向恢复且数据可查;全程验证该 Agent 无法读写源码。

### Tests for User Story 4

- [ ] T055 [P] [US4] [U47][U48][U49][U50][U51][U52][U53] `tests/tools/pipely/test_quality_gate.py`:任一项未达阈值时 `passed=False`,且该项的**实际值与阈值都在返回里**(FR-027、FR-028)
- [ ] T056 [P] [US4] [A34] `tests/policies/pipely/test_no_promote_on_gate_fail.py`:门禁失败时线上指向**不切换**,旧版本继续服务(FR-028、US4 场景 2)
- [ ] T057 [P] [US4] [A35] `tests/policies/pipely/test_g4_independent_approval.py`:门禁通过**不自动放行**,切换必须经独立的交互式审批(FR-029、US4 场景 3)
- [ ] T058 [P] [US4] [A39] `tests/policies/pipely/test_ops_no_source_access.py`:运维发布 Agent 读写源码的尝试被拒——它没有文件与 shell 工具(FR-025、SC-006、US4 场景 7)
- [ ] T059 [P] [US4] [U25][U26][A41] `tests/policies/pipely/test_deploy_within_ref.py`:部署非制品引用范围内的作业定义被拒(FR-056、US4 场景 9)
- [ ] T060 [P] [US4] [U31][A42] `tests/policies/pipely/test_scheduler_cred_separation.py`:调度凭证无法执行平台级治理操作——即便同源部署(FR-057、US4 场景 10)
- [ ] T061 [P] [US4] [A38] `tests/integration/pipely/test_no_change_no_version.py`:上游无变化时尽早结束,不生成新版本、不改动线上指向(FR-032、US4 场景 6)
- [ ] T062 [P] [US4] [A36] `tests/integration/pipely/test_rollback.py`:回滚在约定时限内把指向指回上一副本,**不重建数据、不回退代码**(FR-030、SC-007)

- [ ] T084 [P] [US4] [U58][U59][U60] 编写 `tests/tools/pipely/test_sync_catalog.py`:同步后目录字段与输入一致、**"目录不可达"与"调度器不可达"分别报告**、重复同步不产生重复记录

### Implementation for User Story 4

- [ ] T063 [US4] [U47][U48][U49][U50][U51][U52][U53][A33][A34] 实现 `omnigent/tools/pipely/quality_gate.py`,阈值取自**制品引用中的冻结契约**而非仓库(FR-101),使 T055 转绿
- [ ] T064 [US4] [A33][A38] 编写 `examples/pipely/skills/operate/SKILL.md`:触发、门禁、上线、回滚、状态同步的运行手册
- [ ] T065 [US4] [A39] 在运维发布 Agent 的 `tools` 中注册 `quality_gate` 与 Airflow 操作;**不注册任何文件或 shell 工具**
- [ ] T066 [US4] [A35] 挂载 G4 的审批策略:门禁通过后,切换线上指向作为独立的 `ask` 送达运维负责人
- [ ] T067 [US4] [U58][U59][U60][A37] 在 `omnigent/tools/pipely/sync_catalog.py` 中实现上线后向 OpenMetadata 同步版本、计数、质量、血缘与运行状态(FR-031)
- [ ] T068 [US4] [A40] 在 `examples/pipely/agents/operations/config.yaml` 的 prompt 中写明告警与升级规则:连续失败、结构破坏性变更、权限错误须告警;**仅平台对象或策略变更才升级平台管理员**(FR-034)

- [ ] T090 [US4] [A33][A34][A35][A36][A37][A38][A39][A40][A41][A42] 确认本故事的全部外层行为在 `tests/integration/pipely/` 中**已绿**,故事方可判定完成

**Checkpoint**: US4 可独立演示——能跑通一次带门禁与审批的上线,并能回滚。

---

## Phase 7: User Story 5 - 以最终用户视角验证线上服务 (Priority: P5)

**Goal**: 服务验证 Agent 只持只读 bot,像真实使用者一样消费服务,同时充当权限边界的活体检验。

**Independent Test**: 只注入只读凭证启动,给一组混合问题(定义类、检索类、歧义术语类、越权类),验证路由正确、结果可解释、内部字段不出现、分页上限生效,且每次写尝试都被拒。

### Tests for User Story 5

- [ ] T069 [P] [US5] [A46] `tests/policies/pipely/test_consumer_readonly.py`:任何写入、索引创建、指向切换尝试被拒,且失败信息**不泄漏凭证内容**(FR-035、US5 场景 4)
- [ ] T070 [P] [US5] [A43] `tests/integration/pipely/test_intent_routing.py`:定义/治理类问题走目录,数据记录类走检索服务(FR-036、US5 场景 1)
- [ ] T071 [P] [US5] [A44] `tests/integration/pipely/test_glossary_disambiguation.py`:歧义术语先查词表消歧再检索,并在结果中说明采用了哪个术语(FR-037、US5 场景 2)
- [ ] T072 [P] [US5] [A45][A47] `tests/integration/pipely/test_result_shape.py`:每条结果含唯一标识、标题、命中条件、命中原因;**不含内部路径类字段**;分页上限生效(FR-038、FR-039、SC-011)

### Implementation for User Story 5

- [ ] T073 [US5] [A43][A44][A45] 在 `examples/pipely/agents/consumer/config.yaml` 中补 prompt:意图路由规则、词表消歧、结果须带命中原因、内部字段不得暴露
- [ ] T074 [US5] [A47] 在 `examples/pipely/tools/mcp/openmetadata.yaml` 中为服务验证 bot 配置工具白名单:仅只读检索类,分页上限写入工具参数约束

- [ ] T091 [US5] [A43][A44][A45][A46][A47] 确认本故事的全部外层行为在 `tests/integration/pipely/` 中**已绿**,故事方可判定完成

**Checkpoint**: 五个故事全部可独立演示。

---

## Phase N: Polish & Cross-Cutting Concerns

- [ ] T075 [P] [U67][U68] 补齐 `examples/pipely/.env.example`:10 项凭证逐项注释用途、归属 Agent、是否必需;标明平台管理凭证**不在此列**
- [ ] T076 [P] 编写 `examples/pipely/README.md`:前置配置清单(含**必须手工创建的引导用只读 bot**)、启动方式(运行时不解析配置文件,须 `--env-file` 注入)
- [ ] T077 [P] 为 `omnigent/policies/pipely/` 与 `omnigent/tools/pipely/` 补模块级文档字符串,说明各自承载的 FR 编号
- [ ] T078 用 `.specify/memory/pytest-known.sh --compare tests/policies tests/tools` 跑区域套件,确认**零新增失败**
- [ ] T079 用 `.specify/memory/pytest-known.sh --compare -m "not databricks" -n 8 --dist=loadfile` 跑全量,确认零新增失败
- [ ] T080 运行 `uvx pre-commit run --all-files`,修完 ruff / pyrefly 的全部报告(宪法原则 III)
- [ ] T081 逐条比对 `specs/001-data-pipeline-agent/spec.md` 的 40 条成功标准与 `tests/{policies,tools,integration}/pipely/` 下的用例,补齐缺口(FR-106、SC-031)
- [ ] T082 按 `.github/pull_request_template.md` 填写 PR,勾选类型与测试覆盖,填 Coverage notes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** → 无依赖,最先
- **Phase 2 (Foundational)** → 依赖 Phase 1;**阻塞所有用户故事**
- **Phase 3–7 (US1–US5)** → 均依赖 Phase 2
- **Phase N (Polish)** → 依赖全部故事

### User Story Dependencies

故事之间**按闸门顺序串行**,这是本特性的固有性质而非任务编排的选择:

```
US1 (G1) ──> US2 (G2) ──> US3 (G3) ──> US4 (G4) ──> US5
```

US2 需要 US1 冻结的 Spec;US3 需要 US2 落地的治理空间;US4 需要 US3 交接的制品引用;US5 需要 US4 上线的服务。

**但每个故事仍可独立测试**——用桩数据构造其输入前提即可,不必真的跑完前一个故事。

### Within Each User Story

测试先写(宪法原则 I 不可协商)→ 工具 → 策略 → Agent 声明与 prompt → 接线。

### Parallel Opportunities

- Phase 1:T002–T005 全部可并行
- Phase 2:T007–T012(六份 YAML,互不相干)可并行;T013/T015/T017/T019 四组测试可并行
- 各故事内:标 `[P]` 的测试文件互不相干,可全部并行编写
- **跨故事不建议并行**——闸门是串行的,并行会让集成测试难以构造前提

---

## Parallel Example: User Story 2

```bash
# US2 的六个测试文件互不相干,可一次全部起草
tests/tools/pipely/test_verify_governance.py          # T031
tests/tools/pipely/test_verify_idempotent.py          # T032
tests/policies/pipely/test_gate_g2_from_tool_result.py # T033 ← 最关键
tests/policies/pipely/test_governance_readonly.py     # T034
tests/integration/pipely/test_change_request_package.py # T035
tests/policies/pipely/test_repo_review_precondition.py # T036
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

**MVP = Phase 1 + Phase 2 + Phase 3(US1)**,共 30 个任务。

交付后即可演示:把一句话数据需求变成条目齐备、可评审的统一 Spec,并正确停在 G1。这已经替代了当前最耗人力的环节——**即便后续阶段一个都不自动化,这一段本身就有价值**(spec 对 US1 的定位)。

注意 Phase 2 占了 16 个任务,看起来重,但其中 T013–T021 是**两处硬强制载体**,后面四个故事全靠它们。省掉它们,所有闸门都会退化成提示词。

### Incremental Delivery

每完成一个故事就是一个可演示的增量:

1. **US1** → 需求变 Spec,停 G1
2. **US2** → 治理落地闭环(出手册 → 人执行 → 核验)
3. **US3** → 开发到绿、开 PR、产出制品引用
4. **US4** → 带门禁与审批的上线,可回滚
5. **US5** → 只读消费验证,权限边界活体检验

### Parallel Team Strategy

Phase 2 完成后,若有多人:

- 一人推 US1 + US2(治理线,重 OpenMetadata 语义)
- 一人推 US3(开发线,重 codex 与 git)
- US4 需等 US3 的制品引用契约稳定后再动手,否则接口反复
- US5 最轻,可由任一人在末尾补上

---

## Notes

- **测试先行不可协商**:每个实现任务前都有对应测试任务。`/speckit-tdd-plan` 会进一步把它们排成红-绿-重构的顺序。
- **三条最关键的负向测试**,漏了等于整套强制失效:
  - **T033** 模型自述不能写 `g2_passed`(否则闸门形同虚设)
  - **T013** 只读 bot 的写探测未被拒时自检必须判失败(否则权限边界悄悄失效)
  - **T045** Agent 合并变更请求被凭证层拒绝(否则"Agent 不合并"只是提示词)
- **第 ③ 层不在本清单内**:spec 中关于"Agent 产出的管线"的要求(快照不覆盖、幂等、回滚)是 **Agent 的验收标准而非本包的构建规格**(FR-092)。它们体现在 skill 给出的开发契约与集成测试里,不作为独立实现任务。
- **OpenMetadata 接口细节未核实**是实现阶段第一风险点(research.md R9)。T011/T037/T053/T067 均依赖它,建议开工前先做一次接口勘察。

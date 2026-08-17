---
feature: 001-data-pipeline-agent
loop: outside-in
profile: .specify/memory/tdd-profile.md
spec_criteria: 47
planned_at: d5d7fced
updated_at: d5d7fced
suite_baseline: red
---

# Test List: pipely — 数据管线生命周期 Agent

## 外层循环没有真正的验收运行器

profile 记录的 `acceptance` 是 `uv run pytest tests/e2e_ui`——Playwright 驱动已构建的 Web UI。**本特性没有用户可见的 UI 界面**,它的真实入口是 Agent 会话。因此这个运行器**不适用**。

外层行为改落在仓库能达到的最高层级:`tests/integration/pipely/`(组合模块 + 模拟 LLM)。**这比端到端弱**——它证明各组件装在一起能工作,但不证明真实 OpenMetadata 与 GitHub 上也能工作。清单如实记录这一点,不假装它是 e2e。

## Outer loop: acceptance behaviors

一条验收场景一个行为,按 `spec.md` 顺序。宿主:`tests/integration/pipely/`。

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| A1 | 给定需求与可读数据源样本,产出的统一 Spec 九类条目全部非空 | US1-1, FR-007 | example | PENDING | |
| A2 | 需求缺更新频率与数据规模时,产出 Spec 之前先提问而非填默认值 | US1-2, FR-008 | example | PENDING | |
| A3 | Spec 要求平台不具备的能力时,评审结论指出不可行及原因,状态不进入"可实施" | US1-3, FR-009 | example | PENDING | |
| A4 | 需求评审后被修改时,修订同一份 Spec 并保留变更记录,不另起矛盾文档 | US1-4 | example | PENDING | |
| A5 | Spec 齐备且评审可实施时,停在 G1 并出示权限申请清单,确认前不生成变更请求包 | US1-5, FR-047 | example | PENDING | |
| A6 | 前置配置缺凭证时,派发任何任务之前一次性列出全部缺失项并停止 | US1-6, FR-060 | example | PENDING | |
| A7 | 架构开发 Agent 读自身进程环境时,只能读到模型访问与代码托管两项凭证 | US1-7, FR-062 | example | PENDING | |
| A8 | 会话未共享给平台管理员时,派发前报出"闸门待办无法送达"并指明缺失的共享对象 | US1-8, FR-084 | example | PENDING | |
| A9 | 已共享但未委派审批权时,报出该项并与"未共享"区分开 | US1-9, FR-085 | example | PENDING | |
| A10 | 引导用只读 bot 未创建时,明确报出缺失并停止,不尝试自行创建 | US1-10, FR-076 | example | PENDING | |
| A11 | 治理审计 bot 被误授写权限时,负向探测未被拒即判自检失败并指明多出的权限 | US1-11, FR-074 | example | PENDING | |
| A12 | 全部 bot 权限正确时,只读 bot 写探测被拒、应有权限可用,自检通过且未改动目录 | US1-12, FR-074 | example | PENDING | |
| A13 | 给定已冻结 Spec,变更请求包三件产物齐备,手册每步含五要素 | US2-1, FR-012, FR-013 | example | PENDING | |
| A14 | 目录中存在命名冲突时,手册基于实时状态标出冲突并给出处置选项 | US2-2, FR-014 | example | PENDING | |
| A15 | 变更请求包提交后,待办出现在平台管理员本人的收件箱中(会话非其发起) | US2-3, FR-083 | example | PENDING | |
| A16 | 管理员在收件箱点确认后,触发只读核验并输出逐条比对结果 | US2-4, FR-017 | example | PENDING | |
| A17 | Spec 要求的带写权限 bot,其创建与授权作为平台级操作写入手册交人执行 | US2-5, FR-077 | example | PENDING | |
| A18 | 核验发现任一断言不满足时,G2 不通过且给出需补做的具体步骤 | US2-6, FR-018 | example | PENDING | |
| A19 | 治理审计 Agent 的任何写入尝试被拒 | US2-7, FR-011 | example | PENDING | |
| A20 | 同一变更请求包重复核验,结果一致且无副作用 | US2-8, FR-019 | example | PENDING | |
| A21 | 平台管理员无仓库评审权限时,在生成变更请求包之前报错 | US2-9, FR-020 | example | PENDING | |
| A22 | 给定可实施 Spec,产出的代码带有覆盖每条验收用例的自动化测试且全绿 | US3-1, FR-021 | example | PENDING | |
| A23 | 需要调度编排时,作业定义作为代码纳入同一变更请求一同评审 | US3-2, FR-022 | example | PENDING | |
| A24 | 子 Agent 写入越出工作区被拒,其他在途任务不受影响 | US3-3, FR-042 | example | PENDING | |
| A25 | 推送并开变更请求作为交互式审批送达开发负责人,获批后才执行 | US3-4, FR-044 | example | PENDING | |
| A26 | 测试全绿且变更请求已开时,停在 G3 等人确认,不自行合并 | US3-5, FR-045 | example | PENDING | |
| A27 | 人合并打标签后,交接物为不可变制品引用,不含任何可写源码位置 | US3-6, FR-023 | example | PENDING | |
| A28 | 变更架构或范围时,先改 Spec 再改实现,Spec 未更新则拒绝改实现 | US3-7, FR-024 | example | PENDING | |
| A29 | 私有仓库的克隆、拉取、推送三个动作全部认证成功,且磁盘不留凭证文件 | US3-8, FR-068, FR-069 | example | PENDING | |
| A30 | Agent 令牌无合并权限时,其合并尝试被托管服务拒绝 | US3-9, FR-070 | example | PENDING | |
| A31 | 未配置 git 凭证时,公共仓库匿名克隆正常工作 | US3-10, FR-068 | example | PENDING | |
| A32 | 架构开发 Agent 能从目录读到数据源与落地表的结构与归属,写入正式资产被拒 | US3-11, FR-081, FR-103 | example | PENDING | |
| A33 | 按制品引用执行管线时,新快照以新版本标识存放,旧快照与旧副本未被改动 | US4-1, FR-026 | example | PENDING | |
| A34 | 门禁任一项未达阈值时,线上指向不切换,旧版本继续服务,失败项及实际值被报告 | US4-2, FR-028 | example | PENDING | |
| A35 | 门禁全部通过时,切换作为独立交互式审批送达运维负责人,获批前指向不变 | US4-3, FR-029 | example | PENDING | |
| A36 | 回滚时线上指向指回上一副本且数据可查,不重建数据、不回退代码 | US4-4, FR-030 | example | PENDING | |
| A37 | 上线完成后,目录记录的版本、计数、质量、血缘与运行状态与实际部署一致 | US4-5, FR-031 | example | PENDING | |
| A38 | 上游数据无变化时尽早结束,不生成新版本、不改动指向,并报告"无变化" | US4-6, FR-032 | example | PENDING | |
| A39 | 运维发布 Agent 读取或修改源码的尝试被拒 | US4-7, FR-025 | example | PENDING | |
| A40 | 连续失败/结构破坏性变更/权限错误时告警;仅平台对象或策略变更才升级管理员 | US4-8, FR-034 | example | PENDING | |
| A41 | 部署不在制品引用范围内的作业定义被拒 | US4-9, FR-056 | example | PENDING | |
| A42 | 用调度凭证执行平台级治理操作被拒 | US4-10, FR-057 | example | PENDING | |
| A43 | 字段含义或归属类问题从治理目录取答案,不猜测也不从查询服务拼凑 | US5-1, FR-036 | example | PENDING | |
| A44 | 歧义术语先查词表消歧再检索,并在结果中说明采用了哪个术语 | US5-2, FR-037 | example | PENDING | |
| A45 | 每条检索结果含唯一标识、标题、命中条件与命中原因,不含内部路径类字段 | US5-3, FR-038 | example | PENDING | |
| A46 | 服务验证 Agent 的写入/建索引/切指向尝试被拒,失败信息不泄漏凭证 | US5-4, FR-035 | example | PENDING | |
| A47 | 返回结果超上限时使用分页,不一次性拉取全部 | US5-5, FR-039 | example | PENDING | |

## Inner loop: unit behaviors

按 `plan.md` 定义的组件分组。

### `omnigent/policies/pipely/preflight.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U1 | 标签未写入时,任何工具调用被拒(未校验视同未通过) | FR-091 | example | DONE | `tests/policies/pipely/test_preflight.py::test_tool_call_is_denied_when_no_preflight_result_is_recorded` |
| U2 | 缺一项凭证时,失败清单恰好含该一项 | FR-060 | example | DONE | `tests/policies/pipely/test_preflight.py::test_one_absent_credential_is_reported_as_exactly_that_one` |
| U3 | 缺多项凭证时,失败清单一次性含全部,不止第一项 | FR-060 | example | DONE | `tests/policies/pipely/test_preflight.py::test_several_absent_credentials_are_all_reported_at_once` |
| U4 | 零缺失时校验通过并写入 `pipely.preflight.status = passed` | FR-091 | example | DONE | `tests/policies/pipely/test_preflight.py::test_tool_call_is_allowed_once_preflight_is_recorded_as_passed`(读取端;写入端见 U2/U3/U5) |
| U5 | "未共享"与"已共享但未委派审批权"产出两种不同的失败标识 | FR-084, FR-085 | example | DONE | `tests/policies/pipely/test_preflight.py::test_not_shared_and_no_approve_grant_are_distinct_failures` |
| U6 | 校验只在首个工具调用上执行一次,后续调用读标签不重复探测 | FR-091 | example | DONE | `tests/policies/pipely/test_preflight.py::test_a_recorded_result_short_circuits_further_assessment` |
| U7 | 引导用只读 bot 缺失时,失败原因指明该 bot 且不含"尝试创建"的动作 | FR-076 | example | DONE | `tests/policies/pipely/test_preflight.py::test_absent_bootstrap_bot_is_remediated_by_hand_not_by_creating_it` |

### `omnigent/policies/pipely/gates.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U8 | 标签恰为所需闸门值时放行(边界:等于) | FR-090 | example | DONE | `tests/policies/pipely/test_gates.py::test_a_session_exactly_at_the_required_gate_is_allowed` |
| U9 | 标签为所需闸门的前一级时拒绝(边界:小于) | FR-090 | example | DONE | `tests/policies/pipely/test_gates.py::test_a_session_one_gate_below_the_requirement_is_denied` |
| U10 | 标签已超过所需闸门时放行(边界:大于) | FR-090 | example | DONE | `tests/policies/pipely/test_gates.py::test_a_session_past_the_required_gate_is_still_allowed` |
| U11 | 标签缺失时拒绝,而非按"未设限"放行 | FR-090 | example | DONE | `tests/policies/pipely/test_gates.py::test_a_session_carrying_no_gate_at_all_is_denied` |
| U12 | 拒绝时的原因文本指明当前闸门与所需闸门 | FR-090 | example | DONE | `tests/policies/pipely/test_gates.py::test_a_denial_names_both_where_the_session_is_and_where_it_must_be` |
| U13 | `tool_result` 中工具返回 `passed=true` 时写入下一闸门标签 | FR-097 | example | DONE | `tests/policies/pipely/test_gate_advance.py::test_a_tool_reporting_a_pass_advances_the_gate` |
| U14 | `tool_result` 中工具返回 `passed=false` 时不写标签 | FR-097 | example | DONE | `tests/policies/pipely/test_gate_advance.py::test_a_tool_reporting_a_failure_leaves_the_gate_where_it_was` |
| U15 | 模型在消息中自述"已核验"而无工具结果时不写标签 | FR-097, SC-036 | example | DONE | `tests/policies/pipely/test_gate_advance.py::test_a_model_claiming_it_verified_something_moves_no_gate` |
| U16 | 工具返回缺少 `passed` 字段时不写标签且判为异常,而非默认通过 | FR-097 | example | DONE | `tests/policies/pipely/test_gate_advance.py::test_a_result_with_no_verdict_field_is_flagged_rather_than_ignored` |
| U17 | 闸门标签只进不退:已达高闸门时不被低闸门的结果回写 | FR-090 | example | DONE | `tests/policies/pipely/test_gate_advance.py::test_a_lower_gates_result_does_not_pull_the_session_back` |
| U18 | 首个工具调用写入 `pipely.flow.pipeline` 与 `pipely.flow.kind` | FR-099 | example | DONE | `tests/policies/pipely/test_flow_binding.py::test_the_first_tool_call_records_the_pipeline_and_kind` |
| U19 | 会话已绑定某管线后,出现不同管线标识时拒绝而非覆盖 | FR-099 | example | DONE | `tests/policies/pipely/test_flow_binding.py::test_a_second_pipeline_in_a_bound_session_is_refused_not_absorbed` |
| U20 | `kind=operation` 的流程实例只校验 G4,不要求 G1–G3 | FR-099 | example | DONE | `tests/policies/pipely/test_flow_binding.py::test_an_operation_flow_is_judged_on_its_own_gate_only` |
| U21 | ASK 被拒绝或超时时,闸门标签不被写入(无副作用) | FR-051 | example | DONE | 既有运行时测试已覆盖:`tests/runtime/policies/test_approval.py::test_cancel_does_not_apply_labels`、`::test_timeout_does_not_apply_labels`(另见 `tests/runtime/policies/test_ask_cycle_e2e.py::test_ask_cycle_timeout_drops_labels`) |

### `omnigent/policies/pipely/handoff.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U22 | 交接物含分支名时拒绝 | FR-023 | example | DONE | `tests/policies/pipely/test_handoff.py::test_a_handoff_naming_a_branch_is_refused` |
| U23 | 交接物含工作区路径时拒绝 | FR-023 | example | DONE | `tests/policies/pipely/test_handoff.py::test_a_handoff_naming_a_workspace_path_is_refused` |
| U24 | 交接物仅含代码标签、制品标签与冻结契约时放行 | FR-023 | example | DONE | `tests/policies/pipely/test_handoff.py::test_a_handoff_of_only_immutable_references_is_admitted` |
| U25 | 部署的作业定义在制品引用范围内时放行 | FR-056 | example | DONE | `tests/policies/pipely/test_handoff.py::test_deploying_a_job_the_artifact_covers_is_admitted` |
| U26 | 部署的作业定义不在制品引用范围内时拒绝,原因指明超出范围 | FR-056 | example | DONE | `tests/policies/pipely/test_handoff.py::test_deploying_a_job_outside_the_artifact_names_what_is_out_of_scope` |

### `omnigent/policies/pipely/identity.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U27 | 运维发布 bot 写本管线资产时放行 | FR-105 | example | DONE | `tests/policies/pipely/test_identity.py::test_the_release_bot_may_write_assets_of_its_own_pipeline` |
| U28 | 运维发布 bot 写其他管线资产时拒绝 | FR-105, SC-040 | example | DONE | `tests/policies/pipely/test_identity.py::test_the_release_bot_may_not_write_another_pipelines_assets` |
| U69 | 管线名互为前缀时不得被判为同一作用域(如 `orders_daily` 与 `orders_daily_archive`) | FR-105, SC-040 | example | DONE | `tests/policies/pipely/test_identity.py::test_a_pipeline_whose_name_merely_starts_the_same_is_not_in_scope`(循环中新增,见 Cycle 30/31) |
| U29 | 架构开发 bot 写沙箱 Domain 内资产时放行 | FR-103 | example | DONE | `tests/policies/pipely/test_identity.py::test_the_architect_bot_may_write_inside_its_sandbox_domain` |
| U30 | 架构开发 bot 写沙箱 Domain 外资产时拒绝 | FR-103, SC-038 | example | DONE | `tests/policies/pipely/test_identity.py::test_the_architect_bot_may_not_write_governed_assets_outside_the_sandbox` |
| U31 | 用调度凭证发起目录平台级操作时拒绝 | FR-057 | example | DONE | `tests/policies/pipely/test_identity.py::test_a_scheduler_credential_cannot_reach_platform_administration` |
| U32 | 任何 Agent 出现平台管理凭证时拒绝启动 | FR-003, FR-063 | example | DONE | `tests/policies/pipely/test_identity.py::test_a_platform_admin_credential_in_the_environment_refuses_startup` |

### `omnigent/tools/pipely/bot_selfcheck.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U33 | 只读 bot 的写探测被拒时,该项判通过 | FR-074 | example | DONE | `tests/tools/pipely/test_bot_selfcheck.py::test_readonly_bot_write_probe_refused_passes_the_selfcheck` |
| U34 | **只读 bot 的写探测未被拒时,该项判失败且该 bot 进入越权清单** | FR-074, SC-025 | example | DONE | `tests/tools/pipely/test_bot_selfcheck.py::test_readonly_bot_write_probe_not_refused_fails_the_selfcheck` |
| U35 | 仅"令牌可用"而未执行负向探测时不算通过 | FR-074 | example | DONE | `tests/tools/pipely/test_bot_selfcheck.py::test_a_bot_with_no_write_probe_at_all_does_not_pass` |
| U36 | 权限恰好等于职责所需时判通过(边界:等于) | FR-075 | example | DONE | `tests/tools/pipely/test_bot_selfcheck.py::test_permissions_matching_the_role_exactly_pass` |
| U37 | 权限宽于职责所需时判失败并列出多出的具体项(边界:大于) | FR-075 | example | DONE | `tests/tools/pipely/test_bot_selfcheck.py::test_permissions_wider_than_the_role_name_the_extra_ones` |
| U38 | 权限窄于职责所需时判失败并列出缺失的具体项(边界:小于) | FR-075 | example | DONE | `tests/tools/pipely/test_bot_selfcheck.py::test_permissions_narrower_than_the_role_name_the_absent_ones` |
| U39 | 负向探测选用无害动作,执行后目录状态无变化 | FR-074 | example | DONE(**部分**) | `tests/tools/pipely/test_bot_selfcheck.py::test_every_write_probe_declares_that_it_leaves_no_residue` —— 单元层只钉住"每个探测声明不落盘";"调用前后目录状态无变化"需真实目录,已并入集成行为 A 系列 |

### `omnigent/tools/pipely/verify_governance.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U40 | 全部断言满足时 `passed=true`,`missing_steps` 为空 | FR-017 | example | DONE | `tests/tools/pipely/test_verify_governance.py::test_all_assertions_met_reports_a_pass_with_nothing_outstanding` |
| U41 | 任一断言不满足时 `passed=false`,该项含期望值与实际值 | FR-017, FR-018 | example | DONE | `tests/tools/pipely/test_verify_governance.py::test_an_unmet_assertion_reports_both_the_expected_and_the_found_value` |
| U42 | 不满足时 `missing_steps` 给出需补做的具体步骤,而非仅"不通过" | FR-018 | example | DONE | `tests/tools/pipely/test_verify_governance.py::test_an_unmet_assertion_yields_the_step_that_would_satisfy_it` |
| U43 | 重复调用返回一致结果 | FR-019 | example | DONE | `tests/tools/pipely/test_verify_governance.py::test_verifying_the_same_assertions_twice_gives_the_same_answer` |
| U44 | 调用前后目录状态无变化(无副作用) | FR-019 | example | BLOCKED | 需真实目录,单元层证不了;与 U39 后半一并归入集成行为(A 系列) |
| U45 | 该工具的任何写入尝试被拒——凭证与工具集不具备写能力 | FR-011 | example | DONE | `tests/tools/pipely/test_verify_governance.py::test_the_tool_exposes_no_way_to_write_to_the_catalog` |
| U46 | 断言集为空时判为异常输入,而非空集恒真 | FR-017 | example | DONE | `tests/tools/pipely/test_verify_governance.py::test_an_empty_assertion_set_is_malformed_input_not_a_vacuous_pass` |

### `omnigent/tools/pipely/quality_gate.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U47 | 全部门禁项优于阈值时 `passed=true` | FR-027 | example | PENDING | |
| U48 | 某项**恰好等于**阈值时判通过(边界:等于) | FR-027 | example | PENDING | |
| U49 | 某项劣于阈值一个最小单位时判失败(边界:刚好未达) | FR-028 | example | PENDING | |
| U50 | 每一项的返回都含实际值与阈值,不只含判定 | FR-027 | example | PENDING | |
| U51 | 五类门禁项(记录数、异常率、结构一致性、黄金用例、查询性能)全部出现在返回中 | FR-027 | example | PENDING | |
| U52 | 阈值取自制品引用中的冻结契约,而非从仓库读取 | FR-101 | example | PENDING | |
| U53 | 制品引用缺少冻结契约时判为异常,而非按无阈值放行 | FR-101 | example | PENDING | |

### `omnigent/tools/pipely/artifact_ref.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U54 | 产出的制品引用含代码标签、制品标签、冻结阈值与冻结断言四项 | FR-101 | example | PENDING | |
| U55 | 产出的制品引用不含分支名、工作区路径或任何可写源码位置 | FR-023 | example | PENDING | |
| U56 | 对已存在的制品引用发起修改时拒绝(不可编辑) | FR-102 | example | PENDING | |
| U57 | 同一代码标签重复产出时结果一致(幂等) | FR-102 | example | PENDING | |

### `omnigent/tools/pipely/sync_catalog.py`

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U58 | 同步后目录中的版本、计数、质量、血缘、运行状态与输入一致 | FR-031 | example | PENDING | |
| U59 | 同步失败时明确区分"目录不可达"与"调度器不可达" | FR-059 | example | PENDING | |
| U60 | 同步是幂等的:重复同步不产生重复记录 | FR-033 | example | PENDING | |

### `examples/pipely/**`(声明式配置断言)

配置本身没有运行逻辑,但"声明了什么"是可断言的,且它承载了本特性最强的一道边界(不给工具)。

| id  | behavior | traces | kind | state | test |
| --- | --- | --- | --- | --- | --- |
| U61 | 治理审计、运维发布、服务验证三个子 Agent 的定义中**不含** `os_env` | FR-025, FR-095 | contract | PENDING | |
| U62 | 架构开发子 Agent 的定义中含 `os_env` 且挂载了工作区守卫与爆炸半径策略 | FR-042, FR-043 | contract | PENDING | |
| U63 | 编排者定义中 `agent_session_sharing` 为具名用户档,**不是**匿名公开档 | FR-084 | contract | PENDING | |
| U64 | `ask_timeout` 的取值足以覆盖天级等待 | FR-052 | contract | PENDING | |
| U65 | 各 MCP 声明的工具白名单与该 Agent 职责一致,无越权工具 | FR-098, SC-037 | contract | PENDING | |
| U66 | 平台管理凭证未出现在任何 Agent 的环境或工具配置中 | FR-063, SC-002 | contract | PENDING | |
| U67 | 架构开发 Agent 的进程环境凭证项恰为模型访问与代码托管两项 | FR-062, SC-022 | contract | PENDING | |
| U68 | 变更请求操作凭证与 git 克隆推送凭证是两个独立配置项 | FR-080 | contract | PENDING | |

## Invariants and edge cases still to place

属于本特性但尚无归属组件的行为。每条都必须在完成前变成上面的编号行,或带理由丢弃。

- 会话跨天中断后重新进入时,闸门标签仍可读且流程可从原处继续(标签持久化的前提未在 spec 中显式确认)。
- 同一管线的两个流程实例并发存在时(一个交付迭代、一个日常运行),两者的标签互不干扰。
- 变更请求包在 GitHub 侧被人工修改后再合并,核验应基于**合并后的内容**而非生成时的内容。
- 冻结契约与仓库中的 Spec 事后出现分歧时的检出方式(spec 只规定不可编辑,未规定如何检出漂移)。

## Out of scope

读者可能期待、但本清单刻意不含的东西,各附一句理由。

- **"Agent 产出的管线"自身的行为**(快照不覆盖、幂等、回滚的具体实现):按 FR-092,那是 **Agent 的验收标准而非本包的构建规格**,体现在 skill 给出的开发契约与各管线自己的 Spec 中。本清单只测 pipely 是否**要求**并**校验**了这些。
- **运行期合规监控**:FR-106 已定为以测试用例验收;运行期可见性另立需求。
- **统一登录**:两侧用户体系保持独立(FR-079),显式排除。
- **治理变更执行人的自动记录**:用户决定 v1 不读取目录变更历史。
- **沙箱 + 凭证代理的更强隔离**:v1 用"环境里不放多余凭证"约束有 shell 的 Agent。
- **多环境治理**:单一目标环境,开发期隔离靠沙箱 Domain。
- **OpenMetadata 与 Airflow 自身的行为**:外部系统,不在本特性测试范围。

## Verification commands

从 `.specify/memory/tdd-profile.md` 逐字复制,使本文件可独立阅读:

- 单测:`uv run pytest {file} -k "{name}"`
- 单文件:`uv run pytest {file}`
- 全量套件:`uv run pytest -m "not databricks" -n 8 --dist=loadfile`
- 覆盖率:`uv run pytest {files} --cov=omnigent --cov-report=term-missing`
- 变异测试:**无**(两个 lockfile 中都没有变异工具;`/speckit.tdd.verify` 须用故意突变抽查)
- 属性测试库:**无**(无 hypothesis;不变量以边界样例采样,不得声称已证明)

### 本特性专用:不要对照零

后端基线是 **red**。跑套件请用已知失败基线对照:

- 本特性区域:`.specify/memory/pytest-known.sh --compare tests/policies tests/tools -q`
  (基线 key `1ac6d2ab828b`,记录于 `d5d7fced`:**12 failed / 1577 passed**,12 条全部预先存在,集中在 `tests/tools/test_local.py` 与 `test_manager.py`)
- 全量:`.specify/memory/pytest-known.sh --compare -m "not databricks" -n 8 --dist=loadfile -q`

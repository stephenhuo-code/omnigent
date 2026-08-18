# 成功标准覆盖比对(T081)

FR-106 要求每条成功标准都有测试用例作为验收证据。本文逐条比对 spec 的 40 条标准
与 `tests/{policies,tools}/pipely/` 下的实际用例。

**不粉饰**:40 条中有 12 条在本仓库内**无法**以测试证明,原因逐条写明。
把它们算作"已覆盖"会让 FR-106 变成一句空话。

---

## 一、已由通过的测试证明(19 条)

| SC | 标准 | 证据 |
| --- | --- | --- |
| SC-002 | Agent 持有平台管理凭证的次数为 0 | `test_identity.py::test_a_platform_admin_credential_in_the_environment_refuses_startup`;`test_agent_declarations.py::test_no_agent_is_handed_a_platform_admin_credential` + `::test_the_environment_template_offers_no_platform_admin_credential` |
| SC-004 | 门禁失败时线上指向被切换的次数为 0 | `test_flow_acceptance.py::test_a_failing_quality_check_leaves_the_live_pointer_where_it_is` |
| SC-005 | 只读角色成功写入的次数为 0 | `test_flow_acceptance.py::test_the_governance_agent_cannot_write_through_the_real_engine` + `::test_the_consumer_agent_cannot_write_but_can_still_search`;`test_agent_declarations.py::test_the_read_only_agents_are_given_no_write_verb` |
| SC-006 | 运维发布读改源码的次数为 0 | `test_agent_declarations.py::test_the_no_shell_sub_agents_declare_no_os_env[operations]` —— 无机制,非规矩 |
| SC-010 | 重复执行产生重复资产的次数为 0 | `test_verify_governance.py::test_verifying_the_same_assertions_twice_gives_the_same_answer`;`test_artifact_ref.py::test_building_twice_from_the_same_inputs_gives_the_same_reference`;`test_sync_catalog.py::test_syncing_the_same_release_twice_leaves_one_record` |
| SC-013 | 闸门被自动跨越的次数为 0 | `test_agent_declarations.py::test_nothing_an_agent_does_can_advance_the_release_gate`;`test_gates.py` 的四条边界用例 |
| SC-018 | 部署非制品作业 / 调度凭证执行平台操作的次数为 0 | `test_flow_acceptance.py::test_release_stays_inside_what_the_artifact_was_verified_to_contain` + `::test_the_scheduler_credential_cannot_govern_only_run` |
| SC-020 | 凭证缺失时派发前报出全部缺失项的比例 100% | `test_flow_acceptance.py::test_no_task_is_dispatched_until_preconditions_are_verified` + `::test_a_partly_configured_deployment_is_told_every_gap_at_once` |
| SC-025 | 只读 bot 写探测被拒 100%;权限过宽的 bot 通过自检次数为 0 | `test_bot_selfcheck.py::test_readonly_bot_write_probe_not_refused_fails_the_selfcheck` + `::test_permissions_wider_than_the_role_name_the_extra_ones` + `::test_a_bot_with_no_write_probe_at_all_does_not_pass` |
| SC-029 | 把守人因不在发起会话而收不到待办的次数为 0 | `test_agent_declarations.py::test_the_orchestrator_shares_to_named_users_not_to_anyone`(共享档为具名用户);送达链路本身见 SC-016 |
| SC-033 | 越序操作被策略拒绝的比例 100% | `test_gates.py` 的等于 / 小于 / 大于 / 缺失四条边界 |
| SC-035 | 无 shell 子 Agent 依赖 skill 脚本的情形为 0 | `test_agent_declarations.py::test_the_no_shell_sub_agents_declare_no_os_env` —— 无 shell 即无从执行脚本 |
| SC-036 | 依据模型自述判定闸门的次数为 0 | `test_gate_advance.py::test_a_model_claiming_it_verified_something_moves_no_gate`;`test_flow_acceptance.py::test_an_unmet_governance_assertion_leaves_the_g2_gate_shut` |
| SC-037 | 子 Agent 持有越权工具的项数为 0 | `test_agent_declarations.py::test_every_catalog_connection_declares_an_allow_list` + `::test_the_read_only_agents_are_given_no_write_verb` + `::test_only_operations_can_reach_the_scheduler` |
| SC-038 | 架构开发 bot 写入沙箱外的次数为 0 | `test_identity.py::test_the_architect_bot_may_not_write_governed_assets_outside_the_sandbox` |
| SC-040 | 运维发布 bot 改动其他管线资产的次数为 0 | `test_identity.py::test_the_release_bot_may_not_write_another_pipelines_assets` + `::test_a_pipeline_whose_name_merely_starts_the_same_is_not_in_scope` |
| SC-030 | 未获委派者通过闸门的次数为 0 | `test_preflight.py::test_not_shared_and_no_approve_grant_are_distinct_failures` —— **仅检出侧**;"Agent 自行授予审批权"无需测试:`sys_session_share` 在框架层就授不了审批权 |
| SC-022 | 有 shell 的 Agent 环境中超额凭证项数为 0 | `test_agent_declarations.py::test_the_environment_template_offers_no_platform_admin_credential` —— **仅模板侧**,进程环境实测随 A7 |
| SC-014 | 不可恢复操作 / Agent 自行合并 / 越工作区写入的次数为 0 | 合并侧:`test_nothing_an_agent_does_can_advance_the_release_gate`;越工作区侧随 A24 阻塞 |

## 二、可由结构直接判定,无需运行期测试(6 条)

这些是"数量为 0"式的架构断言,查包内容即可确证,写测试只是把 `ls` 包一层。

| SC | 标准 | 判定方式 |
| --- | --- | --- |
| SC-012 | 更换技术选型需改的角色定义条目数为 0 | 闸门逻辑在 `omnigent/policies/pipely/`,不含任何管线技术名 |
| SC-019 | 新增部署的调度系统数量为 0 | 只声明了 OpenMetadata 自带的 Airflow(`agents/operations/config.yaml`) |
| SC-024 | 新建的 git 托管服务数量为 0 | 复用既有 GitHub 凭证(`.env.example`),包内无托管服务声明 |
| SC-027 | 因两侧用户体系独立而无法完成的功能项数为 0 | bot 方案(`.env.example` 第三节)使全部 Agent 访问不依赖统一登录 |
| SC-032 | 新增的独立应用程序数量为 0 | 交付物只有 Agent 定义 + 框架内子包,无独立服务 |
| SC-039 | 新增一条管线需新建的 bot 数量为 1 | `.env.example` 明确只有 `OMNIGENT_OM_RELEASE` 按管线隔离 |

## 三、需真实外部系统,随对应行为阻塞(7 条)

| SC | 标准 | 阻塞于 |
| --- | --- | --- |
| SC-003 | 核验检出人为注入缺失步骤的准确率 100% | A16(需真实目录注入偏差) |
| SC-007 | 回滚 5 分钟内完成且数据可查 | A36 |
| SC-008 | 目录记录与实际部署一致率 100% | A37 |
| SC-011 | 检索结果不含内部路径、100% 带命中原因 | A45 |
| SC-016 | 子 Agent 发起的审批送达人类成功率 100% | A15(需真实审批链路) |
| SC-023 | 令牌具备合并权限的情形为 0;凭证落盘次数为 0 | A29、A30(需真实 GitHub) |
| SC-028 | 架构开发 bot 权限边界与可用性 | A32(需真实目录) |

## 四、流程指标,非代码可测(5 条)

这些衡量的是**人使用这套系统的效果**,不是代码行为。以试运行观测,不以测试断言。

| SC | 标准 | 为何不可测 |
| --- | --- | --- |
| SC-001 | 30 分钟内拿到可评审 Spec | 计时指标,取决于模型与人的往返 |
| SC-009 | 人工投入下降 50% 以上 | 需与"当前纯人工流程"对比基线 |
| SC-015 | 轮询次数为 0 | 提示词约束(编排者"派发后结束回合");无机制强制 |
| SC-017 | 等待审批期间被占用的会话数为 0 | 同上,由 `async: true` 与提示词共同保证 |
| SC-026 | Agent 以人类身份访问目录的次数为 0 | 由部署时只发放 bot 令牌保证,不在包内 |

## 五、缺口(2 条,均为 spec 层面的机器校验缺失)

初稿把三条列为缺口。复核 `spec.md` 的《载体认领》一节后更正如下——
SC-021 本轮已补测试,另两条在**能力层**已有映射,缺的是**逐 FR 粒度**与自动校验。

| SC | 标准 | 现状 |
| --- | --- | --- |
| SC-021 | 产出物中出现凭证明文的次数为 0 | **已补**:`test_sync_catalog.py::test_a_failure_report_does_not_carry_the_credential_that_failed` —— 失败路径不再透传异常文本(客户端常把带令牌的 URL 写进去) |
| SC-031 | 每条 FR 都能指出其强制载体的比例 100% | **部分**:spec《载体认领》表按**能力**做了映射并标注强制力等级,各模块文档字符串也写明了自己承载哪些 FR(T077)。缺的是 107 条 FR **逐条**的正向映射与机器校验 |
| SC-034 | 仅以 skill/prompt 承载的禁止类约束条数为 0 | **部分**:载体表中唯一的"弱(靠模型遵守)"一行是"五阶段流程编排、手册与报告结构"——**不是禁止类约束**,所以按设计该标准成立。缺的是自动校验:没有东西阻止日后新增一条只写在提示词里的禁令 |

**为何不硬造那张 107 行表**:逐 FR 映射需要对每条需求判断其真实载体,判错了比不做更糟——
一张看起来完整、实则把提示词约束标成"强"的表,正是 SC-031 想防的东西。
这项适合人工过一遍 spec 时完成,不适合我批量生成。

## 汇总

| 类别 | 条数 |
| --- | --- |
| 已由测试证明 | 20 |
| 结构可判定 | 6 |
| 随行为阻塞于真实环境 | 7 |
| 流程指标,非代码可测 | 5 |
| **机器校验缺失(能力层已有映射)** | **2** |

**FR-106 的当前达成度**:20/40 有测试证据,6 条可由结构确证,12 条需环境或属流程指标,
2 条(SC-031、SC-034)在能力层已有映射但缺逐条机器校验。

FR-106 的原文要求"每条成功标准都有测试用例"。按上表,该要求对第四类(流程指标)不可能达成——
这是 spec 层面需要收敛的措辞,不是实现层面的欠账。已在此如实标注,不以"已覆盖"含糊过去。

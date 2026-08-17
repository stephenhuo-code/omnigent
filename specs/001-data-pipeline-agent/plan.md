# Implementation Plan: pipely — 数据管线生命周期 Agent

**Branch**: `001-data-pipeline-agent` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-data-pipeline-agent/spec.md`

## Summary

交付一个名为 **pipely** 的 omnigent Agent 定义包:编排者加四个子 Agent(架构开发、治理审计、运维发布、服务验证),覆盖面向 OpenMetadata 的数据管线五阶段生命周期,以四道人工闸门(G1–G4)与三个人类角色约束流程。

**交付物不是应用程序,而是两块东西**:`examples/pipely/` 下的 Agent 定义(YAML 与 skills,作为资源分发),以及 `omnigent/policies/pipely/` 下的自写策略函数(可被 `import`,承载唯一的硬强制)。

技术路线的核心判断:**强制力来自载体而非措辞**。禁止类约束落策略;"必须做且做成"落「确定性工具 + 在工具结果上求值的策略」组合;纯计算落 Python 函数工具;只有"怎么做"的知识才落 skill 与 prompt。运行时**没有 Agent 启动自检钩子**,因此前置条件校验只能由策略在首个工具调用上拦截。

## Technical Context

**Language/Version**: Python 3.12(`requires-python = ">=3.12"`);Agent 定义为 YAML

**Primary Dependencies**: omnigent 运行时(策略引擎、MCP 客户端、子 Agent 编排、审批与收件箱);codex CLI(架构开发子 Agent 的 harness);deepseek 提供方(其余四个 Agent)

**Storage**: 本特性**不引入任何新存储**。闸门状态寄存于 omnigent 的会话级 guardrails 标签;管线产物在 OpenMetadata 与检索服务侧;变更请求包与 Spec 在 GitHub

**Testing**: pytest,测试落在 `tests/policies/pipely/`(与 `omnigent/policies/pipely/` 逐目录对应,遵宪法原则 II)。命令取自 `.specify/memory/tdd-profile.md`:单测 `uv run pytest {file} -k "{name}"`,区域套件 `uv run pytest tests/policies`

**Target Platform**: omnigent server(本地 macOS 开发,Linux 部署);外部依赖 OpenMetadata(含自带 Airflow)与 GitHub

**Project Type**: Agent 定义包 + 框架内策略子包。**不是** src/tests 式的独立应用

**Performance Goals**: Agent 侧无独立性能目标。spec 中与时长相关的成功标准(SC-001 三十分钟出 Spec、SC-007 五分钟回滚)属流程指标,由端到端场景验证,不作为代码级性能约束

**Constraints**:
- 三个子 Agent(治理审计、运维发布、服务验证)**不声明 `os_env`** ⇒ 无 shell、无文件工具,其确定性逻辑只能以 Python 函数工具提供
- 策略以**点分导入路径**引用 ⇒ 必须放在可 `import` 的包内;`examples/` 是资源目录,不在导入路径上
- **没有 Agent 启动自检钩子** ⇒ 前置校验必须由策略在首个工具调用上拦截
- 有 shell 的架构开发子 Agent 可读取整个进程环境 ⇒ 其环境中只放模型访问与代码托管两项凭证

**Scale/Scope**: 一套 Agent 服务多条管线;三个只读 bot 全局共用,运维发布 bot 每条管线一个;一个会话 = 一次流程实例

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 评估 | 结论 |
| --- | --- | --- |
| **I. 测试先行(不可协商)** | 本特性的每一条行为变更都落在策略函数与工具函数上,均可单测。`.specify/memory/tdd-profile.md` 已就绪,pytest 单测命令双向验证过。spec 的 FR-106 已明确要求"每条成功标准都有测试用例作为验收证据"。 | **通过** |
| **II. 测试就近与最小化** | `omnigent/policies/pipely/` → `tests/policies/pipely/`,逐目录对应;`tests/policies/` 已存在。本特性**不触碰 `web/**`**,因此不触发 `E2E UI Required` 检查,无需 `tests/e2e_ui/` 覆盖。绝大多数行为(策略决策、工具返回值)用单测即可覆盖;跨 Agent 的闸门流转需要 `tests/integration/`。 | **通过** |
| **III. 门禁必须为绿** | 新增文件为 Python 与 YAML,受 ruff / pyrefly 管辖;`uvx pre-commit run` 在本次文档提交上已全绿。 | **通过** |
| **IV. 变更可追溯** | 按 `.github/pull_request_template.md` 填写;提交带 DCO 签名。本特性无废弃项,不涉及 `@deprecated` 标注。 | **通过** |
| **V. 边界清晰** | 自写策略放在 `omnigent/policies/pipely/`——策略是**框架自有的运行时行为**,放在框架模块内符合原则;Agent 定义只做声明,不复制策略逻辑。本特性**不触碰数据库**,`make_named_managed_session_maker` 一条不适用。 | **通过** |

**Baseline 警示(不构成违反,但影响执行)**:tdd-profile 记录后端套件基线为 **red**(`tests/cli` 有 8 个失败在 CI 上同样红)。执行时必须用 `.specify/memory/pytest-known.sh --compare` 对照已知失败,而不是对照零;否则每次"跑套件确认没弄坏别的"都会撞上既有失败。

**Complexity Tracking**:无违反项,该节留空。

### 设计后复检(Phase 1 完成)

| 原则 | 复检结论 |
| --- | --- |
| **I. 测试先行** | **强化**。三份契约(`contracts/`)各自指明了测试落点与**必须覆盖的负向用例**,其中最关键的三条是:核验工具在断言不满足时须判失败并给出补做步骤、门禁在任一项未达阈值时须给出实际值、**bot 自检在只读 bot 的写探测未被拒时须判失败**。第三条测的是"检查器本身有没有用"。 |
| **II. 测试就近与最小化** | **通过,且落点已核实存在**:`tests/policies/`、`tests/tools/`、`tests/integration/` 三个目录均已在仓库中,新增子目录与 `omnigent/policies/pipely/`、`omnigent/tools/pipely/` 逐目录对应。策略与工具都是纯函数,绝大多数行为用单测覆盖;仅跨 Agent 的闸门流转需要 integration。 |
| **III. 门禁必须为绿** | 通过。新增为 Python 与 YAML,受 ruff / pyrefly 管辖。 |
| **IV. 变更可追溯** | 通过。无废弃项。 |
| **V. 边界清晰** | **通过**。设计后新增了 `omnigent/tools/pipely/`,与 `omnigent/tools/builtins/` 并列——理由同策略子包:函数工具的 `callable` 同样以点分路径引用,必须可 `import`。两个子包都是**纯新增目录**,不触碰上游任何文件。 |

**结论:五项全部通过,无需填写 Complexity Tracking。**

## Project Structure

### Documentation (this feature)

```text
specs/001-data-pipeline-agent/
├── spec.md              # 需求规格(已完成,909 行)
├── plan.md              # 本文件
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出
│   ├── tools.md         #   Python 函数工具的调用契约
│   ├── policies.md      #   策略函数的事件与决策契约
│   └── artifacts.md     #   制品引用与变更请求包的结构契约
├── checklists/
│   └── requirements.md  # 规格质量检查清单(16/16)
└── tasks.md             # Phase 2 输出(由 /speckit-tasks 生成,不在本命令范围)
```

### Source Code (repository root)

```text
examples/pipely/                          # Agent 定义(资源,不在 Python 导入路径上)
├── config.yaml                           # 编排者:prompt / executor / tools.agents /
│                                         #   guardrails / agent_session_sharing
├── agents/
│   ├── architect/config.yaml             # 架构开发子 Agent(codex,有 shell)
│   ├── governance/config.yaml            # 治理审计子 Agent(deepseek,无 shell)
│   ├── operations/config.yaml            # 运维发布子 Agent(deepseek,无 shell)
│   └── consumer/config.yaml              # 服务验证子 Agent(deepseek,无 shell)
├── tools/mcp/
│   ├── openmetadata.yaml                 # OpenMetadata 目录接入(按 Agent 分令牌)
│   └── airflow.yaml                      # OpenMetadata 自带 Airflow 的操作接入
└── skills/
    ├── plan-spec/SKILL.md                # 阶段 1:从需求到统一 Spec
    ├── governance-change/SKILL.md        # 阶段 2:出手册、核验
    ├── build-release/SKILL.md            # 阶段 3:开发、门禁、交接
    └── operate/SKILL.md                  # 阶段 4:触发、门禁、上线、回滚

omnigent/policies/pipely/                 # 自写策略函数(可 import,唯一硬强制载体)
├── __init__.py
├── gates.py                              # 闸门状态机(FR-090、FR-099)
├── preflight.py                          # 前置条件校验(FR-091、FR-060)
├── handoff.py                            # 制品引用交接约束(FR-023、FR-056)
└── identity.py                           # bot 权限自检与凭证边界(FR-074、FR-062)

omnigent/tools/pipely/                    # 确定性函数工具(无 shell 的 Agent 唯一可用形式)
├── __init__.py
├── verify_governance.py                  # 只读核验治理落地(FR-017)
├── quality_gate.py                       # 质量门禁判定(FR-027)
└── bot_selfcheck.py                      # bot 权限负向探测(FR-074)

tests/policies/pipely/                    # 与策略子包逐目录对应(宪法原则 II)
tests/tools/pipely/                       # 与工具子包逐目录对应
tests/integration/pipely/                 # 跨 Agent 的闸门流转
```

**Structure Decision**: 采用**双落点**结构而非单一项目树,原因是运行时的两条硬约束:

1. Agent 定义必须放在 `examples/` 才能被既有的分发与发现路径识别,但该目录**不在 Python 导入路径上**(无 `__init__.py`、目录名可含连字符、打包时作资源处理)。
2. 策略与工具以**点分导入路径**引用,必须位于 `omnigent` 包内。

因此把"声明"与"代码"分放两处,并各自与 `tests/` 逐目录对应。选新建 `omnigent/policies/pipely/` 而非并入 `omnigent/policies/builtins/`,是为了与上游内置策略隔离——纯新增目录,变基时冲突面最小。

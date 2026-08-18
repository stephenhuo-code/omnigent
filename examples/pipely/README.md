# pipely — 数据管线生命周期 Agent

面向 OpenMetadata 的数据管线编排者:把一条需求从 Spec 走到治理、开发、上线、验证,
沿途停在**四道人工闸门**上。编排者自己不写管线代码,四个子 Agent 分担实际工作。

需要平台特权的治理操作**不由任何 Agent 执行**——它们被写成变更请求交给人,
之后由一个只读工具核验是否真的落地了。

## 五个 Agent

| Agent | 职责 | 有 shell | 目录访问 |
| --- | --- | --- | --- |
| `pipely` | 编排、持有闸门、跑确定性判定 | 否 | 无(判定工具是纯函数) |
| `architect` | Spec 规划、管线代码与测试 | **是**(codex) | 读全量;写**仅限沙箱 Domain** |
| `governance` | 读目录审阅、写变更请求、报告观测值 | 否 | **只读** |
| `operations` | 发布、跑门禁、切指向、回滚、同步目录 | 否 | 写**本管线**资产 + 调度器 |
| `consumer` | 以消费者身份验证服务 | 否 | **只读** |

三个子 Agent **不声明 `os_env`**——没有 shell、没有文件工具。这不是规矩,是没有机制。

## 四道闸门

```
G1 Spec 冻结      开发负责人确认
G2 治理已落地     人手工执行 + 只读核验工具返回全部通过
G3 发布就绪       人合并变更请求、产出制品引用
G4 已上线         运维负责人批准切换
```

日常运行(`kind=operation`)跳过 G1–G3,只判 G4。

**质量门禁不是闸门**:它跑在 G3 与 G4 之间,结论记在 `pipely.quality`。
切换线上指向要求**同时**满足 `pipely.gate ≥ g3_passed` 与 `pipely.quality = passed`——
前者说"这个版本可以上",后者说"这一跑的结果可以用",重跑只重判后者。

## 判定在哪里发生

omnigent 的会话标签是**逐会话**的,子 Agent 不继承父会话的标签。因此:

- **子 Agent 报告观测值**——用自己作用域内的凭证读出来的值、量出来的数。它们不做判定。
- **编排者做判定**——在自己会话里跑 `verify_governance` 与 `quality_gate`,
  据其**真实返回值**推进标签。

子 Agent 说"检查通过了"不会推进任何东西。这是 FR-097 的落点。

## 前置条件

### 一、必须由人手工创建的东西

**引导用只读 bot**(`OMNIGENT_OM_BOOTSTRAP_READER`)必须在启动 pipely **之前**
由平台管理员在 OpenMetadata 中手工建好。

Agent 不会、也不得尝试自建它——创建这个 bot 所需的权限,正是它本身要引导出来的那个权限。
缺它时前置校验会报出该项并停止。

其余三个 bot(架构开发、运维发布、服务验证)与开发沙箱 Domain,
由 `governance` 写进变更请求包,走 G2 交人执行。

### 二、会话共享与审批权

闸门待办要送到**平台管理员与运维负责人本人**的收件箱——那通常不是发起会话的人。在 omnigent 会话设置里:

1. 把会话共享给他们的账号;
2. 给他们委派 `can_approve`。

缺第 1 项与缺第 2 项**分别报告**,因为处置方式不同。
注意 `sys_session_share` 只能授予访问级别、**授不了审批权**;审批权的唯一开关是编排者的
`agent_session_sharing: non-public`。

### 三、凭证

复制 `.env.example` 为 `.env` 并逐项填写。每一项都注明了用途、归属哪个 Agent、是否必需。

**平台管理凭证不在这个列表里,也绝不应加进去。** 平台管理员直接对 OpenMetadata 操作,
那条线绕开 omnigent。`architect` 有 shell、能读到整个进程环境,
所以"不放进来"是唯一成立的边界,"放进来但不用它"不算。

## 启动

**运行时自身不解析 `.env`**,必须由启动命令注入:

```bash
uv run --env-file examples/pipely/.env omnigent serve
```

漏了 `--env-file` 的表现是前置校验报告所有凭证缺失——不是崩溃,但也不会开始工作。

启动后前置校验在**第一个工具调用**上拦截(运行时没有 Agent 启动自检钩子),
缺任何必需项时会**一次性列出全部缺失项**并停止,不会跑到一半才失败。

## 这个包里有什么

```
examples/pipely/
├── config.yaml              编排者:闸门、裁决记录、派发闸门
├── .env.example             凭证清单,逐项注释
├── agents/{architect,governance,operations,consumer}/config.yaml
├── tools/python/            编排者持有的判定工具(纯函数,无需凭证)
│   ├── verify_governance.py
│   └── quality_gate.py
└── skills/{plan-spec,governance-change,build-release,operate}/SKILL.md
```

强制逻辑不在这里,而在 `omnigent/policies/pipely/` 与 `omnigent/tools/pipely/`——
策略以点分路径引用,必须位于可 import 的包内。各模块的文档字符串写明了它承载哪些 FR。

## 已知限度

**观测值经由模型转述。** 判定是确定性的,且观测方与判定方分离——
这比"同一个模型既做事又宣称做完"强得多,但**不等于观测值不可伪造**。
要封死这条路需要让裁决落到 OpenMetadata 再读回,那是后续方案。

**跨 Agent 的闸门流转依赖派发参数。** 每次派发携带 `phase`,闸门按该参数判定。
参数由编排者填,不是自由文本——但它仍在编排者的自主范围内。

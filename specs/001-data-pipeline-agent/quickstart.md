# Phase 1 · 快速验证指南

本文件描述**如何证明 pipely 真的按 spec 工作**。它是验证与运行指南,不含实现代码。

---

## 前提

### 一次性部署配置

| 项 | 说明 | 由谁做 |
| --- | --- | --- |
| OpenMetadata 实例 | 含自带 Airflow,可访问 | 平台管理员 |
| **治理审计 bot(只读)** | **必须手工创建** —— 引导用,不走流程 | 平台管理员 |
| 开发沙箱 Domain | 架构开发 Agent 的写入范围 | 平台管理员(可随第一次 G2 建) |
| GitHub 仓库 | 管线代码 + Spec + 变更请求包 | — |
| GitHub 令牌 | **不授予合并权限**(使"Agent 不合并"在凭证层强制) | 平台管理员 |
| 会话共享 | 把工作会话共享给平台管理员与运维负责人 | 会话所有者 |
| 审批权委派 | 为上述两人分别开启 —— **与访问权是两回事,默认关闭** | 会话所有者 |

### 环境变量

运行时**自身不解析配置文件**,须由启动命令注入:

```bash
uv run --env-file .env omnigent server
```

变量名支持 `OMNIGENT_` 前缀别名,避免与宿主机同名变量冲突。**平台管理凭证不在此列**——它不进入 omnigent。

---

## 验证一 · 前置校验会拦住漏配

**这是最先该跑的**,因为它证明"漏配会被发现",而不是等到流程中途才炸。

```bash
# 故意漏掉一项凭证后启动一次流程
uv run pytest tests/policies/pipely/test_preflight.py -k "missing_credentials"
```

**期望**:在派发任何任务**之前**,一次性列出**全部**缺失项及其对应 Agent,并停止。

**另外两个必须分别验的场景**:

```bash
uv run pytest tests/policies/pipely/test_preflight.py -k "not_shared"          # 未共享 → 看不到待办
uv run pytest tests/policies/pipely/test_preflight.py -k "no_approve_grant"    # 已共享未委派 → 看得到点不动
```

这两种失败**处置方式不同**,合并成一种错误会误导排查。

---

## 验证二 · 只读 bot 真的写不了

**只验"令牌可用"不算通过。** 一个被误授写权限的只读 bot 不会有任何症状,权限边界却已失效。

```bash
uv run pytest tests/tools/pipely/test_bot_selfcheck.py -k "negative_probe"
```

**期望**:只读 bot 的**写操作探测被 OpenMetadata 拒绝**,自检才算通过;若探测**未**被拒,自检必须判失败并把该 bot 列入越权项。

---

## 验证三 · 闸门不可跨越

```bash
uv run pytest tests/policies/pipely/test_gates.py -k "skip_gate_denied"
```

**期望**:在 `pipely.gate` 未到 `g2_passed` 时发起阶段 3 的操作,被策略拒绝,并说明缺哪一步。

**最关键的一条 —— 模型谎报无效**:

```bash
uv run pytest tests/policies/pipely/test_gates.py -k "self_report_does_not_pass_gate"
```

**期望**:模型声称"我已核验通过"**不会**写出 `g2_passed` 标签;只有 `verify_governance` 工具的**真实返回值** `passed=True` 才会。后续操作照样被拒。

---

## 验证四 · 交接后运维够不着源码

```bash
uv run pytest tests/policies/pipely/test_handoff.py -k "rejects_source_path"
uv run pytest tests/policies/pipely/test_handoff.py -k "deploy_outside_artifact_ref"
```

**期望**:交接物含分支名/工作区路径时被拒;部署非制品引用范围内的作业定义时被拒。

---

## 验证五 · 端到端流程

需要真实的 OpenMetadata 与 GitHub。属 `tests/integration/`,不在默认套件内。

```bash
uv run pytest tests/integration/pipely -v
```

**走一遍 delivery 流程**:

1. 提出一个数据需求 → 产出统一 Spec,九类条目齐备
2. 停在 **G1**,不生成变更请求包
3. 确认 G1 → 治理审计 Agent 出变更请求包(手册 + 断言 + 核验脚本),提 PR
4. 待办出现在**平台管理员本人的收件箱**中 —— 即便会话由开发负责人发起、管理员从未打开过它
5. 管理员合并 PR、按手册执行、在收件箱点确认 → 触发只读核验
6. 核验通过 → **G2**;人为漏做一步再核验 → 判失败并列出需补做的步骤
7. 开发 → 测试全绿 → 开 PR → 停在 **G3**,Agent **不自行合并**
8. 合并打标签 → 产出制品引用(**含冻结的阈值与断言**)
9. 运维发布 Agent 按制品引用触发 Airflow → 质量门禁 → 停在 **G4**
10. 运维负责人批准 → 切换线上指向 → 同步状态回 OpenMetadata
11. 服务验证 Agent 以只读 bot 消费,验证结果可解释、内部字段不暴露、写操作全部失败

**中途必须验的负向场景**:第 9 步人为制造一项门禁失败 → 线上指向**不切换**,旧版本继续服务。

---

## 跑套件时的注意事项

后端套件基线是 **red**(`tests/cli` 有 8 个失败在 CI 上同样红)。**不要对照零**:

```bash
.specify/memory/pytest-known.sh --compare tests/policies       # 区域
.specify/memory/pytest-known.sh --compare -m "not databricks" -n 8 --dist=loadfile   # 全量
```

任何它报出来的失败才是**新的**。

---

## 已知未验证项

| 项 | 说明 |
| --- | --- |
| OpenMetadata 接口细节 | 本仓库无任何 OpenMetadata 代码可供查证。MCP 工具名、bot 与角色的创建方式、Domain 划分接口,均须对照部署的实际版本确认。**这是实现阶段的第一个风险点。** |
| 两份 HTML 设计文档的渲染 | 结构校验通过,但本机无 mermaid,四张图未做渲染校验 |

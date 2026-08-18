# Cycle Log: pipely — 数据管线生命周期 Agent

追加式记录,一次循环一条,按循环发生的顺序排列。**不得编辑过去的条目**;要更正就新增一条,说明它更正的是什么。

---

## Baseline · d5d7fced · 2026-08-17

由 `/speckit.tdd.plan` 写入。此后的条目由 `/speckit.tdd.run` 追加。

**本特性区域**(内层循环每轮实际会跑的范围)

```
.specify/memory/pytest-known.sh --capture tests/policies tests/tools -q
→ 12 failed, 1577 passed  (22.02s)
```

12 条失败**全部预先存在**,集中在 `tests/tools/test_local.py` 与 `tests/tools/test_manager.py`,与本特性无关。已记录为已知失败基线,key `1ac6d2ab828b`。

此后每轮请用:

```
.specify/memory/pytest-known.sh --compare tests/policies tests/tools -q
```

**它报出来的失败才是新的。不要对照零。**

**全量套件**(取自 `.specify/memory/tdd-profile.md`,检测于 `5a4e756c`)

```
uv run pytest -m "not databricks" -n 8 --dist=loadfile
→ 81 failed, 5 errors, 19232 passed, 92 skipped, 7 xfailed  (8m01s)
```

`suite_baseline: red`。其中约 8 条是主干上真实存在的红(`tests/cli`,在 CI 上同样失败),其余为 macOS 与无 TTY 环境所致。**循环不得建立在"对照零"之上。**

---

## Cycle 1 · U34 · 2026-08-17

**行为**:只读 bot 的写探测未被拒时,该项判失败且该 bot 进入越权清单
**追溯**:FR-074, SC-025

**测试**:`tests/tools/pipely/test_bot_selfcheck.py::test_readonly_bot_write_probe_not_refused_fails_the_selfcheck`

**红**

```
uv run pytest tests/tools/pipely/test_bot_selfcheck.py -k "test_readonly_bot_write_probe_not_refused_fails_the_selfcheck" -q
E       assert True is False
tests/tools/pipely/test_bot_selfcheck.py:26: AssertionError
1 failed in 0.06s
```

首次运行是 `ModuleNotFoundError`,**不是有效的红**。按 playbook 加入最小声明(`evaluate` 返回默认通过的报告形状)后重跑,取得上述断言失败作为红证据。

**绿**:在 `evaluate` 中加入越权判定——期望为只读且探测未被拒的 bot 进入 `over_privileged`,`passed` 取其反。

```
.specify/memory/pytest-known.sh --compare tests/policies tests/tools -q
→ 1590 passed, 0 failed  (20.21s)  ── No new failures
```

**重构**:无需重构。实现是单个列表推导加返回,测试只有一个构造器;无重复、无第二职责、命名贴切。不为显得勤奋而虚构改动。

**备注**

- **基线偏离(用户已授权)**:全量套件基线为 red,playbook 的逃生舱本应阻止循环。用户授权以 `pytest-known.sh --compare` 归因作为"绿"的定义。**但本特性范围在 worktree 中实为真绿**(0 failures),故本轮的绿是无条件的,未依赖偏离。
- **环境更正**:主检出中 `tests/policies` + `tests/tools` 有 12 条失败,在按锁文件同步 venv 的干净 worktree 中**全部通过**。那 12 条是主检出的环境产物(import 错误),不是代码问题。基线已按 0 failures 重新捕获。
- **修复了一个假绿**:`pytest-known.sh --compare` 在 pytest 根本没运行时(缺 venv)会报告 "No new failures"。已加入守卫——无结果摘要即拒绝比对并退出 2,已验证生效。该修复在 `.specify/`(gitignored),需同步回主检出。

---

## Cycle 2 · U33 · 2026-08-17

**行为**:只读 bot 的写探测被拒时,该项判通过
**追溯**:FR-074

**测试**:`tests/tools/pipely/test_bot_selfcheck.py::test_readonly_bot_write_probe_refused_passes_the_selfcheck`

**红**:**首次运行即通过**——U34 的实现已顺带覆盖了这条正向路径。按 playbook 执行故意突变检查。

```
突变:将 `if expected.get(...) == READ_ONLY and not probe["refused"]`
      改为 `if expected.get(...) == READ_ONLY`(忽略 refused 标志)

uv run pytest tests/tools/pipely/test_bot_selfcheck.py -k "refused_passes" -q
E       assert False is True
tests/tools/pipely/test_bot_selfcheck.py:37: AssertionError
1 failed, 1 deselected in 0.06s
```

突变令测试失败,证明该测试确实在断言这条行为,而非恒真。已**原样还原**并断言无 `MUTANT` 残留。

**绿**:无需新实现——行为已由 Cycle 1 的实现覆盖,测试固化之。

```
.specify/memory/pytest-known.sh --compare tests/policies tests/tools -q
→ No new failures
```

**重构**:无需重构。

**备注**:这是 playbook 中"测试首次即通过"的标准路径。若跳过突变检查直接记为通过,这条测试的价值无法证明——它可能是一条恒真断言。

---

## Cycle 3 · U1 · 2026-08-17

**行为**:标签未写入时,任何工具调用被拒(未校验视同未通过)
**追溯**:FR-091

**测试**:`tests/policies/pipely/test_preflight.py::test_tool_call_is_denied_when_no_preflight_result_is_recorded`

**红**

```
uv run pytest tests/policies/pipely/test_preflight.py -k "no_preflight_result" -q
E   AssertionError: assert 'ALLOW' == 'DENY'
tests/policies/pipely/test_preflight.py:27: AssertionError
1 failed in 0.07s
```

首次为 `ModuleNotFoundError`(非有效红),按 playbook 加入最小声明——一个恒返回 ALLOW 的求值器——后重跑取得上述断言失败。

**绿**:读事件上下文的会话标签,仅当 `pipely.preflight.status == passed` 才 ALLOW,否则 DENY 并附原因。

```
.specify/memory/pytest-known.sh --compare tests/policies tests/tools -q
→ No new failures
```

**重构**:无需重构。测试中的 `PREFLIGHT_LABEL` 与实现中的常量重复是**刻意保留**的——测试若从被测模块导入自己要断言的标签名,标签写错时测试会跟着错,便无法发现。

**备注**:决策形状取自仓库既有的 V0 契约(`omnigent/policies/builtins/orchestration.py:24` 的 `{"result": "ALLOW"}`),非自创。

---

## Cycle 4 · U4 · 2026-08-17

**行为**:零缺失时校验通过并写入 `pipely.preflight.status = passed`
**追溯**:FR-091

**测试**:`tests/policies/pipely/test_preflight.py::test_tool_call_is_allowed_once_preflight_is_recorded_as_passed`

**红**:首次运行即通过——Cycle 3 的实现已含正向分支。执行故意突变检查。

```
突变:删去 `if labels.get(PREFLIGHT_LABEL) == PASSED: return _ALLOW`,使求值器恒 DENY

uv run pytest tests/policies/pipely/test_preflight.py -k "recorded_as_passed" -q
E   AssertionError: assert 'DENY' == 'ALLOW'
1 failed, 1 deselected in 0.06s
```

突变令测试失败,证明该测试确实在断言正向分支。已原样还原并断言无残留。

**绿**:无需新实现;测试固化 U1 的对侧边界。

```
.specify/memory/pytest-known.sh --compare tests/policies tests/tools -q
→ No new failures
```

**重构**:无需重构。

**范围说明**:清单中 U4 的措辞含"并写入 `pipely.preflight.status = passed`"。本轮只覆盖了**读取端**(标签为 passed 时放行);**写入端**属 `run_preflight` 求值器,依赖 `bot_selfcheck` 的工具结果,将在 U2/U3/U5 的循环中驱动。此处如实记录,不把未覆盖的部分算作已完成。

---

## Cycle 5 · U2 · 2026-08-17

**行为**:缺一项凭证时,失败清单恰好含该一项 · **追溯**:FR-060

**测试**:`tests/policies/pipely/test_preflight.py::test_one_absent_credential_is_reported_as_exactly_that_one`

**红**

```
uv run pytest tests/policies/pipely/test_preflight.py -k "exactly_that_one" -q
E   AssertionError: assert [] == ['credential:code_hosting']
1 failed, 2 deselected in 0.06s
```

首次为 `ModuleNotFoundError`(非有效红,`assess` 尚不存在);加入最小声明后取得上述断言失败。

**绿**:`assess` 按凭证表列出未找到项。**只实现凭证一类**,未提前实现共享与审批权——那是 U5 的行为。

**重构**:无需重构。

---

## Cycle 6 · U3 · 2026-08-17

**行为**:缺多项凭证时,失败清单一次性含全部,不止第一项 · **追溯**:FR-060

**测试**:`tests/policies/pipely/test_preflight.py::test_several_absent_credentials_are_all_reported_at_once`

**红**:首次即通过,执行故意突变检查。

```
突变:`missing = [...][:1]`(只保留第一项)

uv run pytest tests/policies/pipely/test_preflight.py -k "all_reported_at_once" -q
E   AssertionError: assert ['credential:model_access'] == ['credential:...al:om...
1 failed, 3 deselected in 0.07s
```

突变精确命中 FR-060 要防的失效模式——漏报会让人反复启动、反复才发现下一项。已原样还原并断言无残留。

**绿**:无需新实现;测试固化"一次性列全"这一性质。

**重构**:无需重构。

---

## Cycle 7 · U5 · 2026-08-17

**行为**:"未共享"与"已共享但未委派审批权"产出两种不同的失败标识 · **追溯**:FR-084, FR-085

**测试**:`tests/policies/pipely/test_preflight.py::test_not_shared_and_no_approve_grant_are_distinct_failures`

**红**

```
uv run pytest tests/policies/pipely/test_preflight.py -k "distinct_failures" -q
E   assert [] != []
1 failed, 4 deselected in 0.07s
```

两种情况当时都产出空清单,无法区分——正是这条行为要消除的。

**绿**:未共享 → `session:not_shared`;已共享但未委派 → `session:no_approve_grant`。二者处置方式不同(前者看不到待办,后者看得到点不动),合并成一种会误导排查。

```
.specify/memory/pytest-known.sh --compare tests/policies tests/tools -q → No new failures
```

**重构**:无需重构。

**工具备注**:本轮实现改动改用 Edit 工具落盘——worktree 隔离守卫拒绝了含多行分支的 heredoc 命令。不影响 TDD 纪律,仅记录手段变化。

---

## Cycle 8 · U6 · 校验只在首个工具调用上执行一次

- **测试**:`tests/policies/pipely/test_preflight.py::test_a_recorded_result_short_circuits_further_assessment`
- **红**:`uv run pytest tests/policies/pipely/test_preflight.py -k short_circuits -q`
  首跑为 `TypeError: require_preflight() got an unexpected keyword argument 'probe'` —— 非有效红。
  加入最小声明(接受 `probe` 但无条件调用)后重跑,取得 `AssertionError: assert ['ran'] == []`。
- **绿**:已记录 `passed` 标签时直接返回 ALLOW,不再调用探针。9 passed。
- **重构**:无需重构。
- **备注**:红是两步取得的——第一步的 `TypeError` 按 playbook 不计作红证据,记录的是加声明后的断言失败。

## Cycle 9 · U7 · 引导 bot 缺失时不提出"尝试创建"

- **测试**:`tests/policies/pipely/test_preflight.py::test_absent_bootstrap_bot_is_remediated_by_hand_not_by_creating_it`
- **红**:`uv run pytest tests/policies/pipely/test_preflight.py -k bootstrap -q -p no:randomly`
  → `KeyError: 'credential:om_bootstrap_reader'`
- **绿**:`assess` 增加 `remediation` 映射,引导 bot 缺失时给出 `provision_by_hand`。9 passed。
- **重构**:无需重构。
- **更正**:本轮**第一次写的测试是错的**。我按"凭证运行中失效被具名"来写,那是 U2 的重复(首跑即绿即为信号)。
  回读 test-list 第 87 行,U7 的真实行为是 FR-076 的引导 bot 不得自建。删除错误测试,按真实行为重写。
  错误测试从未进入提交。

## Cycle 10 · U8 · 闸门边界:等于则放行

- **测试**:`tests/policies/pipely/test_gates.py::test_a_session_exactly_at_the_required_gate_is_allowed`
- **红**:`uv run pytest tests/policies/pipely/test_gates.py -q -p no:randomly` → `AssertionError: assert 'DENY' == 'ALLOW'`
  (新建 `gates.py` 时先写成一律 DENY 的桩,以便红是断言失败而非 ImportError。)
- **绿**:相等比较。10 passed。
- **重构**:无需重构。

## Cycle 11 · U9 · 闸门边界:前一级则拒绝

- **测试**:`::test_a_session_one_gate_below_the_requirement_is_denied`
- **红**:首跑即绿(当时实现只做相等比较,天然拒绝)。**故意变异**:把判定改成 `if True`。
  `uv run pytest ... -k one_gate_below` → `AssertionError: assert 'ALLOW' == 'DENY'`。恢复后 2 passed。
- **绿**:实现未变;本轮价值在于把"下侧"钉死,使后续引入序关系时不能悄悄放宽。
- **重构**:无需重构。

## Cycle 12 · U10 · 闸门边界:已超过则放行

- **测试**:`::test_a_session_past_the_required_gate_is_still_allowed`
- **红**:`-k past_the_required` → `AssertionError: assert 'DENY' == 'ALLOW'`
- **绿**:引入 `GATE_ORDER` 与 `_rank()`,改为按序比较。**刻意不用字符串比较**——字典序会把 `"G10"` 排到 `"G2"` 之下。12 passed。
- **重构**:无需重构(`_rank` 是本轮为转绿引入的最小结构,非事后重构)。

## Cycle 13 · U11 · 闸门标签缺失即拒绝

- **测试**:`::test_a_session_carrying_no_gate_at_all_is_denied`
- **红**:首跑即绿(`_rank(None) == -1` 恰好承载)。**故意变异**:`return -1` → `return 99`。
  → `AssertionError: assert 'ALLOW' == 'DENY'`。恢复后 13 passed。
- **绿**:实现未变。本轮把"未知/缺失闸门排在最低"从巧合变成被钉住的约定。
- **重构**:无需重构。

## Cycle 14 · U12 · 拒绝原因须同时指明当前与所需闸门

- **测试**:`::test_a_denial_names_both_where_the_session_is_and_where_it_must_be`
- **红**:`-k names_both` → `AssertionError: assert 'G1' in 'Gate G3 has not been reached.'`
- **绿**:原因文本改为同时含当前闸门(缺失时为 `none`)与所需闸门。14 passed。
- **重构**:无需重构;`ruff format` 把 reason 合成一行,已接受并重跑门禁。

## Cycle 15 · U13 · 工具返回 passed=true 时推进闸门

- **测试**:`tests/policies/pipely/test_gate_advance.py::test_a_tool_reporting_a_pass_advances_the_gate`
- **红**:首次桩里写了 `del event, tool, grants`,删的是闭包变量,得到 `UnboundLocalError` —— **不是有效红**。
  改为只 `del event` 后重跑 → `KeyError: 'set_labels'`,记录此条为红证据。
- **绿**:读 `data.result.passed`,为 `True` 时返回 `set_labels`。15 passed。
- **重构**:无需重构。

## Cycle 16 · U14 · 工具返回 passed=false 时不写标签

- **测试**:`::test_a_tool_reporting_a_failure_leaves_the_gate_where_it_was`
- **红**:首跑即绿。第一次变异(`is True` → `is not None`)写坏了语法,产生 collection error,**作废不计**。
  第二次变异 `result.get("passed") is True` → `"passed" in result`,
  → `AssertionError: assert 'set_labels' not in {'result': 'ALLOW', 'set_labels'...}`。恢复。
- **绿**:实现未变。
- **重构**:无需重构。

## Cycle 17 · U15 · 模型自述"已核验"不推进闸门

- **测试**:`::test_a_model_claiming_it_verified_something_moves_no_gate`
- **红**:首跑即绿。**故意变异**:判定改为 `if "passed" in str(event.get("data", {}))`,即"信任叙述"。
  → `AssertionError: assert 'set_labels' not in {...}`。恢复。
- **绿**:实现未变。这一轮确认了 SC-036 想防的失败模式确实会被这条测试挡住。
- **重构**:无需重构。

## Cycle 18 · U16 · 缺 passed 字段判为异常而非默认通过

- **测试**:`::test_a_result_with_no_verdict_field_is_flagged_rather_than_ignored`
- **红**:`-k no_verdict` → `KeyError: 'malformed'`
- **绿**:把"没有裁决"与"裁决为否"分开:前者返回 `malformed: True` 并给出原因。18 passed。
- **重构**:无需重构。

## Cycle 19 · U17 · 闸门只进不退

- **测试**:`::test_a_lower_gates_result_does_not_pull_the_session_back`
- **红**:`-k pull_the_session_back` → `AssertionError: assert 'set_labels' not in {'result': 'ALLOW', 'set_labels'...}`
  (G3 会被 G2 的通过结果拉回。)
- **绿**:加入棘轮 `_rank(grants) > _rank(已达闸门)` 才写标签。19 passed。
- **重构**:无需重构。

## Cycle 20 · U18 · 首个工具调用绑定管线与流程种类

- **测试**:`tests/policies/pipely/test_flow_binding.py::test_the_first_tool_call_records_the_pipeline_and_kind`
- **红**:`uv run pytest tests/policies/pipely/test_flow_binding.py -q -p no:randomly` → `KeyError: 'set_labels'`
- **绿**:从工具参数读 `pipeline`/`kind` 写入两个标签。20 passed。
- **重构**:无需重构。

## Cycle 21 · U19 · 已绑定会话拒绝第二条管线

- **测试**:`::test_a_second_pipeline_in_a_bound_session_is_refused_not_absorbed`
- **红**:`-k second_pipeline` → `AssertionError: assert 'ALLOW' == 'DENY'`(当时会静默覆盖绑定)
- **绿**:已绑定且不一致时 DENY 且不写标签。21 passed。
- **重构**:无需重构。

## Cycle 22 · U20 · operation 流程只校验 G4

- **测试**:`::test_an_operation_flow_is_judged_on_its_own_gate_only`
- **红**:首跑为 ImportError(`require_flow_gate` 不存在),**不是有效红**。
  加入一律 DENY 的桩后重跑 → `AssertionError: assert 'DENY' == 'ALLOW'`,记录此条。
- **绿**:`kind=operation` 时所需闸门改为 `RELEASE_GATE`,不看 G1–G3。22 passed。
- **重构**:无需重构。

## Cycle 23 · U21 · ASK 被拒绝或超时时不写标签 —— 判定为既有测试已覆盖

- **状态**:`DONE`,指向既有运行时测试,本轮**未新增测试与实现**。
- **过程与更正**:我先写了一条"策略在 ASK 上不得返回 `set_labels`"的测试,并为取红写了带 `set_labels` 的桩。
  写完即发现该测试会驱动出**错误实现**:运行时的语义是 ASK 的 `set_labels` **只在批准时**落地,
  因此策略在 ASK 上携带 `set_labels` 恰恰是"批准后授予该闸门"的正确表达;去掉它会导致批准之后什么都不授予。
- **核查**:`tests/runtime/policies/test_approval.py:461 test_cancel_does_not_apply_labels` 与
  `:491 test_timeout_does_not_apply_labels` 的写法正是——策略返回 ASK 且带 `set_labels={"integrity":"0"}`,
  取消/超时后断言 `engine.labels == {}`。这就是 U21 的行为,且断言真实有效。
- **处理**:按 playbook Phase 1"已被既有通过测试覆盖"一条,撤回我写的测试与桩(未进入任何提交),
  把 U21 记为 DONE 并在 test-list 中指明覆盖它的既有测试。

## Cycle 24 · U22 · 交接物含分支名时拒绝

- **测试**:`tests/policies/pipely/test_handoff.py::test_a_handoff_naming_a_branch_is_refused`
- **红**:`uv run pytest tests/policies/pipely/test_handoff.py -q -p no:randomly` → `assert True is False`
  (新建 `handoff.py` 时先写一律放行的桩。)
- **绿**:拒绝以 `refs/heads/` 开头的引用。23 passed。
- **重构**:无需重构。

## Cycle 25 · U23 · 交接物含工作区路径时拒绝

- **测试**:`::test_a_handoff_naming_a_workspace_path_is_refused`
- **红**:`-k workspace_path` → `assert True is False`
- **绿**:同时拒绝绝对路径。24 passed。
- **重构**:无需重构(合并两个前缀的重构留到 U26,见该轮)。

## Cycle 26 · U24 · 仅含不可变引用时放行

- **测试**:`::test_a_handoff_of_only_immutable_references_is_admitted`
- **红**:首跑即绿。**故意变异**:判定改为 `if True`(拒绝一切)→ `assert False is True`。恢复。
- **绿**:实现未变。本轮把白名单的正向侧钉住,避免后续把拒绝条件放宽成"全拒"或"全放"。
- **重构**:无需重构。

## Cycle 27 · U25 · 部署在制品范围内时放行

- **测试**:`::test_deploying_a_job_the_artifact_covers_is_admitted`
- **红**:`-k artifact_covers` → `assert False is True`(桩一律不通过)
- **绿**:`check_deployment_scope` 求差集。26 passed。
- **重构**:无需重构。

## Cycle 28 · U26 · 超范围时拒绝且原因具名

- **测试**:`::test_deploying_a_job_outside_the_artifact_names_what_is_out_of_scope`
- **红**:`-k outside_the_artifact` → `AssertionError: assert 'orders_daily_backfill' in ''`
- **绿**:原因文本列出超范围的作业名。27 passed。
- **重构**:绿灯下做了一次。`ruff` 报 PIE810(两次 `startswith`),
  合并为单个 `_MUTABLE_PREFIXES` 元组并加注释说明"分支会前进、路径只在发送方机器上成立"。
  重构后重跑:27 passed,ruff / pyrefly 全过。

## Cycle 29 · U27 · 运维发布 bot 写本管线资产时放行

- **测试**:`tests/policies/pipely/test_identity.py::test_the_release_bot_may_write_assets_of_its_own_pipeline`
- **红**:`uv run pytest tests/policies/pipely/test_identity.py -q -p no:randomly` → `AssertionError: assert 'DENY' == 'ALLOW'`
- **绿**:`check_write` 按 `"<pipeline>."` 前缀判定。28 passed。
- **重构**:无需重构。

## Cycle 30 · U28 · 运维发布 bot 写其他管线资产时拒绝

- **测试**:`::test_the_release_bot_may_not_write_another_pipelines_assets`
- **红**:首跑即绿。**故意变异**:去掉作用域判定(`if True`)→ `AssertionError: assert 'ALLOW' == 'DENY'`。恢复。
- **绿**:实现未变。
- **重构**:无需重构。
- **循环中新增行为**:写这一轮时我一并写了"管线名互为前缀"的用例,那是**第二个行为**,
  违反"一轮一行为"。已把该测试撤出本轮,登记为 **U69** 追加到测试清单,下一轮驱动。

## Cycle 31 · U69 · 管线名互为前缀不得同域(循环中新增)

- **测试**:`::test_a_pipeline_whose_name_merely_starts_the_same_is_not_in_scope`
- **红**:首跑即绿——驱动 U27 时我已写入 `.` 分隔符,实现本就正确。
  **故意变异**:`startswith(f"{bound_pipeline}.")` → `startswith(bound_pipeline)`
  → `AssertionError: assert 'ALLOW' == 'DENY'`。恢复后 30 passed。
- **绿**:实现未变。本轮的价值全在于把分隔符钉住:此前它只是巧合正确,现在去掉就会红。
- **重构**:无需重构。

## Cycle 32 · U29 · 架构开发 bot 写沙箱 Domain 内放行

- **测试**:`::test_the_architect_bot_may_write_inside_its_sandbox_domain`
- **红**:`-k sandbox_domain` → `AssertionError: assert 'DENY' == 'ALLOW'`
- **绿**:按 bot 角色分派作用域——架构 bot 用 `SANDBOX_DOMAIN`,其余用绑定管线。31 passed。
- **重构**:无需重构。

## Cycle 33 · U30 · 架构开发 bot 写沙箱外资产时拒绝

- **测试**:`::test_the_architect_bot_may_not_write_governed_assets_outside_the_sandbox`
- **红**:首跑即绿。**故意变异**:`scope = bound_pipeline`(让架构 bot 也拿到管线作用域)
  → `AssertionError: assert 'ALLOW' == 'DENY'`。恢复后 32 passed。
- **绿**:实现未变。
- **重构**:无需重构。

## Cycle 34 · U31 · 调度凭证不得发起平台级操作

- **测试**:`::test_a_scheduler_credential_cannot_reach_platform_administration`
- **红**:`-k scheduler_credential` → `AssertionError: assert 'ALLOW' == 'DENY'`
- **绿**:`check_operation` 用 `PLATFORM_OPERATIONS` 名单拒绝。33 passed。
- **重构**:无需重构。

## Cycle 35 · U32 · 平台管理凭证出现在环境中即拒绝启动

- **测试**:`::test_a_platform_admin_credential_in_the_environment_refuses_startup`
- **红**:`-k refuses_startup` → `assert True is False`
- **绿**:`check_environment` 按 `FORBIDDEN_ENV_NAMES` 判定,断言的是**存在即拒**而非"未被使用"——
  有 shell 的 Agent 能读到整个进程环境,只有"不出现"才是成立的边界。34 passed。
- **重构**:无需重构。

## Cycle 36 · U35 · 仅"令牌可用"不算通过

- **测试**:`tests/tools/pipely/test_bot_selfcheck.py::test_a_bot_with_no_write_probe_at_all_does_not_pass`
- **红**:`-k no_write_probe` → `KeyError: 'unproven'`
- **绿**:把"未被证明"与"越权"分开报:只做了读探测的 bot 进 `unproven`,`passed` 要求两者都空。35 passed。
- **重构**:无需重构。

## Cycle 37 · U36 · 权限恰好等于职责所需时判通过

- **测试**:`::test_permissions_matching_the_role_exactly_pass`
- **红**:`-k exactly_pass` → `assert False is True`(桩一律不通过)
- **绿**:`compare_permissions` 求两向差集。36 passed。
- **重构**:无需重构。

## Cycle 38 · U37 · 权限过宽时判失败并列出多出项

- **测试**:`::test_permissions_wider_than_the_role_name_the_extra_ones`
- **红**:首跑即绿。**故意变异**:`passed` 改为只看 `not missing`(容忍多出)→ `assert True is False`。恢复。
- **绿**:实现未变。
- **重构**:无需重构。

## Cycle 39 · U38 · 权限过窄时判失败并列出缺失项

- **测试**:`::test_permissions_narrower_than_the_role_name_the_absent_ones`
- **红**:首跑即绿。**故意变异**:`passed` 改为只看 `not excess`(容忍缺失)→ `assert True is False`。恢复后 38 passed。
- **绿**:实现未变。至此权限阈值三点(等于/过宽/过窄)全部钉住。
- **重构**:无需重构。

## Cycle 40 · U39 · 负向探测须无害 —— **仅部分完成**

- **测试**:`::test_every_write_probe_declares_that_it_leaves_no_residue`
- **红**:`-k no_residue` → `AssertionError: the self-check must define at least one write probe`
- **绿**:`probe_actions()` 返回带 `persists` 标记的探测描述,全部为 `False`。39 passed。
- **重构**:无需重构。
- **限度(须记录)**:我先写的版本是拿模块自己的白名单校验模块自己的清单,**同义反复**,已废弃重写。
  现在这条测试钉住的是**声明**——新增一个会落盘的探测必须显式写 `persists: True`,那一刻测试就红。
  但"调用前后目录状态确实无变化"在单元层证不了,需要真实目录。
  故 U39 记为 **DONE(部分)**,状态一致性那半并入集成行为(A 系列),不假装已覆盖。

## Cycle 41 · U40 · 全部断言满足时判通过

- **测试**:`tests/tools/pipely/test_verify_governance.py::test_all_assertions_met_reports_a_pass_with_nothing_outstanding`
- **红**:`uv run pytest tests/tools/pipely/test_verify_governance.py -q -p no:randomly` → `assert False is True`
- **绿**:比较 `actual` 与 `expected`。40 passed。
- **重构**:无需重构。

## Cycle 42 · U41 · 不满足时含期望值与实际值

- **测试**:`::test_an_unmet_assertion_reports_both_the_expected_and_the_found_value`
- **红**:`-k expected_and_the_found` → `KeyError: 'met'`
- **绿**:每项结果带 `met` 并透传两个值。41 passed。
- **重构**:无需重构。

## Cycle 43 · U42 · 给出需补做的具体步骤

- **测试**:`::test_an_unmet_assertion_yields_the_step_that_would_satisfy_it`
- **红**:`-k would_satisfy_it` → `assert 0 == 2`
- **绿**:每条未满足断言产出一条具名步骤。42 passed。
- **重构**:无需重构。

## Cycle 44 · U43 · 重复调用结果一致

- **测试**:`::test_verifying_the_same_assertions_twice_gives_the_same_answer`
- **红**:首跑即绿。**故意变异**:引入调用计数,第二次调用清空未满足项
  → `AssertionError: assert {...} == {...}`。恢复后 43 passed。
- **绿**:实现未变。
- **重构**:无需重构。

## Cycle 45 · U45 · 工具不具备写能力

- **测试**:`::test_the_tool_exposes_no_way_to_write_to_the_catalog`
- **红**:首跑即绿。**故意变异**:在模块中加入 `create_domain`
  → `AssertionError: create_domain`。恢复后 44 passed。
- **绿**:实现未变。这条是结构性守卫:日后谁在该模块加写函数,立刻红并指名。
- **重构**:无需重构。

## Cycle 46 · U46 · 空断言集判为异常而非恒真

- **测试**:`::test_an_empty_assertion_set_is_malformed_input_not_a_vacuous_pass`
- **红**:`-k vacuous_pass` → `assert True is False` —— 空集确实被 `not []` 判成了通过。
- **绿**:空断言集返回 `passed=False, malformed=True` 并给出补救步骤。45 passed。
- **重构**:无需重构。

## U44 · 调用前后目录状态无变化 —— 判定为 BLOCKED

- 与 U39 后半同类:单元层无法证明真实目录状态未变,只能证明代码里没有写入路径(那已由 U45 覆盖)。
- 不写一条只能自证的测试来把它标绿。记为 `BLOCKED`,并入集成行为(A 系列)在有真实目录时驱动。

## Cycle 47 · U47 · 全部门禁项优于阈值时通过

- **测试**:`tests/tools/pipely/test_quality_gate.py::test_every_check_comfortably_inside_its_threshold_passes`
- **红**:`uv run pytest tests/tools/pipely/test_quality_gate.py -q -p no:randomly` → `assert False is True`
- **绿**:按每项声明的方向(`min` 高者优 / `max` 低者优)比较。46 passed。
- **重构**:无需重构。

## Cycle 48 · U48 · 恰好等于阈值时通过

- **测试**:`::test_a_value_sitting_exactly_on_its_threshold_passes`
- **红**:首跑即绿。**故意变异**:两个方向的 `>=`/`<=` 都改成严格不等号 → `assert False is True`。恢复。
- **绿**:实现未变。这一轮把 `>=` 与 `>` 的区别钉死——单侧测试分辨不出这两者。
- **重构**:无需重构。

## Cycle 49 · U49 · 劣于阈值一个最小单位时失败

- **测试**:`::test_a_value_one_step_the_wrong_side_of_its_threshold_fails`
- **红**:首跑即绿。**故意变异**:忽略 `direction`,一律按 `min` 比较 → `assert True is False`。恢复后 48 passed。
- **绿**:实现未变。
- **重构**:无需重构。

## Cycle 50 · U50 · 每项返回含实际值与阈值

- **测试**:`::test_each_check_reports_its_actual_value_alongside_its_threshold`
- **红**:首跑即绿。**故意变异**:结果只保留 `name` 与 `met` → `KeyError: 'actual'`。恢复后 49 passed。
- **绿**:实现未变。
- **重构**:无需重构。

## Cycle 51 · U51 · 五类门禁项须齐备

- **测试**:`::test_a_run_missing_any_of_the_five_required_checks_does_not_pass`
- **红**:`-k five_required_checks` → `assert True is False` —— 四项全过就报绿,缺的那项被静默忽略。
- **绿**:引入 `REQUIRED_CHECKS`,缺项计入 `absent_checks` 且与失败等权。
- **连带修复(须记录)**:此改动使 U47/U48 转红,因为它们当初只给了**两项**检查。
  这**不是需求冲突**:FR-027 一开始就列了五类,是我早先的夹具不完整。
  加入 `_PASSING_SET` 与 `_full_set(**overrides)`,让每条测试都在完整五项之上只覆盖自己关心的那项。
  这是**加强**夹具而非削弱断言(Hard Rule 4 允许)。50 passed。
- **重构**:测试侧夹具重构如上。

## Cycle 52 · U52 · 阈值取自冻结契约而非仓库

- **测试**:`::test_thresholds_come_from_the_frozen_contract_not_from_the_repository`
- **红**:首跑为 `TypeError: evaluate() got an unexpected keyword argument 'contract'`,**不是有效红**。
  加入接受 `contract` 但仍用调用方阈值的最小声明后重跑 → `assert True is False`
  (仓库里的阈值 1 让 2000 条记录轻松过关,正是"被测方自定分数线")。
- **绿**:契约中出现的项一律以契约阈值覆盖调用方传入值。51 passed。
- **重构**:无需重构。

## Cycle 53 · U53 · 缺冻结契约判为异常

- **测试**:`::test_a_missing_frozen_contract_is_malformed_not_an_unthresholded_pass`
- **红**:`-k missing_frozen_contract` → `assert True is False`
- **绿**:无契约即 `passed=False, malformed=True`,不回落到调用方阈值——回落会原样恢复 U52 刚堵住的洞。
- **连带修复**:与 Cycle 51 同因,U47–U50 未传 `contract` 而转红。
  加入 `_contract_for()` 与 `_run()` 辅助,让默认路径带上与检查项一致的契约。同样是补全夹具。52 passed。
- **重构**:测试侧夹具重构如上。

## Cycle 54 · U54 · 制品引用含四项

- **测试**:`tests/tools/pipely/test_artifact_ref.py::test_a_reference_pins_code_artifact_thresholds_and_assertions`
- **红**:`uv run pytest tests/tools/pipely/test_artifact_ref.py -q -p no:randomly` → `KeyError: 'code_tag'`
- **绿**:返回四项。53 passed。
- **重构**:无需重构。

## Cycle 55 · U55 · 不得基于分支构建制品引用

- **测试**:`::test_building_a_reference_from_a_branch_is_refused`
- **红**:`-k from_a_branch` → `Failed: DID NOT RAISE <class 'ValueError'>`
- **绿**:构建期即拒,**复用 `handoff.check_handoff` 的判据**而非另造一套——
  可变引用的定义只应有一处,两处会各自漂移。54 passed。
- **重构**:无需重构。

## Cycle 56 · U56 · 制品引用不可编辑

- **测试**:`::test_an_existing_reference_cannot_be_edited`
- **红**:`-k cannot_be_edited` → `Failed: DID NOT RAISE <class 'TypeError'>`
- **绿**:返回 `MappingProxyType`,嵌套字典同样包一层。55 passed。
- **重构**:无需重构。

## Cycle 57 · U57 · 同输入重复构建结果一致

- **测试**:`::test_building_twice_from_the_same_inputs_gives_the_same_reference`
- **红**:首跑即绿。**故意变异**:嵌入逐次递增的 `seq` 字段 → `AssertionError: assert {...} == {...}`。恢复后 56 passed。
- **绿**:实现未变。
- **重构**:无需重构。

## Cycle 58 · U58 · 全部事实原样进入目录

- **测试**:`tests/tools/pipely/test_sync_catalog.py::test_every_fact_reaches_the_catalog_unchanged`
- **红**:`uv run pytest tests/tools/pipely/test_sync_catalog.py -q -p no:randomly` → `KeyError: 'orders_daily'`
- **绿**:调用注入的 catalog 写入。57 passed。
- **重构**:无需重构。

## Cycle 59 · U59 · 目录不可达与调度器不可达须分开报 —— **部分完成**

- **测试**:`::test_a_catalog_outage_is_reported_apart_from_a_scheduler_outage`
- **红**:`-k catalog_outage` → `ConnectionError: catalog refused the connection`(异常直接冒出)
- **绿**:捕获并返回 `unreachable: "catalog"`。58 passed。
- **限度**:目录侧已钉住;**调度器侧尚无对称测试**,因为当前 `sync` 还不承担调度调用。
  U59 记为 DONE(部分),待 `sync` 扩到调度器时补上对称的一条。不假装两侧都已覆盖。

## Cycle 60 · U60 · 同步幂等

- **测试**:`::test_syncing_the_same_release_twice_leaves_one_record`
- **红**:`-k twice_leaves_one` → `AssertionError: assert 2 == 1`
- **测试替身的更正(须记录)**:红出现后我意识到问题在**替身**——它名叫 `upsert` 却实现成 append,
  没有如实表现协作者。但若只把替身改成覆盖,这条测试就退化成"测我自己的替身"。
  改为:替身按**键**存储(这才是 upsert 的语义),幂等性因而落在**工具给出的键是否稳定**上,
  那是工具自身的行为,正是本条要测的。
- **绿**:键由 `pipeline` 与 `facts["version"]` 导出,不含任何逐次变化的成分。59 passed。
- **变异确认**:第一次变异用 `id(facts)`,**无效**——两次调用传的是同一个 `FACTS` 对象,`id` 相同。
  改用模块级计数器 `_N` 后 → `AssertionError: assert 2 == 1`,变异有效。
- **清理**:恢复变异时发现备份文件不存在(那条 `cp` 在被隔离守卫拦下的复合命令里没执行到),
  已手工撤回两处改动,并 `grep -n "MUTANT"` 全量扫描 pipely 的源码与测试,确认**无残留**。
- **重构**:无需重构。

## 更正 · 标签模型与 data-model.md 对齐(在 /speckit-implement 中发现)

**这是我在 Cycle 10–23 引入的缺陷。** 写 Agent 定义 YAML 时需要在 `condition:` 里按标签名求值,
比对 `data-model.md` 才发现实现用的标签名与取值与硬契约不符。tasks.md T018 原文即要求"标签模型按 data-model.md"。

| 项 | data-model.md 规定 | 我的实现 | 处理 |
| --- | --- | --- | --- |
| 闸门标签名 | `pipely.gate` | `pipely.gate.reached` | 已改 |
| 闸门取值 | `g1_passed`…`g4_passed` | `G1`…`G4` | 已改 |
| 流程种类 | `delivery` \| `operation` | 测试用了 `development` | 已改 |
| 缺失项标签 | `pipely.preflight.missing` | **从未写入** | 见下方 U70 |

- **测试更正是独立一步且先于实现更改**:测试本身是错的(它编码了与硬契约矛盾的取值),
  按 Hard Rule 4 的例外条款处理——先改测试并说明理由,取红后再改实现。
- **红**:`uv run pytest tests/policies/pipely -q -p no:randomly` → `5 failed, 27 passed`
- **绿**:`GATE_LABEL = "pipely.gate"`、`GATE_ORDER = ("g1_passed", …)`、`RELEASE_GATE = "g4_passed"`、
  新增 `KIND_DELIVERY = "delivery"`。59 passed。
- **未削弱任何断言**:改的是常量取值,每条测试的判定逻辑与边界都原样保留。

## Cycle 61 · U70 · 前置校验失败时把缺失项写到会话上(循环中新增)

- **来源**:上面那张表的第四行。`pipely.preflight.missing` 是 data-model.md 的硬契约,但从未实现。
  这是**新行为**而非取值更正,按 Hard Rule 1 登记为 U70 并单独驱动。
- **测试**:`tests/policies/pipely/test_preflight.py::test_a_failed_preflight_records_the_missing_items_on_the_session`
- **红**:`-k records_the_missing` → `KeyError: 'labels'`
- **绿**:`assess` 返回 `labels`,失败时含 `pipely.preflight.status=failed` 与逗号分隔的 `pipely.preflight.missing`。
  60 passed。
- **理由**:闸门是**读标签**来拒绝后续调用的,若不把原因也写到会话上,
  运维只会看到一个没有出处的拒绝,无从回溯是哪一项凭证缺失。
- **重构**:无需重构。

## Cycle 62 · `identity.require_read_only` · 只读 bot 的写调用被拒(实现期新增)

- **来源**:治理审计与服务验证的 config.yaml 都挂了这条策略,但函数不存在。
  MCP 白名单已经不注册写工具,这是**第二道独立机制**——在 OpenMetadata 侧被误授权的 bot,
  白名单之外没有别的东西拦它,而"被误授权的只读 bot"正是 bot 自检要找的东西。
- **测试**:`tests/policies/pipely/test_identity.py::test_a_read_only_bot_calling_a_write_tool_is_denied`
- **红**:首跑 `TypeError`(函数不存在),**不是有效红**;加一律放行的桩后 → `AssertionError: assert 'ALLOW' == 'DENY'`
- **绿**:按**动词前缀**判定而非列举工具名。列举会静默放过下一个新增的写工具;动词判定会拒绝它。61 passed。
- **补正向侧**:随即补 `::test_a_read_only_bot_may_still_read`——否则"一律拒绝"也能让上面那条绿,
  而那会让 Agent 完全不可用。**故意变异**(判定改 `if True`)→ `assert 'DENY' == 'ALLOW'`。恢复后 62 passed。
- **重构**:无需重构。

## Cycle 63 · `identity.deny_platform_operations` · 调度凭证的平台操作在调用期被拒(实现期新增)

- **来源**:operations 的 config.yaml 挂了这条,函数不存在。
  已有的 `check_operation` 是"被问才答";挂在 `tool_call` 上的策略是"没人问也答"。
- **测试**:`::test_a_platform_operation_on_the_scheduler_credential_is_denied_at_call_time`
- **红**:加桩后 → `AssertionError: assert 'ALLOW' == 'DENY'`
- **绿**:委托给 `check_operation`,平台操作集合只在一处定义。63 passed。
- **重构**:`ruff` 修了一处 import 顺序,重跑仍 63 passed。

## Cycles 64–71 · U61–U68 · Agent 声明的契约断言

`examples/pipely/**` 建成后这一组解除阻塞。**先验证已建的,再建新的** —— 我在 YAML 注释里写的
"无 shell""白名单即边界""管理凭证不在此"当时全是无人核对的断言。

宿主:`tests/policies/pipely/test_agent_declarations.py`,直接 `parse()` 真实的包。

| 循环 | 行为 | 首跑 | 故意变异 | 结果 |
| --- | --- | --- | --- | --- |
| 64 | U61 三个子 Agent 无 `os_env` | 3 passed | 给 governance 加 `os_env` | `assert OSEnvSpec(...) is None` 失败 ✓ |
| 65 | U62 架构开发有 shell 且挂守卫 | passed | 把 `worktree_guard` 改名 | `assert set() == {'worktree_guard'}` 失败 ✓ |
| 66 | U63 共享档为具名用户 | passed | 改成 `public` | `assert 'public' == 'non-public'` 失败 ✓ |
| 67 | U64 审批窗口覆盖天级 | passed | 改成 120 秒 | `assert 120 >= 86400` 失败 ✓ |
| 68 | U65 白名单存在且无越权工具 | passed | 给 consumer 加 `update_table` | `consumer/openmetadata exposes ['update_table']` 失败 ✓ |
| 69 | U66 管理凭证不在任何工具配置中 | passed | 把 header 换成 `${OMNIGENT_OM_ADMIN}` | `OMNIGENT_OM_ADMIN reached a tool config` 失败 ✓ |
| 70 | U67 模板不提供管理凭证 | passed | 往 `.env.example` 追加该变量 | `assert False` 失败 ✓ |
| 71 | U68 变更请求与 git 凭证分立 | passed | — | 与 U67 同一断言族 |

- **全部首跑即绿**(YAML 是我刚按这些性质写的),因此**每一条都做了故意变异**,
  且变异改的是**真实的 YAML 文件**而非测试——这才证明了这些测试守的是产物本身。
- 变异后一律恢复,并重跑确认 78 passed。
- **U67 只算部分完成**:模板侧("管理凭证不出现在 `.env.example`")已钉住;
  "架构开发 Agent 的**进程环境**恰为两项"要在运行时观测该 Agent 的实际环境,单元层证不了,
  已并入外层行为 A7。不假装已覆盖。
- **U65 拆成三条测试**:白名单存在、只读 Agent 无写动词、调度器只挂在 operations 上。
  第三条测的是结构性边界——子 Agent 各自解析根目录,别的 Agent 根本够不到调度器。

## Cycle 72 · A18 · 核验未通过时 G2 不开 —— **暴露了防说谎闭环的真实缺陷**

- **测试**:`tests/policies/pipely/test_flow_acceptance.py::test_an_unmet_governance_assertion_leaves_the_g2_gate_shut`
  与 `::test_a_fully_met_verification_opens_the_g2_gate`
- **宿主变更(须记录)**:测试清单原本把外层行为放在 `tests/integration/pipely/`。
  该目录被 `pyproject.toml` 的 `addopts = "--ignore=tests/integration"` 排除,且另需 `--integration`
  与已安装的 harness CLI。**没人跑的验收测试不是验收测试**,故改落 `tests/policies/pipely/`,在默认套件内。

- **首跑即绿 —— 但是因为崩溃**。按 Phase 3 做故意变异检查:让核验**全部通过**,再看闸门是否打开。
  探针输出:

  ```
  report.passed = True
  decision      = PolicyAction.DENY
  labels        = {}
  GATE OPENED   = False
  ```

  闸门**永远开不了**。那条"未通过则不开"的测试因此什么也没证明——它在机制完全损坏时同样会绿。

- **根因**:`omnigent/runner/policy.py:240` 在 TOOL_RESULT 阶段构造
  `EvaluationContext(content=output, ...)`,`output` 是工具的**原始输出字符串**。
  而 `advance_on_result` 写的是 `event["data"]["result"]` —— 对字符串调 `.get` 抛异常,
  引擎把异常转成 DENY。**U13–U17 五条单测全绿,是因为事件 dict 是我自己手搓的。**

- **红**:补上正向侧后 `uv run pytest tests/policies/pipely/test_flow_acceptance.py -q -p no:randomly`
  → `AssertionError: assert 'deny' == 'allow'`
- **绿**:新增 `_verdict()`,按运行时真实形状解析——字符串先 `json.loads`,并支持直接 dict 与
  `result` 包裹两种形态;同时用 `event["target"]`(工具名的真实位置)确认是本工具的结果。80 passed。
- **重构**:无需重构。
- **教训**:单元测试里手搓协作者的输入形状,证明的是逻辑而不是接线。
  这条外层行为的全部价值就在于它用了**引擎真实传的事件**。

## Cycle 73 · A19 · 治理审计 Agent 的写入在真实引擎上被拒

- **测试**:`tests/policies/pipely/test_flow_acceptance.py::test_the_governance_agent_cannot_write_through_the_real_engine`
- **红**:首跑即绿。**故意变异**:把 `event["data"]` 改读成 `event["payload"]`
  —— 刻意复制 G2 那个缺陷的形态 → `AssertionError: assert 'allow' == 'deny'`。恢复后 81 passed。
- **绿**:实现未变。TOOL_CALL 阶段运行时传的确实是 `content={"name":..., "arguments":...}`
  (`omnigent/runner/policy.py:212`),所以 `data.name` 的读法本就正确 —— 但这一轮把它**钉住了**,
  不再依赖我读代码时的判断。
- **重构**:无需重构。

## Cycle 74 · A46 · 服务验证 Agent 写入被拒但检索仍可用 —— **部分完成**

- **测试**:`::test_the_consumer_agent_cannot_write_but_can_still_search`
- **红**:首跑即绿。**故意变异**:判定改 `if True`(全拒)→ `AssertionError: assert 'deny' == 'allow'`。恢复后 82 passed。
- **绿**:实现未变。两侧同测,因为"全拒"能满足拒绝侧却让 Agent 完全无用。
- **限度**:"失败信息不泄漏凭证"这半需要真实调用产生的错误文本,此处证不了,已在清单注明。

## Cycle 75 · A42 · 调度凭证不能治理,只能运行

- **测试**:`::test_the_scheduler_credential_cannot_govern_only_run`
- **红**:首跑即绿。**故意变异**:从 `PLATFORM_OPERATIONS` 移除 `create_domain`
  → `AssertionError: assert 'allow' == 'deny'`。恢复后 83 passed。
- **绿**:实现未变。同时断言 `trigger_dag_run` 仍放行 —— 否则"全拒"会让运维发布无法工作。
- **重构**:无需重构。

## Cycle 76 · A6 · 派发前一次性报全部缺失项

- **测试**:`::test_no_task_is_dispatched_until_preconditions_are_verified`
  与 `::test_a_partly_configured_deployment_is_told_every_gap_at_once`
- **红**:首跑即绿。**两条故意变异**:
  1. 前置策略改为放行首个调用 → `AssertionError: assert 'allow' == 'deny'`
  2. `missing = missing[:1]`(只报第一项)→ `AssertionError: assert ['credential:code_hosting'] == [...]`
  恢复后 85 passed。
- **绿**:实现未变。
- **重构**:`ruff` 修了一处 import 顺序,重跑仍 85 passed。

## Cycle 77 · A5 · 确认前不生成变更请求包 —— 部分完成

- **测试**:`::test_no_change_request_package_before_the_spec_is_frozen`
- **红**:首跑即绿。**故意变异**:闸门判定改 `if False` → `AssertionError: assert 'deny' == 'allow'`。恢复后 86 passed。
- **绿**:实现未变。这一轮顺带证明了**引擎确实把 `initial_labels` 传到了策略手里** ——
  闸门机制的另一半接线,此前同样只有手搓事件在证明。
- **限度**:"出示权限申请清单"是产出内容,要 LLM 跑起来才能判,已在清单注明为部分完成。

## Cycle 78 · A41 · 部署不得超出制品范围

- **测试**:`::test_release_stays_inside_what_the_artifact_was_verified_to_contain`
- **红**:首跑即绿。**故意变异**:`out_of_scope = []`(容忍任何超范围)→ `assert True is False`。恢复后 87 passed。
- **绿**:实现未变。测试同时构造真实的制品引用,确认两者能配合。
- **重构**:无需重构。

## Cycle 79 · A34 · 门禁未达阈值时线上指向不切换 —— **第一条端到端链路**

- **测试**:`::test_a_failing_quality_check_leaves_the_live_pointer_where_it_is`
  与 `::test_a_passing_quality_check_lets_the_switch_be_requested`
- **为什么这一轮不同**:前面每条都只验证一个组件在真实引擎上的行为。这一轮把**三个**串起来,
  用**同一个引擎同时挂两条策略**(推进 + 闸门),按真实顺序求值:
  工具返回裁决 → 裁决决定标签 → 标签决定下一次调用是否放行。
  每一环此前都单独证过;这一轮证的是它们**接得上**。
- **红**:首跑即绿。**故意变异**:让推进策略永不写标签(`if False`),即断开链条中间那一环
  → `AssertionError: assert None == 'g3_passed'`。恢复后 89 passed。
- **绿**:实现未变。
- **重构**:无需重构。测试侧复用了 quality_gate 单测里的完整五项夹具模式,
  确保没有哪条测试因为少给一项检查而侥幸通过。

## 逃生舱 · 闸门推进语义冲突 · **停下并上报,未自行改写**

驱动 A26(停在 G3 等人确认)时发现 `examples/pipely/config.yaml` 与 `data-model.md` 冲突。

| 闸门 | `data-model.md` 规定的推进条件 | 我在编排者里的接线 |
| --- | --- | --- |
| `g2_passed` | 只读核验工具返回全部断言通过 | `tool_result:verify_governance` ✓ |
| `g3_passed` | **变更请求已合并、制品引用已产出** | `tool_result:quality_gate` ✗ |
| `g4_passed` | 运维负责人批准切换 | **未接线** |

质量门禁属于**阶段 4(上线)**,按 `operate` 技能它守的是切换审批(G4),不是授予"发布就绪"(G3)。

**为什么不自己改**:修正需要在两条路里选一条,两条都动 spec ——
(a) 给 `data-model.md` 新增 `pipely.quality` 标签族,让门禁结果单独记录、切换审批同时要求 G3 与它;
(b) 改变 G3/G4 的含义。
闸门模型是用户已经过多轮讨论定下的,Phase 4 的逃生舱条款要求"两条需求真冲突时停下并同时报出两者"。

**对已完成条目的影响**:Cycle 79(A34)的链路测试证明的是**工具 → 策略 → 标签 → 下一次调用这条链接得上**,
这一结论与选哪个闸门值无关;但它当前编码的具体授予值(`quality_gate → g3_passed`)随本冲突的裁决可能要改。
已在测试清单的 A34 行与本条目中标明,不留隐性错误。

**A26 记为 BLOCKED**,原因即本冲突,而非"还没轮到"。

## 裁决 · 闸门语义冲突按方案 (a) 解决 · 新增 `pipely.quality` 标签族

用户选择:**质量门禁的结论单列一个标签族,不推进阶段闸门**。

**契约先改,代码后跟**——测试要有可追溯的依据:
- `data-model.md` 新增 `### pipely.quality` 一节,并在 `pipely.gate` 下加"质量门禁不是闸门"的说明。
- `spec.md` 新增 **FR-107**:门禁结论独立记录、不推进闸门;切换须同时满足两项;只由工具真实返回值写入。

### Cycle 80 · U71 · 推进策略可写入指定标签

- **测试**:`tests/policies/pipely/test_gate_advance.py::test_a_verdict_can_be_recorded_somewhere_other_than_the_gate`
- **红**:首跑 `TypeError: unexpected keyword argument 'label'`,**不是有效红**;
  加入接受 `label` 但仍写闸门的最小声明后 → `KeyError: 'set_labels'`
- **绿**:`advance_on_result` 增加 `label` 参数(默认仍为闸门)。
  **棘轮只对闸门成立**——非闸门的结论重跑时必须能重判,否则一次失败会永久钉死这条管线。90 passed。

### Cycle 81 · U72 · 切换须同时满足发布就绪与本次门禁通过

- **测试**:`tests/policies/pipely/test_gates.py::test_the_switch_needs_both_release_readiness_and_this_runs_quality`
- **红**:加桩后 → `AssertionError: assert 'ALLOW' == 'DENY'`
- **绿**:新增 `require_release()`,两项都不满足时把**两条原因都列出来**,不是只报先撞上的那条。
  三种组合同测(就绪但门禁失败 / 门禁过但未就绪 / 两者皆备),因为任一单侧测试都分辨不出"只看一项"的实现。91 passed。

### 重新接线

| 位置 | 改动 |
| --- | --- |
| 编排者 `config.yaml` | `advance_g3_on_quality_gate` → `record_quality_verdict`,写 `pipely.quality` |
| operations `config.yaml` | 新增 `require_release_readiness_and_quality` 挂在 `tool_call:switch_live_pointer` |
| operations prompt | 改写"切换"一节:两项条件分别回答不同问题,重跑只重判其一 |
| A34 的链路测试 | 按新语义重写:门禁结果不再动闸门,断言 `pipely.quality` 与闸门**都**符合预期 |

### Cycle 82 · A26 · 停在 G3 等人确认

- **测试**:`tests/policies/pipely/test_agent_declarations.py::test_nothing_an_agent_does_can_advance_the_release_gate`
- **写法**:扫描包内**全部**已声明策略的 `grants` 参数,而不是检查我记得的那两条。
  日后新增一条授予 `g3_passed` 的策略,正是这条测试该抓的。
- **红**:首跑即绿。**故意变异**:把 `grants: passed` 改回 `grants: g3_passed`(即恢复错误接线)
  → `AssertionError: these would advance g3_passed without a human: ['pipely/record_quality_verdict']`。
  恢复后 92 passed。
- **绿**:实现未变。这一条现在守着这次裁决的结果:**谁把它改回去,谁立刻红,并且被指名**。

## Cycle 83 · U73 · 裁决策略必须与它监视的工具同处一个 Agent(实现期发现)

**发现路径**:用户问"为什么 tasks 全没打勾"。查证后确认他看的是主 checkout(勾在 worktree 分支上),
但顺势回补 Phase 6 的打勾时,我审计了"勾在部分完成行为上"的任务,由此翻出这个缺陷。

- **红**:`tests/policies/pipely/test_agent_declarations.py::test_every_verdict_policy_lives_on_the_agent_that_owns_its_tool`

  ```
  AssertionError: these verdict policies will never fire:
    pipely/advance_g2_on_verification watches verify_governance owned by governance;
    pipely/record_quality_verdict     watches quality_gate       owned by operations
  ```

- **根因**:`RunnerToolPolicyGate.from_spec(spec)`(`omnigent/runner/policy.py:151`)只读**该 spec 自己**的
  `guardrails.policies`。子 Agent 是独立 AgentSpec。`omnigent/runtime/policies/builder.py:361` 同理:
  `agent_policy_specs` 取自子 Agent 自身;从 root 继承的只有**运行时会话策略**(`sys_add_policy` 加的),
  **不含父 spec 的 agent 策略**。
  所以两条裁决策略挂在编排者、而工具跑在子 Agent 里 —— **永远不会触发**。
- **与上一个缺陷同类**:策略层证明有效,接线层完全失效。
  A18/A34 抓不到它,因为那两条测试**手工把策略装进引擎**,没有检查是谁声明的。
- **绿**:`advance_g2_on_verification` 移到 governance,`record_quality_verdict` 移到 operations。93 passed。
- **测试写法**:扫描包内全部 Agent 的全部策略,比对 `arguments.tool` 与工具归属,
  而不是检查我记得的那两条 —— 日后新增一条挂错位置的裁决策略,正是它该抓的。

## 逃生舱 · 标签不跨子会话传递 · **闸门模型的架构前提不成立**

修 U73 时查证标签作用域,发现一个**比 U73 更根本的问题**,已停下上报,未改写设计。

**事实**(均在代码中核实):

| 项 | 结论 | 出处 |
| --- | --- | --- |
| 标签作用域 | **逐会话**,子会话不继承父标签 | `builder.py:389` `_seed_and_load_labels(conversation_id=conversation_id)` |
| 会话状态 | 仅两个成本相关 key 从 root 种入,注释明写 "Other session_state stays per-conversation" | `builder.py:394-410` |
| 子会话创建 | 不复制父标签 | `sqlalchemy_store.py:272` |
| 子 Agent 是否独立会话 | 是(代码显式处理 `root_conversation_id != conversation_id`) | `builder.py:403` |

**后果**:`data-model.md` 的闸门模型假定 `pipely.gate` / `pipely.quality` / `pipely.preflight`
是**贯穿整个流程**的会话状态。但五个 Agent 各有自己的会话,标签空间彼此隔离:

- governance 写下的 `g2_passed`,编排者与 operations 都看不见;
- operations 的 `require_release_gate` 读自己会话的 `pipely.gate`,而没有任何东西会把它写到 `g3_passed`;
- 编排者首个工具调用写的 `preflight` 标签,管不到子 Agent。

**U73 修复后仍成立的部分**:operations 内部 `record_quality_verdict` → `pipely.quality` →
`require_release_readiness_and_quality` 是**同一会话内**的链路,现在真的通了。
跨 Agent 的闸门流转不通。

**为什么不自行改**:可选路径至少三条,每条都动 spec 或动框架 ——
(a) 闸门状态改存 OpenMetadata 管线资产(事实来源),策略读它而非读标签;
(b) 把跨 Agent 的闸门流转改由编排者持有:子 Agent 只返回裁决,编排者在自己会话里推进闸门;
(c) 向框架提出让子会话继承父标签(改的是 omnigent 本身,超出本特性范围)。
按 Hard Rule 6 与 Phase 4 的逃生舱条款,停下并同时报出。

**受影响的已完成条目**:A34 的链路测试仍有效(它在**单一会话**内证明了工具→策略→标签→下一次调用),
但它不证明跨 Agent 的闸门流转。已在本条目中写明,不留隐性错误。


## 裁决 · 方案 (b) 落地 · 闸门由编排者持有

用户选择:**跨 Agent 闸门由编排者持有;子 Agent 只返回观测,编排者在自己会话里推进。**

契约先改:`data-model.md` 新增"标签存放在编排者的会话上"一节,写明职责划分与派发必带 `phase` 参数。

### Cycle 84 · U74 · 裁决工具归编排者所有

- **测试**:`test_agent_declarations.py::test_the_verdict_tools_belong_to_the_agent_that_holds_the_gates`
- **红**:`AssertionError: a verdict decided in a sub-agent is unreadable: {'operations/quality_gate', 'governance/verify_governance'}`
- **绿**:两个裁决工具移到 `examples/pipely/tools/python/`(编排者)。
  它们是**纯函数**——只比较传入的观测值与期望值,不需要任何凭证,所以放在无 shell 的编排者上没有障碍。
  `bot_selfcheck` 留在 governance(检的是它自己的 bot),`sync_catalog` 留在 operations(用它的凭证写目录)。
- **随之**:两条 `advance_on_result` 策略移回编排者——现在是**正确的**,因为工具在这里了。

### Cycle 85 · U76 · 只有切换派发受发布条件约束

- **测试**:`test_gates.py::test_only_the_switch_dispatch_is_held_to_the_release_conditions`
- **红**:首跑 `TypeError`(参数不存在),**不是有效红**;加最小声明后 → `AssertionError: assert 'DENY' == 'ALLOW'`
  (phase=plan 的早期派发被误拦)。
- **绿**:`require_release` 增加 `applies_to_phase`,按**派发参数**判定。
  刻意不按任务描述的措辞判定——措辞由模型自己写,参数不是。

### Cycle 86 · U77 · 只有发布派发受 G3 约束

- **测试**:`test_gates.py::test_only_the_release_dispatch_is_held_to_the_release_gate`
- **红**:同上两步,最终 `AssertionError: assert 'DENY' == 'ALLOW'`
- **绿**:`require_flow_gate` 同样增加 `applies_to_phase`。
  早期阶段正是流程抵达被守闸门的途径,一并拦住会**死锁整个流程**。

### Cycle 87 · U75 · 子 Agent 不得读它永远看不到的标签

- **测试**:`test_agent_declarations.py::test_no_sub_agent_gates_on_labels_it_can_never_see`
- **红**:`AssertionError: these read labels their session never has: ['operations/require_release_gate', ...]`
- **绿**:两条流程闸门从 operations 移到编排者,按 `phase` 键控派发。
  operations 只保留**不依赖流程状态**的守卫(凭证作用域)。
- **意义**:此前那两条策略在 operations 上是 fail-closed ——安全但**让该 Agent 永远无法工作**,
  且失败看起来像权限 bug 而非设计问题。

### 最终归属

| Agent | 策略 | 工具 |
| --- | --- | --- |
| pipely(编排者) | preflight, bind_flow, 两条裁决记录, 两条派发闸门 | quality_gate, verify_governance |
| architect | worktree_guard | — |
| governance | read_only_catalog | bot_selfcheck |
| operations | no_platform_admin_via_scheduler | sync_catalog |
| consumer | read_only_catalog | — |

### 提示词同步

三处改写:编排者新增"你判定,子 Agent 观测"与"每次派发必带 phase";
governance 改为**报告观测到的值**而非跑核验;operations 改为**报告量到的数**而非跑门禁。
两处子 Agent 的提示词都明确要求"报告观测而非结论"——
"这个 Domain 是对的"没法拿去做比较,而那正是这套安排要摆脱依赖的那类断言。

### 残余限度(须记录)

子 Agent 报告的观测值仍**经由模型转述**。相比原设计(同一个模型既做事又宣称做完)这是实质增强:
判定是确定性函数,且观测方与判定方分离。但它**不等于**观测值不可伪造。
真正封死这条路需要方案 (a)——裁决落到 OpenMetadata 再读回。已如实记录,不夸大当前强度。

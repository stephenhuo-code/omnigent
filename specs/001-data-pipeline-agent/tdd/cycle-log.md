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

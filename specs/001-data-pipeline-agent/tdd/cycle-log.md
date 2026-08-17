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

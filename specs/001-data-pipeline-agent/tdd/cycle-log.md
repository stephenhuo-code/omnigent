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

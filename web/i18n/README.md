# 界面中文化 (build-time UI translation)

把 Omnigent 的界面译成中文，**不修改 `web/src` 里的任何一行代码**。

翻译发生在构建期：一个 Vite 插件解析每个源文件的 AST，把词表里命中的英文串替换成中文。源码保持英文，因此

- 从上游 rebase 时 `web/src` 不产生冲突；
- 现有的 5000+ 条前端测试断言的仍是英文，无需改动，也照常跑过；
- 想看英文版，不设环境变量重新构建即可，无需回滚代码。

## 构建中文版

```bash
cd web
OMNIGENT_UI_LANG=zh-CN pnpm build            # 主应用
OMNIGENT_UI_LANG=zh-CN pnpm run build:overlay # 桌面端更新浮层
```

不设 `OMNIGENT_UI_LANG` 就是原版英文。开发模式同理：`OMNIGENT_UI_LANG=zh-CN pnpm dev`。

## 词表结构 (`zh-CN.json`)

替换是否安全，取决于字符串**所处的 AST 位置**而不是它长什么样。词表按位置分成五个桶：

| 桶            | 键              | 说明                                                                                                                                          |
| ------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `jsxText`     | 英文原文        | 独立的 JSX 文本节点。按定义就是渲染出来的文案，全局按原文匹配即安全。                                                                         |
| `attr`        | 英文原文        | 白名单内的 JSX 属性（`placeholder` / `aria-label` / `title` …）。同样是面向用户的文案。                                                       |
| `jsxFragment` | 元素形状        | 被 `{expr}` 或子标签打断的句子。键形如 `{} needs Codex authentication on {} — run <code/> on that machine.`，值是按顺序给每个文本片段的译文。 |
| `template`    | 文件 → 模板形状 | 模板字符串，文案分布在 head 和各插值之后。键形如 `Worked for ${}s`。                                                                          |
| `literal`     | 文件 → 英文原文 | 其余普通字符串字面量。**位置不能证明它是 UI**（API 字段名和按钮文案长得一模一样），所以必须按文件限定并人工筛选。                             |

`jsxFragment` / `template` 的值数组里，`null` 表示该片段保持英文。

### 关于间距

`jsxText` 替换的是**修剪后**的范围（首尾空白只是缩进）；`jsxFragment` / `template` 替换的是**整个片段**，因此译文要自带间距——中文挨着拉丁文占位符时留一个空格，句号前不留。

## 日常维护

上游更新后：

```bash
cd web
node scripts/extract-ui-strings.ts --json /tmp/strings.json   # 重新扫描 src/
OMNIGENT_UI_LANG=zh-CN OMNIGENT_UI_LANG_REPORT=1 pnpm build   # 列出未命中的词条
node scripts/audit-ui-strings.mjs i18n/zh-CN.json             # 检查危险词条
```

- **构建报告**：每次构建都打印 `N/M 条词条命中`。`OMNIGENT_UI_LANG_REPORT=1` 会额外列出未命中的词条——要么是上游改了原文（需更新词表），要么是该模块不在本次构建的依赖图里（overlay / embed 各自只拉取 `src/` 的一部分，属正常）。
- **风险审计**：`audit-ui-strings.mjs` 用 AST 找出被 `===`、`switch`、`.includes()`、对象键等**用于比较而非显示**的词条。翻译这类字符串会改变程序行为。逐条确认后，把确实安全的记入 `audit-allowlist.json` 并写明理由；审计只会再报**新**出现的风险。

### 已知的取舍

- `shell/Sidebar.tsx` 的 `"Pinned"` / `"Projects"` / `"Chats"` **故意不翻译**：它们是侧边栏分区的身份标识，会持久化进 localStorage 并用 `.includes()` 匹配。可见表头走的是 `title` 属性（attr 桶），所以界面照样是中文，而折叠状态在中英文之间切换时不会失效。
- 发给智能体的文本不翻译：`lib/composerMentions.ts` 的 `[Attached file: …]`、`lib/designModePrompt.ts`、`lib/agentBundle.ts` 生成的 YAML。翻译它们会改变模型的输入。
- 插值位由变量提供英文动词的句子不翻译（例如 `Failed to ${action} … conversations`），否则会渲染成中英混杂。

## 不受此机制覆盖的部分

`web/electron/src/` 是 Electron 主进程，**没有打包器**（`package.json` 里只有 `electron .` 和 `electron-builder`），插件无法介入，因此菜单栏、系统弹窗和 `setup/` `overlay/` `find/` 三个本地页面是**直接改的源码**。这部分约 100 条，上游改动频率远低于 `web/src`。

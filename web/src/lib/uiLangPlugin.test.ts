import { describe, expect, it } from "vitest";

import { type Dictionary, planEdits, seenKey } from "../../plugins/vite-plugin-ui-lang";

const dict = (over: Partial<Dictionary> = {}): Dictionary => ({
  jsxText: {},
  attr: {},
  literal: {},
  jsxFragment: {},
  template: {},
  ...over,
});

/** Apply a plan the way the plugin does, so tests assert on final source. */
function render(source: string, rel: string, d: Dictionary): string {
  let out = source;
  for (const e of [...planEdits(source, rel, d)].sort((a, b) => b.start - a.start)) {
    out = out.slice(0, e.start) + e.text + out.slice(e.end);
  }
  return out;
}

describe("planEdits", () => {
  it("replaces a JSX text node", () => {
    const src = `const a = <span className="truncate">More</span>;`;
    const out = render(src, "x.tsx", dict({ jsxText: { More: "更多" } }));
    expect(out).toBe(`const a = <span className="truncate">更多</span>;`);
  });

  it("keeps surrounding whitespace when the text node spans lines", () => {
    const src = ["<div>", "  Loading models…", "</div>"].join("\n");
    const out = render(src, "x.tsx", dict({ jsxText: { "Loading models…": "正在加载模型…" } }));
    expect(out).toBe(["<div>", "  正在加载模型…", "</div>"].join("\n"));
  });

  it("matches a JSX text node on its whitespace-collapsed form", () => {
    const src = ["<p>", "  Name can use letters", "  and numbers.", "</p>"].join("\n");
    const d = dict({ jsxText: { "Name can use letters and numbers.": "名称可使用字母和数字。" } });
    expect(render(src, "x.tsx", d)).toContain("名称可使用字母和数字。");
  });

  it("replaces whitelisted JSX attributes only", () => {
    const src = `<input placeholder="Attach files" data-x="Attach files" />`;
    const out = render(src, "x.tsx", dict({ attr: { "Attach files": "附加文件" } }));
    expect(out).toBe(`<input placeholder="附加文件" data-x="Attach files" />`);
  });

  it("escapes quotes in an attribute translation", () => {
    const src = `<input title="Repo" />`;
    const out = render(src, "x.tsx", dict({ attr: { Repo: `仓库"名"` } }));
    expect(out).toBe(`<input title="仓库\\"名\\"" />`);
  });

  it("replaces a bare string literal only in its own file", () => {
    const src = `const label = "binary missing";`;
    const d = dict({ literal: { "lib/harnessSetup.ts": { "binary missing": "缺少可执行文件" } } });
    expect(render(src, "lib/harnessSetup.ts", d)).toBe(`const label = "缺少可执行文件";`);
    expect(render(src, "lib/other.ts", d)).toBe(src);
  });

  it("leaves import and export specifiers alone", () => {
    const src = `import x from "More";\nexport * from "More";`;
    const d = dict({ literal: { "x.ts": { More: "更多" } } });
    expect(render(src, "x.ts", d)).toBe(src);
  });

  it("does not touch a JSX attribute via the literal bucket", () => {
    const src = `<a href="Docs">Docs</a>`;
    const d = dict({ literal: { "x.tsx": { Docs: "文档" } } });
    expect(render(src, "x.tsx", d)).toBe(src);
  });

  it("returns no edits when nothing matches", () => {
    expect(planEdits(`<span>Untranslated</span>`, "x.tsx", dict())).toEqual([]);
  });

  it("reports which dictionary entries were used", () => {
    const seen = new Set<string>();
    planEdits(
      `<span>More</span>`,
      "x.tsx",
      dict({ jsxText: { More: "更多", Less: "更少" } }),
      seen,
    );
    expect(seen.has(seenKey("jsxText", "More"))).toBe(true);
    expect(seen.has(seenKey("jsxText", "Less"))).toBe(false);
  });

  it("translates a sentence split by interpolations, run by run", () => {
    const src =
      "const a = <>{agent} needs Codex authentication on {host} — run <code>codex login</code> on that machine.</>;";
    const key = "{} needs Codex authentication on {} — run <code/> on that machine.";
    const out = render(
      src,
      "x.tsx",
      dict({
        jsxFragment: {
          [key]: [" 需要在 ", " 上完成 Codex 认证 —— 请在该机器上运行 ", "。"],
        },
      }),
    );
    expect(out).toBe(
      "const a = <>{agent} 需要在 {host} 上完成 Codex 认证 —— 请在该机器上运行 <code>codex login</code>。</>;",
    );
  });

  it("leaves a run alone when its entry is null", () => {
    const src = "<p>Error: {msg} now</p>";
    const key = "Error: {} now";
    const out = render(src, "x.tsx", dict({ jsxFragment: { [key]: ["错误: ", null] } }));
    expect(out).toBe("<p>错误: {msg} now</p>");
  });

  it("ignores whitespace-only runs when building the key", () => {
    const src = ["<p>", "  Next run", "  {when}", "</p>"].join("\n");
    const out = render(src, "x.tsx", dict({ jsxFragment: { "Next run {}": ["下次运行"] } }));
    expect(out).toContain("下次运行");
  });

  it("lets a translation drop the English spacing around an interpolation", () => {
    const src = "<p>Delete {n} session(s)?</p>";
    const out = render(
      src,
      "x.tsx",
      dict({ jsxFragment: { "Delete {} session(s)?": ["确定删除 ", " 个会话吗？"] } }),
    );
    expect(out).toBe("<p>确定删除 {n} 个会话吗？</p>");
  });

  it("does not let the jsxText bucket touch a run already claimed by jsxFragment", () => {
    const src = "<p>Remove {name} now</p>";
    const out = render(
      src,
      "x.tsx",
      dict({
        jsxFragment: { "Remove {} now": ["移除", null] },
        jsxText: { Remove: "删除" },
      }),
    );
    expect(out).toBe("<p>移除{name} now</p>");
  });

  it("does not match an element whose shape differs", () => {
    const src = "<p>Error: {msg}</p>";
    const d = dict({ jsxFragment: { "Error: {} now": ["错误:"] } });
    expect(planEdits(src, "x.tsx", d)).toEqual([]);
  });

  it("translates a template literal chunk by chunk", () => {
    const src = "const t = `Worked for ${secs}s`;";
    const d = dict({ template: { "x.ts": { "Worked for ${}s": ["已处理 ", " 秒"] } } });
    expect(render(src, "x.ts", d)).toBe("const t = `已处理 ${secs} 秒`;");
  });

  it("keys templates per file", () => {
    const src = "const t = `Error: ${e}`;";
    const d = dict({ template: { "a.ts": { "Error: ${}": ["错误: "] } } });
    expect(render(src, "a.ts", d)).toBe("const t = `错误: ${e}`;");
    expect(render(src, "b.ts", d)).toBe(src);
  });

  it("handles a template whose head is empty", () => {
    const src = "const t = `${n} files changed`;";
    const d = dict({ template: { "x.ts": { "${} files changed": [null, " 个文件已更改"] } } });
    expect(render(src, "x.ts", d)).toBe("const t = `${n} 个文件已更改`;");
  });

  it("escapes backticks, backslashes, and interpolation openers", () => {
    const src = "const t = `Run ${cmd} now`;";
    const d = dict({ template: { "x.ts": { "Run ${} now": ["跑 `a\\b` ${x} "] } } });
    // The spliced chunk must stay inert text, not close the literal or open a
    // second interpolation.
    expect(render(src, "x.ts", d)).toBe("const t = `跑 \\`a\\\\b\\` \\${x} ${cmd} now`;");
  });

  it("leaves a template with more than three spans intact across chunks", () => {
    const src = "const t = `${a} of ${b} / ${c} done`;";
    const d = dict({
      template: { "x.ts": { "${} of ${} / ${} done": [null, " / ", " / ", " 完成"] } },
    });
    expect(render(src, "x.ts", d)).toBe("const t = `${a} / ${b} / ${c} 完成`;");
  });

  it("applies several edits in one file without corrupting offsets", () => {
    const src = `<div><span>More</span><input placeholder="Search" /><span>Less</span></div>`;
    const out = render(
      src,
      "x.tsx",
      dict({ jsxText: { More: "更多", Less: "更少" }, attr: { Search: "搜索" } }),
    );
    expect(out).toBe(`<div><span>更多</span><input placeholder="搜索" /><span>更少</span></div>`);
  });
});

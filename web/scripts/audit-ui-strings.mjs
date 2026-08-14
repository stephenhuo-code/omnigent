// Flag dictionary entries that are unsafe to translate.
//
// The `literal` bucket is the risky one: an ordinary string literal can be a
// button label or a value the code compares against. Translating the latter
// silently changes behaviour, so this audit reports any literal whose AST
// position shows it being *tested* rather than *displayed*:
//
//   x === "Default"        switch (x) { case "Default": }
//   list.includes("Plan")  set.has("Plan")   x.indexOf("Auto")
//   { "Plan": … }          obj["Plan"]
//
// Run after editing i18n/<lang>.json. A non-empty report means either the entry
// must be dropped, or the surrounding code genuinely uses it only for display
// and the finding can be dismissed after reading it.
//
// Usage:  node scripts/audit-ui-strings.mjs i18n/zh-CN.json

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "../src");

const COMPARISON_OPS = new Set([
  ts.SyntaxKind.EqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken,
]);

const LOOKUP_METHODS = new Set([
  "includes",
  "has",
  "indexOf",
  "lastIndexOf",
  "get",
  "startsWith",
  "endsWith",
]);

/** Why this literal looks like data rather than prose, or null if it looks fine. */
function riskOf(node, sf) {
  const parent = node.parent;
  if (!parent) return null;

  if (ts.isBinaryExpression(parent) && COMPARISON_OPS.has(parent.operatorToken.kind)) {
    return `compared with ${parent.operatorToken.getText(sf)}`;
  }
  if (ts.isCaseClause(parent)) return "switch case label";
  if (ts.isCallExpression(parent) && ts.isPropertyAccessExpression(parent.expression)) {
    const method = parent.expression.name.getText(sf);
    if (LOOKUP_METHODS.has(method) && parent.arguments.includes(node))
      return `argument to .${method}()`;
  }
  if (ts.isPropertyAssignment(parent) && parent.name === node) return "object key";
  if (ts.isElementAccessExpression(parent) && parent.argumentExpression === node)
    return "index into object";
  if (ts.isComputedPropertyName(parent)) return "computed property name";
  return null;
}

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(e.name) && !/\.test\./.test(e.name) && !/\.d\.ts$/.test(e.name))
      out.push(p);
  }
  return out;
}

const dictPath = process.argv[2] ?? path.resolve(HERE, "../i18n/zh-CN.json");
const dict = JSON.parse(fs.readFileSync(dictPath, "utf8"));
const literal = dict.literal ?? {};

// Findings already read and judged safe. Keyed "<file> <string>" so a *new*
// risky use of an already-cleared string still reports (the line moves, the key
// does not). Each entry records why it is safe.
const allowPath = path.resolve(path.dirname(dictPath), "audit-allowlist.json");
const allow = fs.existsSync(allowPath) ? JSON.parse(fs.readFileSync(allowPath, "utf8")) : {};
const allowKey = (rel, text) => `${rel} ${JSON.stringify(text)}`;

const findings = [];
for (const file of walk(SRC)) {
  const rel = path.relative(SRC, file).replaceAll("\\", "/");
  const wanted = literal[rel];
  if (!wanted) continue;
  const source = fs.readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

  const visit = (node) => {
    if (
      ts.isStringLiteral(node) &&
      Object.hasOwn(wanted, node.text.trim()) &&
      wanted[node.text.trim()]
    ) {
      const risk = riskOf(node, sf);
      if (risk && !Object.hasOwn(allow, allowKey(rel, node.text.trim()))) {
        findings.push({
          rel,
          line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1,
          text: node.text.trim(),
          risk,
        });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
}

if (findings.length === 0) {
  console.log("审计通过: 没有词条被用于比较、switch 或查表。");
} else {
  console.log(`发现 ${findings.length} 处高风险词条 —— 逐条确认或从词表中删除:\n`);
  for (const f of findings)
    console.log(`  ${f.rel}:${f.line}  ${JSON.stringify(f.text)}  <- ${f.risk}`);
  process.exitCode = 1;
}

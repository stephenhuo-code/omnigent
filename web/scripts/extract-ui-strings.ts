// Extract translatable UI strings from web/src into a dictionary skeleton.
//
// Buckets mirror `vite-plugin-ui-lang.ts` exactly — it consumes what this
// emits, and shares `ATTR_ALLOW` / `fragmentShape` with it so the two can't
// drift:
//
//   jsxText      a standalone JSX text node — rendered prose by definition, so
//                keying on the text alone is safe everywhere.
//   attr         a whitelisted JSX attribute. Also rendered prose.
//   jsxFragment  a sentence broken across several text nodes by `{expr}` or a
//                nested tag. Keyed by the element's whole shape, valued by one
//                string per text run.
//   literal      any other string literal. Position proves nothing here (an API
//                field name and a button label look identical), so these are
//                keyed per file and must be curated by hand.
//
//   template     a template literal, whose prose splits across the head and each
//                span. Keyed per file by the template's shape, for the same
//                reason as `literal`.
//
// Run with node directly (native TS type stripping):
//   node scripts/extract-ui-strings.ts [--json out.json]

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";

import { ATTR_ALLOW, fragmentShape, templateShape } from "../plugins/vite-plugin-ui-lang.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "../src");

/** Keyboard event `key` values — names of physical keys, never shown as prose. */
const KEY_NAMES = new Set([
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "Enter",
  "Escape",
  "Tab",
  "Backspace",
  "Delete",
  "Shift",
  "Control",
  "Meta",
  "Alt",
  "Home",
  "End",
  "PageUp",
  "PageDown",
  "Space",
]);

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    // Test fixtures are not shipped UI; translating them would only add
    // dictionary entries that never render.
    if (entry.isDirectory()) {
      if (entry.name !== "__fixtures__" && entry.name !== "__mocks__") walk(p, out);
    } else if (
      /\.tsx?$/.test(entry.name) &&
      !/\.test\./.test(entry.name) &&
      !/\.d\.ts$/.test(entry.name)
    )
      out.push(p);
  }
  return out.sort();
}

/** Reject strings that are plainly machine-facing rather than prose. */
export function humanish(raw: string): boolean {
  const t = raw.trim();
  if (t.length < 2) return false;
  if (!/[A-Za-z]/.test(t)) return false;
  if (/^(https?:|wss?:|\/|\.\/|\.\.\/|~\/|#|data:|blob:|@\/|@[a-z-]+\/)/.test(t)) return false;
  if (/^[a-z0-9_.-]+$/.test(t)) return false; // identifier / kebab / dotted key
  if (/^[A-Z0-9_]+$/.test(t)) return false; // CONST_CASE
  if (/^[a-z][a-z0-9]*([A-Z][a-z0-9]*)+$/.test(t)) return false; // camelCase
  if (/^[a-z][a-z0-9]*(\/[a-z0-9.*-]+)+$/i.test(t)) return false; // module / mime path
  const tokens = t.split(/\s+/);
  if (tokens.length >= 2 && tokens.every((x) => /^[a-z0-9:[\]/.\-%()_,#!]+$/.test(x))) {
    // All-lowercase is not enough to call something a class list: "binary
    // missing" and "needs auth" are badge copy. Real Tailwind carries class
    // grammar — a dash, colon, bracket, or slash — in most of its tokens.
    const classy = tokens.filter((x) => /[-:[\]/]/.test(x)).length;
    if (classy / tokens.length >= 0.5) return false;
  }
  return true;
}

/**
 * Reject machine-facing strings that survive {@link humanish} but only ever
 * appear in the bare-literal bucket: CSS, DOM selectors, storage keys, inlined
 * scripts. Applied to `literal` alone — a JSX text node holding "Enter" really
 * is prose.
 */
export function literalNoise(raw: string): boolean {
  const t = raw.trim();
  if (KEY_NAMES.has(t)) return true;
  if (/^\[?data-/.test(t) || t.includes("[data-")) return true; // DOM selector
  if (/^(calc|var|rgb|hsl|oklch|clamp|translate|url|linear-gradient|radial-gradient)\(/.test(t))
    return true; // CSS function
  if (/^use (client|strict|server)$/.test(t)) return true; // module directive
  if (/\b\d+m?s\b/.test(t) && /\b(ease|linear|cubic-bezier|steps|infinite|alternate)\b/.test(t))
    return true; // CSS transition / animation shorthand
  if (t.includes("--omnigent-")) return true; // CSS custom property
  if (/^omnigent[:.]/.test(t)) return true; // storage key
  if (/^[a-z-]+\/$/.test(t)) return true; // MIME prefix, e.g. "image/"
  if (/^(sm|md|lg|xl|2xl|max-sm|max-md|max-lg):/.test(t)) return true; // tailwind variant
  if (/^[a-z][a-z0-9-]*(:[a-z0-9[\]/.,%-]+)+$/.test(t)) return true; // tailwind utility
  if (/^[A-Za-z-]+\/[A-Za-z0-9.+-]+$/.test(t)) return true; // MIME / header value
  if (/^\[[^\]]+\]$/.test(t)) return true; // bracketed selector or log tag
  if (/^[a-z]+, ?[a-z]+(, ?[a-z[])/.test(t)) return true; // selector list
  if (/^\[[A-Za-z][\w-]*\]/.test(t)) return true; // console tag, e.g. "[BrowserPane] …"
  if (/^[A-Z][a-z0-9]+([A-Z][a-z0-9]*)+$/.test(t)) return true; // PascalCase identifier
  if (/^[Mm][\d\s.,-]+[A-Za-z][\d\s.,-]/.test(t)) return true; // SVG path data
  if ([...t].some((ch) => ch.charCodeAt(0) < 32)) return true; // escape sequence
  if (t.length > 400) return true; // inlined script, not a label
  if (/=>|\bfunction\b|\bdocument\.|\bwindow\.|\breturn\b/.test(t) && /[;{}()]/.test(t))
    return true;

  // A Tailwind class list: mostly class-shaped tokens and no sentence ending.
  const tokens = t.split(/\s+/);
  if (tokens.length >= 4 && !/[.!?。！？]$/.test(t)) {
    const classy = tokens.filter((x) => /[[\]:/&*]/.test(x) || /^[a-z0-9-]+$/.test(x)).length;
    if (classy / tokens.length >= 0.8) return true;
  }
  return false;
}

export function extract() {
  const jsxText = new Map<string, number>();
  const attr = new Map<string, number>();
  const jsxFragment = new Map<string, string[]>();
  const literal = new Map<string, Map<string, number>>();
  const template = new Map<string, Map<string, string[]>>();

  const bump = (map: Map<string, number>, text: string) => map.set(text, (map.get(text) ?? 0) + 1);

  for (const file of walk(SRC)) {
    const source = fs.readFileSync(file, "utf8");
    const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const rel = path.relative(SRC, file).replaceAll("\\", "/");
    const claimed = new Set<ts.JsxText>();

    const visit = (node: ts.Node): void => {
      // Whole-element shapes first, so their runs are not also offered as
      // standalone jsxText entries (the plugin resolves them the same way).
      if (ts.isJsxElement(node) || ts.isJsxFragment(node)) {
        const shape = fragmentShape(node.children, sf);
        // Only a shape with a non-text part is a *broken* sentence; an element
        // holding one plain run is the ordinary jsxText case.
        if (shape && /\{\}|<[^>]*\/>/.test(shape.key)) {
          const prose = shape.runs.filter((r) => humanish(r.text.replace(/\s+/g, " ").trim()));
          if (prose.length > 0) {
            jsxFragment.set(
              shape.key,
              shape.runs.map((r) => r.text.replace(/\s+/g, " ").trim()),
            );
            for (const r of shape.runs) claimed.add(r);
          }
        }
      }

      if (ts.isJsxText(node) && !claimed.has(node)) {
        const text = node.text.replace(/\s+/g, " ").trim();
        if (humanish(text)) bump(jsxText, text);
      }

      if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
        if (ATTR_ALLOW.has(node.name.getText(sf))) {
          const text = node.initializer.text.trim();
          if (humanish(text)) bump(attr, text);
        }
      }

      if (
        (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
        !(node.parent && ts.isJsxAttribute(node.parent)) &&
        !(node.parent && ts.isImportDeclaration(node.parent)) &&
        !(node.parent && ts.isExportDeclaration(node.parent)) &&
        !(node.parent && ts.isImportTypeNode(node.parent))
      ) {
        const text = node.text.trim();
        if (humanish(text) && !literalNoise(text)) {
          const perFile = literal.get(rel) ?? new Map<string, number>();
          perFile.set(text, (perFile.get(text) ?? 0) + 1);
          literal.set(rel, perFile);
        }
      }

      if (ts.isTemplateExpression(node)) {
        const head = node.head.text;
        const tails = node.templateSpans.map((s) => s.literal.text);
        const chunks = [head, ...tails];
        // Inside a template, a chunk that hugs an interpolation with a space is
        // sentence text even when it is a single lowercase word (` goal`) —
        // unlike `:user` or `?limit=1`, which carry no space and are structure.
        const adjacentProse = (c: string) => /^\s|\s$/.test(c) && /[A-Za-z]{2}/.test(c);
        const prose = chunks.filter((c) => (humanish(c) || adjacentProse(c)) && !literalNoise(c));
        if (prose.length > 0) {
          const perFile = template.get(rel) ?? new Map<string, string[]>();
          perFile.set(templateShape(node), chunks);
          template.set(rel, perFile);
        }
      }

      ts.forEachChild(node, visit);
    };
    visit(sf);
  }

  return { jsxText, attr, jsxFragment, literal, template };
}

function main() {
  const { jsxText, attr, jsxFragment, literal, template } = extract();
  const outIdx = process.argv.indexOf("--json");

  const skeleton = {
    jsxText: Object.fromEntries([...jsxText.keys()].sort().map((t) => [t, null])),
    attr: Object.fromEntries([...attr.keys()].sort().map((t) => [t, null])),
    jsxFragment: Object.fromEntries([...jsxFragment].sort(([a], [b]) => a.localeCompare(b))),
    literal: Object.fromEntries(
      [...literal]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([rel, m]) => [rel, Object.fromEntries([...m.keys()].sort().map((t) => [t, null]))]),
    ),
    template: Object.fromEntries(
      [...template]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([rel, m]) => [
          rel,
          Object.fromEntries([...m].sort(([a], [b]) => a.localeCompare(b))),
        ]),
    ),
  };

  const literalCount = [...literal.values()].reduce((n, m) => n + m.size, 0);
  console.log(`jsxText     ${jsxText.size} 条`);
  console.log(`attr        ${attr.size} 条`);
  console.log(
    `jsxFragment ${jsxFragment.size} 组 (断裂句子，含 ${[...jsxFragment.values()].reduce((n, r) => n + r.length, 0)} 个片段)`,
  );
  console.log(`literal     ${literalCount} 条 (${literal.size} 文件) — 需人工筛选`);
  const templateCount = [...template.values()].reduce((n, m) => n + m.size, 0);
  console.log(`template    ${templateCount} 组模板串 (${template.size} 文件) — 需人工筛选`);

  const out = outIdx !== -1 ? process.argv[outIdx + 1] : undefined;
  if (out) {
    fs.writeFileSync(out, JSON.stringify({ skeleton }, null, 2) + "\n");
    console.log(`\n已写入 ${out}`);
  }
}

main();

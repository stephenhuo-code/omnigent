// Build-time UI translation.
//
// Swaps English source strings for a target language while leaving `src/`
// untouched, so this fork stays rebasable against upstream. Off unless
// `OMNIGENT_UI_LANG` names a dictionary in `i18n/` — the default build, and
// every vitest run, still sees the original English.
//
// Replacement is driven by the AST position a string occupies, not by the
// string's shape, because position is what makes it safe:
//
//   jsxText      — a JSX text node is rendered prose by definition, so keying
//                  on the text alone is safe everywhere.
//   attr         — a whitelisted JSX attribute is rendered/announced prose.
//   jsxFragment  — a sentence broken across text nodes by `{expr}` or a nested
//                  tag. Keyed by the element's whole shape, one value per run.
//   template     — a template literal, split across its head and each span.
//                  Keyed per file, like `literal`.
//   literal      — anything else. Position proves nothing (an API field name
//                  and a button label are both `"input"`), so keyed per file
//                  and curated by hand, with `scripts/audit-ui-strings.mjs`
//                  flagging any entry the code compares rather than displays.
//
// Between them these cover every string `src/` renders, which is the point:
// nothing under `src/` is edited, so the fork rebases cleanly and the English
// test suite keeps passing unchanged.

import fs from "node:fs";
import path from "node:path";

import ts from "typescript";
import type { Plugin } from "vite";

/** JSX attributes whose string value reaches the user as prose. */
export const ATTR_ALLOW: ReadonlySet<string> = new Set([
  "placeholder",
  "title",
  "aria-label",
  "aria-description",
  "aria-placeholder",
  "alt",
  "label",
  "description",
  "tooltip",
  "emptyMessage",
  "heading",
  "subtitle",
  "confirmLabel",
  "cancelLabel",
  "actionLabel",
  "summary",
]);

export interface Dictionary {
  jsxText: Record<string, string>;
  attr: Record<string, string>;
  /** Keyed by path relative to `src/`, then by source string. */
  literal: Record<string, Record<string, string>>;
  /**
   * Sentences broken across several JSX text nodes by `{expr}` or a nested tag,
   * which no single-string swap can express. Keyed by the element's whole shape
   * — text runs verbatim, `{}` per expression, `<tag/>` per child element — so
   * the key is unambiguous. The value supplies one replacement per text run, in
   * order; `null` leaves that run alone.
   *
   * Chinese keeps the same subject-then-object order as English in these
   * sentences, so the interpolations stay where they are and only the prose
   * between them moves. A sentence that genuinely needs the placeholders
   * reordered is not expressible here and needs a source edit.
   */
  jsxFragment: Record<string, (string | null)[]>;
  /**
   * Template literals, whose prose is split across the head and each span's
   * trailing chunk. Same idea as {@link Dictionary.jsxFragment} — keyed by the
   * template's shape (`Worked for ${}s`), valued by one replacement per chunk —
   * but keyed per file as well, because a shape like `${}: ${}` says nothing
   * about whether it builds a label or a cache key.
   */
  template: Record<string, Record<string, (string | null)[]>>;
}

interface Edit {
  start: number;
  end: number;
  text: string;
}

/**
 * Load and validate a dictionary.
 *
 * `null` values mark entries left untranslated by the extractor; they are
 * dropped rather than treated as an empty translation. JSX text is spliced in
 * raw, so a value containing JSX punctuation would produce invalid syntax —
 * that is a build error, not something to silently paper over.
 */
export function loadDictionary(file: string): Dictionary {
  const raw = JSON.parse(fs.readFileSync(file, "utf8")) as Partial<Dictionary>;
  const clean = (o: Record<string, string | null> | undefined): Record<string, string> =>
    Object.fromEntries(
      Object.entries(o ?? {}).filter(([, v]) => typeof v === "string" && v !== ""),
    ) as Record<string, string>;

  const dict: Dictionary = {
    jsxText: clean(raw.jsxText as Record<string, string | null>),
    attr: clean(raw.attr as Record<string, string | null>),
    literal: Object.fromEntries(
      Object.entries(raw.literal ?? {}).map(([rel, entries]) => [
        rel,
        clean(entries as Record<string, string | null>),
      ]),
    ),
    jsxFragment: Object.fromEntries(
      Object.entries(raw.jsxFragment ?? {}).filter(([, runs]) => Array.isArray(runs)),
    ),
    template: raw.template ?? {},
  };

  const jsxSafe = (en: string, zh: string, where: string) => {
    if (/[{}<>]/.test(zh)) {
      throw new Error(
        `i18n: ${where} translation for ${JSON.stringify(en)} contains JSX punctuation: ${zh}`,
      );
    }
  };
  for (const [en, zh] of Object.entries(dict.jsxText)) jsxSafe(en, zh, "jsxText");
  for (const [en, runs] of Object.entries(dict.jsxFragment)) {
    for (const zh of runs) if (typeof zh === "string") jsxSafe(en, zh, "jsxFragment");
  }
  return dict;
}

/**
 * The shape of a JSX element's children, used as the `jsxFragment` key.
 *
 * Whitespace-only text between tags is layout, not prose, so it is skipped and
 * never occupies a slot — that keeps the key stable against reformatting.
 * Returns `null` when the element holds no prose worth translating.
 */
export function fragmentShape(
  children: readonly ts.JsxChild[],
  sf: ts.SourceFile,
): { key: string; runs: ts.JsxText[] } | null {
  const parts: string[] = [];
  const runs: ts.JsxText[] = [];
  for (const child of children) {
    if (ts.isJsxText(child)) {
      const text = child.text.replace(/\s+/g, " ").trim();
      if (!text) continue;
      parts.push(text);
      runs.push(child);
    } else if (ts.isJsxExpression(child)) {
      parts.push("{}");
    } else if (ts.isJsxElement(child)) {
      parts.push(`<${child.openingElement.tagName.getText(sf)}/>`);
    } else if (ts.isJsxSelfClosingElement(child)) {
      parts.push(`<${child.tagName.getText(sf)}/>`);
    } else if (ts.isJsxFragment(child)) {
      parts.push("<></>");
    }
  }
  if (runs.length === 0) return null;
  return { key: parts.join(" "), runs };
}

/**
 * Key for the "which entries were used" set. JSON-encodes the pair rather than
 * joining on a separator, so a bucket or source string containing the
 * separator can't collide with a different pair.
 */
export function seenKey(bucket: string, key: string): string {
  return JSON.stringify([bucket, key]);
}

/**
 * The shape of a template literal, used as the `template` key: the prose chunks
 * with `${}` standing in for each interpolation.
 */
export function templateShape(node: ts.TemplateExpression): string {
  return node.head.text + node.templateSpans.map((s) => "${}" + s.literal.text).join("");
}

/**
 * Text ranges of a template literal's prose chunks, in shape order.
 *
 * A chunk is bounded by the delimiters around it — a backtick or `}` before,
 * a `${` or backtick after — so the range covers the text and nothing else.
 */
function templateChunkRanges(node: ts.TemplateExpression): [number, number][] {
  const ranges: [number, number][] = [];
  // head: `...${   → skip the opening backtick, stop before "${"
  ranges.push([node.head.getStart() + 1, node.head.getEnd() - 2]);
  for (const span of node.templateSpans) {
    const lit = span.literal;
    // each span literal: }...${  or  }...`  → skip the closing brace, stop
    // before the next "${" or the final backtick
    const tail = ts.isTemplateTail(lit) ? 1 : 2;
    ranges.push([lit.getStart() + 1, lit.getEnd() - tail]);
  }
  return ranges;
}

/** Byte range of the trimmed content inside a JSX text node. */
function trimmedRange(source: string, start: number, end: number): [number, number] | null {
  let s = start;
  let e = end;
  while (s < e && /\s/.test(source[s]!)) s += 1;
  while (e > s && /\s/.test(source[e - 1]!)) e -= 1;
  return e > s ? [s, e] : null;
}

/** Collect every replacement this dictionary implies for one source file. */
export function planEdits(
  source: string,
  rel: string,
  dict: Dictionary,
  seen?: Set<string>,
): Edit[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const perFile = dict.literal[rel] ?? {};
  const edits: Edit[] = [];
  const mark = (bucket: string, key: string) => seen?.add(seenKey(bucket, key));
  // Text runs already rewritten as part of a whole-element translation. The
  // parent is visited before its children, so claiming here reliably stops the
  // single-string jsxText branch from touching the same run twice.
  const claimed = new Set<ts.JsxText>();

  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node) || ts.isJsxFragment(node)) {
      const shape = fragmentShape(node.children, sf);
      const runs = shape && dict.jsxFragment[shape.key];
      if (shape && runs) {
        // Unlike the standalone jsxText bucket, the whole run is replaced —
        // surrounding whitespace included. In a broken sentence the spacing
        // around each interpolation is part of the translation (Chinese wants a
        // space beside a Latin name but none before a full stop), so the
        // dictionary has to own it rather than inherit the English spacing.
        shape.runs.forEach((run, i) => {
          const zh = runs[i];
          if (typeof zh !== "string" || zh === "") return;
          // `pos`, not `getStart()`: for a JSX text run the leading whitespace
          // is reported as trivia and getStart() skips past it, which would
          // leave the English spacing in place next to the new text.
          edits.push({ start: run.pos, end: run.end, text: zh });
          claimed.add(run);
        });
        mark("jsxFragment", shape.key);
      }
    }

    if (ts.isJsxText(node) && !claimed.has(node)) {
      const collapsed = node.text.replace(/\s+/g, " ").trim();
      const zh = dict.jsxText[collapsed];
      if (zh) {
        const span = trimmedRange(source, node.getStart(sf), node.getEnd());
        if (span) {
          edits.push({ start: span[0], end: span[1], text: zh });
          mark("jsxText", collapsed);
        }
      }
    }

    if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
      const name = node.name.getText(sf);
      if (ATTR_ALLOW.has(name)) {
        const zh = dict.attr[node.initializer.text.trim()];
        if (zh) {
          edits.push({
            start: node.initializer.getStart(sf),
            end: node.initializer.getEnd(),
            text: JSON.stringify(zh),
          });
          mark("attr", node.initializer.text.trim());
        }
      }
    }

    if (
      (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
      !(node.parent && ts.isJsxAttribute(node.parent)) &&
      !(node.parent && ts.isImportDeclaration(node.parent)) &&
      !(node.parent && ts.isExportDeclaration(node.parent))
    ) {
      const zh = perFile[node.text.trim()];
      if (zh) {
        edits.push({ start: node.getStart(sf), end: node.getEnd(), text: JSON.stringify(zh) });
        mark(`literal:${rel}`, node.text.trim());
      }
    }

    if (ts.isTemplateExpression(node)) {
      const chunks = dict.template[rel]?.[templateShape(node)];
      if (chunks) {
        const ranges = templateChunkRanges(node);
        chunks.forEach((zh, i) => {
          const range = ranges[i];
          if (typeof zh !== "string" || !range) return;
          edits.push({ start: range[0], end: range[1], text: escapeTemplateChunk(zh) });
        });
        mark(`template:${rel}`, templateShape(node));
      }
    }

    ts.forEachChild(node, visit);
  };
  visit(sf);
  return edits;
}

/**
 * Make a translation safe to splice into a template literal: a backtick,
 * backslash, or `${` would otherwise end the literal or open an interpolation.
 */
function escapeTemplateChunk(text: string): string {
  return text.replaceAll("\\", "\\\\").replaceAll("`", "\\`").replaceAll("${", "\\${");
}

function applyEdits(source: string, edits: Edit[]): string {
  // Apply back-to-front so earlier offsets stay valid. Nested nodes cannot
  // both match (a JSX text node holds no string literal), so ranges are
  // disjoint and a simple sort suffices.
  let out = source;
  for (const e of [...edits].sort((a, b) => b.start - a.start)) {
    out = out.slice(0, e.start) + e.text + out.slice(e.end);
  }
  return out;
}

export interface UiLangOptions {
  /** Directory holding `<lang>.json`. Defaults to `<root>/i18n`. */
  dir?: string;
  /** Language to build. Defaults to `process.env.OMNIGENT_UI_LANG`. */
  lang?: string;
  /** Absolute path to the source root the `literal` keys are relative to. */
  srcRoot?: string;
}

/**
 * Translate `src/` at build time.
 *
 * Runs with `enforce: "pre"` so it sees raw TSX, before the React plugin
 * rewrites JSX into function calls and the text nodes stop being text nodes.
 *
 * Source maps are dropped for edited files: a translated bundle is a
 * deliverable, not a debugging target, and the untranslated default build —
 * which is what anyone debugging runs — keeps its maps intact.
 */
export function uiLang(options: UiLangOptions = {}): Plugin {
  const lang = options.lang ?? process.env.OMNIGENT_UI_LANG ?? "";
  let dict: Dictionary | null = null;
  let srcRoot = options.srcRoot ?? "";
  const seen = new Set<string>();
  let filesTouched = 0;

  return {
    name: "omnigent-ui-lang",
    enforce: "pre",

    configResolved(config) {
      if (!lang) return;
      const dir = options.dir ?? path.resolve(config.root, "i18n");
      const file = path.join(dir, `${lang}.json`);
      if (!fs.existsSync(file)) {
        throw new Error(`OMNIGENT_UI_LANG=${lang} but no dictionary at ${file}`);
      }
      dict = loadDictionary(file);
      srcRoot = srcRoot || path.resolve(config.root, "src");
      config.logger.info(`[ui-lang] ${lang}: 翻译已启用 (${path.relative(config.root, file)})`);
    },

    transform(code, id) {
      if (!dict) return null;
      const file = id.split("?")[0]!;
      if (!/\.tsx?$/.test(file) || /\.test\./.test(file)) return null;
      const rel = path.relative(srcRoot, file).replaceAll("\\", "/");
      if (rel.startsWith("..") || path.isAbsolute(rel)) return null;

      const edits = planEdits(code, rel, dict, seen);
      if (edits.length === 0) return null;
      filesTouched += 1;
      return { code: applyEdits(code, edits), map: null };
    },

    buildEnd() {
      if (!dict) return;
      // An entry that never matched means the source string moved on without
      // the dictionary, OR its module simply isn't in this build's graph (the
      // overlay and embed entries each pull in a different subset). Surfacing
      // the list is what makes the dictionary maintainable across rebases — a
      // silent miss just renders English again.
      const total =
        Object.keys(dict.jsxText).length +
        Object.keys(dict.attr).length +
        Object.keys(dict.jsxFragment).length +
        Object.values(dict.literal).reduce((n, m) => n + Object.keys(m).length, 0) +
        Object.values(dict.template).reduce((n, m) => n + Object.keys(m).length, 0);
      const stale: string[] = [];
      for (const k of Object.keys(dict.jsxText))
        if (!seen.has(seenKey("jsxText", k))) stale.push(`jsxText: ${k}`);
      for (const k of Object.keys(dict.attr))
        if (!seen.has(seenKey("attr", k))) stale.push(`attr: ${k}`);
      for (const k of Object.keys(dict.jsxFragment)) {
        if (!seen.has(seenKey("jsxFragment", k))) stale.push(`jsxFragment: ${k}`);
      }
      for (const [rel, m] of Object.entries(dict.literal)) {
        for (const k of Object.keys(m)) {
          if (!seen.has(seenKey(`literal:${rel}`, k))) stale.push(`literal ${rel}: ${k}`);
        }
      }
      for (const [rel, m] of Object.entries(dict.template)) {
        for (const k of Object.keys(m)) {
          if (!seen.has(seenKey(`template:${rel}`, k))) stale.push(`template ${rel}: ${k}`);
        }
      }

      this.info(
        `[ui-lang] ${total - stale.length}/${total} 条词条命中，覆盖 ${filesTouched} 个文件`,
      );
      // The per-entry list is opt-in: every entry point pulls in a different
      // slice of src/, so the small islands would otherwise warn about ~1300
      // "misses" on every build and train the reader to ignore it. Set
      // OMNIGENT_UI_LANG_REPORT=1 after a rebase, when the list is the point.
      if (stale.length > 0 && process.env.OMNIGENT_UI_LANG_REPORT === "1") {
        this.warn(
          `[ui-lang] ${stale.length} 条词条未命中（原文已改动，或该模块不在本次构建的依赖图中）:\n  ` +
            stale.slice(0, 40).join("\n  ") +
            (stale.length > 40 ? `\n  … 另有 ${stale.length - 40} 条` : ""),
        );
      }
    },
  };
}

export default uiLang;

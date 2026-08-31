#!/usr/bin/env node
/**
 * Additive dark-mode codemod.
 *
 * Appends `dark:` counterparts next to hardcoded light-mode Tailwind classes.
 * Existing classes are never rewritten or removed, so light mode renders
 * exactly as before. Running the script repeatedly is a no-op because a token
 * is skipped when its `dark:` counterpart already exists in the same class list.
 *
 *   node scripts/darkModeCodemod.js --check      report only, exit 1 if work remains
 *   node scripts/darkModeCodemod.js              apply changes
 *   node scripts/darkModeCodemod.js src/foo.jsx  restrict to given paths
 */

const fs = require('fs');
const path = require('path');
const { parse } = require('@babel/parser');

const SRC_ROOT = path.resolve(__dirname, '..', 'src');

/**
 * Printed, emailed and receipt surfaces stay light in both themes so the screen
 * matches the paper/email output. These are never given `dark:` variants.
 */
const PAPER_FILES = [
  'components/reports/PayinTransactionReceiptView.jsx',
  'components/reports/payinReceiptPrint.js',
  'components/reports/payinReceiptFields.js',
  'components/bbps/BbpsTransactionReceiptView.jsx',
  'components/bbps/bbpsReceiptPrint.js',
  'components/bbps/bbpsReceiptFields.js',
  'components/bbps/BAssuredReceiptHeader.jsx',
  'components/bbps/BbpsPartnerLogos.jsx',
  'components/admin/GmailHtmlEditor.jsx',
];

/** Chromatic families whose tinted surfaces need a dark counterpart. */
const TINTS = [
  'red', 'rose', 'orange', 'amber', 'yellow', 'lime', 'green', 'emerald',
  'teal', 'cyan', 'sky', 'blue', 'indigo', 'violet', 'purple', 'fuchsia', 'pink',
];

const NEUTRALS = ['gray', 'slate', 'zinc', 'neutral', 'stone'];

function buildMappings() {
  const map = new Map();
  const add = (light, dark) => {
    if (!map.has(light)) map.set(light, dark);
  };

  // --- Surfaces -----------------------------------------------------------
  add('bg-white', 'dark:bg-slate-900');
  for (const n of NEUTRALS) {
    add(`bg-${n}-50`, 'dark:bg-slate-800/50');
    add(`bg-${n}-100`, 'dark:bg-slate-800');
    add(`bg-${n}-200`, 'dark:bg-slate-700');
    add(`bg-${n}-300`, 'dark:bg-slate-600');
  }

  // --- Text ---------------------------------------------------------------
  for (const n of NEUTRALS) {
    add(`text-${n}-950`, 'dark:text-slate-100');
    add(`text-${n}-900`, 'dark:text-slate-100');
    add(`text-${n}-800`, 'dark:text-slate-200');
    add(`text-${n}-700`, 'dark:text-slate-300');
    add(`text-${n}-600`, 'dark:text-slate-400');
    add(`text-${n}-500`, 'dark:text-slate-400');
    add(`text-${n}-400`, 'dark:text-slate-500');
  }

  // --- Borders, dividers, rings -------------------------------------------
  for (const n of NEUTRALS) {
    add(`border-${n}-100`, 'dark:border-slate-800');
    add(`border-${n}-200`, 'dark:border-slate-700');
    add(`border-${n}-300`, 'dark:border-slate-600');
    add(`divide-${n}-100`, 'dark:divide-slate-800');
    add(`divide-${n}-200`, 'dark:divide-slate-700');
    add(`divide-${n}-300`, 'dark:divide-slate-600');
    add(`ring-${n}-100`, 'dark:ring-slate-800');
    add(`ring-${n}-200`, 'dark:ring-slate-700');
    add(`ring-${n}-300`, 'dark:ring-slate-600');
  }

  // --- Hover / focus neutrals ---------------------------------------------
  add('hover:bg-white', 'dark:hover:bg-slate-900');
  for (const n of NEUTRALS) {
    add(`hover:bg-${n}-50`, 'dark:hover:bg-slate-800');
    add(`hover:bg-${n}-100`, 'dark:hover:bg-slate-700');
    add(`hover:bg-${n}-200`, 'dark:hover:bg-slate-700');
    add(`hover:bg-${n}-300`, 'dark:hover:bg-slate-600');
    add(`hover:text-${n}-900`, 'dark:hover:text-slate-100');
    add(`hover:text-${n}-800`, 'dark:hover:text-slate-200');
    add(`hover:text-${n}-700`, 'dark:hover:text-slate-300');
    add(`hover:text-${n}-600`, 'dark:hover:text-slate-400');
    add(`hover:border-${n}-200`, 'dark:hover:border-slate-700');
    add(`hover:border-${n}-300`, 'dark:hover:border-slate-600');
  }

  // --- Gradient stops -----------------------------------------------------
  // Light gradients stay light unless their stops are mapped, which is how an
  // active nav item ends up as pale blue text on a pale blue background.
  for (const stop of ['from', 'via', 'to']) {
    for (const n of NEUTRALS) {
      add(`${stop}-${n}-50`, `dark:${stop}-slate-900`);
      add(`${stop}-${n}-100`, `dark:${stop}-slate-800`);
      add(`${stop}-white`, `dark:${stop}-slate-900`);
    }
    for (const c of TINTS) {
      add(`${stop}-${c}-50`, `dark:${stop}-${c}-950/40`);
      add(`${stop}-${c}-100`, `dark:${stop}-${c}-900/40`);
    }
  }

  // --- Disabled / placeholder states --------------------------------------
  for (const n of NEUTRALS) {
    add(`disabled:bg-${n}-50`, 'dark:disabled:bg-slate-800/50');
    add(`disabled:bg-${n}-100`, 'dark:disabled:bg-slate-800');
    add(`disabled:bg-${n}-200`, 'dark:disabled:bg-slate-700');
    add(`disabled:text-${n}-400`, 'dark:disabled:text-slate-500');
    add(`disabled:text-${n}-500`, 'dark:disabled:text-slate-500');
    add(`disabled:border-${n}-200`, 'dark:disabled:border-slate-700');
    add(`disabled:border-${n}-300`, 'dark:disabled:border-slate-600');
    add(`placeholder:text-${n}-300`, 'dark:placeholder:text-slate-600');
    add(`placeholder:text-${n}-400`, 'dark:placeholder:text-slate-500');
    add(`placeholder:text-${n}-500`, 'dark:placeholder:text-slate-500');
  }

  // --- Tinted status surfaces ---------------------------------------------
  // Keeps alerts, badges and chips legible: the tint darkens while its text
  // and border lighten, preserving the original semantic colour.
  for (const c of TINTS) {
    add(`bg-${c}-50`, `dark:bg-${c}-950/40`);
    add(`bg-${c}-100`, `dark:bg-${c}-900/40`);
    add(`hover:bg-${c}-50`, `dark:hover:bg-${c}-950/60`);
    add(`hover:bg-${c}-100`, `dark:hover:bg-${c}-900/60`);

    add(`text-${c}-950`, `dark:text-${c}-200`);
    add(`text-${c}-900`, `dark:text-${c}-300`);
    add(`text-${c}-800`, `dark:text-${c}-300`);
    add(`text-${c}-700`, `dark:text-${c}-300`);
    add(`text-${c}-600`, `dark:text-${c}-400`);
    add(`hover:text-${c}-900`, `dark:hover:text-${c}-200`);
    add(`hover:text-${c}-800`, `dark:hover:text-${c}-200`);
    add(`hover:text-${c}-700`, `dark:hover:text-${c}-200`);

    add(`border-${c}-100`, `dark:border-${c}-900`);
    add(`border-${c}-200`, `dark:border-${c}-800`);
    add(`border-${c}-300`, `dark:border-${c}-800`);
    add(`hover:border-${c}-300`, `dark:hover:border-${c}-700`);
    add(`ring-${c}-100`, `dark:ring-${c}-900`);
    add(`ring-${c}-200`, `dark:ring-${c}-800`);
    add(`hover:ring-${c}-200`, `dark:hover:ring-${c}-800`);
    add(`hover:ring-${c}-300`, `dark:hover:ring-${c}-700`);
  }

  return map;
}

const MAPPINGS = buildMappings();

/**
 * Collect the literal text spans of every string in a JS/JSX source.
 *
 * This needs a real parser rather than a scanner: regex literals such as
 * `/"/g`, apostrophes inside JSX text, and nested template literals all break
 * naive quote matching and silently desynchronise the rest of the file.
 * Working from the AST also means JSX text is never mistaken for a class list.
 */
function findStringSpans(src) {
  const ast = parse(src, {
    sourceType: 'unambiguous',
    allowReturnOutsideFunction: true,
    errorRecovery: true,
    plugins: [
      'jsx',
      'classProperties',
      'classPrivateProperties',
      'objectRestSpread',
      'optionalChaining',
      'nullishCoalescingOperator',
      'dynamicImport',
      'numericSeparator',
      'optionalCatchBinding',
    ],
  });

  const spans = [];
  const seen = new Set();

  const visit = (node, parent) => {
    if (!node || typeof node !== 'object') return;

    if (Array.isArray(node)) {
      for (const child of node) visit(child, parent);
      return;
    }
    if (typeof node.type !== 'string') return;

    // Module specifiers are paths, never class lists.
    const isModuleSource =
      parent &&
      (parent.type === 'ImportDeclaration' ||
        parent.type === 'ExportNamedDeclaration' ||
        parent.type === 'ExportAllDeclaration') &&
      parent.source === node;

    if (node.type === 'StringLiteral' && !isModuleSource) {
      spans.push({ start: node.start + 1, end: node.end - 1 });
    } else if (node.type === 'TemplateElement') {
      spans.push({ start: node.start, end: node.end });
    }

    for (const key of Object.keys(node)) {
      if (key === 'loc' || key === 'leadingComments' || key === 'trailingComments') continue;
      const child = node[key];
      if (child && typeof child === 'object') {
        if (seen.has(child)) continue;
        seen.add(child);
        visit(child, node);
      }
    }
  };

  visit(ast, null);
  return spans.sort((a, b) => a.start - b.start);
}

/** A class list is anything that looks like whitespace-separated utilities. */
function isClassLike(value) {
  if (!value.trim()) return false;
  const tokens = value.split(/\s+/).filter(Boolean);
  if (!tokens.length) return false;
  return tokens.some((t) => darkFor(stripImportant(t)) !== null);
}

function stripImportant(token) {
  return token.startsWith('!') ? token.slice(1) : token;
}

/**
 * Identify which CSS property a utility drives, variants included, so an
 * existing hand-written `dark:bg-slate-800` blocks us from also emitting
 * `dark:bg-slate-900` onto the same element.
 */
const PROPERTY = /^((?:[a-z]+:)*)(bg|text|border|divide|ring|from|via|to)-/;

function propertyKey(token) {
  const m = PROPERTY.exec(token);
  return m ? `${m[1]}${m[2]}` : null;
}

/**
 * Resolve a token to its dark counterpart, tolerating an opacity suffix such as
 * `bg-white/80` or `border-slate-200/90`. The original opacity is carried over
 * unless the mapping already specifies one of its own.
 */
function darkFor(token) {
  const direct = MAPPINGS.get(token);
  if (direct) return direct;

  const slash = token.lastIndexOf('/');
  if (slash <= 0) return null;

  const mapped = MAPPINGS.get(token.slice(0, slash));
  if (!mapped) return null;
  return mapped.includes('/') ? mapped : mapped + token.slice(slash);
}

function transformClassList(value) {
  const parts = value.split(/(\s+)/);
  const tokens = parts.map((p) => stripImportant(p.trim())).filter(Boolean);

  // Dark properties already styled, by an earlier run or by hand. Hand-written
  // values always win so deliberate design choices are never overwritten.
  const claimed = new Set();
  for (const t of tokens) {
    if (!t.startsWith('dark:')) continue;
    const key = propertyKey(t);
    if (key) claimed.add(key);
  }

  let changed = false;
  const out = parts.map((part) => {
    const token = part.trim();
    if (!token) return part;

    const dark = darkFor(stripImportant(token));
    if (!dark) return part;

    const key = propertyKey(dark);
    if (!key || claimed.has(key)) return part;

    claimed.add(key);
    changed = true;
    return part.replace(token, `${token} ${dark}`);
  });

  return changed ? out.join('') : null;
}

function transformSource(source, label) {
  let spans;
  try {
    spans = findStringSpans(source);
  } catch (err) {
    console.error(`  !! parse failed, skipped: ${label} (${err.message})`);
    return { output: source, count: 0, failed: true };
  }

  let count = 0;
  let output = '';
  let cursor = 0;

  for (const { start, end } of spans) {
    const body = source.slice(start, end);
    if (!isClassLike(body)) continue;
    const next = transformClassList(body);
    if (next === null) continue;

    output += source.slice(cursor, start) + next;
    cursor = end;
    count += 1;
  }

  output += source.slice(cursor);
  return { output, count };
}

function walk(dir, acc = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'build') continue;
      walk(full, acc);
    } else if (/\.(jsx?|tsx?)$/.test(entry.name)) {
      acc.push(full);
    }
  }
  return acc;
}

function isPaperFile(file) {
  const rel = path.relative(SRC_ROOT, file).split(path.sep).join('/');
  return PAPER_FILES.includes(rel);
}

function main() {
  const args = process.argv.slice(2);
  const check = args.includes('--check');
  const targets = args.filter((a) => !a.startsWith('--'));

  let files;
  if (targets.length) {
    files = targets.flatMap((t) => {
      const abs = path.resolve(t);
      return fs.statSync(abs).isDirectory() ? walk(abs) : [abs];
    });
  } else {
    files = walk(SRC_ROOT);
  }

  const touched = [];
  let totalEdits = 0;
  let failures = 0;

  for (const file of files) {
    if (isPaperFile(file)) continue;
    const source = fs.readFileSync(file, 'utf8');
    const rel = path.relative(SRC_ROOT, file);
    const { output, count, failed } = transformSource(source, rel);
    if (failed) failures += 1;
    if (!count) continue;

    totalEdits += count;
    touched.push({ file: rel, count });
    if (!check) fs.writeFileSync(file, output, 'utf8');
  }

  touched.sort((a, b) => b.count - a.count);
  for (const { file, count } of touched) {
    console.log(`${String(count).padStart(4)}  ${file}`);
  }

  const verb = check ? 'need updating' : 'updated';
  console.log(`\n${touched.length} files ${verb} (${totalEdits} class lists)`);
  console.log(`${PAPER_FILES.length} paper files skipped`);
  if (failures) console.log(`${failures} files could not be parsed`);

  if (failures) process.exit(2);
  if (check && touched.length) process.exit(1);
}

main();

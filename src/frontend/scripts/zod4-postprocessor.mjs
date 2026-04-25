/**
 * zod4-postprocessor.mjs — rewrite zod-v3 idioms emitted by openapi-zod-client
 * into zod-v4 syntax.
 *
 * Pure synchronous transform. Idempotent on already-v4 input.
 *
 * Patterns covered:
 *   - `<expr>.passthrough()`        → wrap `<expr>` arg in `z.looseObject(...)`
 *   - `<expr>.strict()`             → wrap `<expr>` arg in `z.strictObject(...)`
 *   - `z.record(V)` (single arg)    → `z.record(z.string(), V)`
 *   - `z.nativeEnum(X)`             → `z.enum(X)`
 *
 * Patterns intentionally NOT touched (still functional in v4, just deprecated):
 *   - chained `.email()`, `.url()`, `.uuid()`
 */

const PASSTHROUGH = "passthrough";
const STRICT = "strict";

export function rewriteV3ToV4(source) {
  let out = source;
  out = rewriteObjectMethodToWrapper(out, PASSTHROUGH, "z.looseObject");
  out = rewriteObjectMethodToWrapper(out, STRICT, "z.strictObject");
  out = rewriteSingleArgRecord(out);
  out = rewriteNativeEnum(out);
  return out;
}

function rewriteObjectMethodToWrapper(src, method, wrapper) {
  // Scan right-to-left so OUTER `.METHOD()` calls are rewritten BEFORE any
  // nested INNER `.METHOD()` they contain. Left-to-right would corrupt the
  // output: rewriting the inner first leaves the outer's argument range
  // pointing at stale offsets in the original `src`, and the algorithm has no
  // way to reconcile that with already-emitted prefix bytes.
  const needle = `.${method}()`;
  let cur = src;
  let pos = cur.length;
  while (pos > 0) {
    const next = cur.lastIndexOf(needle, pos);
    if (next < 0) break;
    if (insideStringLiteral(cur, next)) {
      pos = next - 1;
      continue;
    }
    const replaced = tryRewriteAt(cur, next, method, wrapper);
    if (replaced === null) {
      pos = next - 1;
      continue;
    }
    cur = cur.slice(0, replaced.start) + replaced.text + cur.slice(replaced.end);
    // Resume scanning from the END of the replacement, working leftward. The
    // outer `.${method}()` we just rewrote is gone, but the args we wrapped
    // may themselves contain another `.${method}()` (e.g. inline
    // `z.object({}).partial().passthrough()` nested inside a passthrough'd
    // outer). Resuming from inside the replacement lets the next iteration
    // find that inner one.
    pos = replaced.start + replaced.text.length - 1;
  }
  return cur;
}

function tryRewriteAt(src, methodIdx, method, wrapper) {
  // cursor points to the '.' of the current method call (e.g. '.passthrough()')
  let cursor = methodIdx;
  const preChains = [];
  while (true) {
    // skip whitespace (including newlines) to the left of cursor to find ')'
    let k = cursor - 1;
    while (k >= 0 && /\s/.test(src[k])) k--;
    if (k < 0 || src[k] !== ")") return null;
    const argEnd = k;
    const argStart = matchOpenParen(src, argEnd);
    if (argStart < 0) return null;
    // read back past whitespace to find identifier end
    let idEnd = argStart;
    while (idEnd > 0 && /\s/.test(src[idEnd - 1])) idEnd--;
    const idStart = readIdentLeft(src, idEnd);
    if (idStart < 0) return null;
    // ident may start with '.' if it was a chained call like '.partial'
    // strip leading dot to get the clean method name
    const rawIdent = src.slice(idStart, idEnd);
    const dotPrefix = rawIdent.startsWith(".") ? "." : "";
    const ident = dotPrefix ? rawIdent.slice(1) : rawIdent;
    // check for z.object (could be "z.object" raw or — after whitespace skip — just "object" with dotPrefix ".")
    const fullIdent = dotPrefix ? `z.${ident}` : rawIdent;
    if (rawIdent === "z.object" || (dotPrefix === "." && ident === "object")) {
      const objArgs = src.slice(argStart + 1, argEnd);
      const tail = preChains.length ? "." + preChains.reverse().join(".") : "";
      // start is the beginning of the whole expression: idStart points to 'z' in 'z.object'
      // or to '.' in '.object' — in the latter case the 'z' is before it with whitespace
      const exprStart = dotPrefix === "." ? findZBefore(src, idStart) : idStart;
      if (exprStart < 0) return null;
      return {
        start: exprStart,
        end: methodIdx + `.${method}()`.length,
        text: `${wrapper}(${objArgs})${tail}`,
      };
    }
    preChains.push(`${ident}(${src.slice(argStart + 1, argEnd)})`);
    // cursor moves to the '.' before this ident
    if (dotPrefix === ".") {
      // idStart points to '.', so cursor = idStart (the '.' separator)
      cursor = idStart;
    } else {
      // no dot included in ident — look for '.' immediately before idStart (skipping whitespace)
      let j = idStart - 1;
      while (j >= 0 && /\s/.test(src[j])) j--;
      if (j < 0 || src[j] !== ".") return null;
      cursor = j;
    }
  }
}

/**
 * When we find '.object' with a leading dot, the 'z' that owns it may be
 * separated by whitespace (multi-line style: `z\n  .object`).
 * Walk left past whitespace to find 'z' and return its index.
 */
function findZBefore(src, dotIdx) {
  let j = dotIdx - 1;
  while (j >= 0 && /\s/.test(src[j])) j--;
  if (j < 0) return -1;
  // expect 'z' (the zod namespace)
  if (src[j] === "z") return j;
  return -1;
}

function matchOpenParen(src, closeIdx) {
  let depth = 1;
  for (let i = closeIdx - 1; i >= 0; i--) {
    const c = src[i];
    if (c === ")") depth++;
    else if (c === "(") {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function readIdentLeft(src, end) {
  let i = end;
  while (i > 0 && /[A-Za-z0-9_.]/.test(src[i - 1])) i--;
  return i < end ? i : -1;
}

function insideStringLiteral(src, idx) {
  let lineStart = src.lastIndexOf("\n", idx - 1) + 1;
  let single = 0, double = 0, back = 0;
  for (let i = lineStart; i < idx; i++) {
    const c = src[i];
    if (c === "\\") { i++; continue; }
    if (c === "'") single++;
    else if (c === '"') double++;
    else if (c === "`") back++;
  }
  return (single % 2 === 1) || (double % 2 === 1) || (back % 2 === 1);
}

function rewriteSingleArgRecord(src) {
  let out = "";
  let i = 0;
  while (i < src.length) {
    const next = src.indexOf("z.record(", i);
    if (next < 0) {
      out += src.slice(i);
      break;
    }
    if (insideStringLiteral(src, next)) {
      out += src.slice(i, next + "z.record(".length);
      i = next + "z.record(".length;
      continue;
    }
    const argStart = next + "z.record(".length;
    const argEnd = matchCloseParen(src, argStart - 1);
    if (argEnd < 0) {
      out += src.slice(i, argStart);
      i = argStart;
      continue;
    }
    const args = src.slice(argStart, argEnd);
    if (hasTopLevelComma(args)) {
      out += src.slice(i, argEnd + 1);
      i = argEnd + 1;
      continue;
    }
    out += src.slice(i, argStart) + "z.string(), " + args + ")";
    i = argEnd + 1;
  }
  return out;
}

function matchCloseParen(src, openIdx) {
  let depth = 1;
  for (let i = openIdx + 1; i < src.length; i++) {
    const c = src[i];
    if (c === "(") depth++;
    else if (c === ")") {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function hasTopLevelComma(args) {
  let depth = 0;
  for (let i = 0; i < args.length; i++) {
    const c = args[i];
    if (c === "(" || c === "[" || c === "{") depth++;
    else if (c === ")" || c === "]" || c === "}") depth--;
    else if (c === "," && depth === 0) return true;
  }
  return false;
}

function rewriteNativeEnum(src) {
  return src.replace(/\bz\.nativeEnum\(/g, "z.enum(");
}

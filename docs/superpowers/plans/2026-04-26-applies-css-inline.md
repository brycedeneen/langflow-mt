# `applies.css` inline pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `src/frontend/src/style/applies.css` from ~687 lines to ≤250 lines by deleting dead rules, inlining low-use rules at their call sites, and relocating cohesive decorative blocks (the empty-page gradient family) to their consuming components.

**Architecture:** Audit-driven 4-stage pipeline run inside an isolated worktree. Stage 1 deletes dead rules and relocates the gradient cluster. Stage 2 dispatches one parallel subagent per surface-area group of pure-`@apply` low-use rules; subagents only edit JSX/TSX call sites, the controller mediates `applies.css` deletions to avoid parallel-write contention. Stage 3 (controller) handles the trickier rules — those that other applies.css rules `@apply`, plus rules with pseudo-elements/raw CSS that need case-by-case relocation. Single commit at the end after the verification gate.

**Tech Stack:** React 19, TypeScript, Tailwind v4 (CSS-first config in `style/index.css`; `@utility` and `.class` rules in `style/applies.css`), Jest for unit tests, Playwright for e2e, Vite for build.

**Spec:** `docs/superpowers/specs/2026-04-26-applies-css-inline-design.md`

**Standing instructions (from user's memory / AGENTS.md):**
- **Never `git commit` without explicit approval.** The commit task explicitly pauses and asks.
- **Stage explicit file paths.** Never `git add -A`/`.`/`-a`. The repo has unrelated WIP — only stage files this plan touches.
- **No upstream PR.** All work lands on `platform-multi-tenant`. Push to the `fork` remote (NOT `origin` which is langflow-ai/langflow upstream).
- **Worktree-first.** Every change happens inside the worktree set up in Task 0.
- **Cadence:** "Ton of work before committing." All implementation tasks land first; verification (Task 6) and commit (Task 7) come once at the end.
- **Subagent commit hygiene:** subagents never commit. They never `git add` either. They edit files; the controller stages and commits at the end.

---

## File structure

| File | Responsibility | Modified by |
|---|---|---|
| `src/frontend/src/style/applies.css` | Source of truth for the rules being audited. Loses ~440 lines total. | Tasks 2 (DEAD-leaf + CLUSTER), 3 (after subagent inlines), 4 (non-leaf), 5 (complex) — controller-mediated |
| `src/frontend/src/pages/MainPage/pages/emptyPage/gradient-bg.css` (new) | Co-located CSS for the 8-class empty-page gradient decoration. | Task 2 |
| `src/frontend/src/pages/MainPage/pages/emptyPage/index.tsx` | Add `import "./gradient-bg.css"` so the relocated rules still load. | Task 2 |
| ~80 `.tsx` / `.ts` call-site files (exact set determined by audit) | Replace `className="<custom-class>"` with the inlined Tailwind utility list at each site. | Task 3 (parallel subagents, one per surface-area group) and Task 4 (controller) |
| `/tmp/p4-audit.tsv` (ephemeral) | Per-class audit map: `name\text\tint\tpure\tbucket`. Output of Task 1's script. Drives Tasks 2-5. | Task 1 |
| `/tmp/p4-call-sites.tsv` (ephemeral) | Per-class call-site list: `name\tfile\tline`. Output of Task 1's script. | Task 1 |

---

## Task 0 — Worktree setup

**Files:** None modified; sets up the workspace.

- [ ] **Step 1: Create the worktree from `platform-multi-tenant` HEAD**

Run (from `/Users/brycedeneen/dev/langflow`):
```bash
git worktree add .worktrees/tailwind-applies-inline -b tailwind/applies-inline platform-multi-tenant
```
Expected: `.worktrees/tailwind-applies-inline/` exists; new branch `tailwind/applies-inline` checked out.

- [ ] **Step 2: Install frontend deps in the worktree**

Run:
```bash
cd .worktrees/tailwind-applies-inline/src/frontend && npm install
```
Expected: clean install on warm cache.

- [ ] **Step 3: Confirm baseline**

Run:
```bash
cd .worktrees/tailwind-applies-inline/src/frontend && npm run type-check 2>&1 | tail -10
```
Expected: 2 pre-existing errors in `src/hooks/flows/use-add-flow.ts:126` and `src/pages/MainPage/hooks/use-handle-duplicate.ts:24` (TagRead vs string[]). Anything else means the baseline is dirtier than expected — stop and report.

```bash
cd .worktrees/tailwind-applies-inline/src/frontend && npm run test -- --silent 2>&1 | tail -5
```
Expected: only pre-existing failures in `src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx` (14 failures, 3069 passing).

```bash
cd .worktrees/tailwind-applies-inline/src/frontend && wc -l src/style/applies.css
```
Expected: ~687 lines. Record the exact number — Task 6 step 4 diffs against it.

**All remaining tasks operate inside `.worktrees/tailwind-applies-inline`.** Paths below are worktree-relative.

---

## Task 1 — Build the audit map

**Files:**
- Create (ephemeral): `/tmp/p4-audit.tsv`
- Create (ephemeral): `/tmp/p4-call-sites.tsv`

This task produces the data that drives Tasks 2-5. It runs as a single shell pipeline; output is examined before proceeding.

- [ ] **Step 1: Extract the full class/utility name list from `applies.css`**

Run (from worktree root):
```bash
{
  grep -E "^\s*\.[a-zA-Z][a-zA-Z0-9_-]*[ ,{]" src/frontend/src/style/applies.css \
    | awk '{ for(i=1;i<=NF;i++) { if ($i ~ /^\.[a-zA-Z]/) { gsub(/[,{:]/, "", $i); sub(/^\./, "", $i); print $i } } }';
  grep -E "^@utility\s+[a-zA-Z]" src/frontend/src/style/applies.css | awk '{ print $2 }';
} | sort -u > /tmp/p4-classes.txt
wc -l /tmp/p4-classes.txt
```
Expected: ~109 lines (109 unique class/utility names). Capture both `.foo` selectors and `@utility foo` Tailwind v4 declarations.

- [ ] **Step 2: Compute external reference counts**

Run:
```bash
cd src/frontend
> /tmp/p4-ext-counts.tsv
while read -r cls; do
  count=$(grep -rn "\b${cls}\b" src --include="*.ts" --include="*.tsx" --include="*.css" 2>/dev/null \
    | grep -v "src/style/applies.css" \
    | wc -l | tr -d ' ')
  printf "%s\t%s\n" "$cls" "$count" >> /tmp/p4-ext-counts.tsv
done < /tmp/p4-classes.txt
cd ../..
wc -l /tmp/p4-ext-counts.tsv
```
Expected: same line count as `/tmp/p4-classes.txt`. Each line is `<name>\t<external-ref-count>`.

- [ ] **Step 3: Compute internal `@apply` reference counts**

Run:
```bash
> /tmp/p4-int-counts.tsv
while read -r cls; do
  count=$(grep -E "^\s*@apply\s+" src/frontend/src/style/applies.css \
    | grep -E "\b${cls}\b" \
    | wc -l | tr -d ' ')
  printf "%s\t%s\n" "$cls" "$count" >> /tmp/p4-int-counts.tsv
done < /tmp/p4-classes.txt
```
Expected: each line is `<name>\t<internal-@apply-ref-count>`. Internal references (count > 0) mean the rule is used by another rule in `applies.css` — deleting/inlining it requires expanding into the parent rule.

- [ ] **Step 4: Compute the `pure` flag**

A rule is "pure" if its body contains only `@apply <utilities>;` lines and the closing `}` — no pseudo-elements (`::before`, `::after`), no raw CSS declarations (`width: 50px`), no nested selectors, no CSS variables. The script extracts each rule body and tests it.

Run:
```bash
> /tmp/p4-pure-flags.tsv
while read -r cls; do
  # Find the rule's start line (either ".cls {" or "@utility cls {")
  start=$(grep -nE "(^\s*\.${cls}\b[^a-zA-Z0-9_-]|^@utility\s+${cls}\b)" \
    src/frontend/src/style/applies.css | head -1 | cut -d: -f1)
  if [ -z "$start" ]; then
    printf "%s\tunknown\n" "$cls" >> /tmp/p4-pure-flags.tsv
    continue
  fi
  # Find matching closing brace (assume rule body ≤ 30 lines for our purposes)
  body=$(awk -v s="$start" 'NR>=s && NR<=s+30 {print}' src/frontend/src/style/applies.css \
    | awk 'BEGIN{depth=0} {
      for(i=1;i<=length($0);i++) {
        c=substr($0,i,1);
        if(c=="{") depth++;
        else if(c=="}") { depth--; if(depth==0) { print substr($0,1,i); exit } }
      }
      print
    }')
  # Pure = every non-blank, non-comment, non-selector line is "  @apply ...;" or "}"
  is_pure=true
  echo "$body" | tail -n +2 | while IFS= read -r line; do
    trimmed=$(echo "$line" | sed 's/^\s*//; s/\s*$//')
    if [ -z "$trimmed" ] || [ "$trimmed" = "}" ] || echo "$trimmed" | grep -qE "^@apply\s"; then
      continue
    fi
    if echo "$trimmed" | grep -qE "^/\*"; then continue; fi
    echo "IMPURE"
    break
  done > /tmp/p4-pure-tmp.txt
  if grep -q IMPURE /tmp/p4-pure-tmp.txt; then
    printf "%s\tfalse\n" "$cls" >> /tmp/p4-pure-flags.tsv
  else
    printf "%s\ttrue\n" "$cls" >> /tmp/p4-pure-flags.tsv
  fi
done < /tmp/p4-classes.txt
```

If the inline script proves too brittle in practice (e.g., the brace-balancing edges out), fall back to the simpler heuristic: a rule is pure iff every line in its body matches `^\s*(@apply\s|}|/\*|\s*$)`.

Expected: each line `<name>\ttrue|false`.

- [ ] **Step 5: Join into the audit table**

Run:
```bash
join -t $'\t' -1 1 -2 1 \
  <(sort /tmp/p4-ext-counts.tsv) \
  <(sort /tmp/p4-int-counts.tsv) \
  > /tmp/p4-tmp1.tsv
join -t $'\t' -1 1 -2 1 \
  /tmp/p4-tmp1.tsv \
  <(sort /tmp/p4-pure-flags.tsv) \
  > /tmp/p4-audit-raw.tsv

# Now add the bucket label
awk -F'\t' 'BEGIN{OFS="\t"}
{
  name=$1; ext=$2+0; int=$3+0; pure=($4=="true");
  bucket = "?";
  if (ext == 0 && int == 0) bucket = "DEAD-leaf";
  else if (ext == 0 && int > 0) bucket = "DEAD-internal-only";
  else if (ext >= 1 && ext <= 2 && int == 0 && pure) bucket = "INLINE-pure-leaf";
  else if (ext >= 1 && ext <= 2 && int > 0 && pure) bucket = "INLINE-pure-non-leaf";
  else if (ext >= 1 && ext <= 2 && !pure) bucket = "INLINE-complex";
  else if (ext >= 3) bucket = "KEEP";
  print name, ext, int, ($4=="true"?"true":"false"), bucket
}' /tmp/p4-audit-raw.tsv > /tmp/p4-audit.tsv

# Override the gradient family — they form a CLUSTER-relocate cohort
for c in gradient-bg gradients-container g1 g2 g3 g4 g5 g6; do
  sed -i.bak "s/^${c}\t.*$/${c}\t1\t0\tfalse\tCLUSTER-relocate/" /tmp/p4-audit.tsv
done
rm -f /tmp/p4-audit.tsv.bak

wc -l /tmp/p4-audit.tsv
echo "=== Bucket counts ==="
awk -F'\t' '{print $5}' /tmp/p4-audit.tsv | sort | uniq -c
```

Expected output:
```
109 /tmp/p4-audit.tsv
=== Bucket counts ===
   8 CLUSTER-relocate
  ?? DEAD-internal-only
  ?? DEAD-leaf
  ?? INLINE-complex
  ?? INLINE-pure-leaf
  ?? INLINE-pure-non-leaf
  ?? KEEP
```

The exact `??` numbers depend on the live audit; verify the bucket counts look reasonable (KEEP ~41, INLINE-pure-leaf is the largest INLINE bucket, no surprises in CLUSTER-relocate's 8 names).

- [ ] **Step 6: Build the call-sites map for INLINE-pure-leaf and INLINE-pure-non-leaf**

For each class in those two buckets, record the file paths where it's referenced:

```bash
> /tmp/p4-call-sites.tsv
awk -F'\t' '$5 == "INLINE-pure-leaf" || $5 == "INLINE-pure-non-leaf" {print $1}' /tmp/p4-audit.tsv \
  | while read -r cls; do
    grep -rn "\b${cls}\b" src/frontend/src \
      --include="*.ts" --include="*.tsx" --include="*.css" 2>/dev/null \
      | grep -v "src/style/applies.css" \
      | while IFS=: read -r file line _; do
        printf "%s\t%s\t%s\n" "$cls" "$file" "$line" >> /tmp/p4-call-sites.tsv
      done
  done
wc -l /tmp/p4-call-sites.tsv
```

Expected: roughly 60-100 lines (one per call-site occurrence).

- [ ] **Step 7: Group call sites by surface area**

Run:
```bash
awk -F'\t' '$5 == "INLINE-pure-leaf"' /tmp/p4-audit.tsv | awk -F'\t' '{print $1}' | sort > /tmp/p4-pure-leaf-classes.txt
echo "=== Class names by prefix (proposed surface-area groups) ==="
cat /tmp/p4-pure-leaf-classes.txt | sed -E 's/^(form-modal|dropdown-component|error-build|success-alert|langflow-chat|skeleton-card|input-component|input-file|generic-node|chat-message|edit-flow|api-modal|node|fade|btn|background-fade|export-modal|deploy-dropdown|side-bar)/\1/; s/^([^-]+)-.*/\1-PREFIX/; s/^([^-]+)$/MISC/' | sort | uniq -c | sort -rn
```

Use the prefix output to bucket classes into surface-area groups. Common groups expected:
- `form-modal-*`
- `dropdown-component-*`
- `error-build-*`, `success-alert-*` (alerts)
- `langflow-chat-*`
- `skeleton-card-*`
- `input-*` (input-component, input-file, input-slider — group as one)
- `generic-node-*`, `node-*`
- `edit-flow-*`
- Misc singletons (one or two classes that don't share a prefix)

Record the surface-area mapping in `/tmp/p4-surface-areas.tsv` as `<prefix>\t<class-name>` for use by Stage 2 (Task 3).

```bash
# Manual: based on the prefix output, create /tmp/p4-surface-areas.tsv with one line per class:
# <prefix-or-MISC>\t<class-name>
# This is human-curated based on the prefix output. Suggested prefixes listed above.
```

The exact grouping is curated, not deterministic — small differences in grouping affect parallelism but not correctness. Aim for 5-8 groups of 4-10 classes each.

---

## Task 2 — DEAD-leaf deletes + CLUSTER-relocate (Stage 1)

**Files:**
- Create: `src/frontend/src/pages/MainPage/pages/emptyPage/gradient-bg.css`
- Modify: `src/frontend/src/pages/MainPage/pages/emptyPage/index.tsx`
- Modify: `src/frontend/src/style/applies.css`

This task is mechanical, low-risk, and small. Done inline by the controller (no subagent — overhead doesn't pay off).

- [ ] **Step 1: List the DEAD-leaf rules**

```bash
awk -F'\t' '$5 == "DEAD-leaf"' /tmp/p4-audit.tsv | awk -F'\t' '{print $1}'
```

Expected: ~14 names. These rules are referenced nowhere — neither externally nor internally.

- [ ] **Step 2: Delete each DEAD-leaf rule from `applies.css`**

For each name from Step 1, find the rule's start line (either `.<name> {` or `@utility <name> {`) and delete the rule block (selector through closing `}`). Use the Edit tool with the full rule text as `old_string`.

After deleting, run:
```bash
grep -E "^\s*\.<name>\b|^@utility\s+<name>\b" src/frontend/src/style/applies.css
```
Expected: empty (rule is gone). Repeat for each name.

- [ ] **Step 3: Create `gradient-bg.css` with the 8 cluster rules**

The 8 classes in CLUSTER-relocate are: `gradient-bg`, `gradients-container`, `g1`, `g2`, `g3`, `g4`, `g5`, `g6`.

Extract their rule bodies from `applies.css` (each rule is roughly 10-20 lines). The exact rule text varies (g1-g6 differ in `--colorN`, position, and animation duration); copy each verbatim.

Create `src/frontend/src/pages/MainPage/pages/emptyPage/gradient-bg.css` with all 8 rules concatenated. Preserve every CSS variable reference, every `@keyframes` reference, every base64 SVG data URL, every line of raw CSS verbatim.

Note: `gradient-bg.css` should NOT use `@layer` wrappers — the rules become plain selectors at the top level of this colocated file (the file is imported only by `emptyPage/index.tsx` and doesn't need to participate in Tailwind's layer ordering).

If the original rules are inside an `@layer base { ... }` block in `applies.css`, the relocated rules can be at the top level of `gradient-bg.css` since CSS specificity for plain class selectors is unchanged.

- [ ] **Step 4: Add the import to `emptyPage/index.tsx`**

Open `src/frontend/src/pages/MainPage/pages/emptyPage/index.tsx`. Add this import alongside the other imports near the top of the file:

```tsx
import "./gradient-bg.css";
```

The import must be a side-effect-only import (no symbol bound). Vite preserves these.

- [ ] **Step 5: Delete the 8 cluster rules from `applies.css`**

For each of the 8 names, delete the rule block from `applies.css` (same Edit-tool approach as Step 2). Verify with:
```bash
grep -E "^\s*\.(gradient-bg|gradients-container|g[1-6])\b" src/frontend/src/style/applies.css
```
Expected: empty.

- [ ] **Step 6: Verify Stage 1 with typecheck and build**

Run:
```bash
cd src/frontend && npm run type-check 2>&1 | tail -5
cd src/frontend && npm run build 2>&1 | tail -5
```
Expected: typecheck shows only the 2 pre-existing TagRead errors. Build succeeds.

```bash
wc -l src/frontend/src/style/applies.css
```
Expected: roughly 100 lines fewer than baseline (~687 → ~580 or so, depending on exact rule sizes).

---

## Task 3 — INLINE-pure-leaf, parallel by surface-area group (Stage 2)

**Files:**
- Modify: every JSX/TSX file listed in `/tmp/p4-call-sites.tsv` for INLINE-pure-leaf classes (one subagent per surface-area group)
- Modify: `src/frontend/src/style/applies.css` — controller deletes the rules after each subagent reports done

Stage 2 is the highest-churn stage. One subagent per surface-area group from `/tmp/p4-surface-areas.tsv`. Subagents only edit JSX/TSX call sites and never touch `applies.css`.

- [ ] **Step 1: For each surface-area group, dispatch one subagent in parallel**

Each subagent receives, in its prompt, the following pre-computed data (controller pulls from `/tmp/p4-audit.tsv`, `/tmp/p4-call-sites.tsv`, and the actual `applies.css` rule bodies):

```
For each rule in your group, here is the rule's @apply utility list and its 1-2 call sites:

Rule: <className>
  @apply utilities: <space-separated Tailwind utility list, copied verbatim>
  Call sites:
    - <file>:<line>
    - <file>:<line>  (if 2)

[repeat for each rule in the group]
```

The subagent's job, for each rule:
1. Open the call-site file.
2. Find the JSX element using `className="<className>"` or `className={"...<className>..."}` or `className={cn("<className>", ...)}` etc. — handle the common composition patterns.
3. Replace `<className>` with the inlined utility list. Preserve any other classes already present in the same className expression.
4. Move to the next call site.

Constraints embedded in every subagent's prompt:
- ONLY edit the JSX/TSX files in your call-sites list.
- DO NOT modify `src/frontend/src/style/applies.css`. The controller handles that.
- DO NOT modify any other file.
- DO NOT `git commit` or `git add`. The controller commits at the end.
- DO NOT install packages.
- DO NOT run jest, build, or Playwright. The controller runs verification at the end.
- After all your edits, run `npm run type-check 2>&1 | grep -E "<your-files-list>"` (controller pre-fills the file list). Errors in your files = fix them. Errors in other files = ignore.
- Report back: list of class names you inlined, list of files you modified.

- [ ] **Step 2: Wait for all surface-area subagents to report**

Each subagent reports DONE with its list of inlined class names. The controller collects the union.

- [ ] **Step 3: Verify combined sweep — old class names gone**

Run:
```bash
awk -F'\t' '$5 == "INLINE-pure-leaf"' /tmp/p4-audit.tsv | awk -F'\t' '{print $1}' \
  | while read -r cls; do
    count=$(grep -rn "\b${cls}\b" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css" 2>/dev/null \
      | grep -v "src/style/applies.css" | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
      echo "MISS: $cls still referenced ($count)"
    fi
  done
```
Expected: empty output. Any MISS line means a subagent missed a call site or `applies.css` itself still contains a self-reference. Investigate before proceeding.

- [ ] **Step 4: Delete the inlined rules from `applies.css`**

For each class name in the union from Step 2, the controller deletes the rule block from `applies.css` (same Edit-tool approach as Task 2 Step 2). Verify with:
```bash
awk -F'\t' '$5 == "INLINE-pure-leaf"' /tmp/p4-audit.tsv | awk -F'\t' '{print $1}' \
  | while read -r cls; do
    grep -E "^\s*\.${cls}\b|^@utility\s+${cls}\b" src/frontend/src/style/applies.css
  done
```
Expected: empty.

- [ ] **Step 5: Stage 2 verification**

Run:
```bash
cd src/frontend && npm run type-check 2>&1 | tail -5
cd src/frontend && npm run build 2>&1 | tail -5
wc -l src/frontend/src/style/applies.css
```
Expected: typecheck only pre-existing errors; build succeeds; line count drops further (~580 → ~250-350 or so).

---

## Task 4 — INLINE-pure-non-leaf (Stage 3a, controller-driven sequential)

**Files:**
- Modify: `src/frontend/src/style/applies.css` (parent rules' `@apply` directives expand inline; the rule itself gets deleted)
- Modify: each call-site file listed in `/tmp/p4-call-sites.tsv` for INLINE-pure-non-leaf classes

These rules are referenced both externally (1-2 call sites) AND by other rules in `applies.css`. Doing them in parallel would risk double-edits to `applies.css`. Controller handles sequentially.

- [ ] **Step 1: List the non-leaf inlines**

```bash
awk -F'\t' '$5 == "INLINE-pure-non-leaf"' /tmp/p4-audit.tsv
```

Expected: a small list (likely 2-4 names based on the audit; e.g., `message-button`).

- [ ] **Step 2: For each non-leaf, expand into parent rules**

For each non-leaf class `<cls>` with utility list `<utilities>`:

1. Find every `@apply` directive in `applies.css` that references `<cls>`. Use:
   ```bash
   grep -nE "^\s*@apply\s+.*\b<cls>\b" src/frontend/src/style/applies.css
   ```
2. For each match line, edit `applies.css`: replace the token `<cls>` in the `@apply` directive with `<utilities>` (the space-separated utility list of `<cls>`).
3. Run typecheck — `cd src/frontend && npm run type-check 2>&1 | tail -3`.

- [ ] **Step 3: For each non-leaf, inline at external call sites**

Same procedure as Task 3 Step 1 (controller does it instead of a subagent). For each external call site of `<cls>`, replace the class name with its `@apply` utility list.

- [ ] **Step 4: Delete the non-leaf rule from `applies.css`**

For each non-leaf class, delete its rule block from `applies.css`. Verify:
```bash
awk -F'\t' '$5 == "INLINE-pure-non-leaf"' /tmp/p4-audit.tsv | awk -F'\t' '{print $1}' \
  | while read -r cls; do
    grep -E "^\s*\.${cls}\b|^@utility\s+${cls}\b" src/frontend/src/style/applies.css
  done
```
Expected: empty.

---

## Task 5 — INLINE-complex case-by-case (Stage 3b, controller-driven sequential)

**Files:**
- Modify: `src/frontend/src/style/applies.css` (delete relocated rules)
- Create or modify: per-rule colocated CSS file (one per relocation case)
- Modify: per-rule consuming JSX file (add `import "./xxx.css"`)

These rules have 1-2 external refs but contain pseudo-elements, raw CSS, or otherwise can't be cleanly inlined as a className string. Each gets a deliberate decision.

- [ ] **Step 1: List the complex inlines**

```bash
awk -F'\t' '$5 == "INLINE-complex"' /tmp/p4-audit.tsv
```

Expected: ~6-14 names, depending on the audit. Likely candidates from the brainstorming exploration:
- `fade-container` (and its `::before`/`::after` companions) — relocate
- `border-frozen`, `border-ring-frozen` — colocate with frozen treatment, or promote to KEEP if they're conceptually part of the `.frozen` (43-ref KEEP) family
- `btn-add-input-list`, `text-container`, `helper-line` — small bodies, likely inline-with-arbitrary or relocate per call site

- [ ] **Step 2: For each complex rule, decide and execute**

For each class `<cls>`:

**Decision rule:**
- If `<cls>` has 1 call site AND the rule body is non-trivial (pseudo-elements, animation references, multiple raw CSS declarations): **relocate** to a CSS file adjacent to the consumer (e.g., `<consumer-dir>/<cls-or-feature>.css`). Add `import "./<file>.css"` to the consumer.
- If `<cls>` has 1-2 call sites AND the rule body fits in 2-3 Tailwind arbitrary-value utilities: **inline** (e.g., a `width: 50px` rule becomes `className="w-[50px]"` ).
- If `<cls>` is conceptually part of a KEEP rule's family (e.g., `border-frozen` is the static-border counterpart of the highly-used `frozen` rule): **promote to KEEP**. Note in `docs/superpowers/followups.md` that the rule was kept due to the family relationship — don't bury this decision.
- Default fallback if no rule fits: **promote to KEEP**.

Execute the decision per rule, then delete the rule from `applies.css` if it was relocated or inlined. Skip the deletion if it was promoted to KEEP.

- [ ] **Step 3: Verify**

```bash
awk -F'\t' '$5 == "INLINE-complex"' /tmp/p4-audit.tsv | awk -F'\t' '{print $1}' \
  | while read -r cls; do
    in_applies=$(grep -E "^\s*\.${cls}\b|^@utility\s+${cls}\b" src/frontend/src/style/applies.css | wc -l)
    in_src=$(grep -rn "\b${cls}\b" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css" 2>/dev/null \
      | grep -v "src/style/applies.css" | wc -l)
    echo "${cls} applies=${in_applies} src=${in_src}"
  done
```

For each line:
- `applies=0 src=0` — relocated and call sites updated to use new file. ✓
- `applies=1 src=N` — promoted to KEEP. ✓
- `applies=0 src=N` — inlined. ✓
- Anything else — investigate.

- [ ] **Step 4: Handle DEAD-internal-only rules (if any)**

```bash
awk -F'\t' '$5 == "DEAD-internal-only"' /tmp/p4-audit.tsv
```

Expected: small list (often 0). For each, follow Task 4's parent-expansion procedure: expand the rule into each parent rule's `@apply`, then delete.

---

## Task 6 — Verification gate

**Files:** None modified.

The five-step bar from the spec, run end-to-end after Stages 1-3 complete.

- [ ] **Step 1: Typecheck**

```bash
cd src/frontend && npm run type-check 2>&1 | tail -10
```
Expected: only `src/hooks/flows/use-add-flow.ts:126` and `src/pages/MainPage/hooks/use-handle-duplicate.ts:24` (pre-existing TagRead errors). Anything else = investigate.

- [ ] **Step 2: Jest**

```bash
cd src/frontend && npm run test -- --silent 2>&1 | tail -8
```
Expected: only `src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx` failures (14, pre-existing). 3069+ pass.

- [ ] **Step 3: Production build**

```bash
cd src/frontend && npm run build 2>&1 | tail -10
```
Expected: bundle builds, no errors. Note any warnings (chunk size warnings are pre-existing and tolerated).

- [ ] **Step 4: applies.css line count**

```bash
wc -l src/frontend/src/style/applies.css
```
Target: ≤ 250 lines. (~64% reduction from 687.) If above 350, the audit either over-classified rules as KEEP or some inlines didn't land — investigate before commit.

- [ ] **Step 5: Class-reference sweep**

For every class that was deleted, inlined, or relocated:
```bash
awk -F'\t' '$5 != "KEEP"' /tmp/p4-audit.tsv | awk -F'\t' '{print $1}' \
  | while read -r cls; do
    # Skip the gradient family — they live in gradient-bg.css now
    case "$cls" in gradient-bg|gradients-container|g[1-6]) continue ;; esac
    count=$(grep -rn "\b${cls}\b" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css" 2>/dev/null \
      | grep -v "src/style/applies.css" | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
      # If it was promoted to KEEP via the complex-rule decision, that's fine
      bucket=$(awk -F'\t' -v c="$cls" '$1==c {print $5}' /tmp/p4-audit.tsv)
      promoted=$(grep -E "^\s*\.${cls}\b|^@utility\s+${cls}\b" src/frontend/src/style/applies.css | wc -l)
      if [ "$promoted" -eq 0 ]; then
        echo "ORPHAN: $cls (bucket=$bucket, refs=$count)"
      fi
    fi
  done
```
Expected: empty output. Any ORPHAN line means a class is referenced somewhere but the rule has been deleted — at runtime that class becomes a no-op. Fix before commit.

---

## Task 7 — Commit, merge, push, cleanup (after explicit approval)

**Files:** All files modified by Tasks 2-5.

- [ ] **Step 1: Summarize the diff**

Run (from worktree):
```bash
git status --short
git diff --stat
wc -l src/frontend/src/style/applies.css
```

Compose a summary covering:
- Number of DEAD-leaf rules deleted.
- Number of INLINE-pure-leaf rules inlined and # of call-site files modified.
- Number of INLINE-pure-non-leaf rules expanded into parents.
- Number of INLINE-complex rules: relocated vs. inlined vs. promoted-to-KEEP.
- New colocated CSS files created (gradient-bg.css plus any from Task 5).
- Final `applies.css` line count vs. baseline (687).
- Verification gate results.

- [ ] **Step 2: Pause and ask for commit permission**

Ask the user verbatim: *"Stage 1-3 complete and verification gate passed. applies.css went from 687 to <N> lines. OK to commit on `tailwind/applies-inline`?"*

**Do NOT commit without explicit approval.**

- [ ] **Step 3: Stage explicit paths and commit (after approval)**

Build the staging command from the actual changed-files list:
```bash
git status --short | awk '{print $NF}' | sort -u > /tmp/p4-changed-files.txt
cat /tmp/p4-changed-files.txt
# Manually inspect — no surprises (no random WIP files); then:
git add $(cat /tmp/p4-changed-files.txt)
```

Verify only the expected paths are staged:
```bash
git diff --cached --name-only
```

Commit with:
```bash
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 4 inline pass — applies.css <BASELINE>→<FINAL> lines

Resolves the Tailwind Maximization Phase 4 deferral (inline 1-2-ref @apply rules).
Audit-driven 4-stage pipeline:
- Deleted N DEAD-leaf rules
- Relocated 8-class gradient cluster to emptyPage/gradient-bg.css
- Inlined N INLINE-pure-leaf rules at their 1-2 call sites
- Expanded N INLINE-pure-non-leaf rules into parent @apply directives
- Resolved INLINE-complex rules case-by-case (relocate / inline / promote-to-KEEP)

applies.css: 687 → <FINAL> lines (~<PCT>% reduction).
Pure refactor: no behavior change. Typecheck + jest + build pass with only pre-existing failures.

Spec: docs/superpowers/specs/2026-04-26-applies-css-inline-design.md
Plan: docs/superpowers/plans/2026-04-26-applies-css-inline.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Replace `<BASELINE>`, `<FINAL>`, `<PCT>`, and the per-bucket `N` counts with actual values from Step 1's summary.

- [ ] **Step 4: Confirm commit landed**

Run:
```bash
git log -1 --stat
```
Expected: one commit on `tailwind/applies-inline` showing the file modifications. No surprise files (verify only the paths from `/tmp/p4-changed-files.txt` appear).

- [ ] **Step 5: Fast-forward merge into `platform-multi-tenant`**

From the main checkout (NOT the worktree):
```bash
# Pre-merge sanity
git -C /Users/brycedeneen/dev/langflow merge-base --is-ancestor platform-multi-tenant tailwind/applies-inline \
  && echo "ff-only is possible" || echo "NOT a strict descendant — investigate"

# Fast-forward merge
git -C /Users/brycedeneen/dev/langflow merge --ff-only tailwind/applies-inline

# Post-merge sanity
git -C /Users/brycedeneen/dev/langflow log -2 --oneline platform-multi-tenant
git -C /Users/brycedeneen/dev/langflow status --short | head -5
```

Expected: ff-only succeeds; HEAD of platform-multi-tenant moves to the new commit; the main checkout's WIP files are unchanged (because the merged commit doesn't touch any of them).

- [ ] **Step 6: Push to `fork` (NOT `origin`)**

```bash
git -C /Users/brycedeneen/dev/langflow push fork platform-multi-tenant
```

**Critical:** push to `fork` (`brycedeneen/langflow-mt`), NOT `origin` (which is upstream `langflow-ai/langflow`). Memory rule: never push to upstream.

- [ ] **Step 7: Cleanup worktree and merged branch**

```bash
cd /Users/brycedeneen/dev/langflow && git worktree remove .worktrees/tailwind-applies-inline
git -C /Users/brycedeneen/dev/langflow branch -d tailwind/applies-inline
git -C /Users/brycedeneen/dev/langflow worktree list
```

Expected: worktree removed; branch deleted; only the main checkout and any other pre-existing worktrees remain.

- [ ] **Step 8: Hand back to user**

Report:
- The commit SHA on `platform-multi-tenant`.
- Final `applies.css` line count and reduction percentage.
- Anything promoted to KEEP via the complex-rule decision (so the user knows what wasn't inlined and why).
- Any followups added to `docs/superpowers/followups.md` (if the audit surfaced follow-on cleanup).

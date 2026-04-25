#!/usr/bin/env python3
"""Flatten Pydantic v2 / OpenAPI 3.1 `$defs` blocks into `components.schemas`.

`openapi-zod-client@1.18.x` (and its underlying `@apidevtools/json-schema-ref-parser`)
do not resolve JSON Schema 2020-12 `$defs` correctly when the blocks are nested
inside individual schemas — refs like `#/$defs/X` are document-root-relative but the
`$defs` block they point to lives nested. Pydantic v2 emits exactly this idiom.

This script reads an OpenAPI doc, walks every schema (in `components.schemas` AND
inline schemas in `paths`), lifts every `$defs` block into `components.schemas` with
a flattened unique name, and rewrites all `#/$defs/X` refs to point to the lifted
names. The resulting doc has zero `$defs` and resolvable refs everywhere.

Usage:
    python3 flatten-openapi-defs.py <input.json> <output.json>
"""
from __future__ import annotations
import json
import sys
from typing import Any


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: flatten-openapi-defs.py <input.json> <output.json>", file=sys.stderr)
        return 2
    in_path, out_path = argv[1], argv[2]

    with open(in_path, encoding="utf-8") as f:
        spec = json.load(f)

    schemas: dict[str, Any] = spec.setdefault("components", {}).setdefault("schemas", {})
    used_names: set[str] = set(schemas.keys())

    # Pass 1: lift $defs from every top-level schema in components/schemas.
    for name, schema in list(schemas.items()):
        lift_defs(schema, parent_namespace=name, schemas=schemas, used_names=used_names)

    # Pass 2: lift $defs from inline schemas in paths.
    paths = spec.get("paths", {})
    for path, ops in paths.items():
        if not isinstance(ops, dict):
            continue
        for method, op in ops.items():
            if not isinstance(op, dict):
                continue
            ns = make_path_namespace(path, method)
            # request body
            rb = op.get("requestBody", {})
            for ct, content in (rb.get("content") or {}).items():
                if isinstance(content, dict) and "schema" in content:
                    lift_defs(content["schema"], parent_namespace=f"{ns}__req",
                              schemas=schemas, used_names=used_names)
            # responses
            for status, resp in (op.get("responses") or {}).items():
                if not isinstance(resp, dict):
                    continue
                for ct, content in (resp.get("content") or {}).items():
                    if isinstance(content, dict) and "schema" in content:
                        lift_defs(content["schema"],
                                  parent_namespace=f"{ns}__res__{status}",
                                  schemas=schemas, used_names=used_names)
            # parameters
            for param in op.get("parameters", []) or []:
                if isinstance(param, dict) and "schema" in param:
                    pname = param.get("name", "param")
                    lift_defs(param["schema"], parent_namespace=f"{ns}__param__{pname}",
                              schemas=schemas, used_names=used_names)

    # Pass 3: cleanup pass. Some `#/$defs/X` refs survive when the original
    # `$defs` block sat at a level outside the immediate parent that owned
    # the ref (FastAPI sometimes emits refs from nested `oneOf`/`anyOf` that
    # logically belong to a sibling's `$defs`). For each remaining ref, find
    # any flattened schema whose name ends in `__<X>` and use that.
    cleanup_orphan_refs(spec, schemas)

    # Sanity check
    text = json.dumps(spec)
    remaining_defs_blocks = text.count('"$defs"')
    remaining_defs_refs = text.count('"#/$defs/')
    if remaining_defs_blocks or remaining_defs_refs:
        print(
            f"WARNING: after flattening, {remaining_defs_blocks} $defs blocks and "
            f"{remaining_defs_refs} #/$defs/ refs remain. Generator may still fail.",
            file=sys.stderr,
        )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(spec, f)

    print(
        f"flattened: {len(schemas)} schemas in components/schemas; "
        f"{remaining_defs_blocks} $defs blocks remaining; "
        f"{remaining_defs_refs} #/$defs/ refs remaining"
    )
    return 0


def lift_defs(
    node: Any,
    *,
    parent_namespace: str,
    schemas: dict[str, Any],
    used_names: set[str],
) -> None:
    """Walk `node`, lift any `$defs` block into `schemas`, rewrite local `#/$defs/X` refs.

    `parent_namespace` becomes the prefix for flattened names (e.g.
    `parent_namespace="FlowRead"` lifts `$defs.SubModel` to
    `components.schemas.FlowRead__SubModel`).

    Safe to recurse — lifted child defs themselves get their `$defs` lifted too.
    """
    if isinstance(node, dict):
        if "$defs" in node:
            local_defs = node.pop("$defs")
            local_renames: dict[str, str] = {}
            for def_name, def_schema in local_defs.items():
                flat_name = unique_name(f"{parent_namespace}__{def_name}", used_names)
                used_names.add(flat_name)
                local_renames[def_name] = flat_name
                schemas[flat_name] = def_schema
                # Recurse into the lifted def — it might have its own $defs.
                lift_defs(def_schema, parent_namespace=flat_name,
                          schemas=schemas, used_names=used_names)
            # Now rewrite any `#/$defs/<name>` ref *within this node* to point at the lifted name.
            rewrite_local_defs_refs(node, local_renames)

        # Always recurse into all values — there can be more $defs deeper.
        for v in list(node.values()):
            lift_defs(v, parent_namespace=parent_namespace,
                      schemas=schemas, used_names=used_names)
    elif isinstance(node, list):
        for item in node:
            lift_defs(item, parent_namespace=parent_namespace,
                      schemas=schemas, used_names=used_names)


def cleanup_orphan_refs(node: Any, schemas: dict[str, Any]) -> None:
    """Final-pass rewrite of any `$ref: "#/$defs/X"` that survived earlier passes.

    Maps `X` to a schema in `schemas` whose name ends in `__X`. If multiple
    candidates exist, picks the shortest (least namespacing) — heuristically the
    most likely intended target. If none match, leaves the ref alone (the
    generator will report it).
    """
    suffix_index: dict[str, list[str]] = {}
    for full_name in schemas:
        if "__" in full_name:
            short = full_name.rsplit("__", 1)[1]
            suffix_index.setdefault(short, []).append(full_name)

    def visit(n: Any) -> None:
        if isinstance(n, dict):
            ref = n.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                want = ref[len("#/$defs/") :]
                if want in schemas:
                    n["$ref"] = f"#/components/schemas/{want}"
                else:
                    candidates = suffix_index.get(want, [])
                    if candidates:
                        # pick shortest = closest-to-root namespacing
                        n["$ref"] = f"#/components/schemas/{min(candidates, key=len)}"
            for v in n.values():
                visit(v)
        elif isinstance(n, list):
            for item in n:
                visit(item)

    visit(node)


def rewrite_local_defs_refs(node: Any, renames: dict[str, str]) -> None:
    """Within a subtree, rewrite `$ref: "#/$defs/<old>"` to `"#/components/schemas/<new>"`.

    Only rewrites refs that match a name in `renames` — refs to outer-scope `$defs`
    are left alone (their parent's lift_defs call will handle them).
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            old = ref[len("#/$defs/") :]
            if old in renames:
                node["$ref"] = f"#/components/schemas/{renames[old]}"
        for v in node.values():
            rewrite_local_defs_refs(v, renames)
    elif isinstance(node, list):
        for item in node:
            rewrite_local_defs_refs(item, renames)


def unique_name(base: str, used: set[str]) -> str:
    if base not in used:
        return base
    i = 2
    while f"{base}_{i}" in used:
        i += 1
    return f"{base}_{i}"


def make_path_namespace(path: str, method: str) -> str:
    # /api/v1/flows/{flow_id} + post -> ApiV1Flows_FlowId__post
    cleaned = []
    for seg in path.strip("/").split("/"):
        if not seg:
            continue
        if seg.startswith("{") and seg.endswith("}"):
            cleaned.append(seg[1:-1])
        else:
            cleaned.append(seg)
    name = "_".join(s.replace("-", "_").replace(".", "_") for s in cleaned)
    return f"{name}__{method}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

#!/usr/bin/env python3
"""Static checks for a Power Automate cloud flow file before packaging.

Accepts either a flow file ({"displayName", "definition", ...}) or a bare
Workflow Definition Language object ({"$schema", "triggers", "actions"}).

Usage: python validate_definition.py flow.json [flow2.json ...]
Exit code 0 = no errors (warnings allowed), 1 = errors found.

These are static checks only. They catch the mistakes that most often make
an import fail or a flow break on first run. They cannot prove that a
connector operation or parameter name is correct; the import and a test run
do that.
"""
import json
import re
import sys

NAME_RE = re.compile(r"^[A-Za-z0-9_\-\.]+$")
REF_RE = re.compile(r"\b(body|outputs|actions|items|result)\('([^']+)'\)")
PLACEHOLDER_RE = re.compile(r"<<[^<>]+>>")


def load_definition(doc):
    if isinstance(doc.get("definition"), dict):
        return doc.get("displayName", "(unnamed)"), doc["definition"]
    if "definition" in doc.get("properties", {}):
        return doc["properties"].get("displayName", "(unnamed)"), doc["properties"]["definition"]
    return "(bare definition)", doc


def walk(actions, scope_path, out):
    """Collect (name, action, sibling_names, scope_path) for every action, recursively."""
    if not isinstance(actions, dict):
        return
    siblings = set(actions.keys())
    for name, act in actions.items():
        out.append((name, act, siblings, scope_path))
        t = act.get("type")
        if t in ("Scope", "Foreach", "Until"):
            walk(act.get("actions", {}), scope_path + [name], out)
        elif t == "If":
            walk(act.get("actions", {}), scope_path + [name + "/yes"], out)
            walk(act.get("else", {}).get("actions", {}), scope_path + [name + "/no"], out)
        elif t == "Switch":
            for cname, case in act.get("cases", {}).items():
                walk(case.get("actions", {}), scope_path + [name + "/" + cname], out)
            walk(act.get("default", {}).get("actions", {}), scope_path + [name + "/default"], out)


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def check(path):
    errors, warnings = [], []
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f"== {path}")
        return [f"Cannot parse JSON: {e}"], []

    display, d = load_definition(doc)
    if "$schema" not in d:
        warnings.append("Definition has no $schema; the packager adds the standard one.")
    triggers = d.get("triggers", {})
    if len(triggers) != 1:
        errors.append(f"Expected exactly one trigger, found {len(triggers)}.")
    actions = d.get("actions", {})
    if not actions:
        errors.append("Definition has no actions.")

    all_actions = []
    walk(actions, [], all_actions)
    names = [n for n, *_ in all_actions] + list(triggers.keys())
    seen = set()
    for n in names:
        if n in seen:
            errors.append(f"Duplicate action name '{n}'. Names must be unique across the whole flow.")
        seen.add(n)
        if not NAME_RE.match(n):
            errors.append(f"Action name '{n}' has illegal characters. Use letters, digits and underscores.")
        if len(n) > 80:
            warnings.append(f"Action name '{n}' is long; the designer may truncate it.")

    foreach_names = {n for n, a, *_ in all_actions if a.get("type") == "Foreach"}
    for name, act, siblings, scope in all_actions:
        for dep, statuses in (act.get("runAfter") or {}).items():
            if dep not in siblings:
                where = "/".join(scope) or "root"
                errors.append(f"'{name}' runs after '{dep}', which is not in the same scope ({where}).")
            for s in statuses:
                if s not in ("Succeeded", "Failed", "Skipped", "TimedOut"):
                    errors.append(f"'{name}' has invalid runAfter status '{s}'.")
        t = act.get("type")
        if t in ("OpenApiConnection", "OpenApiConnectionWebhook"):
            host = act.get("inputs", {}).get("host", {})
            for key in ("apiId", "connectionName", "operationId"):
                if not host.get(key):
                    errors.append(f"'{name}' is a connector action without host.{key}.")
            if act.get("inputs", {}).get("authentication") != "@parameters('$authentication')":
                warnings.append(f"'{name}' should carry \"authentication\": \"@parameters('$authentication')\".")
        if t is None:
            errors.append(f"'{name}' has no type.")

    for trig_name, trig in triggers.items():
        if trig.get("type", "").startswith("OpenApiConnection"):
            host = trig.get("inputs", {}).get("host", {})
            if not host.get("operationId"):
                errors.append(f"Trigger '{trig_name}' has no host.operationId.")

    for s in strings(d):
        for fn, ref in REF_RE.findall(s):
            if fn == "items":
                if ref not in foreach_names:
                    errors.append(f"items('{ref}') refers to a loop that does not exist.")
            elif ref not in seen:
                errors.append(f"{fn}('{ref}') refers to an action that does not exist.")
        for block in re.findall(r"@\{(.*?)\}(?!\})", s):
            if block.count("(") != block.count(")"):
                errors.append(f"Unbalanced brackets in expression: @{{{block[:60]}}}")
        if s.startswith("@") and not s.startswith(("@@", "@{")):
            if s.count("(") != s.count(")"):
                errors.append(f"Unbalanced brackets in expression: {s[:60]}")

    placeholders = sorted({p for s in strings(d) for p in PLACEHOLDER_RE.findall(s)})
    if placeholders:
        warnings.append("Unresolved placeholders (acceptable in a template; must be set after import): "
                        + ", ".join(placeholders))

    print(f"== {path} :: {display}")
    print(f"   trigger: {', '.join(triggers) or '-'} | actions incl. nested: {len(all_actions)}")
    return errors, warnings


def main(paths):
    failed = False
    for p in paths:
        errors, warnings = check(p)
        for e in errors:
            print(f"   ERROR   {e}")
        for w in warnings:
            print(f"   WARNING {w}")
        if not errors:
            print("   OK")
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))

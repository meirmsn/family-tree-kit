"""Shared helpers for kit data migrations.

Migrations may only reshape data structures (add empty fields, rename keys, move
entries). They must never change relationships, facts, or confidence levels, and
never merge people. ``ensure_empty`` only appends a missing assignment. It does
not rewrite anything already in the file.
"""
import ast
import os


def spec_path(project):
    return os.path.join(project, "site", "people_spec.py")


def assigned_names(source):
    """Module-level assignment targets. Raises SyntaxError if ``source`` is not Python."""
    tree = ast.parse(source)
    names = set()
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def ensure_empty(project, fields, dry_run=False, intro=""):
    """Append ``name = expr`` for each missing module-level name.

    ``fields`` is an ordered sequence of ``(name, expr)`` pairs. ``expr`` is a
    Python literal source, usually ``"[]"`` or ``"{}"``. Returns short notes.
    No-op, and does not rewrite the file, when every name is already assigned.
    """
    path = spec_path(project)
    if not os.path.isfile(path):
        return ["no site/people_spec.py; skipped"]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        have = assigned_names(text)
    except SyntaxError as e:
        raise SystemExit(f"cannot parse {path}: {e}")
    missing = [(name, expr) for name, expr in fields if name not in have]
    if not missing:
        return ["already present"]
    if dry_run:
        return [f"would add {name} = {expr}" for name, expr in missing]
    lines = []
    if intro:
        lines.append(intro)
    lines.extend(f"{name} = {expr}" for name, expr in missing)
    prefix = text
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    if prefix and not prefix.endswith("\n\n"):
        prefix += "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(prefix + "\n".join(lines) + "\n")
    return [f"added {name} = {expr}" for name, expr in missing]

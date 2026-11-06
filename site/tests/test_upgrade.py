"""Upgrade a fictional project and run the real site build.

Run: python3 -m unittest discover -s site/tests
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.dirname(SITE)
TOOLS = os.path.join(KIT, "tools")

SHAPE = (
    "FAMILY_ASSERTIONS", "SIBLING_EXCLUSIONS", "CANONICAL_ALIASES",
    "NAME_FORMS", "POSSIBLE_MATCHES", "MATCH_EXCLUSIONS",
)


def run_tool(tool, *args):
    r = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def remove_assignments(text, names):
    tree = ast.parse(text)
    drop = set()
    for node in tree.body:
        ids = []
        if isinstance(node, ast.Assign):
            ids = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if any(i in names for i in ids):
            drop.update(range(node.lineno - 1, node.end_lineno))
    lines = text.splitlines(keepends=True)
    return "".join(line for i, line in enumerate(lines) if i not in drop)


class UpgradeBuild(unittest.TestCase):
    def test_upgrade_then_build_and_a_second_run_is_idle(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        project = os.path.join(tmp, "tree")
        code, out = run_tool("new_project.py", project, "--home-person", "Nia Pell")
        self.assertEqual(code, 0, out)
        spec = os.path.join(project, "site", "people_spec.py")
        before_people = read(os.path.join(project, "people.md"))
        before_rel = read(os.path.join(project, "relationships.md"))
        write(spec, remove_assignments(read(spec), SHAPE))
        os.remove(os.path.join(project, "KIT_VERSION"))

        code, out = run_tool("upgrade.py", project)
        self.assertEqual(code, 0, out)
        self.assertIn("added FAMILY_ASSERTIONS = []", out)
        self.assertIn("added NAME_FORMS = {}", out)
        self.assertIn("build: ok", out)
        self.assertIn("summary: ok", out)
        self.assertEqual(read(os.path.join(project, "KIT_VERSION")).strip(), "0.2.18")
        self.assertTrue(os.path.isfile(os.path.join(project, ".work", "site-build", "index.html")))
        backup_line = next(ln for ln in out.splitlines() if ln.startswith("backup: "))
        dst = backup_line.split("backup: ", 1)[1].split("  (", 1)[0]
        root = os.path.realpath(project)
        self.assertTrue(os.path.realpath(dst).startswith(root + os.sep))
        self.assertEqual(read(os.path.join(project, "people.md")), before_people)
        self.assertEqual(read(os.path.join(project, "relationships.md")), before_rel)
        upgraded = read(spec)

        code, again = run_tool("upgrade.py", project)
        self.assertEqual(code, 0, again)
        self.assertIn("migration: none", again)
        self.assertIn("build: ok", again)
        self.assertEqual(read(spec), upgraded)
        self.assertEqual(read(os.path.join(project, "people.md")), before_people)

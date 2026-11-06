"""Upgrade command and data-shape migrations. Fictional projects only.

Run: python3 -m unittest discover -s tools/tests
"""
import ast
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(KIT, "migrations"))
import common  # noqa: E402
import upgrade  # noqa: E402

SHAPE = (
    "FAMILY_ASSERTIONS", "SIBLING_EXCLUSIONS", "CANONICAL_ALIASES",
    "NAME_FORMS", "POSSIBLE_MATCHES", "MATCH_EXCLUSIONS",
)


def run(tool, *args):
    r = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def call(project, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = upgrade.upgrade(project, **kwargs)
    return code, buf.getvalue()


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
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            ids = [node.target.id]
        if any(i in names for i in ids):
            drop.update(range(node.lineno - 1, node.end_lineno))
    lines = text.splitlines(keepends=True)
    return "".join(line for i, line in enumerate(lines) if i not in drop)


def assignment_source(text, name):
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.get_source_segment(text, node)
    return None


def spec_path(project):
    return os.path.join(project, "site", "people_spec.py")


class Upgrade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = os.path.join(self.tmp, "tree")
        code, out = run("new_project.py", self.project, "--home-person", "Nia Pell")
        self.assertEqual(code, 0, out)
        rel = os.path.join(self.project, "relationships.md")
        with open(rel, "a", encoding="utf-8") as f:
            f.write("\n- Nia Pell's father is Otto Pell (U1, lore)\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _strip(self, names, drop_version=True):
        path = spec_path(self.project)
        write(path, remove_assignments(read(path), names))
        if drop_version:
            version = os.path.join(self.project, "KIT_VERSION")
            if os.path.exists(version):
                os.remove(version)

    def test_new_project_records_kit_version_and_empty_fields(self):
        kit = read(os.path.join(KIT, "VERSION")).strip()
        self.assertEqual(read(os.path.join(self.project, "KIT_VERSION")).strip(), kit)
        self.assertEqual(kit, "0.2.18")
        have = common.assigned_names(read(spec_path(self.project)))
        for name in SHAPE:
            self.assertIn(name, have)

    def test_migrations_are_idempotent_and_do_not_touch_facts(self):
        people = read(os.path.join(self.project, "people.md"))
        relationships = read(os.path.join(self.project, "relationships.md"))
        sources = read(os.path.join(self.project, "sources.md"))
        self.assertIn("Otto Pell (U1, lore)", relationships)
        self._strip(SHAPE)
        path = spec_path(self.project)
        before = read(path)
        people_src = assignment_source(before, "PEOPLE")
        fields_src = assignment_source(before, "FIELDS")
        self.assertIn('conf="confirmed"', people_src)

        code, out = call(self.project, check=False)
        self.assertEqual(code, 0, out)
        self.assertIn("added FAMILY_ASSERTIONS = []", out)
        self.assertIn("added SIBLING_EXCLUSIONS = []", out)
        self.assertIn("added CANONICAL_ALIASES = {}", out)
        self.assertIn("added NAME_FORMS = {}", out)
        self.assertIn("added POSSIBLE_MATCHES = []", out)
        self.assertIn("added MATCH_EXCLUSIONS = []", out)
        once = read(path)
        self.assertTrue(once.startswith(before.rstrip("\n")))
        self.assertEqual(assignment_source(once, "PEOPLE"), people_src)
        self.assertEqual(assignment_source(once, "FIELDS"), fields_src)
        self.assertEqual(assignment_source(once, "CANONICAL_ALIASES"), "CANONICAL_ALIASES = {}")
        self.assertEqual(read(os.path.join(self.project, "people.md")), people)
        self.assertEqual(read(os.path.join(self.project, "relationships.md")), relationships)
        self.assertEqual(read(os.path.join(self.project, "sources.md")), sources)

        # Version stamp lost after the migration ran: a second pass must not change data.
        os.remove(os.path.join(self.project, "KIT_VERSION"))
        code, again = call(self.project, check=False)
        self.assertEqual(code, 0, again)
        self.assertEqual(read(path), once)
        self.assertIn("already present", again)
        self.assertEqual(read(os.path.join(self.project, "people.md")), people)
        self.assertEqual(read(os.path.join(self.project, "relationships.md")), relationships)

        for _ver, text, mig in upgrade.list_migrations():
            notes = upgrade.load_migration(mig, text).apply(self.project, dry_run=False)
            self.assertEqual(notes, ["already present"])
        self.assertEqual(read(path), once)

    def test_present_fields_are_a_noop_and_are_not_merged(self):
        path = spec_path(self.project)
        text = read(path)
        text = text.replace("CANONICAL_ALIASES = {}", 'CANONICAL_ALIASES = {"alias-nia": "p1"}')
        text = text.replace(
            "POSSIBLE_MATCHES = []",
            'POSSIBLE_MATCHES = [{"a": "p1", "b": "nia-index", "sources": ["U1"], "note": "not merged"}]')
        text = text.replace(
            "FAMILY_ASSERTIONS = []",
            'FAMILY_ASSERTIONS = [{"type": "sibling", "a": "p1", "b": "p4", "c": "lore", "s": ["U1"], "label": "Sister"}]')
        write(path, text)
        self._strip(("SIBLING_EXCLUSIONS", "NAME_FORMS", "MATCH_EXCLUSIONS"))
        aliases = assignment_source(read(path), "CANONICAL_ALIASES")
        matches = assignment_source(read(path), "POSSIBLE_MATCHES")
        assertions = assignment_source(read(path), "FAMILY_ASSERTIONS")
        code, out = call(self.project, check=False)
        self.assertEqual(code, 0, out)
        after = read(path)
        self.assertEqual(assignment_source(after, "CANONICAL_ALIASES"), aliases)
        self.assertEqual(assignment_source(after, "POSSIBLE_MATCHES"), matches)
        self.assertEqual(assignment_source(after, "FAMILY_ASSERTIONS"), assertions)
        self.assertIn('{"alias-nia": "p1"}', after)
        self.assertIn("not merged", after)
        self.assertIn("added SIBLING_EXCLUSIONS = []", out)
        self.assertIn("added NAME_FORMS = {}", out)
        self.assertNotIn("added CANONICAL_ALIASES", out)
        self.assertNotIn("added POSSIBLE_MATCHES", out)
        self.assertNotIn("added FAMILY_ASSERTIONS", out)
        os.remove(os.path.join(self.project, "KIT_VERSION"))
        code, again = call(self.project, check=False)
        self.assertEqual(code, 0, again)
        self.assertEqual(read(path), after)

    def test_version_gate_runs_only_newer_migrations(self):
        self._strip(("NAME_FORMS", "POSSIBLE_MATCHES", "MATCH_EXCLUSIONS"))
        write(os.path.join(self.project, "KIT_VERSION"), "0.2.16\n")
        code, out = call(self.project, check=False)
        self.assertEqual(code, 0, out)
        self.assertNotIn("migration v0.2.16", out)
        self.assertIn("migration v0.2.17", out)
        self.assertIn("added NAME_FORMS = {}", out)
        self.assertEqual(read(os.path.join(self.project, "KIT_VERSION")).strip(), "0.2.18")

    def test_current_version_runs_no_migrations(self):
        spec = read(spec_path(self.project))
        code, out = call(self.project, check=False)
        self.assertEqual(code, 0, out)
        self.assertIn("migration: none", out)
        self.assertEqual(read(spec_path(self.project)), spec)
        self.assertEqual(read(os.path.join(self.project, "KIT_VERSION")).strip(), "0.2.18")

    def test_dry_run_writes_nothing(self):
        self._strip(SHAPE)
        spec = read(spec_path(self.project))
        code, out = run("upgrade.py", self.project, "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("(dry-run)", out)
        self.assertIn("would add FAMILY_ASSERTIONS = []", out)
        self.assertIn("would add NAME_FORMS = {}", out)
        self.assertIn("would write KIT_VERSION 0.2.18", out)
        self.assertIn("would run: check_ids, site build", out)
        self.assertIn("no files written", out)
        self.assertEqual(read(spec_path(self.project)), spec)
        self.assertFalse(os.path.exists(os.path.join(self.project, "KIT_VERSION")))
        self.assertEqual(os.listdir(os.path.join(self.project, ".backups")), [])

    def test_backup_is_inside_the_project_and_predates_the_migration(self):
        self._strip(SHAPE)
        code, out = call(self.project, check=False)
        self.assertEqual(code, 0, out)
        line = next(ln for ln in out.splitlines() if ln.startswith("backup: "))
        dst = line.split("backup: ", 1)[1].split("  (", 1)[0]
        root = os.path.realpath(self.project)
        self.assertTrue(os.path.realpath(dst).startswith(root + os.sep))
        self.assertIn(os.sep + ".backups" + os.sep, os.path.realpath(dst))
        backed = read(os.path.join(dst, "site", "people_spec.py"))
        self.assertNotIn("FAMILY_ASSERTIONS", backed)
        self.assertNotIn("NAME_FORMS", backed)
        self.assertIn("FAMILY_ASSERTIONS = []", read(spec_path(self.project)))
        self.assertFalse(os.path.exists(os.path.join(dst, "KIT_VERSION")))
        self.assertTrue(os.path.isfile(os.path.join(dst, "people.md")))
        self.assertIn("Otto Pell (U1, lore)", read(os.path.join(dst, "relationships.md")))

    def test_cli_exits_nonzero_when_check_ids_fails(self):
        os.remove(os.path.join(self.project, "site", "site.config.json"))
        with open(os.path.join(self.project, "people.md"), "a", encoding="utf-8") as f:
            f.write("\n- Sibling: P99 (U1, lore)\n")
        code, out = run("upgrade.py", self.project)
        self.assertNotEqual(code, 0)
        self.assertIn("ERROR", out)
        self.assertIn("P99", out)
        self.assertIn("check_ids: FAILED", out)
        self.assertIn("summary: FAILED", out)
        self.assertIn("restore: ", out)
        kids = os.listdir(os.path.join(self.project, ".backups"))
        self.assertTrue(kids)

    def test_build_failure_exits_nonzero(self):
        path = spec_path(self.project)
        write(path, read(path).replace("LINES = {", "LINES_REMOVED = {", 1))
        code, out = run("upgrade.py", self.project)
        self.assertNotEqual(code, 0)
        self.assertIn("build: FAILED", out)
        self.assertIn("LINES", out)
        self.assertIn("summary: FAILED", out)

    def test_refuses_a_non_project_and_a_bad_version(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        code, out = call(empty, check=False)
        self.assertEqual(code, 1)
        self.assertIn("not a project", out)
        spec = read(spec_path(self.project))
        write(os.path.join(self.project, "KIT_VERSION"), "nope\n")
        code, out = call(self.project, check=False)
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)
        self.assertEqual(read(spec_path(self.project)), spec)

    def test_unparseable_spec_does_not_stamp_the_version(self):
        self._strip(SHAPE)
        path = spec_path(self.project)
        write(path, read(path) + "\nFAMILY_ASSERTIONS = [\n")
        code, out = call(self.project, check=False)
        self.assertEqual(code, 1, out)
        self.assertIn("cannot parse", out)
        self.assertIn("summary: FAILED", out)
        self.assertFalse(os.path.exists(os.path.join(self.project, "KIT_VERSION")))
        self.assertTrue(os.listdir(os.path.join(self.project, ".backups")))

    def test_migration_files_are_ordered_and_name_their_version(self):
        found = upgrade.list_migrations()
        texts = [text for _ver, text, _path in found]
        self.assertEqual(texts, sorted(texts, key=upgrade.parse_version))
        self.assertIn("0.2.16", texts)
        self.assertIn("0.2.17", texts)
        for _ver, text, path in found:
            self.assertEqual(upgrade.load_migration(path, text).VERSION, text)

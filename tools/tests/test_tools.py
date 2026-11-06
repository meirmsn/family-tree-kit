"""Tests for the project tools. Run: python3 -m unittest discover -s tools/tests"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import gklib  # noqa: E402
import migrate_helper  # noqa: E402
import rescue_scans  # noqa: E402


def run(tool, *args):
    r = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def new_project(path, *extra):
    code, out = run("new_project.py", path, "--home-person", "Test Person", *extra)
    assert code == 0, out
    return path


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


SIDECAR = """---
s_number: {s}
title: "t"
date: ""
place: ""
record_type: "birth"
language: "Polish"
archive_ref: ""
archive_unit: "123456"
url: ""
image_files:
  - "{img}"
people:
  - {{id: P1, name: "Test Person", role: "subject"}}
facts_supported: []
related_sources: []
translation_status: "{status}"
collateral: false
---
# {s}

## Why this record matters

x

## Transcription

{tr}
"""


class NewProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_marker_config_and_nesting_refused(self):
        p = new_project(os.path.join(self.tmp, "trees", "a"))
        self.assertTrue(os.path.exists(os.path.join(p, gklib.MARKER)))
        cfg = open(os.path.join(p, "site", "site.config.json")).read()
        self.assertIn("../.work/site-build", cfg)
        self.assertNotIn("genealogy-builds", cfg)
        code, out = run("new_project.py", os.path.join(p, "inner"), "--home-person", "X")
        self.assertNotEqual(code, 0)
        self.assertIn("inside another project", out)
        # an older project without the marker (people.md + sources.md) also counts
        legacy = os.path.join(self.tmp, "legacy")
        write(os.path.join(legacy, "people.md"), "# People\n")
        write(os.path.join(legacy, "sources.md"), "# Sources\n")
        code, out = run("new_project.py", os.path.join(legacy, "nested-tree"), "--home-person", "X")
        self.assertNotEqual(code, 0)

    def test_home_person_comma_warns_and_old_flag_works(self):
        code, out = run("new_project.py", os.path.join(self.tmp, "b"), "--home-person", "Port Sallow, Ardenia")
        self.assertEqual(code, 0)
        self.assertIn("comma", out)
        code, out = run("new_project.py", os.path.join(self.tmp, "c"), "--home", "Old Flag")
        self.assertEqual(code, 0)
        self.assertIn("## P1 Old Flag", open(os.path.join(self.tmp, "c", "people.md")).read())


class Validator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = new_project(os.path.join(self.tmp, "t"))

    def people(self, extra=""):
        write(os.path.join(self.p, "people.md"), "# People\n\n## P1 Test Person\n- Born 1900 (S1, confirmed)\n\n"
              "## P2 Other\n- Father of P1 (S1, confirmed)\n" + extra)

    def sources(self, extra=""):
        write(os.path.join(self.p, "sources.md"), "# Sources\n\n- S1 — **A record** — x (confirmed)\n"
              "- U1 — **Interview** — y\n" + extra)

    def test_unused_rule(self):
        self.people("\nUnused: P3 (merged into P2)\n\n## P4 Third\n- x (S1)\n")
        self.sources()
        code, out = run("check_ids.py", self.p)
        self.assertEqual(code, 0, out)
        self.assertNotIn("undeclared unused", out)
        # another mention of a declared-unused number is a warning, not an error
        write(os.path.join(self.p, "research-log.md"), "# Log\n- P3 retired in pass 2\n")
        code, out = run("check_ids.py", self.p)
        self.assertEqual(code, 0, out)
        self.assertIn("declared unused but mentioned", out)
        # an undeclared mention of a missing number is an error
        write(os.path.join(self.p, "research-log.md"), "# Log\n- P9 something\n")
        code, out = run("check_ids.py", self.p)
        self.assertEqual(code, 1)
        # declaring a defined number is an error; ranges are expanded
        self.people("\n- Unused: P2–P3\n")
        write(os.path.join(self.p, "research-log.md"), "# Log\n")
        code, out = run("check_ids.py", self.p)
        self.assertEqual(code, 1)
        self.assertIn("P2 is declared on an 'Unused:' line but is defined", out)

    def test_placeholder_is_not_a_transcription(self):
        self.people()
        self.sources("- S2 — **B** — z\n- S3 — **C** — z\n")
        d = os.path.join(self.p, "records", "line")
        for s in ("S1", "S2", "S3"):
            write(os.path.join(d, f"{s}.jpg"), "x")
        write(os.path.join(d, "S1.md"), SIDECAR.format(s="S1", img="S1.jpg", status="done",
                                                       tr="Not transcribed in the source project; see the summary."))
        write(os.path.join(d, "S2.md"), SIDECAR.format(s="S2", img="S2.jpg", status="pending", tr="_(not transcribed)_"))
        write(os.path.join(d, "S3.md"), SIDECAR.format(s="S3", img="S3.jpg", status="no image", tr="Nr 5. Real text"))
        code, out = run("check_ids.py", self.p)
        self.assertIn("S1.md: translation_status done but no transcription", out)
        self.assertNotIn("S2.md: translation_status", out)
        self.assertIn("S3.md: has image_files but translation_status is 'no image'", out)
        self.assertIn("with a real transcription: 1; status pending: 1", out)
        for t in ("_(not transcribed)_", "Not transcribed in the source project", "See summary.", "pending", ""):
            self.assertTrue(gklib.is_placeholder(t), t)
        self.assertFalse(gklib.is_placeholder("Nr 7. Kestrava, 12 June 1921"))

    def test_nested_project_not_mixed(self):
        self.people()
        self.sources()
        inner = os.path.join(self.p, "records", "old-copy")
        write(os.path.join(inner, gklib.MARKER), "{}")
        write(os.path.join(inner, "people.md"), "## P77 Someone else\n- (S99)\n")
        write(os.path.join(inner, "sources.md"), "- S99 — **x** — y\n")
        code, out = run("check_ids.py", self.p)
        self.assertEqual(code, 0, out)
        self.assertIn("skipped nested project records/old-copy/", out)
        self.assertNotIn("P77", out)

    def test_spec_lines_and_collapse(self):
        self.people("\n## P3 M\n- (S1)\n## P4 GF\n- (S1)\n## P5 GGF\n- (S1)\n")
        self.sources()
        spec = os.path.join(self.p, "site", "people_spec.py")
        write(spec, "PEOPLE = [\n"
              " dict(id='p1', pid='P1', name='A', sex='F', child=None, line='root', conf='confirmed', src=['U1']),\n"
              " dict(id='p2', pid='P2', name='B', sex='M', child='p1', line='paternal', conf='confirmed', src=['S1']),\n"
              " dict(id='p3', pid='P3', name='C', sex='F', child='p1', line='maternal', conf='confirmed', src=['S1']),\n"
              " dict(id='p4', pid='P4', name='D', sex='M', child='p2', line='pm', conf='confirmed', src=['S1']),\n"
              " dict(id='p5', pid='P5', name='E', sex='M', child=['p4', 'p6'], line='pm', conf='confirmed', src=['S1']),\n"
              " dict(id='p6', name='F', sex='M', child='p3', line='mp', conf='confirmed', src=['S1']),\n"
              "]\nPSEUDO_SOURCES = {'U1': {}}\n")
        code, out = run("check_ids.py", self.p, "--spec", spec)
        self.assertEqual(code, 1)
        self.assertIn("spec p4: line 'pm' but expected 'pp'", out)
        self.assertNotIn("spec p5: line", out)          # p5 follows its (wrong) child: one error, at the source
        self.assertIn("pedigree collapse", out)

    def test_links_parents_line_not_a_mismatch(self):
        write(os.path.join(self.p, "people.md"), "## P1 A\n- Parents: P2 B and P3 C (S1, confirmed)\n"
              "## P2 B\n- x (U1)\n## P3 C\n- x (U1)\n")
        self.sources()
        write(os.path.join(self.p, "records", "sources", "S1.md"),
              SIDECAR.format(s="S1", img="", status="no image", tr="").replace('  - ""\n', "").replace(
                  "image_files:\n", "image_files: []\n"))
        code, out = run("sidecars.py", "links", self.p)
        self.assertIn("0 source(s) with a people mismatch", out)

    def test_stub_place_is_empty(self):
        self.people()
        write(os.path.join(self.p, "sources.md"), "# Sources\n\n## Old Town (Archive 12/345)\n- S1 — **A record** — x\n- U1 — **I** — y\n")
        run("sidecars.py", "stubs", self.p)
        self.assertIn('place: ""', open(os.path.join(self.p, "records", "sources", "S1.md")).read())


DU = namedtuple("DU", "total used free")


class RescueScans(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = new_project(os.path.join(self.tmp, "proj"))
        self.src = os.path.join(self.tmp, "scans")
        big = b"x" * 40000
        write(os.path.join(self.src, "a", "4401234_3_mid.jpg"), "m" * 30000)
        os.makedirs(os.path.join(self.src, "b"))
        for name, data in (("4401234_3.jpg", big + b"1"), ("4401234_4.jpg", big + b"2"), ("999999_1.jpg", big + b"3"),
                           ("4401234_5.jpg", big + b"2"), ("tiny_4401234_9.jpg", b"t"), ("holiday.jpg", big + b"9")):
            with open(os.path.join(self.src, "b", name), "wb") as f:
                f.write(data)
        # another family's project inside the scan folder must never be read
        other = os.path.join(self.src, "other-tree")
        write(os.path.join(other, "people.md"), "x")
        write(os.path.join(other, "sources.md"), "x")
        with open(os.path.join(other, "4401234_7.jpg"), "wb") as f:
            f.write(big)
        self.notes = os.path.join(self.tmp, "notes.md")
        write(self.notes, "Born 1837 (unit 4401234, scan 3): https://example.org/x\n")

    def call(self, *args, free=100 * 1024 ** 3):
        buf = io.StringIO()
        du = DU(200 * 1024 ** 3, 0, free)
        with mock.patch.object(rescue_scans.shutil, "disk_usage", lambda p: du), contextlib.redirect_stdout(buf):
            try:
                code = rescue_scans.main([self.p, self.src, "--units-from", self.notes, *args])
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else str(e.code)
        return code, buf.getvalue()

    def test_inventory_dedupes_filters_and_skips_projects(self):
        code, out = self.call("--list")
        self.assertEqual(code, 0)
        self.assertIn("1 same unit+scan", out)          # _mid vs full: largest kept
        self.assertIn("1 identical content", out)        # 4401234_4 and _5 have the same bytes
        self.assertIn("cited scan:      1 file(s)", out)
        self.assertNotIn("999999", out.split("to copy")[1])   # not a hinted unit
        self.assertNotIn("4401234_7", out)               # inside another project
        self.assertIn("other-tree", out)
        self.assertFalse(os.path.exists(os.path.join(self.p, "records", "_inbox")))   # dry run writes nothing

    def test_refuses_below_margin_then_copies_in_batches_and_resumes(self):
        code, out = self.call("--copy", free=5 * 1024 ** 3)       # margin is max(5 GB, 5% of 200 GB) = 10 GB
        self.assertIsInstance(code, str)
        self.assertIn("refusing to copy", code)
        code, out = self.call("--copy", "--batch", "1", "--archive", "szwa")
        self.assertEqual(code, 0, out)
        inbox = os.path.join(self.p, "records", "_inbox")
        self.assertTrue(os.path.exists(os.path.join(inbox, "szwa_4401234", "szwa_4401234_0003.jpg")))
        self.assertEqual(os.path.getsize(os.path.join(inbox, "szwa_4401234", "szwa_4401234_0003.jpg")), 40001)
        rows = open(os.path.join(inbox, "MANIFEST.tsv")).read().splitlines()
        self.assertEqual(len(rows), 1 + 2)
        self.assertIn("batch 2:", out)
        code, out = self.call("--copy")
        self.assertIn("to copy: 0 file(s)", out)


class Migrate(unittest.TestCase):
    def test_sources_and_people_drafts_only_in_work(self):
        tmp = tempfile.mkdtemp()
        p = new_project(os.path.join(tmp, "proj"))
        old = os.path.join(tmp, "old")
        write(os.path.join(old, "tree.md"), "# Tree\n## Generation 2\n- **Ann Example**: mother. Born 1900. [LORE]\n"
              "  - CONFIRMED: birth act (unit 1234567, scan 4): https://example.org/a\n"
              "- **Bob Example**: father. PROBABLE https://example.org/b and again https://example.org/a\n")
        write(os.path.join(old, "tree.md.bak3"), "old")
        before = open(os.path.join(p, "sources.md")).read()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            migrate_helper.main(["inventory", old])
            migrate_helper.main(["sources", p, os.path.join(old, "tree.md")])
        self.assertIn("1 *.bakNN", out.getvalue())
        self.assertIn("2 distinct URL(s)", out.getvalue())
        self.assertFalse(os.path.exists(os.path.join(p, ".work", "migration")))
        with contextlib.redirect_stdout(io.StringIO()):
            migrate_helper.main(["sources", p, os.path.join(old, "tree.md"), "--write"])
            migrate_helper.main(["people", p, os.path.join(old, "tree.md"), "--write",
                                 "--home-person", "Ann Example"])
            migrate_helper.main(["snapshot", old, p, "--write"])
        d = os.path.join(p, ".work", "migration")
        draft = open(os.path.join(d, "sources-draft.md")).read()
        self.assertIn("(confirmed;", draft)
        self.assertIn("1234567", open(os.path.join(d, "url-map.tsv")).read())
        people = open(os.path.join(d, "people-draft.md")).read()
        self.assertIn("## P1 Ann Example", people)       # --home-person merges into P1
        self.assertIn("## P2 Bob Example", people)
        self.assertIn("← lore", people)                  # per-fact labels
        self.assertIn("← confirmed", people)
        self.assertNotIn("Generation", people)
        self.assertEqual(open(os.path.join(p, "sources.md")).read(), before)   # never touched
        snaps = [x for x in os.listdir(d) if x.startswith("snapshot-")]
        self.assertTrue(os.path.exists(os.path.join(d, snaps[0], "tree.md.bak3")))

    def test_archive_units(self):
        u, pairs = gklib.archive_units("units 20500100-2, 20500300; unit 4401234, scan 03; "
                                       "https://x/jednostka/-/jednostka/777777 sygn. 12/345")
        self.assertEqual(u, {"20500100", "20500101", "20500102", "20500300", "4401234", "777777"})
        self.assertEqual(pairs, {("4401234", "3")})



    def test_label_qualifiers_and_index_urls(self):
        self.assertEqual(migrate_helper.map_label("SPECULATIVE parents"), "possible; conflict")
        self.assertEqual(migrate_helper.map_label("UNVERIFIED fact"), "possible; unverified after audit")
        self.assertEqual(migrate_helper.map_label("POSSIBLE match"), "possible")
        self.assertEqual(migrate_helper.map_label("x", "https://geneteka.genealodzy.pl/?nazwisko=X"),
                         "lead; index only")

    def test_renumber_drafts(self):
        tmp = tempfile.mkdtemp()
        p = new_project(os.path.join(tmp, "proj"))
        d = os.path.join(p, ".work", "migration")
        os.makedirs(d, exist_ok=True)
        write(os.path.join(d, "sources-draft.md"),
              "# Draft\n\n- S1 — **A** — http://a\n- S5 — **B** — http://b\n- S12 — **C** — http://c\n")
        write(os.path.join(d, "url-map.tsv"),
              "s\turl\tunit\trefs\nS1\thttp://a\t\tr\nS5\thttp://b\t\tr\nS12\thttp://c\t\tr\n")
        write(os.path.join(d, "people-draft.md"),
              "# Draft\n\n## P1 Home\n- x\n\n## P4 Other\n- y\n\n## P9 Third\n- z\n")
        with contextlib.redirect_stdout(io.StringIO()):
            migrate_helper.main(["renumber-drafts", p, "--write", "--sources-start", "1"])
        src = open(os.path.join(d, "sources-draft.md")).read()
        self.assertIn("- S1 — **A**", src)
        self.assertIn("- S2 — **B**", src)
        self.assertIn("- S3 — **C**", src)
        self.assertNotIn("S5", src)
        self.assertNotIn("S12", src)
        tsv = open(os.path.join(d, "url-map.tsv")).read()
        self.assertIn("S2\thttp://b", tsv)
        peo = open(os.path.join(d, "people-draft.md")).read()
        self.assertIn("## P1 Home", peo)
        self.assertIn("## P2 Other", peo)
        self.assertIn("## P3 Third", peo)
        baks = [x for x in os.listdir(d) if x.startswith("renumber-bak-")]
        self.assertTrue(baks, "renumber-drafts --write must back up drafts first")

    def _people_drafts(self):
        tmp = tempfile.mkdtemp()
        p = new_project(os.path.join(tmp, "proj"))
        d = os.path.join(p, ".work", "migration")
        os.makedirs(d, exist_ok=True)
        write(os.path.join(d, "people-draft.md"), "# Draft\n\n## P1 Home\n\n## P4 Other\n\n## P9 Third\n")
        return p, d

    def test_renumber_people_start_below_2_refused(self):
        for start in ("1", "0", "-3"):
            p, d = self._people_drafts()
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    migrate_helper.main(["renumber-drafts", p, "--write", "--people-start", start])
            self.assertIn("people-start", str(cm.exception))
            peo = open(os.path.join(d, "people-draft.md")).read()
            self.assertIn("## P4 Other", peo)  # untouched

    def test_renumber_duplicate_target_refused(self):
        p, d = self._people_drafts()
        write(os.path.join(d, "people-draft.md"), "# Draft\n\n## P1 Home\n\n## P1 Dup\n")
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                migrate_helper.main(["renumber-drafts", p, "--write"])
        self.assertIn("same id", str(cm.exception))
        self.assertIn("P1", str(cm.exception))

    def test_renumber_drafts_chain_ids_and_dropped_urlmap(self):
        """S3 and S9 must stay distinct (no sequential S9→S3→S2); dropped S rows leave url-map."""
        tmp = tempfile.mkdtemp()
        p = new_project(os.path.join(tmp, "chain"))
        d = os.path.join(p, ".work", "migration")
        os.makedirs(d, exist_ok=True)
        # Keep S1,S3,S9,S10,S40 — new numbers overlap old ones (the chain case).
        write(os.path.join(d, "sources-draft.md"),
              "# Draft\n\n"
              "- S1 — **A** — http://a\n"
              "- S3 — **B** — http://b\n"
              "- S9 — **C** — http://c\n"
              "- S10 — **D** — http://d\n"
              "- S40 — **E** — http://e\n")
        write(os.path.join(d, "url-map.tsv"),
              "s\turl\tunit\trefs\n"
              "S1\thttp://a\t\tr\n"
              "S2\thttp://dropped\t\tr\n"
              "S3\thttp://b\t\tr\n"
              "S9\thttp://c\t\tr\n"
              "S10\thttp://d\t\tr\n"
              "S40\thttp://e\t\tr\n"
              "S99\thttp://also-dropped\t\tr\n")
        write(os.path.join(d, "people-draft.md"), "# Draft\n\n## P1 Home\n- x\n")
        # No --sources-start: must not crash (AttributeError on .start)
        with contextlib.redirect_stdout(io.StringIO()):
            migrate_helper.main(["renumber-drafts", p, "--write"])
        src = open(os.path.join(d, "sources-draft.md")).read()
        self.assertIn("- S1 — **A**", src)
        self.assertIn("- S2 — **B**", src)
        self.assertIn("- S3 — **C**", src)
        self.assertIn("- S4 — **D**", src)
        self.assertIn("- S5 — **E**", src)
        # Chain bug would turn S9 and S3 both into S2
        self.assertEqual(src.count("- S2 —"), 1)
        self.assertEqual(src.count("- S3 —"), 1)
        self.assertNotIn("S9", src)
        self.assertNotIn("S40", src)
        tsv = open(os.path.join(d, "url-map.tsv")).read().splitlines()
        sids = [ln.split("\t")[0] for ln in tsv[1:] if ln.strip()]
        self.assertEqual(sids, ["S1", "S2", "S3", "S4", "S5"])
        self.assertNotIn("dropped", open(os.path.join(d, "url-map.tsv")).read())
        self.assertEqual(len(sids), len(set(sids)), "url-map must not have duplicate S ids")

    def test_fact_lines_needs_label_marker(self):
        lines = migrate_helper._fact_lines(["born 1900", "CONFIRMED death 1950"])
        self.assertIn("← needs label", lines[0])
        self.assertIn("← confirmed", lines[1])

    def test_new_project_seeds_per_project_private_words(self):
        tmp = tempfile.mkdtemp()
        # Do not touch any shared ~/.config list; only the project path.
        p = new_project(os.path.join(tmp, "pw"), "--home-person", "Ada Exampleton")
        pw = os.path.join(p, ".work", "private-words.txt")
        self.assertTrue(os.path.exists(pw))
        body = open(pw).read()
        self.assertIn("Exampleton", body)
        self.assertIn("Ada", body)

    def test_privacy_ignores_short_words_whole_word_only(self):
        tmp = tempfile.mkdtemp()
        p = new_project(os.path.join(tmp, "priv"))
        words = os.path.join(tmp, "words.txt")
        write(words, "cat\ndog\nZebraTown\n")  # cat/dog < 5; ZebraTown is the real hit
        open(os.path.join(p, "leads.md"), "a").write("\nThe catalog of dogs and cats in ZebraTown.\n")
        code, out = run("privacy_grep.py", p, "--words", words)
        self.assertEqual(code, 1, out)
        # After filtering <5-letter words, ZebraTown is the only loaded word (#1).
        self.assertIn("private word #1", out)
        self.assertIn("(9 chars)", out)  # len("ZebraTown")
        self.assertRegex(out, r"1 hit")


    def test_privacy_matches_simple_suffixes(self):
        tmp = tempfile.mkdtemp()
        p = new_project(os.path.join(tmp, "priv2"))
        words = os.path.join(tmp, "words.txt")
        write(words, "Zebratown\n")
        open(os.path.join(p, "leads.md"), "a").write(
            "\nzebratowners. Zebratown's. ZEBRATOWNS. zebratownes. zebratownish ok.\n")
        code, out = run("privacy_grep.py", p, "--words", words)
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"\b4 hit\(s\)")



class SpecOtherFamilyAndNotes(unittest.TestCase):
    """Fictional fixtures only: OTHER_FAMILY coverage + process-word note lint."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = new_project(os.path.join(self.tmp, "t"))
        write(os.path.join(self.p, "people.md"),
              "# People\n\n## P1 Rowan Ashdown\n- Born 1900 (S1, confirmed)\n"
              "- Sister: Ida (S1, confirmed)\n- Brother: Tomas (S1, confirmed)\n\n"
              "## P2 Father\n- Father of P1 (S1, confirmed)\n\n"
              "## P3 Mother\n- Mother of P1 (S1, confirmed)\n")
        write(os.path.join(self.p, "sources.md"),
              "# Sources\n\n- S1 — **A record** — x (confirmed)\n- U1 — **Interview** — y\n")

    def _spec(self, body):
        path = os.path.join(self.p, "site", "people_spec.py")
        write(path, body)
        return path

    def test_process_word_in_note_warns(self):
        spec = self._spec(
            "PEOPLE = [\n"
            " dict(id='p1', pid='P1', name='Rowan', sex='F', child=None, line='root',"
            " conf='confirmed', src=['U1'], note='Migrated from the old snapshot in the kit build.'),\n"
            " dict(id='p2', pid='P2', name='Father', sex='M', child='p1', line='paternal',"
            " conf='confirmed', src=['S1']),\n"
            " dict(id='p3', pid='P3', name='Mother', sex='F', child='p1', line='maternal',"
            " conf='confirmed', src=['S1']),\n"
            "]\nPSEUDO_SOURCES = {'U1': {}}\nRELATIVES = {}\nOTHER_FAMILY = {}\n")
        code, out = run("check_ids.py", self.p, "--spec", spec)
        self.assertEqual(code, 0, out)  # warn-only without --strict
        self.assertIn("process word", out)
        self.assertRegex(out, r"Migrated|migrated|snapshot|kit|build")
        code2, out2 = run("check_ids.py", self.p, "--spec", spec, "--strict")
        self.assertEqual(code2, 1, out2)

    def test_empty_other_family_warns(self):
        spec = self._spec(
            "PEOPLE = [\n"
            " dict(id='p1', pid='P1', name='Rowan', sex='F', child=None, line='root',"
            " conf='confirmed', src=['U1'], note='Home person.'),\n"
            " dict(id='p2', pid='P2', name='Father', sex='M', child='p1', line='paternal',"
            " conf='confirmed', src=['S1']),\n"
            " dict(id='p3', pid='P3', name='Mother', sex='F', child='p1', line='maternal',"
            " conf='confirmed', src=['S1']),\n"
            "]\nPSEUDO_SOURCES = {'U1': {}}\nRELATIVES = {}\nOTHER_FAMILY = {}\n")
        code, out = run("check_ids.py", self.p, "--spec", spec)
        self.assertEqual(code, 0, out)
        self.assertIn("OTHER_FAMILY/RELATIVES are empty", out)

    def test_wired_other_family_clean_of_empty_warn(self):
        spec = self._spec(
            "PEOPLE = [\n"
            " dict(id='p1', pid='P1', name='Rowan', sex='F', child=None, line='root',"
            " conf='confirmed', src=['U1'], note='Home person on the fan.'),\n"
            " dict(id='p2', pid='P2', name='Father', sex='M', child='p1', line='paternal',"
            " conf='confirmed', src=['S1']),\n"
            " dict(id='p3', pid='P3', name='Mother', sex='F', child='p1', line='maternal',"
            " conf='confirmed', src=['S1']),\n"
            "]\nPSEUDO_SOURCES = {'U1': {}}\n"
            "RELATIVES = {'ida': dict(name='Ida', conf='confirmed', src=['S1'],"
            " note='Born 1923; named on the same birth act.')}\n"
            "OTHER_FAMILY = {'p1': [('Siblings', 'ida', 'Sister')]}\n")
        code, out = run("check_ids.py", self.p, "--spec", spec)
        self.assertEqual(code, 0, out)
        self.assertNotIn("OTHER_FAMILY/RELATIVES are empty", out)
        self.assertNotIn("process word", out)

    def test_thin_other_family_warns(self):
        write(os.path.join(self.p, "people.md"),
              "# People\n\n## P1 Rowan Ashdown\n- Born 1900 (S1, confirmed)\n"
              "- Sister: Ida (S1)\n- Brother: Tomas (S1)\n- Sister: Nora (S1)\n"
              "- Brother: Eli (S1)\n\n"
              "## P2 Father\n- Father of P1 (S1, confirmed)\n\n"
              "## P3 Mother\n- Mother of P1 (S1, confirmed)\n")
        spec = self._spec(
            "PEOPLE = [\n"
            " dict(id='p1', pid='P1', name='Rowan', sex='F', child=None, line='root',"
            " conf='confirmed', src=['U1'], note='Home person.'),\n"
            " dict(id='p2', pid='P2', name='Father', sex='M', child='p1', line='paternal',"
            " conf='confirmed', src=['S1']),\n"
            " dict(id='p3', pid='P3', name='Mother', sex='F', child='p1', line='maternal',"
            " conf='confirmed', src=['S1']),\n"
            "]\nPSEUDO_SOURCES = {'U1': {}}\n"
            "RELATIVES = {'ida': dict(name='Ida', conf='confirmed', src=['S1'], note='Elder.')}\n"
            "OTHER_FAMILY = {'p1': [('Siblings', 'ida', 'Sister')]}\n")
        code, out = run("check_ids.py", self.p, "--spec", spec)
        self.assertEqual(code, 0, out)
        self.assertIn("mention siblings/children about", out)


    def test_process_word_in_why_matters_warns(self):
        # minimal sidecar with process wording in Why this record matters
        rec_dir = os.path.join(self.p, "records", "ashdown")
        os.makedirs(rec_dir, exist_ok=True)
        write(os.path.join(rec_dir, "1925_S1.md"),
              "---\n"
              "s_number: S1\n"
              "title: \"A record\"\n"
              "date: \"\"\n"
              "place: \"\"\n"
              "record_type: \"birth\"\n"
              "language: \"English\"\n"
              "archive_ref: \"\"\n"
              "archive_unit: \"\"\n"
              "url: \"\"\n"
              "image_files: []\n"
              "people: []\n"
              "facts_supported: []\n"
              "related_sources: []\n"
              "translation_status: \"skipped (English)\"\n"
              "collateral: false\n"
              "---\n"
              "# S1 — A record\n\n"
              "## Why this record matters\n\n"
              "Written during migration from the old trees snapshot.\n\n"
              "## Notes / discrepancies\n\n"
              "None.\n")
        spec = self._spec(
            "PEOPLE = [\n"
            " dict(id='p1', pid='P1', name='Rowan', sex='F', child=None, line='root',"
            " conf='confirmed', src=['U1'], note='Home person.'),\n"
            " dict(id='p2', pid='P2', name='Father', sex='M', child='p1', line='paternal',"
            " conf='confirmed', src=['S1']),\n"
            " dict(id='p3', pid='P3', name='Mother', sex='F', child='p1', line='maternal',"
            " conf='confirmed', src=['S1']),\n"
            "]\nPSEUDO_SOURCES = {'U1': {}}\n"
            "RELATIVES = {'ida': dict(name='Ida', conf='confirmed', src=['S1'],"
            " note='Born 1923; named on the same birth act.')}\n"
            "OTHER_FAMILY = {'p1': [('Siblings', 'ida', 'Sister')]}\n")
        code, out = run("check_ids.py", self.p, "--spec", spec)
        self.assertEqual(code, 0, out)  # warn-only
        self.assertIn("process word", out)
        self.assertIn("Why this record matters", out)
        self.assertRegex(out, r"migrat|snapshot")


    def test_bookkeeping_in_source_title_and_summary_warns(self):
        # sources.md title + sidecar title/summary with agent bookkeeping (fictional only)
        write(os.path.join(self.p, "sources.md"),
              "# Sources\n\n"
              "- S1 — **A record checked by the parent agent** — x (confirmed)\n"
              "- U1 — **Interview** — y\n")
        rec_dir = os.path.join(self.p, "records", "ashdown")
        os.makedirs(rec_dir, exist_ok=True)
        write(os.path.join(rec_dir, "1925_S1.md"),
              "---\n"
              "s_number: S1\n"
              "title: \"Family lore, the user via the parent agent, 2026-01-01\"\n"
              "date: \"\"\n"
              "place: \"\"\n"
              "record_type: \"birth\"\n"
              "language: \"English\"\n"
              "archive_ref: \"\"\n"
              "archive_unit: \"\"\n"
              "url: \"\"\n"
              "image_files: []\n"
              "people: []\n"
              "facts_supported: []\n"
              "related_sources: []\n"
              "translation_status: \"skipped (English)\"\n"
              "collateral: false\n"
              "---\n"
              "# S1 — A record\n\n"
              "## Why this record matters\n\n"
              "Names the home person on the birth act.\n\n"
              "## Summary (from sources.md)\n\n"
              "Pass 4 note (relayed by the parent agent; owner message [pt12u]): headed browser check.\n\n"
              "## Notes / discrepancies\n\n"
              "None.\n")
        spec = self._spec(
            "PEOPLE = [\n"
            " dict(id='p1', pid='P1', name='Rowan', sex='F', child=None, line='root',"
            " conf='confirmed', src=['U1'], note='Home person.'),\n"
            " dict(id='p2', pid='P2', name='Father', sex='M', child='p1', line='paternal',"
            " conf='confirmed', src=['S1']),\n"
            " dict(id='p3', pid='P3', name='Mother', sex='F', child='p1', line='maternal',"
            " conf='confirmed', src=['S1']),\n"
            "]\nPSEUDO_SOURCES = {'U1': {}}\n"
            "RELATIVES = {'ida': dict(name='Ida', conf='confirmed', src=['S1'],"
            " note='Born 1923; named on the same birth act.')}\n"
            "OTHER_FAMILY = {'p1': [('Siblings', 'ida', 'Sister')]}\n")
        code, out = run("check_ids.py", self.p, "--spec", spec)
        self.assertEqual(code, 0, out)  # warn-only
        self.assertIn("bookkeeping phrase", out)
        self.assertTrue(("title" in out) or ("sources.md S1" in out), out)
        self.assertRegex(out, r"parent agent|the user|Pass 4|owner message|relayed by|headed browser|\[pt12u\]")


class FreshProject(unittest.TestCase):
    def test_check_ids_clean_on_brand_new_project(self):
        tmp = tempfile.mkdtemp()
        p = new_project(os.path.join(tmp, "fresh"))
        code, out = run("check_ids.py", p)
        self.assertEqual(code, 0, out)
        self.assertNotIn("S40 is not defined", out)
        self.assertNotIn("S49 is not defined", out)
        self.assertNotIn("S40", open(os.path.join(p, "sources.md")).read())


class PrivacyFail(unittest.TestCase):
    def test_missing_word_list_is_error(self):
        tmp = tempfile.mkdtemp()
        missing = os.path.join(tmp, "no-such-words.txt")
        code, out = run("privacy_grep.py", KIT, "--words", missing)
        self.assertEqual(code, 1)
        self.assertIn("ERROR: no usable private word list", out)



def git_repo(path):
    os.makedirs(path, exist_ok=True)
    for args in (["init", "-q"], ["config", "user.name", "Test"], ["config", "user.email", "test@example.invalid"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", "-C", path, *args], check=True, capture_output=True)
    return path


def commit_all(path, msg="c"):
    subprocess.run(["git", "-C", path, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", path, "commit", "-q", "-m", msg], check=True, capture_output=True)


def run_env(tool, env_extra, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("CI", "GITHUB_ACTIONS", "GENEALOGY_PRIVATE_WORDS")}
    env.update(env_extra)
    r = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


class PrivacyLayers(unittest.TestCase):
    """Fictional words only (Zebratown, Quillmere)."""

    def setUp(self):
        import privacy_grep
        self.pg = privacy_grep
        self.tmp = tempfile.mkdtemp()
        self.words = os.path.join(self.tmp, "outside", "words.txt")
        write(self.words, "Zebratown\n")

    def test_env_var_word_list(self):
        repo = git_repo(os.path.join(self.tmp, "r"))
        write(os.path.join(repo, "a.md"), "born in Zebratown\n")
        code, out = run_env("privacy_grep.py", {"GENEALOGY_PRIVATE_WORDS": self.words}, repo)
        self.assertEqual(code, 1, out)
        self.assertIn("private word #1", out)
        self.assertNotIn("Zebratown", out)

    def test_quarantine_shapes(self):
        q = self.pg.quarantine_category
        for ok in ("site/example/people_spec.py", "site/site.config.json", "templates/records/INDEX.md",
                   "site/example/data/records/a/x.jpg", "docs/screenshot-phone.png", "site/web/favicon.svg",
                   "tools/privacy_grep.py", "README.md"):
            self.assertIsNone(q(ok), ok)
        for bad in ("genealogy-trees/t/people.md", "x/.work/private-words.txt", "private-words.txt",
                    "people_spec.py", "site/people_spec.py", "mytree/site/site.config.json",
                    "records/a/scan.jpg", "correspondence/letter.md", ".env", "notes.private.md",
                    "shots/screenshot.png", ".genealogy-project", "site/site.config.local.json"):
            self.assertIsNotNone(q(bad), bad)

    def test_public_ci_is_name_blind_and_generic(self):
        repo = git_repo(os.path.join(self.tmp, "pub"))
        write(os.path.join(repo, "README.md"), "Zebratown is never checked here\n")
        commit_all(repo)
        code, out = run_env("privacy_grep.py", {"GENEALOGY_PRIVATE_WORDS": self.words}, repo, "--public-ci", "--history")
        self.assertEqual(code, 0, out)   # env word list ignored
        write(os.path.join(repo, "genealogy-trees", "Quillmere", "people.md"), "x\n")
        write(os.path.join(repo, "cfg.py"), "api_" + 'key = "abcdefghijklmnopqrstuv"\n')
        commit_all(repo)
        code, out = run_env("privacy_grep.py", {"CI": "true"}, repo, "--public-ci", "--history")
        self.assertEqual(code, 1, out)
        self.assertIn("privacy check failed", out)
        for leak in ("Quillmere", "genealogy-trees/", "cfg.py", "abcdef"):
            self.assertNotIn(leak, out)
        code, out = run_env("privacy_grep.py", {"CI": "true"}, repo, "--public-ci", "--details")
        self.assertEqual(code, 2, out)
        code, out = run_env("privacy_grep.py", {}, repo, "--public-ci", "--words", self.words)
        self.assertEqual(code, 2, out)

    def test_kit_passes_public_ci(self):
        code, out = run_env("privacy_grep.py", {"CI": "true"}, KIT, "--public-ci")
        self.assertEqual(code, 0, out)

    def test_tracked_word_list_refused(self):
        repo = git_repo(os.path.join(self.tmp, "tw"))
        inside = os.path.join(repo, "lists", "w.txt")
        write(inside, "Zebratown\n")
        commit_all(repo)
        code, out = run_env("privacy_grep.py", {}, repo, "--words", inside)
        self.assertEqual(code, 1, out)
        self.assertIn("tracked by git", out)

    def test_install_hook_pre_commit_and_pre_push(self):
        repo = git_repo(os.path.join(self.tmp, "h"))
        write(os.path.join(repo, "README.md"), "fictional\n")
        commit_all(repo)
        code, out = run_env("privacy_grep.py", {}, repo, "--install-hook", "--words", self.words)
        self.assertEqual(code, 0, out)
        hooks = os.path.join(repo, ".git", "hooks")
        for h in ("pre-commit", "pre-push"):
            self.assertTrue(os.access(os.path.join(hooks, h), os.X_OK), h)
        # pre-commit blocks a staged private word
        write(os.path.join(repo, "a.md"), "Zebratown\n")
        subprocess.run(["git", "-C", repo, "add", "a.md"], check=True)
        r = subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "x"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        # pre-push blocks once the word is in history (commit with --no-verify to simulate a bypass)
        subprocess.run(["git", "-C", repo, "commit", "-q", "--no-verify", "-m", "x"], check=True)
        r = subprocess.run(["sh", os.path.join(hooks, "pre-push"), "origin", "none"], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("push blocked", r.stderr)

    def test_install_hook_env_mode_fails_closed(self):
        repo = git_repo(os.path.join(self.tmp, "he"))
        code, out = run_env("privacy_grep.py", {"GENEALOGY_PRIVATE_WORDS": self.words}, repo, "--install-hook")
        self.assertEqual(code, 0, out)
        body = open(os.path.join(repo, ".git", "hooks", "pre-commit")).read()
        self.assertNotIn(self.words, body)
        write(os.path.join(repo, "a.md"), "ok\n")
        env = {k: v for k, v in os.environ.items() if k != "GENEALOGY_PRIVATE_WORDS"}
        subprocess.run(["git", "-C", repo, "add", "a.md"], check=True)
        r = subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "x"], capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0)   # no list at commit time -> blocked

    def test_install_hook_keeps_foreign_hook(self):
        repo = git_repo(os.path.join(self.tmp, "fh"))
        write(os.path.join(repo, ".git", "hooks", "pre-push"), "#!/bin/sh\nexit 0\n")
        code, out = run_env("privacy_grep.py", {}, repo, "--install-hook", "--words", self.words)
        self.assertEqual(code, 1, out)
        code, out = run_env("privacy_grep.py", {}, repo, "--install-hook", "--words", self.words, "--force")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()

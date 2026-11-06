"""Build the fictional example and check the output. Run: python3 -m unittest discover -s site/tests"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SITE)
import build  # noqa: E402


def example_config(tmp, **over):
    cfg = json.load(open(os.path.join(SITE, "site.config.json")))
    cfg.update({"data_dir": os.path.join(SITE, "example", "data"), "spec": os.path.join(SITE, "example", "people_spec.py"),
                "out_dir": os.path.join(tmp, "out"), "image_cache": os.path.join(tmp, "cache")})
    cfg.update(over)
    p = os.path.join(tmp, "site.config.json")
    with open(p, "w") as f:
        json.dump(cfg, f)
    return p


class BuildExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        build.configure(example_config(cls.tmp))
        cls.data = build.build()
        cls.out = build.OUT

    def test_no_source_files_in_output(self):
        bad = [f for f in glob.glob(os.path.join(self.out, "**", "*"), recursive=True)
               if f.endswith((".md", ".py", ".map")) or "node_modules" in f]
        self.assertEqual(bad, [])

    def test_no_placeholders(self):
        for f in ("index.html", "sw.js"):
            self.assertNotIn("{{", open(os.path.join(self.out, f), encoding="utf-8").read())

    def test_every_id_resolves(self):
        d = self.data
        ids = {p["id"] for p in d["people"]}
        for p in d["people"]:
            self.assertTrue(p["child"] is None or p["child"] in ids)
            for x in p["parents"]:
                self.assertIn(x, ids)
            for s in p["sources"]:
                self.assertIn(s, d["sources"])
        for pid, i in d["links"]["pids"].items():
            self.assertTrue(i in ids or i in d["relatives"])

    def test_strict_privacy(self):
        by = {p["id"]: p for p in self.data["people"]}
        self.assertTrue(by["p1"]["nameOnly"])                 # possibly living: name only
        self.assertNotIn("f", by["p1"])
        self.assertTrue(self.data["sources"]["S5"].get("restricted"))   # 1952: under 100 years
        self.assertNotIn("summary", self.data["sources"]["S5"])
        self.assertFalse(self.data["sources"]["S4"].get("restricted"))  # allowed via PUBLIC_RECENT_SOURCES
        blob = open(os.path.join(self.out, "data", "family.json"), encoding="utf-8").read()
        blob += open(os.path.join(self.out, "data", "search.json"), encoding="utf-8").read()
        self.assertNotIn("12 May 1988", blob)

    def test_neutral_title_and_manifest(self):
        html = open(os.path.join(self.out, "index.html"), encoding="utf-8").read()
        self.assertIn("<title>Family tree</title>", html)
        man = json.load(open(os.path.join(self.out, "manifest.webmanifest")))
        for tok in build.name_tokens():
            self.assertNotIn(tok, build._pfold(man["name"]))

    def test_example_flag(self):
        self.assertTrue(self.data["example"])

    def test_pedigree_collapse(self):
        """Fictional example: Aron Marrow (p16) and Rachel (p17) are parents of Lena (p9, primary) and of
        Dora (p19, Hanna Quill's mother), so they are ancestors twice."""
        by = {p["id"]: p for p in self.data["people"]}
        self.assertEqual(by["p16"]["child"], "p9")
        self.assertEqual(by["p16"]["children"], ["p9", "p19"])
        self.assertEqual(by["p19"]["parents"], ["p16", "p17"])
        self.assertEqual(by["p9"]["parents"], ["p16", "p17"])
        # primary: 1 -> p2 (2) -> p4 (4) -> p9 (9) -> Aron 18 / Rachel 19
        self.assertEqual((by["p16"]["ahnen"], by["p17"]["ahnen"]), (18, 19))
        # repeat: 1 -> p3 (3) -> p6 (6) -> p13 (13) -> p19 (27) -> Aron 54 / Rachel 55
        self.assertEqual(by["p19"]["ahnen"], 27)
        r16, r17 = by["p16"]["repeats"], by["p17"]["repeats"]
        self.assertEqual([(r["ahnen"], r["child"], r["line"]) for r in r16], [(54, "p19", "mp")])
        self.assertEqual(r17[0]["ahnen"], 55)
        self.assertEqual(r16[0]["link"], {"c": "probable", "s": ["S13"]})
        self.assertIn("maternal", r16[0]["relation"])
        self.assertEqual(by["p16"]["gen"], 4)
        self.assertEqual(r16[0]["gen"], 5)
        self.assertEqual(self.data["maxGen"], 5)            # the repeat ring is drawn
        self.assertEqual(self.data["collapse"], 2)
        positions = [p["ahnen"] for p in by.values()] + [r["ahnen"] for p in by.values() for r in p.get("repeats", [])]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertIn("S13", by["p16"]["sources"])
        js = open(os.path.join(self.out, "assets", "fan.js"), encoding="utf-8").read()
        self.assertIn("repeats", js)
        self.assertIn("collapsedOf", js)

    def test_placeholders_are_not_transcriptions(self):
        for t in ("_(not transcribed)_", "Not transcribed in the source project; see summary", "See summary.", ""):
            self.assertTrue(build.is_boiler(t), t)
        self.assertFalse(build.is_boiler("No. 7. Kestrava, 12 June 1921 ..."))
        n = sum(1 for s in self.data["sources"].values() if s.get("transcription"))
        self.assertEqual(n, 4)

    def test_all_known_siblings_on_example(self):
        """Fictional example: every panel has a sibling list; shared parents and explicit lists meet."""
        by = {p["id"]: p for p in self.data["people"]}
        rels = self.data["relatives"]
        for person in list(self.data["people"]) + list(rels.values()):
            self.assertIn("siblings", person)
            ids = [e["id"] for e in person["siblings"]]
            self.assertEqual(ids, sorted(set(ids)))
            self.assertNotIn(person["id"], ids)
            for e in person["siblings"]:
                self.assertEqual(set(e), {"id", "c", "s", "kind"})
        # Tomas and Ida: explicit sister link, not Tomas's own identity field.
        ida = by["p4"]["siblings"]
        self.assertEqual([e["id"] for e in ida], ["r-ida"])
        self.assertEqual(ida[0]["kind"], "Sister")
        self.assertEqual(ida[0]["c"], "confirmed")
        self.assertEqual(rels["r-ida"]["siblings"][0]["id"], "p4")
        self.assertEqual(rels["r-ida"]["siblings"][0]["c"], ida[0]["c"])
        # Lena (confirmed) and Dora (probable) share two parents; the link stays probable.
        lena = next(e for e in by["p9"]["siblings"] if e["id"] == "p19")
        dora = next(e for e in by["p19"]["siblings"] if e["id"] == "p9")
        self.assertEqual(lena["c"], "probable")
        self.assertEqual(dora, {**lena, "id": "p9"})
        # Nora is name-only in strict mode; the edge does not carry her hidden note or years.
        nora_edge = next(e for e in by["p2"]["siblings"] if e["id"] == "r-nora")
        self.assertEqual(nora_edge["c"], "lore")
        self.assertTrue(rels["r-nora"]["nameOnly"])
        self.assertNotIn("note", rels["r-nora"])
        self.assertNotIn("years", rels["r-nora"])
        # A spouse is not a sibling. Daniel's sister is not also his child.
        self.assertNotIn("p5", [e["id"] for e in by["p4"]["siblings"]])
        self.assertNotIn("r-nora", [e["id"] for e in by["p1"]["siblings"]])
        self.assertEqual(by["p1"]["siblings"], [])
        js = open(os.path.join(self.out, "assets", "app.js"), encoding="utf-8").read()
        self.assertIn("All known siblings", js)
        self.assertGreaterEqual(js.count("siblingsSection("), 3)
        # Sibling citations are visible from the chart person's sources.
        cited = self.data["sources"]["S3"]["citedBy"]
        self.assertTrue(any(c["id"] == "p4" and "sibling" in c["what"] for c in cited))
        self.assertTrue(any(c["id"] == "r-ida" and "sibling" in c["what"] for c in cited))

    def test_name_spelling_and_possible_match(self):
        """Fictional example: record spelling, family spelling in parentheses, other spellings, unmerged match."""
        import names
        by = {p["id"]: p for p in self.data["people"]}
        lena = by["p9"]
        self.assertEqual(lena["name"], "Lena Marrow (Lina)")
        self.assertEqual(lena["alsoRecorded"], [{"name": "Liena Marrow", "s": ["S2"]}])
        self.assertEqual(lena["soundsLike"], ["Lina"])
        self.assertEqual(by["p11"]["name"], "Clara W[?] (Clara Wendt)")
        self.assertNotIn("alsoRecorded", by["p11"])
        match = by["p18"]["possibleMatches"]
        self.assertEqual(match[0]["id"], "r-natan-index")
        self.assertIn("not merged", match[0]["note"])
        rel = self.data["relatives"]["r-natan-index"]
        self.assertEqual(rel["name"], "Natan Corvell")
        self.assertEqual(rel["possibleMatches"][0]["id"], "p18")
        self.assertNotEqual(rel["id"], "p18")
        search = json.load(open(os.path.join(self.out, "data", "search.json"), encoding="utf-8"))
        alt = next(p["alt"] for p in search["people"] if p["id"] == "p9")
        self.assertIn("Lina", alt)
        self.assertIn("Liena Marrow", alt)
        js = open(os.path.join(self.out, "assets", "app.js"), encoding="utf-8").read()
        self.assertIn("Also recorded as", js)
        self.assertIn("Possible match", js)
        warns = names.spec_name_warnings(
            build.spec.PEOPLE, build.spec.RELATIVES, build.spec.NAME_FORMS,
            build.spec.POSSIBLE_MATCHES, build.spec.MATCH_EXCLUSIONS, build.spec.CANONICAL_ALIASES,
            sources_md=open(os.path.join(SITE, "example", "data", "sources.md"), encoding="utf-8").read(),
            pseudo_sources=build.spec.PSEUDO_SOURCES)
        self.assertEqual(warns, [])


class CollapseErrors(unittest.TestCase):
    def test_cycle_and_bad_child_refused(self):
        tmp = tempfile.mkdtemp()
        build.configure(example_config(tmp))
        orig = build.spec.PEOPLE
        try:
            build.spec.PEOPLE = [dict(p) for p in orig]
            next(p for p in build.spec.PEOPLE if p["id"] == "p16")["child"] = ["p9", "nobody"]
            with self.assertRaises(SystemExit):
                build.build_people({}, "", [])
        finally:
            build.spec.PEOPLE = orig


class Refusals(unittest.TestCase):
    def test_title_with_surname_refused(self):
        tmp = tempfile.mkdtemp()
        build.configure(example_config(tmp, site_title="Ashdown family"))
        with self.assertRaises(SystemExit):
            build.site_title()

    def test_project_with_surname_refused(self):
        tmp = tempfile.mkdtemp()
        build.configure(example_config(tmp, cloudflare={"project": "corvell-tree"}))
        with self.assertRaises(SystemExit):
            build.cf_settings()

    def test_deploy_stops_if_not_locked(self):
        tmp = tempfile.mkdtemp()
        build.configure(example_config(tmp, cloudflare={"project": "ft-0123456789", "access_team_domain": "team.cloudflareaccess.com"}))
        calls = []

        def fake_wrangler(args, cf, capture=True):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        with mock.patch.object(build, "wrangler", fake_wrangler), \
                mock.patch.object(build, "access_locked", lambda u, t="": (False, "200 -> (no redirect)")):
            with self.assertRaises(SystemExit):
                build.deploy()
        self.assertFalse(any(a[:2] == ["pages", "deploy"] for a in calls), "must not upload when the pre-check fails")

    def test_access_wrong_team_is_not_locked(self):
        r = subprocess.CompletedProcess([], 0, stdout="302 https://other.cloudflareaccess.com/cdn-cgi/access/login", stderr="")
        with mock.patch.object(build.subprocess, "run", lambda *a, **k: r):
            self.assertFalse(build.access_locked("https://x.pages.dev/", "team.cloudflareaccess.com")[0])
            self.assertTrue(build.access_locked("https://x.pages.dev/", "other.cloudflareaccess.com")[0])


if __name__ == "__main__":
    unittest.main()

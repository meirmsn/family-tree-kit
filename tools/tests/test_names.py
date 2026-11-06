"""Name spelling and possible-match checks. Fictional names only."""
import os
import sys
import tempfile
import textwrap
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import names  # noqa: E402


def person(pid, name, by=None, child=None, born=""):
    row = {"id": pid, "name": name, "born": born}
    if by is not None:
        row["by"] = by
    if child is not None:
        row["child"] = child
    return row


class ResolveForm(unittest.TestCase):
    def test_record_and_family_compose(self):
        form = {"record": "Lena Marrow", "record_source": "S2", "record_kind": "act",
                "family": "Lina", "aliases": [{"name": "Liena Marrow", "source": "S2", "kind": "act"}]}
        view = names.resolve_form("p9", form, "Lena Marrow (Lina)", {"S2": "marriage act 1921"}, {"S2"})
        self.assertEqual(view["title"], "Lena Marrow (Lina)")
        self.assertEqual(view["also"], [{"name": "Liena Marrow", "s": ["S2"]}])
        self.assertEqual(view["sounds"], ["Lina"])
        self.assertEqual(view["warnings"], [])

    def test_family_spelling_does_not_replace_record(self):
        texts = {"S5": "marriage index 1952"}
        unmarked = {"record": "Clara W[?]", "record_source": "S5", "record_kind": "index"}
        view = names.resolve_form("p11", unmarked, "Clara Wendt", texts, {"S5"})
        self.assertEqual(view["title"], "Clara W[?]")
        self.assertTrue(any("differs from cited record spelling" in w for w in view["warnings"]))
        self.assertTrue(any("mark the family spelling" in w for w in view["warnings"]))
        marked = dict(unmarked, family="Clara Wendt", family_source="U2")
        view2 = names.resolve_form("p11", marked, "Clara Wendt", texts, {"S5", "U2"})
        self.assertEqual(view2["title"], "Clara W[?] (Clara Wendt)")
        self.assertTrue(any("should be 'Clara W[?] (Clara Wendt)'" in w for w in view2["warnings"]))

    def test_marked_family_title_is_quiet(self):
        form = {"record": "Clara W[?]", "record_source": "S5", "record_kind": "index", "family": "Clara Wendt"}
        view = names.resolve_form("p11", form, "Clara W[?] (Clara Wendt)", {"S5": "index"}, {"S5"})
        self.assertEqual(view["warnings"], [])

    def test_no_record_yet_uses_family_spelling(self):
        form = {"family": "Rosa Delmont", "family_source": "U1"}
        view = names.resolve_form("p7", form, "Rosa Delmont", {"U1": "family interview"}, {"U1"})
        self.assertEqual(view["title"], "Rosa Delmont")
        self.assertEqual(view["warnings"], [])

    def test_alias_without_source_warns(self):
        form = {"record": "Marta Pell", "record_source": "S1", "record_kind": "act",
                "aliases": [{"name": "Martha Pell"}]}
        view = names.resolve_form("p2", form, "Marta Pell", {"S1": "birth act"}, {"S1"})
        self.assertTrue(any("alias 'Martha Pell' lacks a source" in w for w in view["warnings"]))

    def test_act_outranks_index(self):
        texts = {"S1": "birth index only", "S2": "civil birth act 14"}
        form = {"record": "Marta Bell", "record_source": "S1", "record_kind": "index",
                "aliases": [{"name": "Marta Pell", "source": "S2", "kind": "act", "year": 1901}]}
        view = names.resolve_form("p2", form, "Marta Bell", texts, {"S1", "S2"})
        self.assertEqual(view["title"], "Marta Pell")
        self.assertTrue(any("differs from cited record spelling 'Marta Pell'" in w for w in view["warnings"]))
        # The losing index spelling is still shown.
        self.assertEqual(view["also"], [{"name": "Marta Bell", "s": ["S1"]}])

    def test_earlier_act_wins_when_title_already_follows_it(self):
        texts = {"S1": "marriage act", "S2": "birth act"}
        form = {"record": "Marta Pell", "record_source": "S1", "record_kind": "act", "record_year": 1920,
                "aliases": [{"name": "Martha Pell", "source": "S2", "kind": "act", "year": 1901}]}
        view = names.resolve_form("p2", form, "Martha Pell", texts, {"S1", "S2"})
        self.assertEqual(view["title"], "Martha Pell")
        self.assertTrue(any("outranked by 'Martha Pell'" in w for w in view["warnings"]))
        self.assertTrue(any("earliest or most official" in w for w in view["warnings"]))

    def test_index_does_not_replace_an_unclassified_record(self):
        form = {"record": "Marta Pell", "record_source": "S1",
                "aliases": [{"name": "Marta Bell", "source": "S2", "kind": "index"}]}
        view = names.resolve_form("p2", form, "Marta Pell", {"S1": "a note", "S2": "index row"}, {"S1", "S2"})
        self.assertEqual(view["title"], "Marta Pell")
        self.assertEqual(view["warnings"], [])

    def test_same_surname_is_not_near(self):
        self.assertFalse(names.near_identical("Ida Ashdown", "Tomas Ashdown"))
        self.assertFalse(names.near_identical("Rachel", "Rachel"))
        self.assertTrue(names.near_identical("Marta Pell", "Marta Bell"))
        self.assertTrue(names.near_identical("Marta Pell", "Marte Pell"))
        self.assertTrue(names.near_identical("Natan Corvell", "Natan Corvell"))


class PossibleMatch(unittest.TestCase):
    def _rows(self):
        people = [
            person("p1", "Rowan Ashdown", by=1988),
            person("p2", "Marta Pell", by=1900, child="p1"),
        ]
        relatives = {
            "marta-b": {"name": "Marta Bell", "by": 1902, "conf": "possible"},
        }
        return people, relatives

    def test_warns_without_a_match_or_exclusion(self):
        people, relatives = self._rows()
        warns = names.possible_match_warnings(people, relatives, [])
        self.assertEqual(len(warns), 1)
        self.assertIn("near-identical", warns[0])
        self.assertIn("p2", warns[0])
        self.assertIn("r-marta-b", warns[0])
        self.assertIn("no possible-match or exclusion", warns[0])

    def test_possible_match_and_exclusion_are_quiet(self):
        people, relatives = self._rows()
        linked = names.possible_match_warnings(
            people, relatives, [{"a": "p2", "b": "marta-b", "sources": ["S1"]}])
        self.assertEqual(linked, [])
        excluded = names.possible_match_warnings(
            people, relatives, [], exclusions=[("p2", "r-marta-b")])
        self.assertEqual(excluded, [])

    def test_canonical_alias_is_already_merged_and_is_not_rewritten(self):
        people, relatives = self._rows()
        aliases = {"r-marta-b": "p2"}
        before = dict(aliases)
        warns = names.possible_match_warnings(people, relatives, [], canonical_aliases=aliases)
        self.assertEqual(warns, [])
        self.assertEqual(aliases, before)

    def test_parent_child_and_distant_years_stay_quiet(self):
        # Inside the 8-year window, but one is the parent of the other.
        close = [
            person("p1", "Marta Pell", by=1906),
            person("p2", "Marta Bell", by=1900, child="p1"),
        ]
        self.assertEqual(names.possible_match_warnings(close, {}, []), [])
        far = [
            person("p1", "Marta Pell", by=1900),
            person("p2", "Marta Bell", by=1920),
        ]
        self.assertEqual(names.possible_match_warnings(far, {}, []), [])

    def test_missing_year_is_quiet(self):
        people = [person("p1", "Marta Pell", by=1900), person("p2", "Marta Bell")]
        self.assertEqual(names.possible_match_warnings(people, {}, []), [])

    def test_apply_does_not_merge(self):
        rows = [
            {"id": "p2", "name": "Marta Bell", "sources": ["S1"]},
            {"id": "r-marta-b", "name": "Marta Pell", "s": ["S2"]},
        ]
        forms = {"p2": {"record": "Marta Pell", "record_source": "S2", "record_kind": "act",
                        "family": "Marta Bell",
                        "aliases": [{"name": "Martha Pell", "source": "S1", "kind": "index"}]}}
        aliases = {}
        names.apply_display_names(rows, forms, {"S1": "index", "S2": "birth act"}, {"S1", "S2"})
        self.assertEqual(rows[0]["name"], "Marta Pell (Marta Bell)")
        self.assertEqual(rows[0]["alsoRecorded"][0]["name"], "Martha Pell")
        self.assertEqual(rows[0]["soundsLike"], ["Marta Bell"])
        self.assertEqual([r["id"] for r in rows], ["p2", "r-marta-b"])
        self.assertEqual(aliases, {})
        edges = names.match_edges(
            [{"a": "p2", "b": "marta-b", "note": "not merged", "sources": ["S2"]}],
            {"p2"}, {"r-marta-b"})
        by = {r["id"]: r for r in rows}
        names.attach_possible_matches(by, edges)
        self.assertEqual(by["p2"]["possibleMatches"][0]["id"], "r-marta-b")
        self.assertEqual(by["r-marta-b"]["possibleMatches"][0]["id"], "p2")
        self.assertEqual(set(by), {"p2", "r-marta-b"})


class CheckIdsWiring(unittest.TestCase):
    def test_check_ids_prints_spelling_and_match_warnings(self):
        sys.path.insert(0, os.path.dirname(__file__))
        from test_tools import new_project, run, write
        tmp = tempfile.mkdtemp()
        project = new_project(os.path.join(tmp, "tree"))
        write(os.path.join(project, "people.md"), textwrap.dedent("""\
            # People
            ## P1 Rowan Ashdown
            - Born: 1900 (S1, confirmed)
            ## P2 Marta Pell
            - Born: 1900 (S1, confirmed)
            ## P3 Otto Pell
            - Born: 1880 (S1, confirmed)
            """))
        write(os.path.join(project, "sources.md"),
              "# Sources\n\n- S1 — **Fictional birth act** — x (confirmed)\n- U1 — **Interview** — y\n")
        spec = os.path.join(project, "site", "people_spec.py")
        write(spec, textwrap.dedent("""\
            PEOPLE = [
             dict(id='p1', pid='P1', name='Rowan Ashdown', sex='F', child=None, line='root',
                  conf='confirmed', src=['S1'], by=1980),
             dict(id='p2', pid='P2', name='Marta Bell', sex='F', child='p1', line='maternal',
                  conf='confirmed', src=['S1'], by=1900),
             dict(id='p3', pid='P3', name='Otto Pell', sex='M', child='p1', line='paternal',
                  conf='confirmed', src=['S1'], by=1880),
            ]
            PSEUDO_SOURCES = {'U1': {'title': 'Interview'}}
            RELATIVES = {'marta2': dict(name='Marta Pell', conf='possible', src=['S1'], by=1901, dead=True)}
            OTHER_FAMILY = {'p1': [('Siblings', 'marta2', 'Sister')]}
            LINES = {'root': 'Home', 'paternal': 'Paternal', 'maternal': 'Maternal',
                     'pp': 'PP', 'pm': 'PM', 'mp': 'MP', 'mm': 'MM'}
            NAME_FORMS = {'p2': {'record': 'Marta Pell', 'record_source': 'S1', 'record_kind': 'act',
                                 'aliases': [{'name': 'Martha Bell'}]}}
            POSSIBLE_MATCHES = []
            MATCH_EXCLUSIONS = []
            CANONICAL_ALIASES = {}
            """))
        code, out = run("check_ids.py", project, "--spec", spec)
        self.assertEqual(code, 0, out)
        self.assertIn("differs from cited record spelling", out)
        self.assertIn("lacks a source", out)
        self.assertIn("near-identical", out)
        # Mark the family spelling and the possible match: those two warnings go away.
        with open(spec, encoding="utf-8") as fh:
            body = fh.read()
        write(spec, body.replace(
            "name='Marta Bell'", "name='Marta Pell (Marta Bell)'").replace(
            "POSSIBLE_MATCHES = []",
            "POSSIBLE_MATCHES = [{'a': 'p2', 'b': 'marta2'}]").replace(
            "'aliases': [{'name': 'Martha Bell'}]",
            "'family': 'Marta Bell', 'aliases': [{'name': 'Martha Pell', 'source': 'S1'}]"))
        code2, out2 = run("check_ids.py", project, "--spec", spec)
        self.assertEqual(code2, 0, out2)
        self.assertNotIn("differs from cited record spelling", out2)
        self.assertNotIn("lacks a source", out2)
        self.assertNotIn("near-identical", out2)


if __name__ == "__main__":
    unittest.main()

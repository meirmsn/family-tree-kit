"""Sibling graph for the fictional example only. Run: python3 -m unittest discover -s site/tests"""
import copy
import os
import sys
import tempfile
import unittest

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SITE)
import build  # noqa: E402

TOOLS = os.path.join(os.path.dirname(SITE), "tools")
sys.path.insert(0, TOOLS)
import siblings  # noqa: E402

DATA = os.path.join(SITE, "example", "data")
PEOPLE_MD = open(os.path.join(DATA, "people.md"), encoding="utf-8").read()
REL_MD = open(os.path.join(DATA, "relationships.md"), encoding="utf-8").read()
SRC = {f"S{i}": {"title": f"S{i}"} for i in range(1, 21)}
_SPEC_KEYS = ("PEOPLE", "RELATIVES", "OTHER_FAMILY", "FIELDS", "FAMILY_ASSERTIONS",
              "SIBLING_EXCLUSIONS", "CANONICAL_ALIASES")


class SibBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # local import of the helper living in test_build
        sys.path.insert(0, os.path.dirname(__file__))
        from test_build import example_config
        build.configure(example_config(self.tmp))
        self.saved = {k: copy.deepcopy(getattr(build.spec, k)) for k in _SPEC_KEYS}

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(build.spec, k, copy.deepcopy(v))

    def graph(self):
        warnings = []
        people = build.build_people(SRC, PEOPLE_MD, warnings)
        rels = build.build_relatives(people)
        snap = {p["id"]: (p.get("child"), list(p.get("children") or []), list(p.get("parents") or []),
                          p.get("ahnen"), p.get("gen")) for p in people}
        known = set(SRC) | set(build.spec.PSEUDO_SOURCES)
        siblings.attach_siblings(
            people, rels, other_family=build.spec.OTHER_FAMILY, relatives_spec=build.spec.RELATIVES,
            assertions=build.spec.FAMILY_ASSERTIONS, exclusions=build.spec.SIBLING_EXCLUSIONS,
            aliases=build.spec.CANONICAL_ALIASES, known_sources=known,
        )
        after = {p["id"]: (p.get("child"), list(p.get("children") or []), list(p.get("parents") or []),
                           p.get("ahnen"), p.get("gen")) for p in people}
        self.assertEqual(snap, after)
        return {p["id"]: p for p in people}, rels, known

    def coverage(self, people_md=None, relationships_md=None):
        return siblings.sibling_coverage_warnings(
            build.spec.PEOPLE, build.spec.RELATIVES, build.spec.OTHER_FAMILY,
            people_md=PEOPLE_MD if people_md is None else people_md,
            relationships_md=REL_MD if relationships_md is None else relationships_md,
            family_assertions=build.spec.FAMILY_ASSERTIONS,
            exclusions=build.spec.SIBLING_EXCLUSIONS,
            aliases=build.spec.CANONICAL_ALIASES,
            fields=build.spec.FIELDS,
            known_sources=set(SRC) | set(build.spec.PSEUDO_SOURCES),
        )


def _ids(person):
    return [e["id"] for e in person.get("siblings") or []]


def _edge(person, other):
    return next(e for e in person["siblings"] if e["id"] == other)


class ExampleSiblings(SibBase):
    def test_example_panels_are_reciprocal_and_complete(self):
        by, rels, _known = self.graph()
        for bucket in (by, rels):
            for i, person in bucket.items():
                self.assertIn("siblings", person)
                self.assertEqual(_ids(person), sorted(set(_ids(person))))
                self.assertNotIn(i, _ids(person))
                for e in person["siblings"]:
                    self.assertEqual(set(e), {"id", "c", "s", "kind"})
                    back = _edge(by.get(e["id"]) or rels[e["id"]], i)
                    self.assertEqual(back["c"], e["c"])
                    self.assertEqual(back["s"], e["s"])
                    self.assertEqual(back["kind"], e["kind"])
        # Two off-chart children are not required yet: Ida is the one curated sister of Tomas.
        self.assertEqual(_ids(by["p4"]), ["r-ida"])
        self.assertEqual(_edge(by["p4"], "r-ida")["kind"], "Sister")
        self.assertEqual(_ids(rels["r-ida"]), ["p4"])
        # One explicit list plus two parents still yields a single edge.
        self.assertEqual(len(by["p4"]["siblings"]), 1)
        # Second on-chart sibling: Lena and Dora share Aron and Rachel.
        self.assertEqual(_ids(by["p9"]), ["p19"])
        self.assertEqual(_ids(by["p19"]), ["p9"])
        self.assertEqual(_edge(by["p9"], "p19")["kind"], "Sibling")
        self.assertEqual(_edge(by["p9"], "p19")["c"], "probable")
        self.assertIn("S2", _edge(by["p9"], "p19")["s"])
        self.assertIn("S13", _edge(by["p9"], "p19")["s"])
        # Benjamin's link stays probable; Samuel's identity is confirmed.
        self.assertEqual(_edge(by["p6"], "r-benjamin")["c"], "probable")
        self.assertEqual(_edge(by["p6"], "r-benjamin")["kind"], "Brother")
        # Nora is lore and name-only. Derived "other children" rows are not parentage.
        self.assertEqual(_edge(by["p2"], "r-nora")["c"], "lore")
        self.assertEqual(_ids(rels["r-nora"]), ["p2"])
        self.assertNotIn("r-nora", _ids(by["p1"]))
        self.assertTrue(rels["r-nora"]["nameOnly"])
        self.assertNotIn("note", rels["r-nora"])
        self.assertNotIn("years", rels["r-nora"])
        self.assertNotIn("born", rels["r-nora"])
        # Spouse and empty panels.
        self.assertNotIn("p5", _ids(by["p4"]))
        self.assertEqual(by["p1"]["siblings"], [])
        self.assertEqual(self.coverage(), [])

    def test_three_children_then_second_on_chart_sibling(self):
        build.spec.RELATIVES["edith"] = dict(
            name="Edith Ashdown", conf="probable", src=["S3"], by=1927, dead=True,
            years="1927–1991", note="Younger sister of Tomas and Ida.")
        build.spec.OTHER_FAMILY["p8"] = list(build.spec.OTHER_FAMILY.get("p8", [])) + [
            ("Other children", "edith", "Daughter")]
        build.spec.OTHER_FAMILY["p9"] = list(build.spec.OTHER_FAMILY.get("p9", [])) + [
            ("Other children", "edith", "Daughter")]
        by, rels, _k = self.graph()
        for i, others in (("p4", {"r-edith", "r-ida"}), ("r-ida", {"p4", "r-edith"}),
                          ("r-edith", {"p4", "r-ida"})):
            person = by[i] if i in by else rels[i]
            self.assertEqual(set(_ids(person)), others)
        # Explicit Sister label is kept for Tomas/Ida; the derived pair is a plain sibling.
        self.assertEqual(_edge(by["p4"], "r-ida")["kind"], "Sister")
        self.assertEqual(_edge(by["p4"], "r-edith")["kind"], "Sibling")
        # Second on-chart sibling of the same couple, plus two off-chart children.
        build.spec.RELATIVES["ruth"] = dict(
            name="Ruth Marrow", conf="probable", src=["S13"], by=1882, dead=True, years="c. 1882–1940",
            note="Daughter of Aron and Rachel.")
        build.spec.RELATIVES["lev"] = dict(
            name="Lev Marrow", conf="lore", src=["U2"], by=1878, dead=True,
            note="Son of Aron and Rachel, family lore.")
        for par in ("p16", "p17"):
            build.spec.OTHER_FAMILY[par] = list(build.spec.OTHER_FAMILY.get(par, [])) + [
                ("Other children", "ruth", "Daughter"), ("Other children", "lev", "Son")]
        by, rels, _k = self.graph()
        cohort = {"p9", "p19", "r-ruth", "r-lev"}
        for i in cohort:
            person = by[i] if i in by else rels[i]
            self.assertEqual(set(_ids(person)), cohort - {i})
        # Lev's parentage is lore, so the link is not promoted to Lena's confirmed identity.
        self.assertEqual(_edge(by["p9"], "r-lev")["c"], "lore")
        self.assertNotEqual(base_of(_edge(by["p9"], "r-lev")["c"]), "confirmed")

    def test_explicit_confidence_is_not_identity(self):
        build.spec.RELATIVES["edith"] = dict(
            name="Edith Ashdown", conf="confirmed", src=["S1"], by=1927, dead=True, years="1927–1990",
            note="Named as a probable sister.")
        build.spec.RELATIVES["nils"] = dict(
            name="Nils Ashdown", conf="confirmed", src=["U1"], by=1931, dead=True,
            note="Family lore only.")
        build.spec.OTHER_FAMILY["p4"] = list(build.spec.OTHER_FAMILY["p4"]) + [
            ("Siblings", "edith", "Sister (probable)", "probable|S3"),
            ("Siblings", "nils", "Brother (family lore)", "lore|U1"),
        ]
        by, rels, _k = self.graph()
        edith = _edge(by["p4"], "r-edith")
        nils = _edge(by["p4"], "r-nils")
        self.assertEqual(edith["c"], "probable")
        self.assertEqual(edith["kind"], "Sister (probable)")
        self.assertEqual(edith["s"], ["S3"])
        self.assertEqual(nils["c"], "lore")
        self.assertEqual(nils["kind"], "Brother (family lore)")
        # From the off-chart panel the link back to confirmed Tomas stays at the edge confidence.
        self.assertEqual(_edge(rels["r-edith"], "p4")["c"], "probable")
        self.assertEqual(_edge(rels["r-nils"], "p4")["c"], "lore")
        # A weaker explicit assertion is not overwritten by a stronger explicit one, or the reverse.
        build.spec.OTHER_FAMILY["p4"] = [
            ("Siblings", "ida", "Sister", "lore|U1") if e[1] == "ida" else e
            for e in build.spec.OTHER_FAMILY["p4"]
        ]
        build.spec.FAMILY_ASSERTIONS = [{
            "type": "sibling", "a": "p4", "b": "r-ida", "c": "confirmed", "s": ["S1"],
            "label": "Sister (index only)",
        }]
        by, rels, _k = self.graph()
        edge = _edge(by["p4"], "r-ida")
        self.assertEqual(edge["c"], "lore")
        self.assertEqual(edge["kind"], "Sister (index only)")
        self.assertEqual(edge["s"], ["S1", "U1"])
        self.assertEqual(len([e for e in by["p4"]["siblings"] if e["id"] == "r-ida"]), 1)

    def test_half_sibling_second_union_and_spouse(self):
        build.spec.RELATIVES["greta"] = dict(
            name="Greta Brannock", conf="confirmed", src=["S5"], by=1927, dead=True, years="1927–2001",
            note="Daughter of Oskar and Clara.")
        build.spec.RELATIVES["johan"] = dict(
            name="Johan Brannock", conf="possible", src=["S6"], by=1935, dead=True, years="1935–1990",
            note="Son of Oskar and a second partner.")
        build.spec.RELATIVES["annek"] = dict(
            name="Annek Holst", conf="probable", src=["S6"], by=1905, dead=True,
            note="Second partner of Oskar.")
        build.spec.OTHER_FAMILY["p10"] = [("Other children", "greta", "Daughter"),
                                          ("Other children", "johan", "Son"),
                                          ("Spouse", "annek", "Wife")]
        build.spec.OTHER_FAMILY["p11"] = list(build.spec.OTHER_FAMILY.get("p11", [])) + [
            ("Other children", "greta", "Daughter")]
        build.spec.FAMILY_ASSERTIONS = [
            {"type": "parent", "parent": "r-annek", "child": "r-johan", "c": "probable", "s": ["S6"],
             "label": "Son"},
            {"type": "half-sibling", "a": "p5", "b": "r-johan", "c": "possible", "s": ["S6"],
             "label": "Half-brother (second union)"},
        ]
        by, rels, _k = self.graph()
        self.assertEqual(_edge(by["p5"], "r-johan")["kind"], "Half-brother (second union)")
        self.assertEqual(_edge(by["p5"], "r-johan")["c"], "possible")
        self.assertEqual(_edge(rels["r-johan"], "p5")["kind"], "Half-brother (second union)")
        # Greta shares both recorded parents with Helena: a full sibling, not a half.
        self.assertEqual(_edge(by["p5"], "r-greta")["kind"], "Sibling")
        # Johan and Greta share only Oskar. The second union does not invent Clara as Johan's parent.
        self.assertEqual(_edge(rels["r-johan"], "r-greta")["kind"], "Sibling (shared parent)")
        self.assertNotEqual(_edge(rels["r-johan"], "r-greta")["kind"], "Sibling")
        for person in list(by.values()) + list(rels.values()):
            self.assertNotIn("r-annek", _ids(person))
        self.assertEqual(rels["r-annek"]["siblings"], [])

    def test_exclusion_alias_missing_and_cross_chart(self):
        build.spec.SIBLING_EXCLUSIONS = [("p9", "p19")]
        by, _rels, _k = self.graph()
        self.assertNotIn("p19", _ids(by["p9"]))
        self.assertNotIn("p9", _ids(by["p19"]))
        warns = self.coverage()
        self.assertFalse(any("p19" in w and "fewer" in w for w in warns), warns)
        # Unresolved duplicate of Dora: alias, not a sibling of herself.
        build.spec.SIBLING_EXCLUSIONS = []
        build.spec.RELATIVES["ruth"] = dict(
            name="Ruth Marrow", conf="possible", src=["S13"], by=1880, dead=True,
            note="Might be the same person as Dora.")
        for par in ("p16", "p17"):
            build.spec.OTHER_FAMILY[par] = list(build.spec.OTHER_FAMILY.get(par, [])) + [
                ("Other children", "ruth", "Daughter")]
        build.spec.CANONICAL_ALIASES = {"r-ruth": "p19"}
        by, rels, _k = self.graph()
        self.assertNotIn("r-ruth", _ids(by["p19"]))
        self.assertNotIn("p19", _ids(rels["r-ruth"]))
        self.assertNotIn("r-ruth", _ids(rels["r-ruth"]))
        self.assertIn("p9", _ids(by["p19"]))
        self.assertIn("p9", _ids(rels["r-ruth"]))
        self.assertEqual(_ids(by["p19"]).count("p9"), 1)
        # Missing target and an on-chart pair that is not a fan child pointer.
        before = {i: (p.get("child"), list(p.get("children") or [])) for i, p in by.items()}
        build.spec.CANONICAL_ALIASES = {}
        build.spec.FAMILY_ASSERTIONS = [
            {"type": "sibling", "a": "p4", "b": "ghost", "c": "possible", "s": ["S1"], "label": "Brother"},
            {"type": "sibling", "a": "p9", "b": "p6", "c": "possible", "s": ["S99", "S12"],
             "label": "Possible sibling (not parentage)"},
        ]
        by, rels, _k = self.graph()
        self.assertTrue(all("ghost" not in _ids(p) and "r-ghost" not in _ids(p)
                            for p in list(by.values()) + list(rels.values())))
        self.assertEqual(_edge(by["p9"], "p6")["c"], "possible")
        self.assertEqual(_edge(by["p9"], "p6")["s"], ["S12"])
        self.assertNotIn("S99", _edge(by["p9"], "p6")["s"])
        self.assertEqual(_edge(by["p6"], "p9")["kind"], "Possible sibling (not parentage)")
        self.assertEqual({i: (p.get("child"), list(p.get("children") or [])) for i, p in by.items()}, before)

    def test_name_only_edge_drops_hidden_fields_and_unknown_sources(self):
        build.spec.OTHER_FAMILY["p2"] = [
            ("Siblings", "nora", "Sister", "lore|U1,S99") if e[1] == "nora" else e
            for e in build.spec.OTHER_FAMILY["p2"]
        ]
        by, rels, _k = self.graph()
        edge = _edge(by["p2"], "r-nora")
        self.assertEqual(set(edge), {"id", "c", "s", "kind"})
        self.assertEqual(edge["s"], ["U1"])
        self.assertNotIn("S99", edge["s"])
        blob = str(edge)
        self.assertNotIn("1960", blob)
        self.assertNotIn("family knowledge", blob.lower())
        self.assertNotIn("f", by["p1"])

    def test_output_is_deterministic(self):
        build.spec.OTHER_FAMILY = {k: list(reversed(v)) for k, v in build.spec.OTHER_FAMILY.items()}
        by1, rels1, _k = self.graph()
        build.spec.OTHER_FAMILY = {k: list(reversed(v)) for k, v in build.spec.OTHER_FAMILY.items()}
        by2, rels2, _k = self.graph()

        def dump(by, rels):
            return {i: p["siblings"] for i, p in {**by, **rels}.items()}
        self.assertEqual(dump(by1, rels1), dump(by2, rels2))

    def test_app_js_uses_one_section_for_both_panels(self):
        js = open(os.path.join(SITE, "web", "app.js"), encoding="utf-8").read()
        self.assertIn("function siblingsSection(", js)
        self.assertIn("All known siblings", js)
        self.assertGreaterEqual(js.count("siblingsSection("), 3)


def base_of(c):
    return str(c).split(";", 1)[0].strip()


class CoverageWarnings(SibBase):
    def test_named_sibling_and_child_of_a_couple_not_encoded(self):
        # Research names a sister and a child of a couple who have no person records.
        people = PEOPLE_MD.replace(
            "- Sister: Ida Ashdown, b. 1923 (S3, confirmed)\n",
            "- Sister: Ida Ashdown, b. 1923 (S3, confirmed)\n- Sister: Mara Quill (S1, possible)\n",
        )
        rels = REL_MD + "\n- P8 and P9 are the parents of P40 (S1, confirmed)\n"
        warns = self.coverage(people_md=people, relationships_md=rels)
        self.assertTrue(any("Mara Quill" in w and "not encoded as a linked person" in w for w in warns), warns)
        self.assertTrue(any("P40" in w and "not encoded as a linked person" in w and "couple" in w for w in warns), warns)

    def test_one_way_claim_is_not_reciprocal_and_panel_shows_fewer(self):
        # Drop the explicit wiring and the reverse note, but leave the people.md sister line.
        build.spec.OTHER_FAMILY = {k: [e for e in v if e[1] != "ida"] for k, v in build.spec.OTHER_FAMILY.items()}
        build.spec.RELATIVES["ida"] = dict(build.spec.RELATIVES["ida"], note="Birth act S3.")
        warns = self.coverage()
        self.assertTrue(any("is not reciprocal" in w for w in warns), warns)
        self.assertTrue(any("panel would show fewer siblings" in w and "r-ida" in w for w in warns), warns)


if __name__ == "__main__":
    unittest.main()

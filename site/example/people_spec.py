"""FICTIONAL EXAMPLE spec for the Family Tree Kit site.

Every person, place, date, archive and record in this file and in example/data/ is INVENTED for
demonstration. The countries ("Velmar", "Ardenia"), towns and archives do not exist; URLs use the
reserved example.org domain. Any resemblance to real people is coincidental.

Your own spec is PERSONAL DATA: keep it in your private project folder (for example
~/genealogy-trees/<tree-name>/site/people_spec.py) and point site.config.json at it. Never commit it to
the public kit.

Schema (see also site/SPEC.md)
------------------------------
PEOPLE: direct ancestors only (the fan chart). Fields:
  id        short unique id used by the site ("p1" is the home person by default; see HOME)
  pid       P-number in people.md (optional; validated)
  name, sex ("M"/"F")
  child     id of the person this one is a parent of (None for the home person). PEDIGREE COLLAPSE: a
            list of ids when the same person is a parent of two people on the chart, e.g.
            child=["p9", "p19"]. The first id is the primary position (full arc, own ancestors behind it);
            each further id gives a repeat arc marked "↺" that links back to the primary arc.
  line      "root" (home person), "paternal"/"maternal" (parents), or one of the four grandparent lines
            "pp" (father's father), "pm" (father's mother), "mp" (mother's father), "mm" (mother's mother)
  conf      overall confidence: confirmed | probable | possible | lore
  born, died, places   free text; ";" splits parts that carry their own FIELDS entry
  src       S- and U-numbers (validated against sources.md / PSEUDO_SOURCES)
  note      short paragraph
  by        birth year or estimate (privacy rule); death=True if any death is recorded
  name_only True to force name-only display
FIELDS[id][field] = "conf|S1,S2" or a list (one per ";" part). Fields: born, died, places, occ, aka,
  link (parentage: this person is a parent of `child`), link_<child id> (parentage for a further child
  in a pedigree collapse), spouse (married the other parent of `child`).
OCC, AKA: occupation and name variants per id.
LINES: labels for the line keys (shown in the legend and filters; inside the protected site only).
PSEUDO_SOURCES: U-numbers (family testimony).
OPEN_QUESTIONS: the few key questions to show (the full open-questions.md stays private).
ARCHIVE_REQUESTS: (code, archive, what, status) rows.
RELATIVES + OTHER_FAMILY: relatives not on the fan, attached to fan people in "Other family" panels.
GAZETTEER, PLACE_ALIASES: search places and spelling variants (keys folded: lower case, no accents).
SOURCE_TITLES: hand-written titles; UNLINKED_SOURCES: shown although nobody cites them.
RESTRICTED_SOURCES {S: reason}: never published. PUBLIC_RECENT_SOURCES: recent records allowed in strict mode.
"""

FICTIONAL_EXAMPLE = True
HOME = "p1"
BYLINE = "Fictional example family (all names and places are invented)"

PEOPLE = [
    # ---- generation 0 / 1 ----
    dict(id="p1", pid="P1", name="Rowan Ashdown", sex="F", child=None, line="root", conf="confirmed",
         born="12 May 1988, Port Sallow, Ardenia", places="Port Sallow, Ardenia", src=["U1"], by=1988,
         note="Home person of the fictional example."),
    dict(id="p2", pid="P2", name="Daniel Ashdown", sex="M", child="p1", line="paternal", conf="lore",
         born="1958, Port Sallow", places="Port Sallow, Ardenia", src=["U1"], by=1958,
         note="Son of Tomas Ashdown and Helena Brannock (family knowledge)."),
    dict(id="p3", pid="P3", name="Miriam Corvell", sex="F", child="p1", line="maternal", conf="lore",
         born="1961, Haverlow", places="Haverlow; Port Sallow, Ardenia", src=["U1"], by=1961,
         note="Daughter of Samuel Corvell and Rosa Delmont (family knowledge)."),

    # ---- father's father line (pp) ----
    dict(id="p4", pid="P4", name="Tomas Ashdown", sex="M", child="p2", line="pp", conf="confirmed",
         born="3 Feb 1925, Kestrava, Velmar", died="1999, Port Sallow", by=1925, death=True,
         places="Kestrava, Velmar; Port Sallow, Ardenia (from 1948)", src=["S1", "S4", "U1"],
         note="Emigrated from Velmar to Ardenia in 1948 (passenger list S4). His birth act (S1) names both parents."),
    dict(id="p8", pid="P8", name="Jakob Ashdown", sex="M", child="p4", line="pp", conf="confirmed",
         born="c. 1896, Kestrava (age 29 in 1925)", died="Unknown", by=1896, death=True,
         places="Kestrava, Velmar", src=["S1", "S2"],
         note="Weaver. Father on the 1925 birth act (S1); groom on the 1921 marriage act (S2). "
              "Death not yet found; the family says he died in Kestrava before 1948."),
    dict(id="p9", pid="P9", name="Lena (Lina) Marrow", sex="F", child="p4", line="pp", conf="confirmed",
         born="c. 1899, Brindlow", by=1899, death=True, died="before 1948 (family)",
         places="Brindlow; Kestrava, Velmar", src=["S1", "S2"],
         note="Bride on the 1921 marriage act (S2), daughter of Aron Marrow and Rachel."),
    # pedigree collapse: Aron and Rachel are the parents of Lena (p9, primary position) and probably
    # also of Dora (p19), Hanna Quill's mother, so they appear twice in the fan.
    dict(id="p16", pid="P16", name="Aron Marrow", sex="M", child=["p9", "p19"], line="pp", conf="probable",
         born="c. 1855 (estimate)", by=1855, death=True, died="before 1921 (\u201clate\u201d on S2)",
         places="Brindlow, Velmar", src=["S2", "S13"],
         note="Named as the bride's late father on the 1921 marriage act (S2). Probably also Dora Marrow's father "
              "(S13), which makes him an ancestor twice (pedigree collapse)."),
    dict(id="p17", pid="P17", name="Rachel", sex="F", child=["p9", "p19"], line="pp", conf="probable",
         born="Unknown", by=1858, death=True, places="Brindlow, Velmar", src=["S2", "S13"],
         note="Maiden name not stated on S2. Probably also Dora Marrow's mother (S13)."),

    # ---- father's mother line (pm) ----
    dict(id="p5", pid="P5", name="Helena Brannock", sex="F", child="p2", line="pm", conf="probable",
         born="1929, Orvenna, Velmar", died="2010, Port Sallow", by=1929, death=True,
         places="Orvenna, Velmar; Port Sallow, Ardenia", src=["S5", "U1"],
         note="Married Tomas Ashdown in Port Sallow in 1952 (S5)."),
    dict(id="p10", pid="P10", name="Oskar Brannock", sex="M", child="p5", line="pm", conf="probable",
         born="c. 1900", by=1900, death=True, died="1944 (family)", places="Orvenna, Velmar", src=["S5", "S6"],
         note="Named as Helena's father on the 1952 marriage record (S5); a 1931 town list (S6) shows a tailor of this name."),
    dict(id="p11", pid="P11", name="Clara Wendt", sex="F", child="p5", line="pm", conf="possible",
         born="Unknown", by=1903, death=True, places="Orvenna, Velmar", src=["S5", "U2"],
         note="The 1952 record gives the mother as \u201cClara W[?]\u201d; the family remembers Wendt."),

    # ---- mother's father line (mp) ----
    dict(id="p6", pid="P6", name="Samuel Corvell", sex="M", child="p3", line="mp", conf="confirmed",
         born="1930, Saltreach, Ardenia", died="2004, Haverlow", by=1930, death=True,
         places="Saltreach; Haverlow, Ardenia", src=["S7", "S8", "U1"],
         note="Born in Ardenia to immigrant parents (S7)."),
    dict(id="p12", pid="P12", name="Elias Corvell", sex="M", child="p6", line="mp", conf="confirmed",
         born="c. 1901, Kestrava, Velmar", died="1967, Saltreach", by=1901, death=True,
         places="Kestrava, Velmar; Saltreach, Ardenia (from 1927)", src=["S7", "S9"],
         note="Gravestone (S9) gives his father's name as Natan."),
    dict(id="p13", pid="P13", name="Hanna Quill", sex="F", child="p6", line="mp", conf="confirmed",
         born="c. 1905", died="Unknown", by=1905, death=True, places="Saltreach, Ardenia", src=["S7"],
         note="Mother on Samuel's 1930 birth record (S7)."),
    dict(id="p19", pid="P19", name="Dora Marrow", sex="F", child="p13", line="mp", conf="probable",
         born="c. 1880, Brindlow", by=1880, death=True, died="Unknown", places="Brindlow, Velmar", src=["S12", "S13"],
         note="Hanna Quill's mother on the 1924 marriage index (S12); a Dora Marrow born 1880 in Brindlow to Aron "
              "and Rachel (S13) is probably her. Lena Marrow (p9) would then be her sister."),
    dict(id="p18", pid="P18", name="Natan Corvell", sex="M", child="p12", line="mp", conf="possible",
         born="Unknown", by=1875, death=True, places="Kestrava, Velmar (probably)", src=["S9", "S10"],
         note="Father's name from Elias's gravestone (S9). A Natan Corvell in the 1890s Kestrava index (S10) may be him: possible only."),

    # ---- mother's mother line (mm) ----
    dict(id="p7", pid="P7", name="Rosa Delmont", sex="F", child="p3", line="mm", conf="lore",
         born="1933, Haverlow", died="2015, Haverlow", by=1933, death=True, places="Haverlow, Ardenia", src=["U1"],
         note="Family knowledge only; no record yet."),
    dict(id="p14", pid="P14", name="Viktor Delmont", sex="M", child="p7", line="mm", conf="lore",
         born="Unknown", by=1905, death=True, places="Velmar (family)", src=["U2"],
         note="The family says he came from \u201csomewhere near Orvenna\u201d."),
    dict(id="p15", pid="P15", name="Sofia Tresk", sex="F", child="p7", line="mm", conf="lore",
         born="Unknown", by=1908, death=True, places="Haverlow, Ardenia", src=["U2"], note=""),
]

PSEUDO_SOURCES = {
    "U1": {"title": "Family interview with the home person (fictional example)", "urls": []},
    "U2": {"title": "Family lore from an aunt, relayed by the home person (fictional example)", "urls": []},
}

OPEN_QUESTIONS = [
    "When and where did Jakob Ashdown die? The family says Kestrava, before 1948.",
    "Was Clara Brannock's maiden name Wendt? The 1952 record is hard to read.",
    "Is the Natan Corvell of the Kestrava index (S10) Elias's father?",
    "Is Dora Marrow (S13) really Lena's sister? If so Aron and Rachel are ancestors twice.",
    "No record yet for Rosa Delmont's parents: the Haverlow civil registry has not been asked.",
]

ARCHIVE_REQUESTS = [
    ("A", "Kestrava District Archive (fictional)", "Ashdown deaths 1930\u20131948; Corvell births 1895\u20131905", "awaiting"),
    ("B", "Haverlow Civil Registry (fictional)", "Delmont \u00d7 Tresk marriage, c. 1930", "hold"),
]

LINES = {
    "root": "Home person",
    "paternal": "Paternal",
    "maternal": "Maternal",
    "pp": "Ashdown \u00b7 Marrow",
    "pm": "Brannock \u00b7 Wendt",
    "mp": "Corvell \u00b7 Quill",
    "mm": "Delmont \u00b7 Tresk",
}

FIELDS = {
    "p1": dict(born="confirmed|U1", places="confirmed|U1"),
    "p2": dict(born="lore|U1", link="lore|U1"),
    "p3": dict(born="lore|U1", link="lore|U1"),
    "p4": dict(born="confirmed|S1", died="lore|U1", places=["confirmed|S1", "confirmed|S4"], link="lore|U1",
               spouse="confirmed|S5"),
    "p8": dict(born="probable|S1", places="confirmed|S1,S2", occ="confirmed|S2", link="confirmed|S1", spouse="confirmed|S2"),
    "p9": dict(born="probable|S2", died="lore|U1", places=["confirmed|S2", "confirmed|S1"], link="confirmed|S1"),
    "p16": dict(link="probable|S2", link_p19="probable|S13", died="probable|S2"),
    "p17": dict(link="probable|S2", link_p19="probable|S13"),
    "p19": dict(born="probable|S13", places="probable|S12,S13", link="probable|S12"),
    "p5": dict(born="probable|S5", died="lore|U1", places=["probable|S5", "lore|U1"], link="lore|U1"),
    "p10": dict(link="probable|S5", occ="possible|S6", died="lore|U2"),
    "p11": dict(link="possible|S5,U2", aka="lore|U2"),
    "p6": dict(born="confirmed|S7", died="confirmed|S8", places="confirmed|S7,S8", link="lore|U1", spouse="lore|U1"),
    "p12": dict(born="probable|S9", died="confirmed|S9", places=["probable|S9", "confirmed|S7"], link="confirmed|S7",
                spouse="confirmed|S7"),
    "p13": dict(link="confirmed|S7"),
    "p18": dict(link="possible|S9,S10"),
    "p7": dict(born="lore|U1", died="lore|U1", link="lore|U1"),
    "p14": dict(link="lore|U2", spouse="lore|U2"),
    "p15": dict(link="lore|U2"),
}

OCC = {"p8": "Weaver", "p10": "Tailor (1931 town list, possible)", "p12": "Baker"}
AKA = {"p9": "Lina", "p11": "Clara W[?] (1952 record)", "p12": "Eli"}

SOURCE_TITLES = {}

RELATIVES = {
    "ida": dict(name="Ida Ashdown", conf="confirmed", src=["S3"], by=1923, dead=True, years="1923\u20131943",
                born="1923, Kestrava", places="Kestrava, Velmar", note="Elder sister of Tomas (birth act S3)."),
    "benjamin": dict(name="Benjamin Corvell", conf="probable", src=["S7"], by=1928, dead=True, years="1928\u20131990",
                     places="Saltreach, Ardenia", note="Elder brother of Samuel, named as a sibling on S7."),
    "nora": dict(name="Nora Ashdown", conf="lore", src=["U1"], by=1960,
                 note="Sister of Daniel (family knowledge)."),
}

OTHER_FAMILY = {
    "p4": [("Siblings", "ida", "Sister")],
    "p8": [("Other children", "ida", "Daughter")],
    "p9": [("Other children", "ida", "Daughter")],
    "p6": [("Siblings", "benjamin", "Brother")],
    "p12": [("Other children", "benjamin", "Son")],
    "p2": [("Siblings", "nora", "Sister")],
}

GAZETTEER = {"Kestrava", "Brindlow", "Orvenna", "Velmar", "Ardenia", "Port Sallow", "Haverlow", "Saltreach"}
PLACE_ALIASES = {"kestrawa": "Kestrava", "port salow": "Port Sallow"}

UNLINKED_SOURCES = ["S11"]
RESTRICTED_SOURCES = {}
# Strict mode hides records under 100 years old; these three (fictional) ones are allowed, to show the switch.
PUBLIC_RECENT_SOURCES = {"S4", "S7", "S9"}

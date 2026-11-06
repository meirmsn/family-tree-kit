"""v0.2.17 — add empty name-variant and possible-match fields if they are absent.

No-op when ``NAME_FORMS``, ``POSSIBLE_MATCHES``, and ``MATCH_EXCLUSIONS`` are
already assigned. Does not change relationships, facts, or confidence, and does
not merge people.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

VERSION = "0.2.17"


def apply(project, dry_run=False):
    return common.ensure_empty(
        project,
        (
            ("NAME_FORMS", "{}"),
            ("POSSIBLE_MATCHES", "[]"),
            ("MATCH_EXCLUSIONS", "[]"),
        ),
        dry_run=dry_run,
        intro="# v0.2.17: empty name spellings and unmerged possible matches. Not inferred.",
    )

"""v0.2.16 — add empty sibling-structure fields if they are absent.

No-op when ``FAMILY_ASSERTIONS``, ``SIBLING_EXCLUSIONS``, and ``CANONICAL_ALIASES``
are already assigned. Does not change relationships, facts, or confidence, and
does not merge people.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

VERSION = "0.2.16"


def apply(project, dry_run=False):
    return common.ensure_empty(
        project,
        (
            ("FAMILY_ASSERTIONS", "[]"),
            ("SIBLING_EXCLUSIONS", "[]"),
            ("CANONICAL_ALIASES", "{}"),
        ),
        dry_run=dry_run,
        intro="# v0.2.16: empty unless a link is recorded. Not inferred.",
    )

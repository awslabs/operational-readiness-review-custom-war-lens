"""Release notes for a dated release tag, taken from CHANGELOG.md.

A release tag is release-YYYY-MM-DD. The notes are every CHANGELOG.md section whose heading is dated with that day,
in file order. Both heading styles are accepted: "## [2099-01-15] core 2.0.0 and event 1.0.0" (one section per
dated release) and "## [core 2.0.0] - 2099-01-15" (one section per lens). An "## [Unreleased]" section is always
skipped, even if it carries a date ("## [Unreleased] - 2099-01-15"), because it holds work that is not part of any
release yet. A release with no dated section is an error, so a release never ships without its changelog.

Relative Markdown links are rewritten to absolute ones at the release tag. On a release page a relative link
resolves against /releases/tag/<tag>/, where no repository file exists, so "[MIGRATION.md](MIGRATION.md)" becomes
"<repo>/blob/<tag>/MIGRATION.md". Absolute links, in-page anchors and mail links are left alone.
"""

from __future__ import annotations

import datetime
import re

from . import config as C

TAG_RE = re.compile(r"^release-(\d{4}-\d{2}-\d{2})$")
# A Markdown inline link target that is a repository-relative path: not a scheme, not "//", not an anchor.
RELATIVE_LINK_RE = re.compile(r"(?<=\]\()(?!\s)(?![a-zA-Z][a-zA-Z0-9+.-]*:)(?!//)(?!#)([^()\s]+)(?=\))")
UNRELEASED_RE = re.compile(r"^## \[\s*unreleased\s*\]", re.I)
HEADING_RES = [re.compile(r"^## \[(?P<date>\d{4}-\d{2}-\d{2})\]\s*(?P<name>.*?)\s*$"),
               re.compile(r"^## \[(?P<name>[^\]]+)\] - (?P<date>\S+)(?:\s.*)?$")]


def _heading(line: str):
    for rx in HEADING_RES:
        m = rx.match(line)
        if m:
            return m
    return None


class ReleaseNotesError(Exception):
    pass


def tag_date(tag: str) -> str:
    m = TAG_RE.match(tag or "")
    if not m:
        raise ReleaseNotesError(f"tag {tag!r} is not release-YYYY-MM-DD")
    try:
        datetime.date.fromisoformat(m.group(1))
    except ValueError as exc:
        raise ReleaseNotesError(f"tag {tag!r} does not carry a real date") from exc
    return m.group(1)


def sections(changelog: str) -> list:
    """(name, date, text) for every dated "## " section of CHANGELOG.md, in file order; "## [Unreleased]" excluded."""
    out, cur = [], None
    for line in changelog.splitlines():
        m = None if UNRELEASED_RE.match(line) else _heading(line)
        if m or line.startswith("## "):
            if cur:
                out.append(cur)
            cur = (m.group("name") or m.group("date"), m.group("date"), [line]) if m else None
            continue
        if cur:
            cur[2].append(line)
    if cur:
        out.append(cur)
    return [(n, d, "\n".join(lines).strip() + "\n") for n, d, lines in out]


def absolutize_links(text: str, tag: str) -> str:
    """Rewrite repository-relative Markdown link targets to absolute URLs at the release tag."""
    base = f"{C.SELF_REPO_URL}/blob/{tag}/"
    return RELATIVE_LINK_RE.sub(lambda m: base + m.group(1).lstrip("./"), text)


def notes_for(changelog: str, tag: str) -> str:
    date = tag_date(tag)
    picked = [(n, text) for n, d, text in sections(changelog) if d == date]
    if not picked:
        placeholders = [n for n, d, _ in sections(changelog) if "{{" in d]
        hint = f" (sections with a placeholder date: {', '.join(placeholders)})" if placeholders else ""
        raise ReleaseNotesError(f"CHANGELOG.md has no section dated {date}{hint}")
    return absolutize_links("\n".join(text for _, text in picked), tag)

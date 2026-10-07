"""Which files the public export contains, and the internal-wording scan over them.

The public repository receives the tracked tree (git ls-files) minus the private-only paths below. The
internal-wording check scans exactly that set (plus, while drafting, untracked files that are not ignored, so new
files are scanned before anyone commits them).

Symbolic links are never exported: a link on a public path could point into private/ and would be copied as a
regular file. Files that are not UTF-8 (or UTF-16/UTF-32 with a byte order mark) text fail the scan unless their
extension is on config.BINARY_EXTENSIONS, so text in an unexpected encoding cannot slip past it.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from pathlib import Path

from . import config as C
from .textscan import decode_text, parse_denylist, scan_text_with_denylist

# Never exported. Folder patterns end with "/" and match at the root; "**/<name>/" matches a folder of that name at
# any depth.
PRIVATE_ONLY = [
    "private/",
    "**/private/",
    "build/",
    ".gitlab-ci.yml",
    ".gitlab-ci.yaml",
    ".gitlab/",
    "**/.gitlab/",
    ".gitlab-*",
    "*.private.md",
    "*.private.yaml",
    "*.private.json",
    "**/*.private.*",
]

# Already-public history: the published v1 files are not scanned for internal wording.
WORDING_EXEMPT = [f"{C.V1_DIR}/orr-v1.3.*-PUBLISHED.json"]


class ExportError(Exception):
    """The tree cannot be exported safely (for example a symbolic link, or git is unavailable)."""


def is_private(rel: str) -> bool:
    parts = Path(rel).parts
    for pat in PRIVATE_ONLY:
        if pat.startswith("**/") and pat.endswith("/"):
            if pat[3:-1] in parts[:-1] or (parts and parts[-1] == pat[3:-1]):
                return True
        elif pat.endswith("/"):
            if rel == pat[:-1] or rel.startswith(pat):
                return True
        elif fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(Path(rel).name, pat):
            return True
    return False


def _git(root: Path, *args) -> list:
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


def tracked_files(root: Path) -> list:
    return sorted(_git(root, "ls-files", "-z", "--cached"))


def untracked_files(root: Path) -> list:
    return sorted(_git(root, "ls-files", "-z", "--others", "--exclude-standard"))


def symlink_problems(root: Path, files) -> list:
    """A problem string for every path that is, or passes through, a symbolic link."""
    out = []
    for rel in files:
        p = root
        for part in Path(rel).parts:
            p = p / part
            if os.path.islink(p):
                try:
                    target = os.path.realpath(p)
                except OSError:
                    target = "?"
                out.append(f"{rel}: symbolic links are never exported ({p.relative_to(root)} -> {target}); "
                           "replace it with a regular file or remove it")
                break
    return out


def export_files(root: Path, include_untracked: bool = False) -> list:
    """Relative paths that the public export would contain.

    Raises ExportError when git cannot list the files (the export never falls back to every file on disk, which
    would include ignored files such as .venv or a local .env) or when an exported path is a symbolic link.
    """
    try:
        files = tracked_files(root)
        if include_untracked:
            files = sorted(set(files) | set(untracked_files(root)))
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ExportError(f"cannot list the exportable files with git ({exc}); run the export from a git "
                          "checkout") from exc
    files = [f for f in files if not is_private(f)]
    problems = symlink_problems(root, files)
    if problems:
        raise ExportError("\n".join(problems))
    return [f for f in files if (root / f).is_file()]


def load_denylist(path: Path):
    """Return (patterns, problems), or (None, []) when the denylist does not exist (public clones)."""
    if not path.exists():
        return None, []
    return parse_denylist(path.read_text(encoding="utf-8"))


def sensitive_patterns() -> list:
    """Built-in patterns (account ids, ARNs with an account id) in the denylist's (line, regex) shape."""
    return [(f"built-in: {name}", re.compile(rx)) for name, rx in C.SENSITIVE_PATTERNS]


def wording_scan(scan_root: Path, files, patterns) -> list:
    """Return "file:line: match" strings for every denylist hit in the given files under scan_root.

    Also reports files that cannot be scanned: symbolic links, and files that are not text in a known encoding
    and do not have an allowlisted binary extension.
    """
    hits = []
    for rel in files:
        if any(fnmatch.fnmatch(rel, pat) for pat in WORDING_EXEMPT):
            continue
        if rel == C.DENYLIST_FILE:
            continue
        path = scan_root / rel
        if os.path.islink(path):
            hits.append(f"{rel}: is a symbolic link; symbolic links are never exported")
            continue
        if not path.is_file():
            continue
        for ln, match in scan_text_with_denylist(rel, patterns):
            hits.append(f"{rel}: file name matches: {match}")
        if rel.lower().endswith(C.BINARY_EXTENSIONS):
            continue
        text = decode_text(path.read_bytes())
        if text is None:
            hits.append(f"{rel}: not UTF-8 text (or UTF-16/UTF-32 with a byte order mark) and not an allowlisted "
                        f"binary type ({', '.join(C.BINARY_EXTENSIONS)}); the internal-wording check cannot scan it")
            continue
        for ln, match in scan_text_with_denylist(text, patterns):
            hits.append(f"{rel}:{ln}: {match}")
    return hits

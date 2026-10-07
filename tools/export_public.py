#!/usr/bin/env python3
"""Export the public tree of this repository into <target_dir>, after scanning it.

    python3 tools/export_public.py <target_dir> [--delete] [--allow-dirty]

- Copies every tracked file (git ls-files) except the private-only paths in tools/orrlens/export.py
  (maintainer-only paths, build/, non-public CI configuration, *.private.* and similar). The
  working-tree content of each tracked file is
  copied, so commit first; the export refuses to run with uncommitted changes unless --allow-dirty is given.
  Symbolic links are refused, and the export fails if git cannot list the files.
- The export is first staged in a temporary directory. The internal-wording check (the maintainer-only denylist
  file from this repository, plus the built-in account-id and ARN patterns) and a check for private paths and
  symbolic links run
  on the staged tree. Only when both pass is the target touched, so a failed scan never leaves files behind.
- target_dir must be either a new or empty directory (a scratch export), or a git worktree whose remotes include
  the public repository (github.com/awslabs/operational-readiness-review-custom-war-lens). It must be outside this
  repository. With --delete, which needs the public worktree, files in target_dir that the export does not
  contain are removed (never .git); without it they are listed.
- Hits are reported as file:line: match, and the script exits non-zero.

This script never runs git commit, push or tag; the maintainer does that by hand.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orrlens import config as C  # noqa: E402
from orrlens.export import (ExportError, export_files, is_private, load_denylist, sensitive_patterns,  # noqa: E402
                            wording_scan)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_REMOTE_RE = re.compile(r"(?:^|[/:@])github\.com[/:]" + re.escape(C.SELF_REPO_SLUG) + r"(?:\.git)?/?$", re.I)


def is_public_worktree(target: Path) -> bool:
    """True when target is the top level of a git worktree with a remote that points to the public repository."""
    if not (target / ".git").exists():
        return False
    top = subprocess.run(["git", "-C", str(target), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != target:
        return False
    remotes = subprocess.run(["git", "-C", str(target), "remote", "-v"], capture_output=True, text=True)
    if remotes.returncode != 0:
        return False
    return any(PUBLIC_REMOTE_RE.search(line.split()[1]) for line in remotes.stdout.splitlines()
               if len(line.split()) >= 2)


def tree_problems(tree: Path) -> list:
    """Private paths and symbolic links in an exported tree (walked on disk, not taken from the file list)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(tree):
        dirnames[:] = [d for d in dirnames if not (Path(dirpath) == tree and d == ".git")]
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            rel = str(p.relative_to(tree))
            if os.path.islink(p):
                out.append(f"symbolic link in the export: {rel}")
            elif is_private(rel) or name in (".gitlab-ci.yml", ".gitlab-ci.yaml"):
                out.append(f"private path in the export: {rel}")
    return out


def extras(target: Path, wanted: set) -> list:
    out = []
    for dirpath, dirnames, filenames in os.walk(target):
        if Path(dirpath) == target:
            dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            rel = str((Path(dirpath) / name).relative_to(target))
            if rel != ".git" and rel not in wanted:
                out.append(rel)
    return sorted(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir")
    ap.add_argument("--delete", action="store_true",
                    help="remove files in target_dir that the export lacks (target must be a public worktree)")
    ap.add_argument("--allow-dirty", action="store_true", help="export even with uncommitted changes")
    args = ap.parse_args(argv)

    target = Path(args.target_dir).expanduser().resolve()
    if target == ROOT or ROOT in target.parents or target in ROOT.parents:
        print(f"refusing: {target} is this repository, inside it, or one of its parent folders", file=sys.stderr)
        return 2
    if target.exists() and not target.is_dir():
        print(f"refusing: {target} is not a directory", file=sys.stderr)
        return 2
    public = target.is_dir() and is_public_worktree(target)
    empty = not target.exists() or not any(target.iterdir())
    if not (public or empty):
        print(f"refusing: {target} is neither empty nor a git worktree of github.com/{C.SELF_REPO_SLUG} "
              "(check the path, or add the worktree with 'git worktree add <dir> public/main --detach')",
              file=sys.stderr)
        return 2
    if args.delete and not public:
        print(f"refusing: --delete needs a git worktree of github.com/{C.SELF_REPO_SLUG}", file=sys.stderr)
        return 2
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True,
                           check=True).stdout.strip()
    if dirty and not args.allow_dirty:
        print("refusing: the working tree has uncommitted changes (commit them, or pass --allow-dirty)",
              file=sys.stderr)
        return 2

    pats, problems = load_denylist(ROOT / C.DENYLIST_FILE)
    if pats is None:
        print(f"refusing: {C.DENYLIST_FILE} not found; the internal-wording check cannot run", file=sys.stderr)
        return 2
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    try:
        files = export_files(ROOT)
    except ExportError as exc:
        print(f"refusing:\n{exc}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="orr-export-") as tmp:
        stage = Path(tmp) / "public"
        for rel in files:
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dst, follow_symlinks=False)
        print(f"staged {len(files)} files")

        bad = tree_problems(stage)
        hits = wording_scan(stage, files, pats + sensitive_patterns())
        if bad or hits:
            if bad:
                print(f"\nEXPORT CHECK FAILED: {len(bad)} private path(s) or symbolic link(s)", file=sys.stderr)
                for b in bad:
                    print(f"  {b}", file=sys.stderr)
            if hits:
                print(f"\nINTERNAL-WORDING CHECK FAILED: {len(hits)} hit(s) in the exported tree", file=sys.stderr)
                for h in hits:
                    print(f"  {h}", file=sys.stderr)
            print(f"\nnothing was written to {target}", file=sys.stderr)
            return 1
        print(f"internal-wording check passed: {len(pats)} denylist patterns plus the built-in patterns, "
              f"{len(files)} files, 0 hits")

        target.mkdir(parents=True, exist_ok=True)
        for rel in files:
            dst = target / rel
            if os.path.islink(dst):
                dst.unlink()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / rel, dst, follow_symlinks=False)
    print(f"exported {len(files)} files to {target}")

    for rel in extras(target, set(files)):
        if args.delete:
            (target / rel).unlink()
            print(f"deleted {rel} (not in the export)")
        else:
            print(f"extra file in target (not in the export; use --delete to remove): {rel}")
    if args.delete:
        for dirpath, _dirnames, _ in sorted(os.walk(target), key=lambda x: -len(x[0])):
            if ".git" in Path(dirpath).relative_to(target).parts:
                continue
            p = Path(dirpath)
            if p != target and not any(p.iterdir()):
                p.rmdir()
    bad = tree_problems(target)
    if bad:
        print("\nprivate paths or symbolic links are present in the target:", file=sys.stderr)
        for b in bad:
            print(f"  {b}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

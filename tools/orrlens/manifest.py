"""dist/manifest.json, dist/SHA256SUMS and the release staging directory build/release/.

dist/ holds the versioned lens files (orr-core-2.0.0.json, orr-core-2.0.0.min.json, ...), manifest.json and
SHA256SUMS. The version-free copies that GitHub's releases/latest/download/<file> aliases need, one pair per lens
under lens-src/ (orr-core.json, orr-core.min.json, orr-event.json, orr-event.min.json, orr-genai.json,
orr-genai.min.json), are written only to build/release/, never to dist/.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import config as C
from .render import dumps


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sha256sums(files: dict) -> str:
    """files: name -> content. Output in the format of `sha256sum` (two spaces, sorted by name)."""
    return "".join(f"{_sha(content)}  {name}\n" for name, content in sorted(files.items()))


def source_commit(root: Path):
    """The commit recorded in a manifest: ORRLENS_SOURCE_COMMIT or GITHUB_SHA when set, else None.

    A local build records no commit, so that a manifest built outside the release workflow never names a commit
    that does not exist in the public repository. The release workflow sets ORRLENS_SOURCE_COMMIT to the commit
    it builds. `sources_dirty` is reported as a build warning only, never written to the manifest.
    """
    return os.environ.get("ORRLENS_SOURCE_COMMIT") or os.environ.get("GITHUB_SHA") or None


def sources_dirty(root: Path) -> bool:
    """True when lens-src/ or data/ has uncommitted changes (reported as a warning by `manifest`)."""
    try:
        return bool(subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "lens-src", "data"],
                                   capture_output=True, text=True, check=True).stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def build_manifest(ctx, source_commit: str | None, dirty: bool = False) -> dict:
    lenses = []
    for lens in ctx.lenses:
        doc = ctx.rendered[lens.key]
        stem = f"{lens.meta.get('file_stem')}-{lens.version}"
        pretty, mini = dumps(doc), dumps(doc, minify=True)
        lenses.append({
            "key": lens.key,
            "name": doc["name"],
            "version": lens.version,
            "schemaVersion": doc["schemaVersion"],
            "pillars": len(doc["pillars"]),
            "questions": sum(len(p["questions"]) for p in doc["pillars"]),
            "statements": sum(len(q["choices"]) - 1 for p in doc["pillars"] for q in p["questions"]),
            "file": f"{stem}.json",
            "sha256": _sha(pretty),
            "bytes": len(pretty.encode()),
            "min_file": f"{stem}.min.json",
            "min_sha256": _sha(mini),
            "min_bytes": len(mini.encode()),
            "latest_alias": f"{lens.meta.get('file_stem')}.json",
            "latest_min_alias": f"{lens.meta.get('file_stem')}.min.json",
            "source_commit": source_commit,
        })
    return {
        "schema": "orrlens/manifest/1",
        "repository": C.SELF_REPO_URL,
        "source_commit": source_commit,
        "source_dirty": dirty,
        "lenses": lenses,
    }


def write(ctx, release_dir: Path | None = None) -> list:
    """Write dist/manifest.json, dist/SHA256SUMS and the staging directory. Returns notes."""
    import json

    root = ctx.root
    commit, dirty = source_commit(root), sources_dirty(root)
    man = build_manifest(ctx, commit)
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    files = {}
    for lens in ctx.lenses:
        doc = ctx.rendered[lens.key]
        stem = f"{lens.meta.get('file_stem')}-{lens.version}"
        files[f"{stem}.json"] = dumps(doc)
        files[f"{stem}.min.json"] = dumps(doc, minify=True)
    man_text = json.dumps(man, indent=2, ensure_ascii=True) + "\n"
    (dist / "manifest.json").write_text(man_text, encoding="utf-8")
    (dist / "SHA256SUMS").write_text(sha256sums(files), encoding="utf-8")
    notes = ["wrote dist/manifest.json and dist/SHA256SUMS"]

    rel = release_dir or (root / C.RELEASE_STAGING)
    if rel.exists():
        shutil.rmtree(rel)
    rel.mkdir(parents=True)
    staged = dict(files)
    for lens in ctx.lenses:
        doc = ctx.rendered[lens.key]
        base = lens.meta.get("file_stem")
        staged[f"{base}.json"] = dumps(doc)
        staged[f"{base}.min.json"] = dumps(doc, minify=True)
    staged["manifest.json"] = man_text
    for name, content in staged.items():
        (rel / name).write_text(content, encoding="utf-8")
    (rel / "SHA256SUMS").write_text(sha256sums(staged), encoding="utf-8")
    notes.append(f"staged {len(staged) + 1} release assets in {rel.relative_to(root) if rel.is_relative_to(root) else rel}")
    notes_path = release_notes(root, ctx, rel.parent / "release-notes.md")
    if notes_path:
        notes.append(f"wrote {notes_path.relative_to(root) if notes_path.is_relative_to(root) else notes_path}")
    if dirty:
        notes.append("warning: lens-src/ or data/ has uncommitted changes; commit them before a release")
    return notes


def release_notes(root: Path, ctx, out: Path):
    """Release notes from the newest section of CHANGELOG.md, plus a file table. None if no CHANGELOG.md."""
    path = root / "CHANGELOG.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    sections = [m.start() for m in re.finditer(r"^## ", text, re.M)]
    body = text[sections[0]:sections[1]] if len(sections) > 1 else (text[sections[0]:] if sections else text)
    lines = [body.rstrip(), "", "## Files", "",
             "| Lens | Version | File | Latest alias |", "|---|---|---|---|"]
    for lens in ctx.lenses:
        doc = ctx.rendered[lens.key]
        stem = lens.meta.get("file_stem")
        lines.append(f"| {doc['name']} | {lens.version} | `{stem}-{lens.version}.json` | "
                     f"`{C.SELF_REPO_URL}/releases/latest/download/{stem}.json` |")
    lines += ["", "Verify downloads with `sha256sum -c SHA256SUMS`. `manifest.json` records each lens's version, "
              "question and statement counts, SHA-256 and source commit.", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out

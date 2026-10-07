"""The starter add-on lens: lens-src/templates/org-addon.yaml -> templates/org-addon-lens.json.

Source format (schema orrlens/addon/1):

    schema: orrlens/addon/1
    name: <lens name, at most 128 characters>
    description: <at most 1,024 characters; {version} is replaced with `version` (default 1.0.0)>
    version: 1.0.0                       # optional
    pillar: {id: <pillar id>, name: <pillar name>}
    questions:                           # question mappings in the orrlens/question/1 format
      - id: ...                          # schema, pillar, order, priority, core_path and lineage may be
                                         # omitted; they default to the add-on's pillar, list order, P1,
                                         # false and []
        ...

The add-on is rendered with the same renderer as the ORR lenses and its rules are proved the same way.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from . import config as C
from .model import Lens, _err, _text, lens_level_checks, validate_question


def load_addon(root: Path):
    """Return a Lens for the add-on template, or None when lens-src/templates/org-addon.yaml does not exist."""
    path = root / C.ADDON_SOURCE
    if not path.exists():
        return None
    e: list = []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raw = None
        _err(e, C.ADDON_SOURCE, f"cannot parse YAML: {' '.join(str(exc).split())}")
    if not isinstance(raw, dict):
        if not e:
            _err(e, C.ADDON_SOURCE, "not a mapping")
        raw = {}
    if raw and raw.get("schema") != "orrlens/addon/1":
        _err(e, C.ADDON_SOURCE, "schema must be orrlens/addon/1")
    pillar = raw.get("pillar") if isinstance(raw.get("pillar"), dict) else {}
    if not pillar.get("id") or not pillar.get("name"):
        _err(e, C.ADDON_SOURCE, "pillar needs id and name")
    version = str(raw.get("version") or "1.0.0")
    name = _text(raw.get("name"))
    if not name or len(name) > C.MAX_LENS_NAME:
        _err(e, C.ADDON_SOURCE, f"name missing or longer than {C.MAX_LENS_NAME}")
    desc = _text(raw.get("description")).replace("{version}", version)
    if not desc or len(desc) > C.MAX_LENS_DESCRIPTION:
        _err(e, C.ADDON_SOURCE, f"description missing or longer than {C.MAX_LENS_DESCRIPTION}")
    meta = {
        "schema": "orrlens/lens/1",
        "key": "addon",
        "name": name,
        "version": version,
        "file_stem": "org-addon-lens",
        "description": raw.get("description") or "",
        "none_exclusive_guard": bool(raw.get("none_exclusive_guard")),
        "pillars": [{"id": pillar.get("id"), "name": pillar.get("name")}] if pillar else [],
    }
    lens = Lens(key="addon", path=path.parent, meta=meta, errors=e)
    qs = raw.get("questions") or []
    if not isinstance(qs, list) or not qs:
        _err(e, C.ADDON_SOURCE, "questions must be a non-empty list")
        qs = []
    for i, q in enumerate(qs):
        where = f"{C.ADDON_SOURCE} questions[{i}]"
        if not isinstance(q, dict):
            _err(e, where, "not a mapping")
            continue
        q = dict(q)
        q.setdefault("schema", "orrlens/question/1")
        q.setdefault("pillar", pillar.get("id"))
        q.setdefault("order", (i + 1) * 10)
        q.setdefault("priority", "P1")          # authoring metadata the add-on does not need
        q.setdefault("core_path", False)
        q.setdefault("lineage", [])
        before = len(e)
        validate_question(q, f"{where} {q.get('id')}", [pillar.get("id")], None, e, check_filename=False,
                          allow_overlay=True)
        q["_file"] = C.ADDON_SOURCE
        q["_valid"] = len(e) == before
        lens.questions.append(q)
    lens_level_checks(lens.questions, "addon", e)
    return lens

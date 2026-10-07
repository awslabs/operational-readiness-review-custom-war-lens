"""Tolerant loaders for the reference data under data/ (formats are documented in tools/orrlens/README.md).

Each loader returns None when the file does not exist, so checks can report "not present yet" instead of crashing
while the data files are still being written. Malformed entries are returned as problems, never raised.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config as C


@dataclass
class DataFile:
    path: str
    entries: dict = field(default_factory=dict)       # key -> normalized entry
    meta: dict = field(default_factory=dict)          # top-level scalars such as framework_version
    extra: dict = field(default_factory=dict)         # other top-level lists (for example not_services)
    problems: list = field(default_factory=list)     # failures
    warnings: list = field(default_factory=list)     # reported, not failures


def _read(root: Path, rel: str):
    path = root / rel
    if not path.exists():
        return None, None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), None
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        return None, f"{rel}: cannot parse YAML: {' '.join(str(exc).split())}"


def _items(raw, list_keys):
    """Return (items, meta, extra) from a list, a {list_key: [...]} mapping, or an {id: entry} mapping."""
    meta, extra = {}, {}
    if isinstance(raw, list):
        return raw, meta, extra
    if not isinstance(raw, dict):
        return [], meta, extra
    for k in list_keys:
        if k in raw:
            items = raw[k]
            for kk, vv in raw.items():
                if kk == k:
                    continue
                if isinstance(vv, (str, int, float, bool, datetime.date)) or vv is None:
                    meta[kk] = vv
                else:
                    extra[kk] = vv
            if isinstance(items, dict):
                items = [dict(v, _key=kk) if isinstance(v, dict) else {"_key": kk, "_value": v}
                         for kk, v in items.items()]
            return items if isinstance(items, list) else [], meta, extra
    items = []
    for kk, v in raw.items():
        if isinstance(v, dict):
            items.append(dict(v, _key=kk))
        elif isinstance(v, (str, int, float, datetime.date)) and kk in ("framework_version", "as_of", "schema",
                                                                        "checked", "source"):
            meta[kk] = v
        elif isinstance(v, list):
            extra[kk] = v
        else:
            items.append({"_key": kk, "_value": v})
    return items, meta, extra


def _first(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def _s(v) -> str:
    if isinstance(v, datetime.date):
        return v.isoformat()
    return " ".join(str(v).split()) if v is not None else ""


# ---------------------------------------------------------------------------
# data/wa-best-practices.yaml
# ---------------------------------------------------------------------------

def load_wa_bps(root: Path):
    raw, err = _read(root, C.DATA_WA_BPS)
    if raw is None and err is None:
        return None
    df = DataFile(C.DATA_WA_BPS)
    if err:
        df.problems.append(err)
        return df
    items, df.meta, df.extra = _items(raw, ("best_practices", "practices", "bps", "entries"))
    fv = _first(df.meta, "framework_version", "version")
    for it in items:
        if not isinstance(it, dict):
            df.problems.append(f"{C.DATA_WA_BPS}: entry is not a mapping: {it!r}")
            continue
        bp = _s(_first(it, "id", "bp", "bp_id", "_key"))
        e = {
            "id": bp,
            "title": _s(_first(it, "title", "name")),
            "url": _s(_first(it, "url", "link")),
            "level_of_risk": _s(_first(it, "level_of_risk", "risk", "level", "risk_level")).capitalize(),
            "framework_version": _s(_first(it, "framework_version", default=fv)),
            "alt_urls": [_s(u) for u in (_first(it, "alt_urls", default=[]) or []) if _s(u)],
        }
        if not bp:
            df.problems.append(f"{C.DATA_WA_BPS}: entry without id: {it!r}")
            continue
        for k in ("title", "url", "level_of_risk"):
            if not e[k]:
                df.problems.append(f"{C.DATA_WA_BPS}: {bp} has no {k}")
        if e["level_of_risk"] and e["level_of_risk"] not in ("High", "Medium", "Low"):
            df.problems.append(f"{C.DATA_WA_BPS}: {bp} level_of_risk must be High, Medium or Low")
        if bp in df.entries:
            df.problems.append(f"{C.DATA_WA_BPS}: duplicate entry {bp}")
        df.entries[bp] = e
    return df


# ---------------------------------------------------------------------------
# data/partition-availability.yaml
# ---------------------------------------------------------------------------

PARTITION_VALUES = ("available", "not available", "n/a")   # n/a: no partition-specific availability


def load_partitions(root: Path):
    raw, err = _read(root, C.DATA_PARTITIONS)
    if raw is None and err is None:
        return None
    df = DataFile(C.DATA_PARTITIONS)
    if err:
        df.problems.append(err)
        return df
    items, df.meta, df.extra = _items(raw, ("services", "entries", "items"))
    for it in items:
        if not isinstance(it, dict):
            df.problems.append(f"{C.DATA_PARTITIONS}: entry is not a mapping: {it!r}")
            continue
        name = _s(_first(it, "service", "name", "_key"))
        aliases = _first(it, "aliases", "alias", default=[]) or []
        if isinstance(aliases, str):
            aliases = [aliases]
        gov = _first(it, "aws-us-gov", "aws_us_gov", "govcloud", "aws-us-gov-status")
        e = {
            "service": name,
            "aliases": [_s(a) for a in aliases if _s(a)],
            "aws": _s(_first(it, "aws", "commercial")).lower(),
            "aws-us-gov": _s(gov).lower(),
            "as_of": _s(_first(it, "as_of", "checked", default=df.meta.get("as_of"))),
            "kind": _s(_first(it, "kind", default="service")),
        }
        if not name:
            df.problems.append(f"{C.DATA_PARTITIONS}: entry without service name: {it!r}")
            continue
        for part in ("aws", "aws-us-gov"):
            if e[part] not in PARTITION_VALUES:
                df.problems.append(f"{C.DATA_PARTITIONS}: {name}: {part} must be 'available', 'not available' or "
                                   f"'n/a' (got {e[part]!r})")
        if not e["as_of"]:
            df.problems.append(f"{C.DATA_PARTITIONS}: {name}: as_of is required")
        if name in df.entries:
            df.problems.append(f"{C.DATA_PARTITIONS}: duplicate entry {name}")
        df.entries[name] = e
    return df


def not_services(df) -> list:
    names = list(C.NOT_SERVICES)
    if df is not None:
        for k in ("not_services", "ignore", "non_services"):
            v = df.extra.get(k) or []
            names += [_s(x) for x in v if isinstance(x, str)]
    return names


# ---------------------------------------------------------------------------
# data/lifecycle-denylist.yaml
# ---------------------------------------------------------------------------

def load_lifecycle(root: Path):
    raw, err = _read(root, C.DATA_LIFECYCLE)
    if raw is None and err is None:
        return None
    df = DataFile(C.DATA_LIFECYCLE)
    if err:
        df.problems.append(err)
        return df
    items, df.meta, df.extra = _items(raw, ("services", "entries", "denylist", "items"))
    for it in items:
        if not isinstance(it, dict):
            df.problems.append(f"{C.DATA_LIFECYCLE}: entry is not a mapping: {it!r}")
            continue
        name = _s(_first(it, "service", "name", "_key"))
        pats = _first(it, "patterns", "pattern", "match", default=[]) or []
        if isinstance(pats, str):
            pats = [pats]
        aliases = _first(it, "aliases", "alias", default=[]) or []
        if isinstance(aliases, str):
            aliases = [aliases]
        urls = _first(it, "url_patterns", "urls", default=[]) or []
        if isinstance(urls, str):
            urls = [urls]
        e = {
            "service": name,
            "status": _s(_first(it, "status")),
            "effective": _s(_first(it, "effective", "effective_date", "date", "since")),
            "patterns": [str(p) for p in pats],
            "aliases": [_s(a) for a in aliases],
            "url_patterns": [str(u) for u in urls],
        }
        if not name:
            df.problems.append(f"{C.DATA_LIFECYCLE}: entry without service name: {it!r}")
            continue
        if not e["status"]:
            df.problems.append(f"{C.DATA_LIFECYCLE}: {name}: status is required")
        if not e["effective"]:
            df.warnings.append(f"{C.DATA_LIFECYCLE}: {name}: no effective date recorded")
        df.entries[name] = e
    return df


# ---------------------------------------------------------------------------
# data/builder-allowlist.yaml
# ---------------------------------------------------------------------------

def load_builder_allowlist(root: Path):
    raw, err = _read(root, C.DATA_BUILDER)
    if raw is None and err is None:
        return None
    df = DataFile(C.DATA_BUILDER)
    if err:
        df.problems.append(err)
        return df
    items, df.meta, df.extra = _items(raw, ("articles", "entries", "allowlist", "items"))
    for it in items:
        if not isinstance(it, dict):
            df.problems.append(f"{C.DATA_BUILDER}: entry is not a mapping: {it!r}")
            continue
        aid = _s(_first(it, "id", "article_id", "_key"))
        title = _s(_first(it, "title", "_value"))
        if not aid or not title:
            df.problems.append(f"{C.DATA_BUILDER}: entry needs id and title: {it!r}")
            continue
        df.entries[aid] = {"id": aid, "title": title, "slug": _s(it.get("_key")),
                           "legacy_url": _s(_first(it, "legacy_url", "source", "from")),
                           "url": _s(_first(it, "url", "location"))}
    return df

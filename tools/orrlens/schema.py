"""Validate rendered lens JSON against tools/orrlens/schema/custom-lens.schema.json.

Uses the jsonschema package when it is importable; otherwise a built-in validator for the subset of JSON Schema
that the bundled schema uses ($ref to #/$defs, type, const, enum, required, properties, additionalProperties,
items, minItems, maxItems, minLength, maxLength, pattern, if/then/else, boolean schemas).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "custom-lens.schema.json"

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _path(p) -> str:
    return "/" + "/".join(str(x) for x in p) if p else "/"


def builtin_validate(instance, schema: dict) -> list:
    """Return a list of 'path: message' strings (empty when valid)."""
    root = schema
    errors: list = []

    def resolve(ref: str):
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref {ref}")
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
        return node

    def ok(inst, sch) -> bool:
        probe: list = []
        walk(inst, sch, [], probe)
        return not probe

    def walk(inst, sch, path, out):
        if sch is True:
            return
        if sch is False:
            out.append(f"{_path(path)}: not allowed")
            return
        if "$ref" in sch:
            walk(inst, resolve(sch["$ref"]), path, out)
        if "type" in sch:
            want = sch["type"]
            types = want if isinstance(want, list) else [want]
            match = any(isinstance(inst, _TYPES[t]) and not (t in ("integer", "number") and isinstance(inst, bool))
                        for t in types)
            if not match:
                out.append(f"{_path(path)}: expected {want}, got {type(inst).__name__}")
                return
        if "const" in sch and inst != sch["const"]:
            out.append(f"{_path(path)}: must equal {sch['const']!r}")
        if "enum" in sch and inst not in sch["enum"]:
            out.append(f"{_path(path)}: {inst!r} is not one of {sch['enum']}")
        if isinstance(inst, str):
            if "minLength" in sch and len(inst) < sch["minLength"]:
                out.append(f"{_path(path)}: shorter than {sch['minLength']}")
            if "maxLength" in sch and len(inst) > sch["maxLength"]:
                out.append(f"{_path(path)}: longer than {sch['maxLength']} ({len(inst)})")
            if "pattern" in sch and not re.search(sch["pattern"], inst):
                out.append(f"{_path(path)}: {inst!r} does not match {sch['pattern']}")
        if isinstance(inst, list):
            if "minItems" in sch and len(inst) < sch["minItems"]:
                out.append(f"{_path(path)}: fewer than {sch['minItems']} items")
            if "maxItems" in sch and len(inst) > sch["maxItems"]:
                out.append(f"{_path(path)}: more than {sch['maxItems']} items ({len(inst)})")
            if "items" in sch:
                for i, item in enumerate(inst):
                    walk(item, sch["items"], path + [i], out)
        if isinstance(inst, dict):
            for k in sch.get("required", []):
                if k not in inst:
                    out.append(f"{_path(path)}: '{k}' is a required property")
            props = sch.get("properties", {})
            for k, v in inst.items():
                if k in props:
                    walk(v, props[k], path + [k], out)
                elif sch.get("additionalProperties") is False:
                    out.append(f"{_path(path)}: additional property '{k}' is not allowed")
        if "if" in sch:
            branch = sch.get("then", True) if ok(inst, sch["if"]) else sch.get("else", True)
            walk(inst, branch, path, out)

    walk(instance, schema, [], errors)
    return errors


def validate(instance, schema: dict | None = None, force_builtin: bool = False):
    """Return (errors, engine) where engine is 'jsonschema' or 'builtin'."""
    schema = schema or load_schema()
    if not force_builtin:
        try:
            import jsonschema  # type: ignore
        except ImportError:
            jsonschema = None
        if jsonschema is not None:
            cls = jsonschema.validators.validator_for(schema)
            v = cls(schema)
            errs = sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path))
            return [f"{_path(list(e.absolute_path))}: {e.message}" for e in errs], "jsonschema"
    return builtin_validate(instance, schema), "builtin"

"""orrlens: build and check the ORR custom lens family.

Run from the repository root, either way:
  python3 -m tools.orrlens <command> ...
  PYTHONPATH=tools python3 -m orrlens <command> ...

Commands:
  build [--lens core|event|all] [--candidate rcN]   render dist/ (or a sandbox candidate into build/)
  check [--offline] [--lens ...] [--only a,b] [--skip a,b] [--verbose]
  links [--changed-only <git-ref>] [--strict-redirects] [--report <path>]
  docs                                              regenerate the generated docs and blocks
  table <question_id> [--v1]                        print one question's rules and truth table
  manifest                                          dist/manifest.json, dist/SHA256SUMS, build/release/
  release-notes --tag release-YYYY-MM-DD [--out <path>]   CHANGELOG.md sections dated with the tag's day
  ids update                                        regenerate ids.yaml from the sources
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path

from . import checks as CK
from . import config as C
from . import docs as DOCS
from . import manifest as MAN
from . import registry as REG
from . import release_notes as RN
from .render import dumps, render_lens
from .rules import generate_rules, legacy_max_risk, prove_rule_properties, risk_of

ROOT = Path(__file__).resolve().parents[2]


def _print_errors(lens):
    for e in lens.errors:
        print(f"  {e}", file=sys.stderr)


def cmd_build(args) -> int:
    rc = 0
    ctx = CK.make_context(ROOT, args.lens)
    if args.candidate and not re.match(r"^rc\d+$", args.candidate):
        print("--candidate must look like rc0, rc1, ...", file=sys.stderr)
        return 2
    if not ctx.lenses:
        print("no lens sources found under lens-src/", file=sys.stderr)
        return 1
    for lens in ctx.lenses:
        if lens.errors:
            print(f"not built: {lens.key} has {len(lens.errors)} source error(s):", file=sys.stderr)
            _print_errors(lens)
            rc = 1
            continue
        version = lens.version + (args.candidate or "")
        if not CK.version_name_ok(version):
            print(f"not built: version name {version!r} is not a valid WA version name", file=sys.stderr)
            rc = 1
            continue
        doc = render_lens(lens, version)
        out_dir = ROOT / ("build" if args.candidate else "dist")
        out_dir.mkdir(exist_ok=True)
        stem = f"{lens.meta['file_stem']}-{version}"
        (out_dir / f"{stem}.json").write_text(dumps(doc), encoding="utf-8")
        (out_dir / f"{stem}.min.json").write_text(dumps(doc, minify=True), encoding="utf-8")
        n_q = sum(len(p["questions"]) for p in doc["pillars"])
        n_s = sum(len(q["choices"]) - 1 for p in doc["pillars"] for q in p["questions"])
        print(f"built {out_dir.name}/{stem}.json: {n_q} questions, {n_s} statements")
    if not args.candidate and args.lens in (None, "all"):
        if ctx.addon is None:
            print(f"skipped {C.ADDON_OUTPUT}: {C.ADDON_SOURCE} does not exist yet")
        elif ctx.addon.errors:
            print(f"not built: {C.ADDON_OUTPUT}: the add-on template has source errors:", file=sys.stderr)
            _print_errors(ctx.addon)
            rc = 1
        else:
            out = ROOT / C.ADDON_OUTPUT
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(dumps(ctx.addon_doc), encoding="utf-8")
            print(f"built {C.ADDON_OUTPUT}: {sum(len(p['questions']) for p in ctx.addon_doc['pillars'])} questions")
    return rc


def _names(v):
    return {x.strip() for x in v.split(",") if x.strip()} if v else None


def cmd_check(args) -> int:
    only, skip = _names(args.only), _names(args.skip)
    known = {n for n, _ in CK.CHECKS}
    unknown = (only or set()) | (skip or set())
    if unknown - known:
        print(f"unknown check(s): {', '.join(sorted(unknown - known))}; known: {', '.join(n for n, _ in CK.CHECKS)}",
              file=sys.stderr)
        return 2
    ctx = CK.make_context(ROOT, args.lens)
    full = ctx if args.lens in (None, "all") else CK.make_context(ROOT)
    failed, passed = [], []
    limit = None if args.verbose else 40
    for name, fails, notes in CK.run(ctx, only, skip, args.offline, full_ctx=full):
        status = "PASS" if not fails else f"FAIL ({len(fails)})"
        print(f"{status:10} {name}")
        for n in notes:
            print(f"           note: {n}")
        for f in fails[:limit]:
            print(f"           - {f}")
        if limit is not None and len(fails) > limit:
            print(f"           ... {len(fails) - limit} more (use --verbose)")
        (failed if fails else passed).append(name)
    if args.offline and not only:
        print("           (offline: the links check was skipped)")
    print(f"\n{len(passed)} of {len(passed) + len(failed)} checks passed"
          + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


def cmd_links(args) -> int:
    from .links import run_links
    res = run_links(ROOT, changed_only=args.changed_only, strict_redirects=args.strict_redirects,
                    report=Path(args.report).resolve() if args.report else None)
    for n in res["notes"]:
        print(f"note: {n}")
    for f in res["fails"]:
        print(f"FAIL {f}")
    print(f"\n{len(res['fails'])} broken link(s)" if res["fails"] else "\nno broken links")
    return 1 if res["fails"] else 0


def cmd_docs(args) -> int:
    ctx = CK.make_context(ROOT)
    for n in DOCS.write(ROOT, ctx.lenses, ctx.rendered, ctx.data("wa")):
        print(n)
    return 0


def cmd_table(args) -> int:
    ctx = CK.make_context(ROOT)
    for lens in ctx.all_lenses():
        for q in lens.questions:
            if q.get("id") != args.question_id or args.v1:
                continue
            if not q.get("_valid"):
                print(f"{q['id']} has source errors:", file=sys.stderr)
                for e in lens.errors:
                    if q.get("_file", "~") in e or q["id"] in e:
                        print(f"  {e}", file=sys.stderr)
                return 1
            rules = generate_rules(q["statements"], q["max_risk"], bool(lens.meta.get("none_exclusive_guard")))
            print(f"{lens.key}/{q['id']} (max {q['max_risk']}): "
                  + ", ".join(f"{s['id']}={s['tier']}" for s in q["statements"]))
            for r in rules:
                print(f"{r['risk']:12} {r['condition']}")
            ids = [s["id"] for s in q["statements"]]
            for n in range(1, len(ids) + 1):
                for combo in itertools.combinations(ids, n):
                    print(f"  {risk_of(rules, set(combo)):12} {', '.join(combo)}")
            print(f"  {risk_of(rules, {C.NONE_ID}):12} {C.NONE_ID}")
            return 0
    v1 = REG.load_v1(ROOT).get(C.V1_CURRENT) or {}
    for p in v1.get("pillars", []):
        for q in p["questions"]:
            if q["id"] != args.question_id:
                continue
            ids = [c["id"] for c in q["choices"]]
            print(f"v{C.V1_CURRENT} {q['id']}: {q['title']}")
            for r in q["riskRules"]:
                print(f"{r['risk']:12} {r['condition']}")
            for n in range(0, len(ids) + 1):
                for combo in itertools.combinations(ids, n):
                    print(f"  {risk_of(q['riskRules'], set(combo)):12} {', '.join(combo) or '(nothing)'}")
            for f in prove_rule_properties(q["id"], ids, q["riskRules"], legacy_max_risk(q["title"])):
                print(f"  property failure: {f}")
            return 0
    print(f"unknown question {args.question_id}", file=sys.stderr)
    return 1


def cmd_manifest(args) -> int:
    ctx = CK.make_context(ROOT)
    bad = [lens.key for lens in ctx.lenses if lens.errors]
    if bad:
        print(f"refusing to write a manifest: source errors in {', '.join(bad)}", file=sys.stderr)
        return 1
    fails, _ = CK.check_reproducibility(ctx)
    fails = [f for f in fails if "manifest" not in f and "SHA256SUMS" not in f]
    if fails:
        print("refusing to write a manifest: dist/ does not match a fresh build:", file=sys.stderr)
        for f in fails:
            print(f"  {f}", file=sys.stderr)
        return 1
    for n in MAN.write(ctx, Path(args.release_dir).resolve() if args.release_dir else None):
        print(n)
    return 0


def cmd_release_notes(args) -> int:
    try:
        text = RN.notes_for((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), args.tag)
    except (RN.ReleaseNotesError, OSError) as exc:
        print(f"release notes: {exc}", file=sys.stderr)
        return 1
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_ids(args) -> int:
    ctx = CK.make_context(ROOT)
    if args.action == "update":
        text, changed = REG.update(ROOT, ctx.lenses)
        reg = REG.load_registry(ROOT)
        counts = {k: sum(1 for e in reg[k].values() if e.get("status") == "active") for k in
                  ("pillars", "questions", "choices")}
        print(("updated " if changed else "unchanged ") + C.IDS_FILE
              + f": active pillars {counts['pillars']}, questions {counts['questions']}, choices {counts['choices']}")
        return 0
    if args.action == "show":
        print(json.dumps(REG.compute_registry(ROOT, ctx.lenses, REG.load_registry(ROOT)), indent=2))
        return 0
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="orrlens", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="render the lenses into dist/ (or a candidate into build/)")
    b.add_argument("--lens", default="all")
    b.add_argument("--candidate", help="build a sandbox candidate such as rc0 into build/ (never published)")
    c = sub.add_parser("check", help="run every check")
    c.add_argument("--lens", default="all")
    c.add_argument("--offline", action="store_true", help="skip network checks (links)")
    c.add_argument("--only", help="comma-separated check names")
    c.add_argument("--skip", help="comma-separated check names")
    c.add_argument("--verbose", action="store_true", help="print every failure")
    lk = sub.add_parser("links", help="check URLs (network)")
    lk.add_argument("--changed-only", metavar="GIT_REF", help="check only URLs added since this ref")
    lk.add_argument("--strict-redirects", action="store_true", help="fail on any non-trivial redirect")
    lk.add_argument("--report", help="where to write the JSON report (default build/links-report.json)")
    sub.add_parser("docs", help="regenerate generated docs and blocks")
    tb = sub.add_parser("table", help="print one question's rules and truth table")
    tb.add_argument("question_id")
    tb.add_argument("--v1", action="store_true", help=f"show the v{C.V1_CURRENT} question with this id")
    m = sub.add_parser("manifest", help="write dist/manifest.json, dist/SHA256SUMS and build/release/")
    m.add_argument("--release-dir", help="staging directory (default build/release)")
    rn = sub.add_parser("release-notes", help="release notes for a release tag, from CHANGELOG.md")
    rn.add_argument("--tag", required=True, help="release-YYYY-MM-DD")
    rn.add_argument("--out", help="write the notes to this file instead of standard output")
    i = sub.add_parser("ids", help="ID registry")
    i.add_argument("action", choices=["update", "show"])
    args = ap.parse_args(argv)
    return {"build": cmd_build, "check": cmd_check, "links": cmd_links, "docs": cmd_docs, "table": cmd_table,
            "manifest": cmd_manifest, "ids": cmd_ids, "release-notes": cmd_release_notes}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

# orrlens: generator and checks for the ORR lens family

`orrlens` turns the YAML sources in `lens-src/` into AWS Well-Architected Tool custom-lens JSON, generates the
risk rules from statement tiers, and runs every CI check. It needs Python 3.10 or later and PyYAML; `jsonschema` is
used when it is installed (otherwise a built-in validator runs the same schema). It uses no AWS credentials and
makes no AWS API calls; only `links` (and `check` without `--offline`) uses the network, to fetch public pages.

## Running it

From the repository root, either form works:

```
python3 -m tools.orrlens <command> [options]
PYTHONPATH=tools python3 -m orrlens <command> [options]
```

Install the dependencies with `python3 -m pip install --require-hashes -r tools/orrlens/requirements-ci.txt`
(pinned with hashes, including jsonschema's dependencies; or just `pyyaml jsonschema` for local work).
`requirements-zizmor.txt` pins the workflow linter the same way.

| Command | What it does |
|---|---|
| `build [--lens core\|event\|genai\|all] [--candidate rcN]` | Renders `dist/<file_stem>-<version>.json` and `.min.json` for each lens (core, event and genai: `orr-core`, `orr-event`, `orr-genai`), and `templates/org-addon-lens.json` from `lens-src/templates/org-addon.yaml`. With `--candidate rc0`, writes `build/<file_stem>-<version>rc0.json` for sandbox gates only (never published). Refuses to build a lens with source errors or with no questions |
| `check [--offline] [--only a,b] [--skip a,b] [--verbose]` | Runs every check below and exits non-zero if any fails. `--offline` skips only the network check (`links`) |
| `links [--changed-only <git-ref>] [--strict-redirects] [--report <path>]` | Checks every URL in `lens-src/`, `data/`, `docs/` and `README.md`. `--changed-only origin/main` checks only URLs added since that ref (pull requests). `--strict-redirects` (weekly run) also fails on redirects. Writes `build/links-report.json` with the final URL of each link |
| `docs` | Regenerates `docs/questions.md`, `docs/ownership.csv`, `docs/post-event-lessons.md`, `crosswalk/wa-bp-map.csv`, and the generated blocks in `MIGRATION.md` and `docs/scoring.md`, for every lens. `ownership.csv` ends with an `orr_lens` column; `wa-bp-map.csv` ends with `bp_source` (the Framework or the AI lens), `bp_source_version` and `orr_lens`, and its `framework_version` is set for Framework practices only |
| `table <question_id> [--v1]` | Prints one question's tiers, generated rules and full truth table. `--v1` shows the v1.3.6 question with that id and its property failures |
| `manifest` | Writes `dist/manifest.json` and `dist/SHA256SUMS`, and stages the release assets (versioned files, version-free copies such as `orr-genai.json` and `orr-genai.min.json` for every lens, manifest, checksums, release notes) in `build/release/`. Refuses if `dist/` does not match a fresh build or a lens has no questions, and warns when a lens's release copy is missing from `wafr-operational-readiness-lens/` |
| `release-notes --tag release-YYYY-MM-DD [--out <path>]` | Prints (or writes) every `CHANGELOG.md` section dated with the tag's day, in file order; an `## [Unreleased]` section is always skipped, even if it is dated. Fails when there is no such section. `release.yml` uses it for the body of the draft GitHub Release |
| `ids update` | Regenerates `ids.yaml` deterministically from the v1 files, the lens sources and the existing history (`ids show` prints the computed registry) |

Unit tests: `python3 -m unittest discover -s tools/orrlens/tests`.

A typical authoring loop: edit a question file, then `python3 -m tools.orrlens ids update`, `build`, `docs`, and
`check --offline`. Commit the regenerated files with the source change; CI fails when they are stale.

## Checks

| Check | What it enforces |
|---|---|
| `source` | Every `lens.yaml` and question file follows `lens-src/SCHEMA.md` (keys, ids, tiers, prefixes, required text, https URLs on allowed hosts). Broken YAML is reported, never fatal. Family rules: at most `config.MAX_FAMILY_LENSES` (4) lenses; `key` equals the folder name; lens names and file stems are unique; every lens and every pillar in its `lens.yaml` has at least one question. The family rules cover every lens under `lens-src/` even when `--lens` filters the run |
| `schema` | The rendered JSON validates against `tools/orrlens/schema/custom-lens.schema.json`, which mirrors the WA lens format specification (`schemaVersion` 2021-11-01) |
| `limits` | Repository limits, set at or below the AWS Well-Architected Tool custom lens limits (lens format specification and API reference field maxima, see `config.py` and `docs/gates.md` G4): titles 128; question description 1,024; question helpful text 64; choice texts and URLs 1,024; 5 additional resources per type; 4 statements per question (repository rule; the WA Tool allows 15 choices); 15 choices; 20 questions per pillar; 10 pillars; ids 3-64 of `[a-z0-9_]` (repository rule; the specification allows 3-128); lens description 1,024; version names 1-32 alphanumerics and periods; 400 KB size budget (repository rule; the quota is 500 KB); the ImportLens character set (`config.RESTRICTED_FIELD_CHARS`, gate G4) in the lens name and description, pillar names, question titles and descriptions, and choice titles |
| `rules` | Generates each question's rules from its tiers and proves the risk-rule properties with exhaustive truth tables (format, None of these, endpoints, monotonicity, effect, tier meaning), plus exact equivalence with the tier definition (`rules.expected_risk`) on every subset of choices, and no duplicate conditions |
| `severity` | Core and alt statements have a `severity_basis`; `wa:<BP> (High)` names a best practice in `data/wa-best-practices.yaml` whose level of risk is High (a Framework id such as `REL05-BP02`, or a Generative AI, Agentic AI or Responsible AI lens id such as `GENOPS01-BP01`, `AGENTSEC02-BP01` or `RAISP01-BP01`; formats in `config.WA_BP_SOURCES`); every `wa_bp` exists there; every `deviation:` statement is listed in `docs/scoring.md`; a question helpful text that starts with a BP id links that BP's page |
| `ownership` | Each `concept` is owned by exactly one statement across all lenses |
| `partitions` | Every AWS or Amazon product name in the rendered text (a capitalized run after "AWS" or "Amazon", plus every name and alias in `data/partition-availability.yaml`) is registered there (full names and CamelCase aliases match case-insensitively); partition notes are dated with real dates ("as of YYYY-MM-DD"); a core or alt statement that names a service not available in `aws-us-gov` has partition notes that mention AWS GovCloud (US) and say what to use or do there; a question whose title or description names such a service has a statement with dated AWS GovCloud (US) partition notes; and text that says a service or feature "is (not) available in AWS GovCloud (US)" (or "... there", or "In AWS GovCloud (US), ... is available") agrees with its `aws-us-gov` value, in both directions. That last rule reads the rendered lens text and the repository prose in `config.PARTITION_CLAIM_FILE_GLOBS` (paragraphs joined across line breaks), and counts only names that are the whole subject of the claim, so "CodePipeline cross-Region actions are not available" says nothing about CodePipeline itself |
| `lifecycle` | No pattern from `data/lifecycle-denylist.yaml` appears in rendered text outside a reader note, and no link matches an entry's `url_patterns` unless the statement has a reader note. Only the `reader_note` field and one trailing "Reader note:" in the improvement text (which must state the lifecycle status) are exempt; "Reader note:" anywhere else fails. Every sentence that mentions API Gateway usage plans calls them best-effort and never a hard or blocking control |
| `language` | Rendered text and repository text files: ASCII only, no em or en dashes, no forward-looking availability wording (`FORWARD_LOOKING` in `config.py`; URLs are not scanned for it), inclusive language, and in lens text only https URLs on the allowlisted hosts (github.com only under the AWS organizations in `config.ALLOWED_GITHUB_ORGS`; no `..`, `//` or encoded dots in the path; any letter case of the scheme is found) and no scheme-less host names outside the allowlist |
| `wording` | The internal-wording denylist (a maintainer-only file, not in this repository) plus built-in account-id and ARN patterns over every file the public export would contain, including untracked files that are not ignored. Phrases are found across line breaks, extra spaces and Markdown emphasis; UTF-16/UTF-32 files with a byte order mark are decoded; other non-UTF-8 files fail unless they have a binary extension (`config.BINARY_EXTENSIONS`); symbolic links fail. Public clones run only the built-in patterns |
| `placeholders` | No leftover placeholder in any exportable text file except Python sources and the published v1 files: double-brace template tokens (GitHub Actions `$`-prefixed expressions excepted), angle-bracket or square-bracket fill-ins for a release or publication date, a date, a URL to insert and similar (`config.PLACEHOLDER_PATTERNS`), and upper-case unfinished-work markers. Documented format tokens such as `<register-id>`, `<yyyy-mm>` and `YYYY-MM-DD` are not placeholders. Runs in public clones too |
| `ids` | `ids.yaml` is current; no retired id is reused; kept question ids exist in v1.3.6; no v2 choice id repeats a v1 choice id of the same question; only the generated `none_no` ends in `_no`; `x_` is reserved; choice prefixes are unique per lens and every choice id uses its question's prefix; every lineage entry is a v1.3.6 question id and every v1.3.6 question id appears in some lineage |
| `reproducibility` | `dist/` equals a fresh build for the versions in each `lens.yaml`, and so do `templates/org-addon-lens.json`, `dist/manifest.json` (except the source commit) and `dist/SHA256SUMS`; copies of the current release in `wafr-operational-readiness-lens/` equal `dist/` (a missing copy is a note until release) |
| `docs` | The generated docs and blocks equal what `docs` would write |
| `links` | The network link check (see `links` above); skipped by `--offline` |

## Generated blocks in hand-written files

`docs` replaces only the text between these markers, and never creates the files or the markers:

```
<!-- BEGIN GENERATED: migration-mapping (python3 -m tools.orrlens docs; do not edit) -->
<!-- END GENERATED: migration-mapping -->          (in MIGRATION.md)

<!-- BEGIN GENERATED: scoring-deviations (python3 -m tools.orrlens docs; do not edit) -->
<!-- END GENERATED: scoring-deviations -->         (in docs/scoring.md)
```

`<!-- BEGIN GENERATED MAPPING -->` / `<!-- END GENERATED MAPPING -->` and `<!-- BEGIN GENERATED DEVIATIONS -->` /
`<!-- END GENERATED DEVIATIONS -->` are accepted too.

## ID registry rules (`ids.yaml`)

- Every pillar, question and choice id ever published, with `status` (active, retired, reserved), `introduced`
  and, when retired, `retired`. Choice ids are keyed `<question_id>/<choice_id>`.
- v1 history is computed from `wafr-operational-readiness-lens/orr-v1.3.*-PUBLISHED.json`, which never change.
- History is never rewritten: an entry retired in an earlier version stays retired. An id introduced in a lens's
  current, unreleased version disappears again if its source is removed before release, and an id retired in the
  current version is provisional until that version ships.
- `config.PERMANENT_RETIREMENTS` (the four typo'd v1 ids and `releases_onebox_deployments`) are always retired.
- Forks that add `x_<org>_` overlays set `ORRLENS_ALLOW_OVERLAYS=1`; upstream CI never does. The add-on template
  may use `x_` ids because it is a separate lens.

## Reference data formats (`data/`)

The loaders in `data.py` accept a list, a `{<list key>: [...]}` mapping, or an `{<id>: {...}}` mapping. Top-level
scalars such as `as_of` and `framework_version` apply to every entry that does not set its own.

| File | List key | Entry fields |
|---|---|---|
| `data/wa-best-practices.yaml` | `practices` (or `best_practices`) | key or `id`; `title`; `url`; `alt_urls` (optional); `level_of_risk` (High, Medium, Low); `framework_version`; `lens` (optional: `generative-ai`, `agentic-ai` or `responsible-ai`; absent means a Framework practice). The id must have its source's format and the URL must be a page of that source. A top-level `lenses:` mapping gives each AI lens's `name`, `version` (publication date) and `source` |
| `data/partition-availability.yaml` | `entries` (or `services`) | `name` (or `service`); `aliases`; `kind` (optional); `aws` and `aws-us-gov`: `available`, `not available` or `n/a`; `as_of`. An optional top-level `not_services` list adds terms the name matcher ignores: exact capitalized runs, or word prefixes when the term ends with ` *` |
| `data/lifecycle-denylist.yaml` | `entries` | `name`; `patterns` (case-insensitive regexes; when absent, the name and `aliases` are matched literally); `url_patterns` (required: case-insensitive regexes for links to the item's own documentation); `status` (maintenance, closed to new customers, end of support, discontinued or preview); `effective` |
| `data/builder-allowlist.yaml` | `articles` | key (slug) ; `article_id`; `title`; `legacy_url`; `url` |

## Layout

| File | Purpose |
|---|---|
| `__main__.py` | Command line |
| `config.py` | Limits, allowlists, language rules, paths |
| `model.py` | Loading and validating `lens-src/` |
| `render.py` | Deterministic JSON rendering (description template, helpful text, None choice) |
| `rules.py` | Rule generation, the condition evaluator, the tier prover and the tier-agnostic prover used on v1 files |
| `checks.py` | Every check |
| `registry.py` | `ids.yaml` seeding, updates, the ids check, and the MIGRATION.md dispositions |
| `docs.py` | Generated documentation |
| `addon.py` | The add-on template source |
| `manifest.py` | `dist/manifest.json`, `dist/SHA256SUMS`, `build/release/` |
| `links.py` | The link checker |
| `export.py` | The public export file set (no symbolic links, no private paths, git required) and the internal-wording scan (used by `tools/export_public.py`) |
| `release_notes.py` | Release notes for a release tag from `CHANGELOG.md`, with relative links rewritten to the tag |
| `schema/custom-lens.schema.json` | JSON Schema for the WA custom lens format |
| `tests/` | Unit tests (`tests/fixtures/sample_rules.json` holds six worked questions' rules) |

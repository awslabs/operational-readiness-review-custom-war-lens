# Lens source format (`orrlens/question/1`)

Every lens in this repository is generated from YAML under `lens-src/`. Nobody edits the JSON in `dist/` or
`wafr-operational-readiness-lens/` by hand, and nobody writes `riskRules` by hand: the generator emits them from
statement tiers.

```
lens-src/
  core/lens.yaml                       lens metadata and pillar order
  core/<pillar_id>/<question_id>.yaml  one file per question
  event/lens.yaml
  event/<pillar_id>/<question_id>.yaml
  genai/lens.yaml
  genai/<pillar_id>/<question_id>.yaml
  templates/org-addon.yaml             starter add-on lens (generated to templates/org-addon-lens.json)
```

## Lens file (`lens.yaml`)

```yaml
schema: orrlens/lens/1
key: core                  # core | event | genai (must equal the folder name)
name: AWS Operational Readiness Review   # <= 128 characters; must equal the published lens name (gate G8)
version: 2.0.0             # SemVer; WA version name uses the same string (alphanumerics and periods only)
file_stem: orr-core        # dist/<file_stem>-<version>.json, plus version-free copies at release
description: >-            # <= 1,024 characters after {version} is substituted
  Operational Readiness Review (ORR) custom lens {version} for the AWS Well-Architected Tool, ...
none_exclusive_guard: true   # gate G1: the API does not make "None of these" exclusive, so keep this true
pillars:                   # order is the pillar order in the lens
  - id: architecture
    name: 01 - Architecture
```

## Question file

```yaml
schema: orrlens/question/1
id: architecture_defensive_throttling   # lowercase [a-z0-9_], 3-64 characters, unique in the lens, never reused
pillar: architecture                    # a pillar id from lens.yaml
order: 70                               # sort key within the pillar (10, 20, 30, ...)
title: Overload protection and tenant fairness   # <= 128 characters; no (H)/(M)/(L) tags
max_risk: HIGH                          # HIGH | MEDIUM
priority: P0                            # P0 | P1 (authoring order only; not shown to users)
core_path: true                         # true if the question is on the published 15-question core path
category: Defense against customers     # one of the categories listed below
lineage: [architecture_defensive_throttling, event_queue_backlog]   # v1.3.6 question ids it absorbs; [] if new
choice_prefix: tp_                      # every statement id starts with this; unique within the lens
description:
  question: How do you stop one client, tenant or traffic source from overloading the workload and degrading it for everyone else?
  out_of_scope_if: the workload accepts no requests or events from users or other systems (rare).   # optional
  evidence_to_collect: limit configuration per API, tenant or source. The most recent surge test report.
helpful:                                # question-level helpful resource
  display_text: REL05-BP02 Throttle requests (AWS Well-Architected)   # <= 64 characters
  url: https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_throttle_requests.html
statements:                             # 1-4 statements, in display order
  - id: tp_per_source_limits            # <= 64 characters, starts with choice_prefix, never reused
    tier: core                          # scope | core | alt:A (alt:B ...) | sec
    title: Per-client, tenant, API key or source limits are enforced (or there is one trusted, bounded caller)
    concept: per-source-rate-limits     # kebab-case; one owning statement per concept across all lenses
    severity_basis: "wa:REL05-BP02 (High)"   # required for core and alt tiers (see below)
    wa_bp: REL05-BP02                   # optional; a Well-Architected best-practice id in data/wa-best-practices.yaml
                                        # (Framework, or Generative AI, Agentic AI or Responsible AI lens)
    large_scale: false                  # optional; sec only: practice sized for very large or multi-tenant workloads
    good: >-                            # rendered as "Good looks like: ..."
      Every entry point enforces a limit per caller identity ...
    platform_notes: >-                  # optional; rendered as "Platform notes: ..."
      EC2 and containers: ... Serverless: ...
    partition_notes: >-                 # optional; rendered as "Partition notes: ..."
      Amazon CloudFront is not available in AWS GovCloud (US) as of 2026-10-05; ...
    reader_note: >-                     # optional; rendered as "Reader note: ..." (lifecycle notes for linked pages)
      ...
    helpful_url: https://builder.aws.com/content/3Eupj3d2bo4fEvlzYbICMZNhQ3B/fairness-in-multi-tenant-systems
    improvement: >-                     # what to do; rendered as the improvement plan
      Inventory every entry point and caller type. ...
    improvement_url: https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html
    additional_helpful:                 # optional; at most 5 per statement including a Post-Event Summary lesson
      - display_text: ...
        url: https://...
    additional_improvement:             # optional; at most 5 per statement
      - display_text: Amazon API Gateway usage plans (best-effort limits for per-client fairness)
        url: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html
pes_lesson:                             # optional; at most one per question
  statement: tp_shed_early              # the statement whose helpful resources carry it
  month: Dec 2021                       # "Mon YYYY"
  url: https://aws.amazon.com/message/12721/
  lesson: clients that did not back off adequately drove congestion that also impaired monitoring, so shed excess work early and bound queues and retries.
```

### Tiers and generated rules

| Tier | Meaning |
|---|---|
| `scope` | A scope exit. If it is true the question scores No risk. Its helpful text must list the evidence to collect |
| `core` | Needed to avoid High |
| `alt:A` | One statement of group A is needed to avoid High (groups are A, B, ...) |
| `sec` | Needed only for No risk |

Rules emitted by `python -m orrlens build`:

1. `NO_RISK` = OR(scope statements) OR AND(all non-scope statements)
2. `MEDIUM_RISK` = AND(core statements) AND OR(each alt group); emitted only for `max_risk: HIGH` and only when it differs from rule 1
3. `default` = `HIGH_RISK`, or `MEDIUM_RISK` when `max_risk: MEDIUM`

Every question also gets a `none_no` "None of these" choice. No rule references it except through the guard, so it scores the question's
maximum risk.

With `none_exclusive_guard: true` (required since gate G1 showed that the WA Tool API does not make "None of
these" exclusive), the build appends `&& !none_no` to rules 1 and 2, so "None of these" with any other choice also
scores the question's maximum risk.

Constraints:
- `max_risk: HIGH` needs at least one `core` or `alt:` statement.
- `max_risk: MEDIUM` uses only `scope` and `sec` statements.
- An alt group has at least two statements.
- At most 4 statements per question; at most one `pes_lesson`.

### `severity_basis`

Required on `core` and `alt:` statements. One of:
- `wa:<BP-ID> (High)`: a Well-Architected best practice whose level of risk is High. The id is a Framework id
  (`REL05-BP02`) or an AWS Well-Architected lens id: Generative AI Lens `GEN<pillar>NN-BPNN` (`GENOPS01-BP01`),
  Agentic AI Lens `AGENT<pillar>NN-BPNN` (`AGENTSEC02-BP01`) or Responsible AI Lens `RAI<area>NN-BPNN`
  (`RAISP01-BP01`). It must be recorded in `data/wa-best-practices.yaml` (lens BPs with a `lens` field);
- `wp-orr:<example>`: an example question that the AWS ORR whitepaper scores High risk;
- `deviation:<written rationale>`: the lens rates the practice higher than the Framework; the rationale is
  published in `docs/scoring.md`.

### Categories

Deployment safety, Defense against customers, Defense against dependencies, Data recovery, Operator safety,
Blast radius containment, Event detection, Service restart, Forensics, Escalation (the ORR whitepaper's ten), plus
two additions: Readiness governance, Security readiness.

## Rendering

- **Description:** `Maximum risk: High (launch-blocking unless remediated or formally accepted).` or
  `Maximum risk: Medium (not launch-blocking, remediate on a plan).`, then `Category: <category>.`, the question,
  `Out of scope if: <...>` and `Evidence to collect: <...>`. At most 1,024 characters.
- **Choice helpful text:** `Good looks like: <good>` + ` Platform notes: <platform_notes>` +
  ` Partition notes: <partition_notes>` + ` Reader note: <reader_note>`. At most 1,024 characters.
- **Improvement plan:** `<improvement>`, at most 1,024 characters, with `improvement_url`.
- **Post-Event Summary lesson:** an additional helpful resource on `pes_lesson.statement` with display text
  `Related AWS Post-Event Summary (<month>): <lesson>`.
- **None of these:** `Select this if none of the statements above is true today. The question then scores <High|Medium> risk.`

## Writing rules

- One observable practice per statement, never a fact about the workload; no catch-all "risk mitigated" choices.
- Alternatives become alt groups and are never combined with AND.
- Platform specifics go in `platform_notes`, not in titles.
- Public sources only: AWS documentation, Well-Architected, DevOps Guidance, Builders' Library, What's New, official
  AWS blogs, AWS Post-Event Summaries; open standards (for example OpenTelemetry, OWASP) are linked, never copied.
- `https` URLs only, from the allowlisted domains (see `tools/orrlens/config.py`).
- Plain ASCII; no em or en dashes; no forward-looking availability wording.
- `ImportLens` rejects some characters in the lens name, lens description, pillar names, question titles, question
  descriptions (including `out_of_scope_if` and `evidence_to_collect`) and statement titles (gate G4). Use only
  letters, digits, spaces and `- _ . , : / ( ) @ ! & # + ' ?` there: no semicolons, `%`, `<`, `>`, `=`, `*`,
  double quotes, brackets, braces, `$`, `|` or `~`. Write evidence lists as short sentences. The `limits` check
  enforces this. Helpful, improvement and additional-resource texts are not restricted.
- Date every service-availability statement ("as of 2026-10-05").

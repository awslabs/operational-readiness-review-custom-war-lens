# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, a new question, a
correction, or additional documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary
information to effectively respond to your bug report or contribution.


## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest features. Choose the form that fits:

* **Question proposal**: a new question or statement. It must cite a public source and the incident or guidance
  that motivates it.
* **Bar change**: promote, demote, rewrite or remove a statement, or change a question's maximum risk. It must
  include the evidence described in [Changing a bar](#changing-a-bar).
* **Broken link**: a link in a lens file or in the documentation that fails, redirects or points to the wrong page.
* **Bug**: the lens does not import, a question scores unexpectedly, the generator or a check fails, or the
  documentation is wrong.

When filing an issue, please check existing open, or recently closed, issues to make sure somebody else hasn't
already reported the issue. Please try to include as much information as you can. Details like these are incredibly
useful:

* A reproducible test case or series of steps
* The lens and version being used (for example core 2.0.0)
* Any modifications you've made relevant to the bug
* Anything unusual about your environment, such as the AWS partition (for example AWS GovCloud (US))

Never include AWS account IDs, workload IDs, ARNs that contain account IDs, WA Tool notes, customer names, or any
sensitive or personal information in an issue.


## Contributing via Pull Requests

Contributions via pull requests are much appreciated. External contributions arrive as public pull requests
against this repository. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the *main* branch.
2. You check existing open, and recently merged, pull requests to make sure someone else hasn't addressed the
   problem already.
3. You open an issue to discuss any significant work, such as a new question or a bar change - we would hate for
   your time to be wasted.

To send us a pull request, please:

1. Fork the repository.
2. Modify the source; please focus on the specific change you are contributing. If you also reformat all the code,
   it will be hard for us to focus on your change.
3. Ensure local checks pass: `python3 -m tools.orrlens check` (see [Running the checks](#running-the-checks)).
4. Commit to your fork using clear commit messages.
5. Send us a pull request, answering any default questions in the pull request interface.
6. Pay attention to any automated CI failures reported in the pull request, and stay involved in the
   conversation.

Maintainers prepare each release, run every check plus a manual read of the full diff, and land it as one reviewed
squash commit before cutting the GitHub Release.

### Where to make changes

* **Lens content** lives in YAML under `lens-src/`, one file per question. The format is documented in
  [`lens-src/SCHEMA.md`](lens-src/SCHEMA.md).
* **Never edit generated files by hand:** the JSON in `dist/`, the copies in `wafr-operational-readiness-lens/`,
  and generated documentation such as `docs/questions.md`.
* **Never write `riskRules` by hand.** Tag each statement with a tier (`scope`, `core`, `alt:A`, `sec`) and the
  generator emits the rules.
* **Never edit, move or delete released files**, including the v1.3.2 to v1.3.6 files in
  `wafr-operational-readiness-lens/`. Fixes ship as a new version.
* **Never reuse an ID.** Pillar, question and choice IDs are never reused and never change meaning. The `x_` prefix
  is reserved for organization overlays and is never merged upstream.
* **Your organization's own questions** belong in a separate add-on lens, not in this repository
  ([`docs/customizing.md`](docs/customizing.md)).


## Content rules

Every change to lens content must follow these rules. Reviewers reject changes that do not.

1. **Every bar needs a public source and a `severity_basis`.** Cite public AWS sources first: Well-Architected
   Framework best practices, lenses and whitepapers (including the
   [Operational Readiness Reviews whitepaper](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/wa-operational-readiness-reviews.html)),
   DevOps Guidance, service documentation, the Amazon Builders' Library, AWS What's New, official AWS blogs, and
   [AWS Post-Event Summaries](https://aws.amazon.com/premiumsupport/technology/pes/). Every `core` and `alt:`
   statement records a `severity_basis`: `wa:<BP-ID> (High)`, `wp-orr:<example question>`, or
   `deviation:<written rationale>`, which is published in `docs/scoring.md`.
2. **One practice per statement.** Each statement describes one observable practice, never a fact about the
   workload ("We use third-party services" is a fact, not a practice). No catch-all "risk has been mitigated"
   choices. Alternatives become an `alt:` group and are never combined with AND. At most four statements per
   question. Platform specifics go in `platform_notes`, not in titles.
3. **No customer names.** Do not name customers, partners' customers or their workloads, and do not describe an
   identifiable customer incident.
4. **No internal material.** Do not add non-public documents, internal tool or program names, internal URLs,
   internal statistics, or wording copied from non-public checklists. Do not suggest that a bar reflects how any
   company operates internally; every bar stands on its public source.
5. **Link third-party standards; never copy their text.** Open standards such as
   [OpenTelemetry](https://opentelemetry.io/) or OWASP may be linked, with a date. Paraphrase category names only.
   Some sources are licensed in ways that are not compatible with this repository's MIT-0 license; for example, the
   [OWASP GenAI Security Project](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/) content is licensed
   CC BY-SA 4.0.
6. **Use current, available services.** Name AWS services as examples of a capability ("for example AWS
   AppConfig"). Never recommend a service that is closed to new customers, in maintenance, discontinued, or at or
   near end of support; check the
   [AWS Services in Maintenance](https://docs.aws.amazon.com/general/latest/gr/maintenance_services.html) page.
   Never present Amazon API Gateway usage plans as a hard limit or a way to block a caller: their throttling and
   quotas are applied on a best-effort basis.
7. **Date every availability statement** ("as of 2026-10-06"), and record only "available" or "not available".
   Never use forward-looking availability wording. Where a core practice names a service that is not available in
   AWS GovCloud (US), offer a method-based alternative.
8. **Links:** `https` only, from `docs.aws.amazon.com`, `aws.amazon.com`, `builder.aws.com`, `github.com/aws*`,
   `opentelemetry.io`, `owasp.org` or `genai.owasp.org`. A link must return HTTP 200, and a `docs.aws.amazon.com`
   link must not redirect.
9. **Style:** plain ASCII, no em or en dashes, titles of at most 128 characters, inclusive language (for example
   "allowlist" and "primary").
10. **Characters the WA Tool rejects:** names, titles and descriptions (including "Out of scope if" and "Evidence
    to collect") may use only letters, digits, spaces and `- _ . , : / ( ) @ ! & # + ' ?`. No semicolons: write
    evidence lists as short sentences. See `lens-src/SCHEMA.md`.


## Changing a bar

A bar change adds or changes a statement, tier, rule or maximum risk. It needs the maintainer named in
[CODEOWNERS](CODEOWNERS) plus a subject-matter reviewer, and a CHANGELOG entry with the rationale. Open a **Bar change** issue first
with this evidence:

1. The public source and the `severity_basis` for the proposed bar.
2. The truth-table difference: `python3 -m tools.orrlens table <question_id>` before and after.
3. For changes based on field use: the number of workloads reviewed (no rule applies until at least 5 have been
   reviewed) and how reviewers rated the gap.

The rules for field-based changes:

* Prevalence alone never demotes a core statement. If most reviewed workloads lack a practice, that is the
  finding.
* If reviewers disagree on a statement in more than 25% of reviewed workloads, rewrite it as a clarity problem; do
  not demote it.
* Demote a core statement only if its `severity_basis` is a documented deviation with no public High basis, and
  reviewers rate the gap non-blocking in at least 2/3 of reviewed workloads.
* Never demote statements that have a public High basis, such as `tp_per_source_limits`, `rec_restore_tested`,
  `cc_review_enforced`, `rb_auto`, `can_own_metrics_alarms`, `az_static_capacity`, `ev_shift_mechanism` and
  `exp_no_leaf_pinning`. Where many workloads fail one of these, publish implementation guidance instead.
* Promote a secondary statement to core only if reviewers rate the gap launch-blocking in at least 2/3 of reviewed
  workloads and a public rationale is added to `docs/scoring.md`.
* If at least 70% of reviewed workloads are Medium on a question because of the same secondary statement, rewrite
  that statement, or move it to unscored improvement guidance (which retires its ID in a major release).

A new question also needs a **Question proposal** issue that cites a public source and the incident or guidance
behind it, and must fit the statement budget. Removing a statement or question retires its ID, needs a major
release, and updates `MIGRATION.md`.


## Running the checks

From the repository root, with Python 3 and PyYAML:

```bash
python3 -m pip install -r tools/orrlens/requirements-ci.txt   # pyyaml, jsonschema (the versions CI pins)
python3 -m tools.orrlens ids update            # after any new or renamed id
python3 -m tools.orrlens build                 # regenerates dist/ and templates/
python3 -m tools.orrlens docs                  # regenerates the generated docs and blocks
python3 -m tools.orrlens manifest              # writes dist/manifest.json and dist/SHA256SUMS
python3 -m tools.orrlens check                 # runs every check CI runs, locally
python3 -m tools.orrlens table <question_id>   # prints one question's rules and truth table
```

Run the generators before `check`: the `reproducibility` and `docs` checks compare the committed output with a
fresh build, so `check` fails on a source change until `ids update`, `build`, `docs` and `manifest` have run.
`check --offline` skips only the network link check.

`check` validates the schema, limits, IDs, generated rules and their truth-table properties (High reachable on
High-capped questions, "None of these" scores the maximum risk, every practice scores No risk, adding a practice
never raises the risk, every statement has an effect), lens size, and links. Pull requests fail only on links they
add.


## Finding contributions to work on

Looking at the existing issues is a great way to find something to contribute on. The issue forms in this
repository apply the labels `bar-change`, `question-proposal`, `broken-link` and `bug`, so filtering the issue
list on one of those is a good place to start.


## Code of Conduct

This project has adopted the Amazon Open Source Code of Conduct; see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). For
more information see the Code of Conduct FAQ or contact opensource-codeofconduct@amazon.com with any additional
questions or comments.


## Security issue notifications

If you discover a potential security issue in this project we ask that you notify AWS/Amazon Security via our
[vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a
public GitHub issue. See [SECURITY.md](SECURITY.md).


## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. This project is licensed under MIT-0 (MIT No
Attribution). We will ask you to confirm the licensing of your contribution.

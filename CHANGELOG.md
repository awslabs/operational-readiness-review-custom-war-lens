# Changelog

All notable changes to the lenses in this repository are recorded here. The format follows Keep a Changelog
1.1.0, and each lens has its own Semantic Versioning (SemVer) number:

| Change | Lens version | WA Tool version type |
|---|---|---|
| Text, links or typos; no ID or rule change | PATCH (2.0.1) | Minor (applied silently to every workload) |
| New or changed statements or rules, a severity change, or a new question | MINOR (2.1.0) | Major (owners are notified and upgrade per workload) |
| Restructure, or removing a statement or question (which retires its ID) | MAJOR (3.0.0) | Major, plus a `MIGRATION.md` section |

Releases from 2.0.0 onward are dated tags that attach every lens file, `manifest.json` and `SHA256SUMS`. Released
files are never edited; fixes ship as a new version. Entries for v1.3.2 to v1.3.6 were reconstructed from the
repository history.

## [2026-10-06] core 2.0.0 and ORR - Mission-Critical Event Readiness 1.0.0

### Core lens 2.0.0

Operational Readiness Review (ORR) core lens 2.0.0. Publish it as a **major version of your existing ORR lens**
(Edit the lens, never Create custom lens); see [`MIGRATION.md`](MIGRATION.md).

#### Changed

- **Scoring rebuilt from tiers, with CI-proven properties.** Each statement is tagged as a scope exit, a core
  practice, one of a group of alternatives, or a secondary practice, and the generator emits at most three risk
  rules per question from the tags, with `default` last and no negation other than the "None of these" guard below. Before every release, CI evaluates every
  combination of answers and proves that High is reachable on every High-capped question, that selecting only
  "None of these" scores the question's maximum risk, that selecting every practice scores No risk, that adding a
  practice never raises the risk, and that every statement changes the risk in at least one combination.
- **36 questions and 134 scored statements in 4 pillars**, down from 52 questions in 3 pillars: 01 - Architecture (14), 02 - Release
  Quality (5), 03 - Event Management (16), and a new 04 - Readiness Decision (1, `readiness_signoff`, answered
  last). The three v1 pillar IDs are unchanged.
- **20 question IDs kept, all choice IDs new.** The kept questions are rewritten, and none of their v1.3.6 choice
  IDs is reused, so v1.3.6 selections do not carry over and every question must be re-answered. "None of these" is
  now the WA Tool's None choice, `none_no`, on every question (it was `noneofthese`).
- **Two kept IDs were replaced because their meaning broadened**, so that a v1.3.6 "does not apply" flag cannot
  silently exclude a High question: `releases_onebox_deployments` became `releases_phased_rollout` ("Phased
  production rollout with automated stage gates"), from EC2 to every platform, and `architecture_health_checks`
  became `architecture_health_lifecycle` ("Health checks and safe capacity lifecycle"), from load balancer and DNS
  checks to health checks and the capacity lifecycle on all compute. Both old IDs are retired.
- **Severity changes.** Net effect on scoring: four questions move from a Medium to a High maximum (phased rollout,
  tracing, expiring materials, game days); recovery objectives and pre-production gates already reached High in
  v1.3.6 and change only their title; two prerequisites move from High to Medium. The questions are
  `releases_phased_rollout`, `event_transaction_tracing`, `event_expiring_materials` and `event_gameday` (Medium to
  High); `architecture_rpo_rto` and `releases_staged_deployments` (title only); and `architecture_failure_models`
  and `underlying_dependencies` (High to Medium). `docs/scoring.md` lists every place where the lens rates a
  practice higher than the Well-Architected Framework.
- **Every v1.3.6 topic is merged, split or kept; none is dropped.** Of the 52 v1.3.6 questions, 20 are kept
  (revised), 24 are merged into one 2.0.0 question and 8 are split across several. `MIGRATION.md` maps every
  v1.3.6 question ID to its 2.0.0 home.
- **Question format.** Severity tags such as (H) and (M) are gone from titles. Every description starts with its
  maximum risk and category, and lists the evidence to collect and, where it applies, when the question is out of
  scope.
- **Lens description.** The description carries the disclaimer from the README. The lens keeps its published
  name, "AWS Operational Readiness Review", because the WA Tool does not allow a major version to rename a
  published lens.
- **"None of these" guard.** Neither the WA Tool console nor the API makes "None of these" exclusive: the API
  saves it alongside any other choice, and the console greys out the other choices when it is ticked but keeps
  any already ticked and saves them with it. The No risk and Medium rules therefore also require
  that "None of these" is not selected (`&& !none_no`), so selecting it with any other choice scores the
  question's maximum risk.
- **Distribution.** Lens files are published on GitHub Releases with `manifest.json` and `SHA256SUMS`, plus
  version-free copies (`orr-core.json`, `orr-core.min.json`) for the `releases/latest/download/` links. Release
  tags and checksums replace the `-PUBLISHED` file suffix. Each release's files are also copied into
  `wafr-operational-readiness-lens/`.
- **README rewritten**, with numbered first-install and upgrade steps illustrated by console screenshots
  refreshed for the current AWS Well-Architected Tool console, guidance on running an ORR, what a question
  looks like in the tool, the known v1.3.x scoring limitations, AWS GovCloud (US) notes, data handling and a
  disclaimer.
- **Console screenshots refreshed, not removed.** The images in `_img/` were recaptured against the current AWS
  Well-Architected Tool console and replaced in place under the same file names, so earlier links keep working,
  and new captures were added for the edit, publish-update, workload-upgrade and question pages.

#### Added

- **16 new question IDs:** `architecture_recovery_dependencies`, `architecture_dependency_failure_handling`,
  `architecture_hybrid_connectivity`, `architecture_edge_protection`, `architecture_cold_start`,
  `architecture_health_lifecycle`, `releases_phased_rollout`, `releases_security_readiness`,
  `event_saturation_alarms`, `event_provider_escalation`, `event_customer_impact`, `event_az_evacuation`,
  `event_emergency_access`, `event_operator_tooling_safety`, `event_post_incident_analysis` and
  `readiness_signoff`.
- **A 15-question core path** for triage and recurring check-ins. A launch go or no-go still requires the full
  core.
- **Actionable statements.** At most four statements per question, each one observable practice with a "Good looks
  like" description, platform notes for EC2, containers and serverless where they differ, dated partition notes
  where AWS GovCloud (US) availability differs, and helpful and improvement links. Some questions link one related
  AWS Post-Event Summary, stated as a customer design lesson.
- **Repository tooling and files:** the YAML source of truth under `lens-src/`, the `tools/orrlens` generator and
  checks, `MIGRATION.md`, this changelog, `SECURITY.md`, `CODEOWNERS`, issue forms and a pull request template.

#### Removed

- **32 v1.3.6 question IDs retired** from the active lens; their content lives in the 2.0.0 questions listed in
  `MIGRATION.md`. They include the four misspelled IDs `architecture_plane_redundency`,
  `architecture_gradeful_recovery`, `architecture_mulitaccount_stragy` and `architecture_mutliaccount_credentials`,
  and the two replaced IDs `releases_onebox_deployments` and `architecture_health_checks`. Retired IDs are never
  reused.

#### Fixed

- The v1.3.x scoring defects listed in the README: High unreachable on 22 questions, "None of these" scoring only
  Medium on 23, a good practice raising the risk on `architecture_services_used`, the missing default rule on
  `releases_manual_changes`, and the unused `queueing` and `async_execution` choices.
- **Stale guidance and links from v1.3.6**, which 2.0.0 replaces rather than shipping as a separate v1.3.7 text
  release: the AWS X-Ray SDK guidance is now OpenTelemetry instrumentation; incident guidance is tool-neutral and
  no longer names a product that is closed to new customers; the Amazon S3 eventual-consistency example, the "CW
  Synthetics" shorthand for dynamic alarms, the collectd JVM note, the network ACL based Availability Zone test and
  root credentials held "at the executive level" are gone; the two `wellarchitectedlabs.com` links, the redirected
  links and the `http://` links are replaced with current `https://` AWS pages.

### ORR - Mission-Critical Event Readiness 1.0.0

ORR - Mission-Critical Event Readiness 1.0.0, a new companion lens. Install it with **Create custom lens** and
attach it alongside a current core review.

#### Added

- **8 questions and 26 scored statements in 3 pillars:** 01 - Prepare (`evt_calendar_freeze`, `evt_peak_retest`, `evt_capacity_quotas`,
  `evt_ddos_response`, `evt_rehearsal`), 02 - Operate (`evt_war_room`, `evt_degraded_modes`) and 03 - After the
  event (`evt_post_event`).
- **Timing guidance:** budget and procure 3-6 months before the event, complete the review at least 8 weeks
  before, re-test load 30-60 days before, close High risks 4 weeks before, and review within 2 weeks after.
- The same tier-generated scoring and CI-proven properties as the core lens. Event statements build on core
  practices instead of scoring them again.
- Version-free release copies `orr-event.json` and `orr-event.min.json`.

## [1.3.6] - 2023-09-13

Merged in pull request #9; content changes dated 2023-08-09 and 2023-09-13. 52 questions in 3 pillars.

### Added

- A "None of these" choice (`noneofthese`) on all 52 questions.
- Question `event_budget_alerts` (Alarms for cost management).
- New choices, including `manual_changes` and `manual_changes_template` (`releases_manual_changes`), `throttled`
  (`architecture_demand_estimates`), `async_API` (`architecture_dependency_retry`, replacing `aws_services`) and
  `move_traffic` (`event_resilience_recoveries`, replacing `runbooks_exist`).

### Changed

- Risk rules changed on 29 questions, and improvement plans were revised.
- Severity tags changed in question titles, for example Software Certificates (L to H), Automated Deployment
  Rollback (M to H), Independent Canary Alarms (L to H), Mutating Access (M to H), Withstand failures and enable
  fast recoveries (M to H) and Event preparedness through game days (H to M); several (L) questions became (M).
- Questions specific to Amazon EC2 were titled as such: One Box EC2 Deployments, EC2 Deployment Gating and EC2
  Deployment Validation.
- The five individual metric choices of `event_jvm_metrics` were consolidated into one, and the single choice of
  `event_frontend_alarms` was split into two.

### Repository

- README update merged in pull request #6 (2023-07-31).

## [1.3.5] - 2023-07-10

Merged in pull request #8; content dated 2023-06-21.

### Changed

- Spelling and minor content revisions: three question descriptions and the helpful or improvement text of four
  choices. No question, choice or rule changes.
- The lens name no longer carries the version number.

## [1.3.4] - 2023-05-19

Merged in pull requests #4 and #5. 51 questions in 3 pillars.

### Added

- Content merged from the AWS Operational Readiness Review Whitepaper Sample lens, including three questions:
  `event_canary_alarms`, `event_gameday` and `event_resilience_recoveries`.
- New choices `failure_model_documented` (`architecture_failure_models`), `sync_API`
  (`architecture_dependency_retry`) and `kpis_reviewed` (`event_kpis`); `event_jvm_metrics` gained individual metric
  choices in place of a single "risk mitigated" choice.

### Changed

- Pillars renamed to "02 - Release Quality" and "03 - Event Management".
- Seven question descriptions and the helpful or improvement text of 23 choices revised; the lens description
  corrected.

## [1.3.3] - 2023-04-27

Merged in pull request #3.

### Added

- Choice `dataimpact_radius_flow_diagram` on `architecture_architecture_diagram` (an impact-radius check), with its
  risk rule.

## [1.3.2] - 2023-03-06

Initial public release: 48 questions in 3 pillars (01 - Architecture, 02 - Release Quality & Procedures,
03 - Incident & Event Management). The README feedback guidance was clarified on 2023-03-10 (pull request #2).

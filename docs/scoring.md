# How this lens scores

This page explains how answers become risk levels in the ORR lens family, what each level means, which properties
the build proves for every question, how the bars are calibrated, and how they may change. It applies to the core
lens (2.0.x), to ORR - Mission-Critical Event Readiness (1.0.x) and to ORR - Generative AI and Agents (1.0.x).

## Summary

- Every question has 1-4 statements plus "None of these" (`none_no`).
- Authors tag each statement with a tier. Nobody writes `riskRules` by hand; the generator emits them from the
  tiers.
- Selecting every practice gives No risk. Selecting "None of these", alone or together with other choices, gives
  the question's maximum risk. Adding a good practice never raises the risk.
- **High** means launch-blocking unless remediated or formally accepted. **Medium** means the core practice is in
  place and hardening is outstanding. **No risk** means every listed practice is in place.

## Statement tiers

| Tier | Meaning |
|---|---|
| `scope` | A scope exit. If it is true, the question scores No risk. Its helpful text lists the evidence to collect, and a facilitator accepts it only with that evidence |
| `core` | Needed to avoid High |
| `alt:A` | One statement of group A is needed to avoid High. Alternatives are never combined with AND |
| `sec` | Secondary: needed only for No risk |

Every question description starts with its maximum risk:
`Maximum risk: High (launch-blocking unless remediated or formally accepted).` or
`Maximum risk: Medium (not launch-blocking, remediate on a plan).`, followed by its category, the question,
`Out of scope if:` (where it applies) and `Evidence to collect:`.

## Generated rules

The WA Tool evaluates a question's `riskRules` in order, and the first true condition wins. The generator emits at
most three rules per question:

| Rule | Condition | Emitted when |
|---|---|---|
| 1 | `NO_RISK` = OR(scope statements) OR AND(all non-scope statements) | Always |
| 2 | `MEDIUM_RISK` = AND(core statements) AND OR(each alt group) | The question's maximum is High, and this condition differs from rule 1 |
| 3 | `default` = `HIGH_RISK`, or `MEDIUM_RISK` for Medium-capped questions | Always, last |

Examples from the core lens:

| Question | Generated rules |
|---|---|
| `architecture_defensive_throttling` (2 core, 2 secondary) | No risk: `tp_per_source_limits && tp_shed_early && tp_dynamic_limits && tp_surge_tested`; Medium: `tp_per_source_limits && tp_shed_early`; otherwise High |
| `event_resilience_recoveries` (scope exit, 2 core, 1 secondary) | No risk: `az_regional_managed \|\| (az_multi_az && az_static_capacity && az_tested_at_load)`; Medium: `az_multi_az && az_static_capacity`; otherwise High |
| `event_customer_impact` (alt group, 1 secondary) | No risk: `ci_identify && ci_comms_plan && ci_status_independent`; Medium: `ci_identify \|\| ci_comms_plan`; otherwise High |
| `architecture_cold_start` (Medium-capped, secondary only) | No risk: all four statements; otherwise Medium |

The examples above leave out the `&& !none_no` guard that every generated No risk and Medium rule carries (see
["None of these"](#none-of-these)): `event_resilience_recoveries`, for example, renders as
`(az_regional_managed || (az_multi_az && az_static_capacity && az_tested_at_load)) && !none_no`.

To see the full truth table of any question, run `python3 -m tools.orrlens table <question_id>` from the
repository root. [questions.md](questions.md) lists every question with its statements and rules.

### "None of these"

Every question ends with a `none_no` choice. A choice ID ending in `_no` acts as "None of these" in the WA Tool
([lens format specification](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-format-specification.html)).
Sandbox gate G1 (2026-10-06, [gates.md](gates.md)) showed that the WA Tool API does not make `none_no` exclusive:
`UpdateAnswer` accepts it together with other choices and does not clear them. So the build sets
`none_exclusive_guard: true` in both `lens.yaml` files, which adds `&& !none_no` to rules 1 and 2. Selecting
"None of these", alone or with any other choice, therefore falls through to the default and scores the question's
maximum risk. That is the only negation the checks allow; there are still at most three rules, and the rules stay
monotone over the practices. A later console check the same day found the same: ticking "None of these" greys
out the other choices but does not clear any already ticked, and **Save and exit** saves both.

An unanswered question shows as Unanswered in the WA Tool, not as High risk. That is why `readiness_signoff`
requires every question to be answered or marked not applicable before a launch decision.

## Properties CI proves for every question

The checks evaluate every combination of each question's choices (at most 5 choices, so at most 32 states) and
fail the build if any property does not hold:

- **Format:** at most 3 rules; one rule per risk level; `default` last; every identifier is a choice ID of that
  question; no `!` except the G1 guard (`&& !none_no` at the end of rules 1 and 2).
- **"None of these":** selecting `none_no`, alone or with any combination of statements, gives the maximum risk;
  no rule references `none_no` except through the guard.
- **Endpoints:** selecting all practices gives No risk; a scope statement alone gives No risk.
- **Monotonicity:** adding any statement never increases the risk.
- **Effect:** every statement changes the risk in at least one state, so no choice is effort without signal.
- **Tier meaning:**
  - dropping any core statement from "all practices" gives High;
  - dropping any secondary statement gives Medium;
  - without every core statement and one statement from each alt group, the score is the question's maximum risk
    however many secondary statements are selected (on a Medium-capped question, any incomplete selection scores
    Medium).
- **Severity basis:** every core and alt statement has a `severity_basis` (below).
- **Limits:** at most 4 statements per question; titles at most 128 characters; descriptions and choice texts at
  most 1,024 characters; question-level helpful text at most 64 characters; lens IDs lowercase and at most 64
  characters.

These properties fix the v1.3.6 scoring defects: in v1.3.6, High could not be reached on 22 questions (7 of them
titled High); selecting only "None of these" scored Medium on 23 questions (8 of them titled High); on
`architecture_services_used`, also documenting third-party dependencies raised the risk to Medium;
`releases_manual_changes` had no default rule; and the `queueing` and `async_execution` choices were used by no
rule.

## What each risk level means

| Risk | Meaning | What to do |
|---|---|---|
| High | A launch-blocking gap | Remediate before launch, or record a formal, time-bound acceptance by the accountable owner |
| Medium | The core practice is in place; hardening is outstanding | Fix it on a plan; it does not block launch |
| No risk | Every listed practice is in place and the evidence lines are satisfied | Re-confirm at the next recurring review |

Read reports High first.

### What Medium means (documented deviation, decision D-9)

The ORR whitepaper keeps ORRs High-only to stay lightweight: its page
[The ORR tool](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/the-orr-tool.html)
states that medium or low risks are not included in the ORR. This lens keeps a Medium tier as a deliberate,
documented deviation (decision D-9 in [decisions.md](decisions.md)), with one fixed meaning:

> **Medium: the core practice is in place; hardening is outstanding; fix on a plan; not launch-blocking.**

Medium carries a useful hardening signal, and the High-focused triage pass is still available through the core
path. Three core questions are capped at Medium:

| Question | Why Medium-capped |
|---|---|
| `architecture_failure_models` | A prerequisite: the system model is evidence for other questions, and its launch-blocking outcomes are scored in the resilience questions |
| `underlying_dependencies` | A prerequisite: dependency behaviors are scored in three other questions, so they are not double counted |
| `architecture_cold_start` | Restart-from-zero hardening; its practices are secondary |

In the event lens, `evt_post_event` is Medium-capped as well: post-event learning and scale-down matter, but they
are not launch-blocking. In the generative AI lens, `gai_observability` is Medium-capped: proven telemetry coverage
and per-request attribution matter, but they are not launch-blocking on their own.

Some secondary statements describe practices that mainly pay off for very large or multi-tenant workloads, and are
tagged `large_scale: true` in the source (`rp_no_shared_fate`, `can_independent`, `ev_per_az_detection`,
`df_backlog_recovery`, `rt_retry_budget` and `pd_blockers`). Aggregated feedback uses the tag to show how much of a
Medium total these statements cause.

## Severity basis

Every core and alt statement records why missing it is launch-blocking, as one of:

- `wa:<BP-ID> (High)`: a Well-Architected best practice whose level of risk is High;
- `wp-orr:<example>`: an example question that the
  [ORR whitepaper](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/appendix-b-example-orr-questions.html)
  scores High risk;
- `deviation:<written rationale>`: the lens rates the practice higher than the Framework; the rationale is
  published in the next section.

## Where this lens rates higher than the Framework

Each entry below is a High bar whose matching Well-Architected best practice is rated Medium, or has no matching
best practice, with the reason: irreversibility, or a design lesson from a public
[AWS Post-Event Summary](https://aws.amazon.com/premiumsupport/technology/pes/). The list is generated from the
`deviation:` entries in `lens-src/` by `python3 -m tools.orrlens build`; do not edit it by hand. CI fails if a
`deviation:` entry is missing from this page.

<!-- BEGIN GENERATED DEVIATIONS -->
| Question | Statement | Rationale |
|---|---|---|
| `well_architected` | `wa_current` A Well-Architected Framework review was completed in the last 12 months and after the last major architecture change | the Framework review process calls for a review before go-live and after significant architecture changes; a review that predates the current design leaves its design risks unknown at launch, and no Framework best practice carries a risk level for this step |
| `well_architected` | `wa_hri_dispositioned` Every open high-risk issue from that review is remediated, owned with a target date, or formally accepted | a high-risk issue with no owner, target date or written acceptance is an unmanaged risk at launch, and this lens treats unmanaged High risks as launch-blocking |
| `architecture_recovery_dependencies` | `rp_dataplane_recovery` Failover uses data-plane actions on pre-provisioned resources, and no recovery step creates resources in the impaired location | REL11-BP04 is rated Medium; the October 2025 Post-Event Summary reports that new EC2 instance launches failed for hours while existing instances remained healthy, so a recovery plan that creates resources can fail exactly when it is needed |
| `architecture_recovery_dependencies` | `rp_no_cross_region_cp` The critical path and recovery steps have no runtime dependency on another Region or on a global service's control plane | REL11-BP04 is rated Medium; the AWS Fault Isolation Boundaries whitepaper states that most global services host their control plane in a single Region, so a runtime dependency on one couples the workload to an event in that Region |
| `releases_phased_rollout` | `pd_staged_expansion` Each production change, including configuration and flags, first reaches a small slice, then expands in automated, gated stages | OPS06-BP03 is rated Medium; the lens rates it High because a change released to all capacity at once turns any defect into impact for every customer, and phased exposure is the primary control that limits the blast radius of a change. |
| `releases_security_readiness` | `sec_detection_routed` Threat detection and posture findings are enabled in every Region used and routed to an owned on-call queue | SEC04-BP01 (High) covers turning on detection sources such as Amazon GuardDuty in every Region used. The lens also requires routing findings to an owned on-call queue, which relates to SEC04-BP03 (rated Low), because a finding that reaches no responder does not shorten a security event. |
| `event_provider_escalation` | `pe_escalation_runbook` A tested runbook escalates to AWS and other providers, with fallbacks that do not depend on the Support Center console or API | OPS10-BP04 is rated Medium; the lens rates an untested provider escalation path High because the October 2025 Post-Event Summary reports that customers were unable to create, view and update support cases through the AWS Support Console and API for almost three hours during a Regional event. |
| `event_customer_impact` | `ci_comms_plan` A communication plan (channels, templates, approvers, cadence, required notices) exists and has been exercised | OPS10-BP05 is rated Medium; the lens rates having neither impact identification nor an exercised customer communication plan High because, without either, a workload cannot tell affected customers what to do or meet contractual or regulatory notice deadlines during an event, and, as the November 2020 Post-Event Summary shows, status updates are delayed when the usual channel depends on the impaired system and the fallback is unfamiliar. Impact identification alone is backed by OPS10-BP03 (High). |
| `event_emergency_access` | `ea_tested_independent` Each emergency path is tested on a schedule, including one that depends on neither your IdP nor the Region hosting identity | SEC03-BP03 is rated Medium; the lens rates it High because the October 2025 Post-Event Summary describes IAM Identity Center, root and federated console sign-in errors during a Regional event, and an emergency path that has never been used cannot be relied on to mitigate one. |
| `event_operator_tooling_safety` | `ot_blast_radius_limits` Operator tools and runbook commands validate inputs, cap what one action can change, and refuse to go below minimum capacity | OPS07-BP03 (Use runbooks to perform procedures), the nearest Framework best practice, is rated Medium; the lens rates it High because the February 2017 Post-Event Summary describes one incorrect input to an operational command removing a larger set of servers than intended, with hours of impact. |
| `event_operator_tooling_safety` | `ot_resource_protections` Critical resources have deletion protection, stack policies or equivalent safeguards | deleting or replacing a critical stateful resource is often irreversible or slow to recover, and the AWS ORR whitepaper's Appendix A asks how an operator is prevented from deleting a stack or critical resources. |
| `event_gameday` | `gd_fault_injection` On-call engineers mitigated injected failures (such as AZ impairment or dependency loss) with real alarms in the last 12 months | REL12-BP05 and REL12-BP04 are rated Medium; the lens rates exercises High because an unrehearsed response plan slows every recovery, and only an exercise shows that alarms, runbooks and access work together. |
| `event_gameday` | `gd_tabletop` A tabletop or live exercise rehearsed incident command, stakeholder communications and escalation to AWS and vendors | REL12-BP05 and SEC10-BP07 are rated Medium; the lens rates exercises High because incident command, communications and provider escalation that were never rehearsed slow every recovery. |
| `evt_calendar_freeze` | `cf_owner` A named event owner and go/no-go criteria for the event are documented | Without a named owner and pre-agreed go/no-go criteria nobody can decide to proceed, degrade, delay or abort when a late risk appears, and on a fixed-date event that decision cannot wait for a meeting to be arranged. |
| `evt_ddos_response` | `dd_l7_enforcing` Application-layer DDoS rules were tuned in count mode, are enforcing before the event, and match IaC | A high-visibility event is a predictable DDoS target, and an application-layer rule group left in Count mode, or reverted by the next IaC deployment, detects a request flood without stopping it. |
| `evt_rehearsal` | `rh_tabletop` An event-scenario tabletop (DDoS, AZ impairment, dependency outage, surge beyond forecast) ran within 60 days | REL12-BP05 is rated Medium; the lens rates an unrehearsed event plan High because a fixed event window leaves no time to discover in production that runbooks, access or escalation paths do not work. |
| `evt_rehearsal` | `rh_gameday` A game day under event-like load ran within 60 days | REL12-BP05 is rated Medium; the lens rates an unrehearsed event plan High because a fixed event window leaves no time to discover in production that runbooks, access or escalation paths do not work. |
| `evt_war_room` | `wr_staffing` A staffed shift plan or war room covers the window, including dependency owners, with shifts and handoffs that limit fatigue | A fixed event window concentrates risk into hours that cannot be re-run, so an unstaffed shift or a missing dependency owner turns a recoverable fault into a failed event. |
| `evt_war_room` | `wr_escalation_tree` An escalation tree per component, including AWS, partners and vendors, was verified within two weeks of the event | OPS10-BP04 is rated Medium; the lens rates an unverified event escalation tree High because contacts go stale between events and the event window leaves no time to find the right person. |
| `evt_degraded_modes` | `dm_kill_switches` Non-essential features can be shed within minutes without a deployment | REL05-BP07 is rated Medium; during a fixed-date peak, demand above forecast has to be absorbed within minutes and a code deployment during the window adds risk, so shedding features by configuration is one of the two acceptable floors. |
| `gai_inventory_routing` | `mi_lifecycle_tracked` Every model in use, including fallback and recovery models, has an owner and a tracked lifecycle state and end-of-life date | after a model reaches end of life, requests to it fail in all Regions and migration is not automatic, and some models now have a 45-day Legacy period, so an untracked model deadline is a fixed-date outage. GENREL04-BP02 (model catalog) is rated Low. |
| `gai_dependency_fallback` | `fb_stop_reasons` Truncated, filtered or malformed model output, and mid-stream errors, are handled as failures, never as complete answers | model APIs report truncation, content filtering, malformed output and context overflow as stop reasons on a successful call, and streams can fail after they start, so unchecked code passes incomplete answers to users and downstream systems as if complete. GENREL03-BP01 (use logic to manage prompt flows and gracefully recover from failure) is rated Medium. |
| `gai_safeguards` | `sg_enforced_outside_code` Safeguards are enforced outside app code on every call path, including fallback and streaming (or risk assessment requires none) | a guardrail applied only by application code is skipped by any new, fallback or direct call path, and AWS documents enforcing guardrails through IAM conditions, organization policies and gateways. GENSEC02-BP01 scores having guardrails, not enforcing them, and AGENTSEC04-BP01 scores layered guardrail design for agents, not enforcement outside code. |
| `gai_runaway_cost` | `sp_spend_stop` An automated stop or degrade, driven by near-real-time token metrics, halts model use at an approved ceiling, and was tested | AWS Budgets data updates up to three times a day and Cost Anomaly Detection can take up to 24 hours, so billing-based controls cannot stop runaway token spend in time. For agent workloads, the Agentic AI Lens rates per-agent cutoffs and agent cost anomaly detection High (AGENTCOST07-BP01 and AGENTCOST07-BP02). This statement scores what those practices do not: one tested ceiling across all model use, including non-agent and third-party calls, where the Framework practices REL05-BP07 and COST02-BP05 are rated Medium. An untested stop is assumed not to work. |
<!-- END GENERATED DEVIATIONS -->

## Where this lens rates lower than the whitepaper

The [ORR whitepaper's Appendix B](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/appendix-b-example-orr-questions.html)
scores a deployment that does not run on-host validation before re-registering with the load balancer as High
risk. This lens scores the matching statement, `hc_enter_leave_safely` in `architecture_health_lifecycle`, as
secondary (Medium at most), because other High bars already bound the blast radius of a unit that starts badly:
`hc_check_and_replace` removes and replaces units that fail health checks, `releases_phased_rollout` exposes a
change to a small slice first, and `releases_deployment_rollback` (`rb_auto`) rolls back automatically on alarms.

## Severity changes from v1.3.6

Decisions D-4 and D-5 in [decisions.md](decisions.md). "Effective v1.3.6 max" is the highest risk any combination
of v1.3.6 answers could reach, which sometimes differed from the (H) or (M) in the title.

| Question | v1.3.6 title | Effective v1.3.6 max | v2 max | Why |
|---|---|---|---|---|
| `architecture_rpo_rto` | M | High (default rule is High) | High | An untested restore is an unknown recovery. Title change only ([REL13-BP03](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_planning_for_recovery_dr_tested.html)) |
| `releases_staged_deployments` | M | High | High | Promotion without blocking tests ships defects to all customers. Title change only |
| `releases_phased_rollout` (was `releases_onebox_deployments`) | M | Medium | High | Phased rollout is the primary blast-radius control for changes. The ID changed because the meaning broadened from EC2 to every platform |
| `event_transaction_tracing` | M | Medium | High | Without correlated logs you cannot diagnose a problem or identify impacted customers |
| `event_expiring_materials` | M | Medium | High | Expiry outages are fully preventable; the whitepaper's worked example scores certificate pinning High; public certificate lifetimes are shrinking |
| `event_gameday` | M | Medium | High | Only exercises prove that runbooks, access and escalation work. Stricter than the Medium rating of [REL12-BP05](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_game_days_resiliency.html), because an unrehearsed response plan slows every recovery |
| `architecture_failure_models` | H | High | Medium | Prerequisite; the outcomes are scored in the resilience questions |
| `underlying_dependencies` | H | High | Medium | Prerequisite; dependency behaviors are scored in three other questions |

Net effect: four questions move from a Medium to a High maximum (phased rollout, tracing, expiring materials, game
days); recovery objectives and pre-production gates already reached High in v1.3.6 and change only their titles;
two prerequisites move from High to Medium.

Two statements ship as secondary in 2.0.0 (decision D-3): `az_tested_at_load` and `tp_dynamic_limits`. Their
public bases,
[REL12-BP04](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_failure_injection_resiliency.html)
and [REL05-BP07](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_mitigate_interaction_failure_emergency_levers.html),
are rated Medium. A later release promotes either to core only under rule 5 in [How bars change](#how-bars-change).

## Not applicable

Three mechanisms, in order of preference:

1. **Scope-exit statements**, for example "The workload has no internet-facing endpoints". They make partial
   applicability explicit and score predictably. A facilitator accepts one only with the evidence its helpful text
   lists.
2. **Question-level "does not apply" with a reason**, for whole-question cases (console, or
   [UpdateAnswer](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_UpdateAnswer.html) with
   `IsApplicable` and `Reason`). Sandbox gate G9 confirms how reports count it.
3. **Choice-level not applicable: not recommended.** Sandbox gate G3 (2026-10-06) showed that it scores
   deterministically, but the behavior is not described in the lens format specification, and it is easy to
   misuse. A statement marked not applicable is neutral: it counts as satisfied in an `&&` (AND) term and as not
   satisfied in an `||` (OR) term. So marking every statement of a question not applicable, with nothing selected,
   scores **No risk**, and marking a core statement not applicable lets the question reach Medium or No risk
   without that practice. "None of these" cannot be marked not applicable. Rules cannot see this status, so the
   build cannot guard against it. Reviewers should check each answer's choice statuses (`ChoiceAnswers` in
   `GetAnswer`) for `NOT_APPLICABLE` and treat each one as a claim that needs evidence, like a scope exit.

Question-level "does not apply" removes the question from the risk counts in lens, pillar and workload totals and
from the improvement plan (gate G9). The JSON consolidated report breaks counts down only for the AWS
Well-Architected Framework lens, and its workload totals include every lens on the workload, so use
`GetLensReview` or `ListLensReviewImprovements` for ORR-only counts.

See [gates.md](gates.md) for the gate results.

## Exceptions and accepted risks

Record each accepted High in the question notes as a tag only:

```
EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>
```

- `<register-id>` is the entry in your risk register or plan of action and milestones (POA&M).
- `exp:` is the expiry date. Every acceptance expires; after that date the risk is open again.
- `role:` is the approver's role, for example `business-owner` or `authorizing-official`.

Keep the approver's name, the reason and the compensating controls in the register, never in WA Tool notes. Notes
appear in reports, sync to Jira when it is enabled, and may be reachable through public-records requests.
`readiness_signoff` requires every High in this lens and its companion lenses to be fixed or accepted this way. A
consistent tag format lets you report acceptances that have expired.

An accepted High still shows as High in the WA Tool. The tag records that the accountable owner decided to launch
with it, until the expiry date.

## Calibration

Bars are calibrated against public sources only:

- the ORR whitepaper's example questions (Appendix B) and its page "The ORR tool";
- Well-Architected Framework best practices and their levels of risk;
- [AWS DevOps Guidance](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/devops-guidance.html);
- the Amazon Builders' Library;
- public [AWS Post-Event Summaries](https://aws.amazon.com/premiumsupport/technology/pes/), each cited as a
  one-sentence customer design lesson.

Numeric targets in the lens (for example "in the last 12 months" or "within 30-60 days") are this lens's
suggestions. The bars are not a statement of how AWS operates its own services, and completing the lens is not an
AWS certification, attestation or audit.

## How bars change

Each practice is scored by exactly one owning statement, so a bar changes in one place. After a release, feedback
from field use informs bar changes under these rules:

1. Prevalence alone never demotes a core statement. If most reviewed workloads lack a practice, that is the
   finding.
2. If reviewers disagree on a statement in more than 25% of reviewed workloads, rewrite it as a clarity problem; do
   not demote it.
3. Demote a core statement (to secondary, or cap the question at Medium) only if its `severity_basis` is a
   documented deviation with no public High basis, and reviewers rate the gap non-blocking in at least 2/3 of
   reviewed workloads. Record the rationale in the CHANGELOG.
4. Never demote these, each with a public High basis: `tp_per_source_limits` (REL05-BP02), `rec_restore_tested`
   (REL13-BP03), `cc_review_enforced` and `rb_auto` (whitepaper example questions scored High risk),
   `can_own_metrics_alarms` (whitepaper example), `az_static_capacity` and `ev_shift_mechanism` (whitepaper
   Availability Zone examples), and `exp_no_leaf_pinning` (the whitepaper's certificate-pinning example). Where many
   workloads fail one of these, publish implementation guidance and a suggested fix-by window instead.
5. Promote a secondary statement to core only if reviewers rate the gap launch-blocking in at least 2/3 of reviewed
   workloads and a public rationale is added to this page (decision D-3).
6. If at least 70% of reviewed workloads are Medium on a question because of the same secondary statement, rewrite
   that statement (a MINOR release) or move it to unscored improvement-plan guidance, which retires its ID (a MAJOR
   release), with the rationale in the CHANGELOG.
7. No rule fires until at least 5 workloads have been reviewed.

Release types:

| Change | SemVer | WA version type | Effect on workloads |
|---|---|---|---|
| Text, links or typos; no ID or rule change | PATCH (for example 2.0.1) | Minor | Applied silently to every workload |
| New or changed statements or rules, a severity change, or a new question | MINOR (for example 2.1.0) | Major | Owners are notified and upgrade per workload, with a milestone |
| Restructure, or removing a statement or question (which retires its ID) | MAJOR (for example 3.0.0) | Major | As above, plus a `MIGRATION.md` section |

IDs are never reused, and an ID never changes meaning. Every bar change needs a public source and a
`severity_basis`, a truth-table diff and a CHANGELOG entry with the rationale (see `CONTRIBUTING.md`).

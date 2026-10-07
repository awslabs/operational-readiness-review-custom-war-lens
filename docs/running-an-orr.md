# Running an Operational Readiness Review

This guide explains how to run an Operational Readiness Review (ORR) with this lens in the AWS Well-Architected
Tool (WA Tool): when to run it, who takes part, how long it takes, what you produce, and how you follow up. It
follows the AWS [Operational Readiness Reviews whitepaper](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/wa-operational-readiness-reviews.html)
and Well-Architected best practice
[OPS07-BP02 Ensure a consistent review of operational readiness](https://docs.aws.amazon.com/wellarchitected/latest/framework/ops_ready_to_support_const_orr.html).

Cadences and time boxes on this page are the maintainers' suggestions. Field use measures them, and they change
when the evidence says so.

Related guides: [facilitator-guide.md](facilitator-guide.md) (for the person who runs the session),
[scoring.md](scoring.md) (what the risk levels mean and how they are computed),
[ops-review-agenda.md](ops-review-agenda.md) (the recurring operations review that keeps ORR findings visible),
[govcloud.md](govcloud.md) (AWS GovCloud (US) notes) and [faq.md](faq.md).

## The lens family

| Lens | What it covers | Attach it when |
|---|---|---|
| Operational Readiness Review (ORR), the core lens | 36 questions in four pillars: 01 - Architecture, 02 - Release Quality, 03 - Event Management and 04 - Readiness Decision | Every production workload, before launch and on a recurring schedule |
| ORR - Mission-Critical Event Readiness | 8 questions in three pillars: 01 - Prepare, 02 - Operate, 03 - After the event | A scheduled peak, for example an election, an enrollment or tax deadline, a product launch, ticket sales, a broadcast, or a migration or cutover. Attach it alongside a current core review |

Each lens you import uses one of the 15 custom-lens slots per account per Region, and a workload can have up to
20 lenses attached ([AWS Well-Architected Tool endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/wellarchitected.html)).

## When to run it

| Use | Lenses | When | Time box | Output |
|---|---|---|---|---|
| Pre-launch ORR (the primary use) | Core | A self-assessment at design-complete; a mid-cycle check-in on the release and testing questions; then a facilitated review 2-4 weeks before launch. Answer `readiness_signoff` last | Core path only (triage and check-ins): about 90-120 minutes. Full core (required for a launch go or no-go): about 3 hours, in two 90-minute sessions. Plus 2-4 hours of evidence gathering by the team beforehand | Milestone `ORR-<yyyy-mm>-launch`, improvement plan, one-page readout, go or no-go record |
| Recurring ORR | Core | At least yearly, and after a major architecture change or a significant incident | About 2 hours: review answers that changed since the last milestone, then confirm the rest | Milestone `ORR-<yyyy-mm>-recurring`, trend against the last milestone |
| Event readiness | Core plus Event | See [Event timeline](#event-timeline) below | About 60 minutes for the event lens, on top of a current core review | Milestones before and after the event |

### The three phases of a pre-launch ORR

1. **Design-complete self-assessment.** The workload team answers the core lens on its own, early enough to change
   the design. Expect many High risks at this stage; that is the point. Save a milestone (for example
   `ORR-2026-11-design`).
2. **Mid-cycle check-in.** Revisit the release and testing questions (pillar 02 - Release Quality, plus
   `architecture_load_testing`, `event_resilience_recoveries`, `event_az_evacuation` and `event_gameday`) once the
   pipeline and test environments exist. You do not need to re-run the whole core at this stage; answer these
   questions and save a milestone (for example `ORR-2026-11-midcycle`).
3. **Facilitated review, 2-4 weeks before launch.** An independent facilitator challenges every answer against
   evidence. Run the full core. Answer `readiness_signoff` last, and save the launch milestone at sign-off.

## The core path, and why a launch decision needs the full core

The core path is a published subset of 15 questions for triage and recurring check-ins. It covers every
launch-blocking failure class:

| Failure class | Core-path questions |
|---|---|
| Irreversible data loss | `architecture_rpo_rto`, `architecture_data_corruption` |
| Failures triggered from outside the team's control (certificate expiry, DDoS, overload, loss of an Availability Zone, a Region dependency or a private network path) | `event_expiring_materials`, `architecture_edge_protection`, `architecture_defensive_throttling`, `architecture_load_testing`, `event_resilience_recoveries`, `architecture_recovery_dependencies`, `architecture_hybrid_connectivity` |
| Change-induced failure | `releases_manual_changes`, `releases_staged_deployments`, `releases_deployment_rollback` |
| Detection and response | `event_alarms`, `event_oncall_rotation` |
| The decision itself | `readiness_signoff` |

Its basis is public: Well-Architected rates
[REL13-BP03](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_planning_for_recovery_dr_tested.html),
[REL05-BP02](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_throttle_requests.html)
and [REL02-BP02](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_planning_network_topology_ha_conn_private_networks.html)
High risk; the whitepaper's
[example questions](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/appendix-b-example-orr-questions.html)
score a missing independent change review and missing automatic rollback as High risk; and its page
[The ORR tool](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/the-orr-tool.html)
scores certificate pinning as High risk. Questions that refine a class already on the path, such as
`architecture_retry_timeouts`, `releases_phased_rollout`, `event_canary_alarms` and `event_az_evacuation`, stay in
the full core with the same High bars.

**A core-path-only session is preliminary.** A launch go or no-go requires the full core. `readiness_signoff`
includes the core statement `rd_scope_complete` ("every question in this lens is answered or marked not
applicable with a reason"), so a review that skips questions cannot score better than High on the decision
question.

## Roles

| Role | Responsibility |
|---|---|
| Accountable owner | The business owner or, in government, the authorizing official. Makes the go or no-go decision and accepts risks. Acceptances are recorded in your risk register or plan of action and milestones (POA&M), not in WA Tool notes |
| Facilitator | Independent of the workload team, in the role the whitepaper gives the Ops Champion, who challenges the team on its answers during the review ([Iteration](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/iteration.html)). See [facilitator-guide.md](facilitator-guide.md) |
| Workload team leads | Answer the questions and bring the evidence |
| On-call representative | Confirms paging, runbooks, access and escalation work as described |
| Security representative | Answers `releases_security_readiness` and reviews the access questions |

### Who answers

Answers come from whoever operates the practice. That can be the in-house team, or an operations partner, such as
a systems integrator or managed service provider, that runs part of the workload under contract. When a partner
answers, it answers for its part with evidence you can inspect: for example its paging records, restore test
reports or pipeline configuration. A contract clause alone is not evidence that a practice works.

## Before the review

1. Import the lens (see the README quick start) and attach it to the workload. Attach the event lens too if a
   scheduled peak is coming.
2. Name the accountable owner, the facilitator and the session dates.
3. Give the workload team 2-4 hours to gather evidence. Each question's description ends with an
   `Evidence to collect:` line; use it as the checklist. Link to evidence from the notes; do not paste it.
4. Agree the go or no-go criteria up front (`rd_criteria_owner`): for example no unaccepted High risks, load test
   passed, on-call staffed.

## During the review

- Run the full core for a launch decision, in two sessions of about 90 minutes. A suggested split: session 1
  covers 01 - Architecture; session 2 covers 02 - Release Quality, 03 - Event Management and 04 - Readiness
  Decision.
- Select a statement only when it is true today and the evidence supports it. Selecting "None of these" means none
  of the statements is true, and the question scores its maximum risk.
- A scope exit (for example "The workload has no internet-facing endpoints") scores No risk outright, so the
  facilitator accepts it only with the evidence its helpful text lists.
- Mark a whole question "does not apply" only with a reason. Prefer a scope-exit statement where the question has
  one, and do not mark individual statements not applicable: a statement marked not applicable is treated as met
  in AND conditions but not in OR conditions (alternatives and scope exits), so marking a core statement not
  applicable can lift the question to Medium or No risk without the practice
  (see [scoring.md](scoring.md#not-applicable)).
- If the PDF lens review report is your record of the review, note that it shows improvement plans and additional
  resources but not question descriptions or question-level helpful text (sandbox gate G4), so keep the evidence
  list for each question with your own review records.
- Keep notes short and free of sensitive data (see [Notes and data handling](#notes-and-data-handling)).

## After the review: the one-page readout

Share a one-page readout with the accountable owner and stakeholders. It holds:

| Section | Content |
|---|---|
| Scope | Workload, lenses and versions, milestone name, date, participants by role |
| Decision | Go, no-go or conditional go, the decision owner, and the date |
| High risks | Each open High: question, the gap in one line, the owner, the target date, and whether it is fixed or accepted |
| Accepted risks | Each acceptance: the register or POA&M ID, the approver role and the expiry date |
| Medium risks | Count per pillar, and the hardening items scheduled on the improvement plan |
| Mitigations | Compensating controls agreed for accepted risks (details stay in the register) |
| Next review | Date of the next recurring ORR, and any event review that is due |

Save a milestone at sign-off. Name milestones `ORR-<yyyy-mm>-<purpose>`, for example `ORR-2026-12-launch` or
`ORR-2027-06-recurring`. A workload can hold up to 100 milestones
([quotas](https://docs.aws.amazon.com/general/latest/gr/wellarchitected.html),
[Milestones](https://docs.aws.amazon.com/wellarchitected/latest/userguide/milestones.html)).

## What the answers mean

| Risk | Meaning |
|---|---|
| High | Launch-blocking unless remediated, or formally accepted in writing by the accountable owner with an expiry date |
| Medium | The core practice is in place but hardening is outstanding. Fix it on a plan; it does not block launch |
| No risk | Every listed practice is in place and the evidence lines are satisfied |

Read reports High first. [scoring.md](scoring.md) explains how each level is computed and where this lens rates a
practice higher than the Well-Architected Framework does.

### Accepting a High risk

Record each accepted High in the question notes as a tag only:

```
EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>
```

`<register-id>` is the entry in your risk register or POA&M, and the role is, for example, `business-owner` or
`authorizing-official`. The approver's name, the reason and the compensating controls stay in the register. An
acceptance always has an expiry date; when it passes, the risk is open again.

## Inspect: keep the review alive

The whitepaper describes inspecting the ORR process in a recurring operations review
([Inspect the process](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/inspect-the-process.html)).
For each workload, report:

- the date of the last ORR milestone;
- open High items, with owners and dates;
- acceptances that have expired or expire within 30 days.

[ops-review-agenda.md](ops-review-agenda.md) gives a tool-neutral agenda that includes these items.

## Track improvement items

Pick one tracking path and use it for every workload:

| Path | Notes |
|---|---|
| WA Tool Connector for Jira | Syncs improvement items in both directions. Items are organized as an epic per workload, a task per question and a sub-task per best practice (statement), with the pillar as a label. Available in commercial Regions; not available in AWS GovCloud (US) as of 2026-10-06 ([Jira connector](https://docs.aws.amazon.com/wellarchitected/latest/userguide/jira.html)). Do not put sensitive information in notes if you sync to Jira |
| AWS Systems Manager OpsCenter | Create an OpsItem per High risk. Available in AWS GovCloud (US) as of 2026-10-06 ([OpsCenter](https://docs.aws.amazon.com/systems-manager/latest/userguide/OpsCenter.html)) |
| Your own tracker (for example an ITSM tool) | Export improvement items on a schedule with [ListLensReviewImprovements](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_ListLensReviewImprovements.html) for each workload, and import the CSV. For ORR-only risk counts use `GetLensReview`: the JSON [GetConsolidatedReport](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_GetConsolidatedReport.html) breaks counts down only for the AWS Well-Architected Framework lens, and its workload totals include every lens on the workload (sandbox gate G9, [gates.md](gates.md)) |

## Notes and data handling

- Lens files contain no customer data. Answers and notes stay in your account and Region.
- Notes appear in reports, and they sync to Jira when that is enabled. Never paste secrets, credentials, personal
  data or sensitive incident details into notes. Link to evidence instead.
- Accepted risks carry only the `EXC:` tag in notes; everything else stays in the risk register or POA&M.
- In AWS GovCloud (US), some workload fields may leave the GovCloud (US) Regions in normal operation. See
  [govcloud.md](govcloud.md#data-handling).

## Event timeline

For a scheduled peak, attach the event lens alongside a current core review and follow this timeline:

| When | What |
|---|---|
| 3-6 months before | Budget and procure anything you must buy, for example a 1-year AWS Shield Advanced subscription, a support plan change, AWS Countdown Premium, or a load-test or DDoS test partner. Request large quota increases |
| At least 8 weeks before | Complete the event review. If the event needs reserved EC2 capacity, 56 days is AWS's recommended lead time for future-dated Capacity Reservations, which apply to eligible instance families and requests of at least 32 vCPUs. Request remaining quota increases |
| 30-60 days before | Re-run the load test against this event's forecast |
| 4 weeks before | Close every High risk, or record a formal acceptance. Items that can only be done in the final two weeks (escalation tree verification) need a dated plan and are re-scored at the 2-week checkpoint |
| 2-3 weeks before | If you use AWS Countdown Premium, sign up: the [AWS Countdown](https://aws.amazon.com/premiumsupport/aws-countdown/) page says to begin 2-3 weeks before the event |
| 2 weeks before | Freeze changes or arm deployment blockers. Re-verify the escalation tree, edge rules and privileged access |
| Within 2 weeks after | Post-event review, scale-down, and a milestone |

Answer the event lens at 8 weeks, update it and save a milestone at 4 weeks and 2 weeks, and again after the event.
A time-boxed statement whose window has not opened yet stays unselected, and its improvement plan is the schedule.

The event lens is a self-assessment that comes before, or feeds, an AWS Countdown engagement; it does not replace
one.

## How this lens relates to the Well-Architected Framework review and AWS offerings

- **Well-Architected Framework review (WAFR).** The Framework lens covers breadth across six pillars. The ORR
  covers launch-blocking operational risk in depth and is run separately. The question `well_architected` checks
  that a current WAFR exists and that its high-risk issues are dispositioned, so the two are not double counted.
- **AWS offerings.** These complement the lens; none is required, and the lens's partition notes say where each is
  available:
  - AWS Resilience Hub, to validate recovery time and recovery point objectives;
  - AWS Fault Injection Service (FIS) and Amazon Application Recovery Controller (ARC), for testing and
    Availability Zone evacuation;
  - AWS Countdown and Countdown Premium, for events;
  - AWS Support plans, for escalation ([AWS Support plans](https://docs.aws.amazon.com/awssupport/latest/user/aws-support-plans.html));
  - the AWS Operational Readiness Review Workshop, a proactive service in the Enterprise Support and Unified
    Operations plans, for building your organization's own checklist
    ([Proactive Services](https://aws.amazon.com/premiumsupport/technology-and-programs/proactive-services/));
  - AWS Trusted Advisor and the AWS Well-Architected Agent preview, for automated Framework checks. As of
    2026-10-06 the agent's architecture reviews support only the Well-Architected Framework lens, so it does not
    evaluate this custom lens ([Conducting architecture reviews](https://docs.aws.amazon.com/wellarchitected/latest/userguide/agent-architecture-reviews.html)).
- **Who runs it.** The ORR is customer-run. AWS account teams or partners may facilitate it, but the lens never
  assumes they will. Completing it does not mean AWS has reviewed your workload.

### Companion lenses

Attach the AWS lenses that fit the workload; the statement `wa_lenses_applied` checks that they were applied.

| Where it comes from | Examples | Custom-lens slots used |
|---|---|---|
| WA Tool [Lens Catalog](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lens-catalog.html), no import needed | Government, Generative AI, Serverless Applications, SaaS, DevOps, Financial Services Industry | None |
| Imported as custom lenses from [aws-samples/sample-well-architected-custom-lens](https://github.com/aws-samples/sample-well-architected-custom-lens) | Agentic AI, Responsible AI, Digital Sovereignty | 1 of the 15 per account per Region, each |
| This repository | ORR core, ORR - Mission-Critical Event Readiness | 1 each |

If your organization needs its own questions, put them in a separate add-on lens; see
[customizing.md](customizing.md).

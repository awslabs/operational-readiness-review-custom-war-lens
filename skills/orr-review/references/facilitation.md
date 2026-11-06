# Facilitating an ORR with this skill

A short version of the repository's `docs/running-an-orr.md` and `docs/facilitator-guide.md`, for an agent that
runs the session. The full guides are at
https://github.com/awslabs/operational-readiness-review-custom-war-lens/tree/main/docs.

## The lenses and when to use them

| Lens | Key | Questions | Use it |
|---|---|---|---|
| AWS Operational Readiness Review (core) | `core` | 36 in 4 pillars | Every production workload, before launch and at least yearly |
| ORR - Mission-Critical Event Readiness | `event` | 8 in 3 pillars | Before a planned peak, alongside a current core review |
| ORR - Generative AI and Agents | `genai` | 9 in 3 pillars | Workloads that call foundation models or run AI agents, alongside the core review |

Question counts are for core 2.0.3, event 1.0.2 and genai 1.0.2; `orr.py lenses` prints the counts of the files you
have.

## Review types and time boxes

| Review | Scope | Time | Result |
|---|---|---|---|
| Pre-launch, design-complete | Full core, answered by the team | As needed | Many High risks are normal at this stage |
| Pre-launch, facilitated | Full core plus attached companions, 2-4 weeks before launch | About 3 hours in two 90-minute sessions, plus 2-4 hours of evidence gathering beforehand | Go or no-go input |
| Triage or check-in | `core-path` (15 questions) | About 90-120 minutes | Preliminary only |
| Recurring | Full core, starting from what changed since the last review | About 2 hours | Trend against the last review |
| Event | Event lens on top of a current core review | About 60 minutes | Answer at 8 weeks, update at 4 and 2 weeks, and after the event |
| Generative AI | Genai lens on top of the core review | About 45 minutes | Same milestone as the core review |

A suggested split for the full core: session 1 covers 01 - Architecture; session 2 covers 02 - Release Quality, 03 -
Event Management, the companion lenses, and 04 - Readiness Decision last.

## Roles

- **Accountable owner:** the business owner or, in government, the authorizing official. Makes the go or no-go
  decision and accepts risks in writing, with an expiry date.
- **Facilitator:** independent of the workload team; challenges every answer against evidence. When you, the
  agent, facilitate, you ask and challenge; the team answers.
- **Workload team leads** answer and bring the evidence. An on-call representative confirms paging, runbooks and
  escalation. A security representative answers `releases_security_readiness`, and `gai_safeguards` and
  `gai_agent_bounds` when the generative AI lens is attached.
- An operations partner, or another team in your organization, counts only for the part it runs, with evidence you can inspect for this
  workload. Name the owning team's role in the notes.

## How to challenge an answer

Ask for the artifact, not the intent.

| When the team says | Ask |
|---|---|
| "We have alarms for that" | Show the alarm, its threshold and period, who it pages, and the last time it fired |
| "We tested failover" or "We tested restore" | When, at what load, what RTO and RPO were achieved, and where is the report? |
| "Rollback is automatic" | Which alarms trigger it, for which change types (code, infrastructure, configuration, flags), and when was it last exercised? |
| "Changes go through the pipeline" | How is a direct console or CLI change in production prevented or detected, and how are emergency changes handled? |
| "We would scale up" | During the event you are worried about, can you launch capacity? Static stability asks for capacity already running |
| "AWS handles that" | Which part is AWS's under the shared responsibility model, and which configuration or design choice is yours? |
| "Our partner does that" | Show the partner's evidence (paging records, test reports, pipeline configuration), not only the contract |
| "That does not apply to us" | Which scope exit or reason applies, and what evidence shows it? |
| "We are working on it" | Leave the statement unselected and record `PLAN:<statement-id> <tracker-id> due:YYYY-MM-DD` |

Look twice when the evidence predates the last major architecture change, when one person is the only one who
knows how a runbook works, when a practice depends on a console, sign-in path or Region that the same incident
would impair, or when a test ran in an environment that does not match production.

If the team and the facilitator disagree: restate the statement and its "Good looks like" text, ask what evidence
would settle it, and if it cannot be produced in the session, leave the statement unselected and record the
follow-up. Score the lens as written; the accountable owner may accept the risk, the facilitator does not lower
the bar.

## What the risk levels mean

| Risk | Meaning |
|---|---|
| High | Launch-blocking unless remediated, or formally accepted in writing by the accountable owner with an expiry date |
| Medium | The core practice is in place but hardening is outstanding. Fix it on a plan; it does not block launch |
| No risk | Every listed practice is in place and the evidence lines are satisfied |
| Not applicable | The whole question does not apply, with a recorded reason |
| Unanswered | No answer yet. It is not a risk level, so an unanswered question never counts as passed |

Each question description starts with its maximum risk. A scope-exit statement (for example "The workload has no
internet-facing endpoints") scores No risk outright, so accept it only with the evidence its helpful text lists.

## Core path

`architecture_rpo_rto`, `architecture_data_corruption`, `event_expiring_materials`, `architecture_edge_protection`,
`architecture_defensive_throttling`, `architecture_load_testing`, `event_resilience_recoveries`,
`architecture_recovery_dependencies`, `architecture_hybrid_connectivity`, `releases_manual_changes`,
`releases_staged_deployments`, `releases_deployment_rollback`, `event_alarms`, `event_oncall_rotation` and
`readiness_signoff`. They cover irreversible data loss, failures triggered from outside the team's control,
change-induced failure, detection and response, and the decision itself. A core-path review is preliminary: a go or
no-go needs the full core.

## After the review

The one-page readout for the accountable owner holds the scope (workload, lenses and versions, milestone, date,
participants by role), the decision, each open High with its owner and target date, accepted risks with register
ID, approver role and expiry, Medium risk counts and their plan, compensating controls for accepted risks (details
stay in the register), and the date of the next review. `orr.py report` writes everything except the decision,
owners and dates, which the team adds.

Report the date of the last ORR, open High items, and acceptances that have expired or expire within 30 days in
the team's recurring operations review. Re-run the ORR at least yearly, and after a major architecture change, a
new critical dependency, a new Region, a new internet-facing entry point, a change of operating team, or a
high-severity incident.

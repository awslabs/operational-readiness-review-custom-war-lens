# Facilitator guide

This guide is for the person who runs an ORR session with this lens. The facilitator is independent of the
workload team. The ORR whitepaper gives this role to the Ops Champion, who challenges the team on its answers
during the review
([Iteration](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/iteration.html)).
Your job is not to score the team well or badly; it is to make sure every answer is true today and backed by
evidence, so the accountable owner decides on facts.

Read [running-an-orr.md](running-an-orr.md) first for the phases, roles, readout and follow-up, and
[scoring.md](scoring.md) for how answers become risk levels.

## Three rules

1. **Run the full core for a launch decision.** The 15-question core path is for triage and recurring check-ins. A
   go or no-go needs every question answered or marked not applicable with a reason. `readiness_signoff` enforces
   this through `rd_scope_complete`: a review that skips questions cannot score better than High on the decision
   question.
2. **Accept a scope exit only with evidence.** A scope exit, such as "The workload has no internet-facing
   endpoints" or "Only Regional managed services on the critical path", scores No risk outright. Its helpful text
   lists the evidence to collect. If the team cannot show it, the scope exit is not selected.
3. **Select a statement only when it is true today.** Intended work, a ticket, a design document or a practice that
   works "most of the time" does not count. If it is not true today, leave it unselected and put the work on the
   improvement plan.

## Before the session

- Confirm the accountable owner, the attendees by role (workload leads, on-call, security) and the two session
  slots of about 90 minutes each.
- Send the team the `Evidence to collect:` lines from each question description and ask for links to evidence 2-4
  days ahead. Unanswered evidence requests are a finding in themselves.
- Check that the lens version attached to the workload is the current release, and that a milestone from any
  earlier review exists.
- If the workload is in AWS GovCloud (US), read [govcloud.md](govcloud.md); some statements name services that are
  not available there, and the helpful text offers a method-based alternative.

## Running the session

A suggested agenda for the full core:

| Session | Time | Content |
|---|---|---|
| 1 | 5 min | Purpose, decision criteria, how to answer (true today, with evidence) |
| 1 | 80 min | 01 - Architecture (14 questions) |
| 1 | 5 min | Parking lot and evidence follow-ups |
| 2 | 30 min | 02 - Release Quality (5 questions) |
| 2 | 50 min | 03 - Event Management (16 questions) |
| 2 | 10 min | 04 - Readiness Decision (`readiness_signoff`, answered last), readout summary |

Keep a parking lot for questions that need evidence the team does not have in the room. A parked question stays
unanswered until the evidence arrives; do not guess.

### How to challenge an answer

Ask for the artifact, not the intent. Useful prompts:

| When the team says | Ask |
|---|---|
| "We have alarms for that" | Show the alarm, its threshold and period, who it pages, and the last time it fired |
| "We tested failover" or "We tested restore" | When, at what load, what was the achieved RTO and RPO, and where is the report? |
| "Rollback is automatic" | Which alarms trigger it, for which change types (code, infrastructure, configuration, flags), and when was it last exercised? |
| "Changes go through the pipeline" | Show how a direct console or CLI change in production is prevented or detected, and how emergency changes are handled |
| "We would scale up" | During the event you are worried about, can you launch capacity? The static-stability statements ask for capacity that is already running |
| "AWS handles that" | Which part is AWS's under the shared responsibility model, and which configuration or design choice is yours? |
| "Our partner does that" | Show the partner's evidence (paging records, test reports, pipeline configuration), not only the contract clause |
| "That does not apply to us" | Which scope exit or reason applies, and what evidence shows it? |

Other signs that an answer needs a second look:

- The evidence predates the last major architecture change.
- One person is the only one who knows how a runbook works.
- A practice depends on a console, sign-in path or Region that the incident in question would also impair.
- A test ran only in an environment that does not match production (see `pp_parity`).

### "None of these" and not applicable

- If none of a question's statements is true today, select **None of these**. The question then scores its
  maximum risk. That is the honest answer, and it is better than leaving the question unanswered. The WA Tool does
  not clear other selections when you select it, and any question with "None of these" selected scores its
  maximum risk, so clear "None of these" when a statement becomes true.
- Mark a whole question **does not apply** only with a written reason, and prefer a scope-exit statement where the
  question has one. Do not mark individual statements not applicable: a statement marked not applicable is treated
  as met in AND conditions but not in OR conditions (alternatives and scope exits), so marking a core statement
  not applicable can lift the question to Medium or No risk without the practice, and marking every statement not
  applicable scores No risk (sandbox gate G3, see [gates.md](gates.md) and
  [scoring.md](scoring.md#not-applicable)). Before you close a review, check for
  statement-level not-applicable marks and challenge each one as you would a scope exit.
- A "does not apply" flag carried over from a v1 review does not count in this review until you re-confirm it here
  (see [MIGRATION.md](../MIGRATION.md)). Check the questions whose scope or maximum risk changed in 2.0.0 first,
  for example `event_expiring_materials` and `event_gameday`: a stale flag on either keeps a launch-blocking
  question out of the risk counts, and `rd_scope_complete` is not met until every carried flag is re-confirmed.

### Notes

- Keep notes short: what evidence was shown, as links. Notes appear in reports and sync to Jira when it is enabled.
- Never put secrets, credentials, personal data, customer names or sensitive incident details in notes.
- For an accepted High risk, the note carries only `EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>`. The
  approver's name, the reason and the compensating controls stay in the risk register or POA&M.

### Disagreements

If the team and the facilitator disagree on whether a statement is true:

1. Restate the statement and its "Good looks like" text, and ask what evidence would settle it.
2. If evidence cannot be produced in the session, leave the statement unselected and record the follow-up.
3. If the disagreement is about whether the bar is right for this workload, record it, but score the lens as
   written. Send the disagreement to the maintainers as feedback (below). The accountable owner may accept the
   risk; the facilitator does not lower the bar.

## Closing the review

- Answer `readiness_signoff` last, after every other question in this lens and any companion lens.
- Walk the accountable owner through the High risks first, then the Medium risks.
- Confirm each accepted High has an `EXC:` tag, a register entry and an expiry date.
- Save a milestone named `ORR-<yyyy-mm>-<purpose>` (for example `ORR-2026-12-launch`).
- Send the one-page readout (template in [running-an-orr.md](running-an-orr.md#after-the-review-the-one-page-readout)).
- Make sure the next review is scheduled: at least yearly, and before major launches, architecture changes or peak
  events.

## Recurring reviews

For a recurring ORR (about 2 hours):

1. Compare the current answers with the last milestone (in the console, or with `GetAnswer` and a
   `MilestoneNumber`).
2. Walk through what changed since then: architecture, dependencies, traffic, team, incidents and near misses, and
   relevant public [AWS Post-Event Summaries](https://aws.amazon.com/premiumsupport/technology/pes/).
3. Re-challenge every answer those changes affect, then confirm the rest.
4. Re-check every acceptance's expiry date.
5. Save a new milestone and send the readout.

## Feedback to the maintainers

The bars change only under the rules in [scoring.md](scoring.md#how-bars-change). Facilitator feedback is the main
input. Useful feedback, sent as a GitHub issue on this repository, includes:

- minutes spent per question;
- statements the team and facilitator could not agree on, and why;
- statements that were unclear, or that did not fit a platform (EC2, containers or serverless) or a partition;
- broken or outdated links.

Never include customer names, account IDs, workload names or incident details in an issue. Describe the pattern,
not the workload.

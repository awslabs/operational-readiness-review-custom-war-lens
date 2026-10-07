# Recurring operations review agenda

An ORR is a point-in-time review. A recurring operations review keeps its findings visible between reviews, and
the ORR whitepaper describes inspecting the ORR process there: the date of the last ORR and open action items are
reviewed on a schedule
([Inspect the process](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/inspect-the-process.html)).
The statement `slo_reviewed` in the core lens asks for this review.

The agenda below is tool-neutral: use whatever dashboards, ticketing, paging and deployment tools you already have.
It modernizes the eight-item operations meeting agenda that v1.3.6 carried in the `event_kpis` question (action
items, high-severity tickets, pipeline rollbacks and blocks, customer support tickets, open high-severity tickets,
new runbook entries, a component dashboard deep dive, and the on-call rotation), and adds service level objectives
(SLOs), error budgets, open ORR High risks, expired risk acceptances and exercise findings.

## Format

| | Suggestion |
|---|---|
| Cadence | Weekly for production workloads; every two weeks at minimum |
| Length | 30-60 minutes. Keep it to the agenda; move deep design discussions to their own meeting |
| Attendees | Workload owner or delegate (chairs), the outgoing and incoming on-call engineers, one lead per component, and, when the ORR items are covered, the facilitator or whoever tracks ORR risks |
| Inputs | Prepared before the meeting, not built live: an SLO report, the incident and change lists, the alarm report and the ORR status for each workload |
| Output | Action items with an owner and a due date, recorded in your tracker |

## Agenda

| # | Item | Time | What to look at | Typical action |
|---|---|---|---|---|
| 1 | Action items from the last review | 5 min | Each open item: done, on track or late | Close done items; escalate late ones |
| 2 | SLO attainment and error budgets | 5-10 min | For each critical user journey and API: availability, latency and asynchronous-completion SLOs against target, and error budget consumed in the period and the rolling window | If a budget is burning faster than its window allows, prioritize reliability work over feature work until it recovers |
| 3 | Incidents and near misses | 5-10 min | Customer-impacting events and near misses since the last review; status of each post-incident analysis and its corrective actions; for each, whether an ORR question would have prevented the impact | Assign analyses; add corrective actions; propose new or revised questions for your add-on lens ([customizing.md](customizing.md)) |
| 4 | Changes and deployments | 5 min | Rollbacks (automatic and manual), blocked or stopped deployments, failed changes, emergency changes, and any change made outside the pipeline | Find out why each rollback or block happened; treat an out-of-pipeline change as a finding |
| 5 | Alarms and paging | 5 min | Pages per on-call shift, alarms that fired without action (noisy), alarms that should have fired but did not (missing), and alarms in a missing-data state | Tune or remove noisy alarms; add missing ones; link a runbook to every paging alarm |
| 6 | Customer support signals | 5 min | Open customer support cases and escalations, and the trend in contact volume | Link cases to incidents or known issues |
| 7 | ORR status | 5 min | For each workload: date of the last ORR milestone; open High risks with owners and dates; accepted risks whose `exp:` date has passed or falls within 30 days; whether a recurring or event review is due | Schedule overdue reviews; renew or close expiring acceptances through the accountable owner |
| 8 | Exercise findings | 5 min | Findings from game days, tabletop exercises, recovery drills and load tests since the last review, and their status | Track each finding to closure; update runbooks, alarms and the ORR answers they affect |
| 9 | Capacity, quotas and cost signals | 5 min | Quota and scaling-ceiling headroom against forecast peak plus failover, saturation trends, and usage or cost anomalies | Request quota increases early; investigate anomalies |
| 10 | Upcoming changes from providers and expiring materials | 5 min | Provider notices (for example AWS Health lifecycle events: engine, runtime and certificate authority changes), third-party status notices, and certificates, keys, secrets, tokens, licenses and domains that expire within 60 days | Schedule pre-production testing for provider changes; confirm renewals are automated or owned |
| 11 | Runbook changes | 2 min | Runbook entries added or changed since the last review | Make sure the on-call engineers know about them |
| 12 | Dashboard deep dive | 5-10 min | One component's detailed dashboard, rotating through components each week: what normal looks like, outliers, and signals nobody watches | Add alarms or remove unused signals |
| 13 | On-call handoff and health | 3 min | Load on the outgoing on-call, open issues handed over, rotation gaps for the coming period (including holidays and peak dates) | Fix gaps in the schedule before they arrive |

Total: about 60 minutes. For a shorter meeting, keep items 1, 2, 3, 4, 7 and 13 every time, and rotate the rest.

## Notes

- **Error budgets.** An error budget is the amount of unreliability an SLO allows over its window (for example, a
  99.9% availability SLO over 28 days allows about 40 minutes of full unavailability). The decision it drives is
  what the team works on next, not who is blamed. If you use Amazon CloudWatch Application Signals, its SLO
  feature reports attainment and budget
  ([Service level objectives](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-ServiceLevelObjectives.html));
  any SLO tool meets this practice.
- **ORR status.** Pull it from the WA Tool rather than by hand: milestones per workload, and ORR risk counts per
  workload from `GetLensReview` or
  [ListLensReviewImprovements](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_ListLensReviewImprovements.html).
  The JSON consolidated report breaks counts down only for the AWS Well-Architected Framework lens, and its
  workload totals include every lens on the workload (sandbox gate G9, [gates.md](gates.md)).
  Expired acceptances are easy to find when every acceptance uses the
  `EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>` note format ([scoring.md](scoring.md#exceptions-and-accepted-risks)).
- **Keep it blameless.** The review looks for gaps in mechanisms, not for people to blame.
- **Keep records clean.** Meeting notes are often shared widely. Do not copy secrets, credentials, personal data
  or sensitive incident details into them; link to the incident record instead.

## Related

- [running-an-orr.md](running-an-orr.md#inspect-keep-the-review-alive): what to inspect between reviews.
- The core lens questions `event_alarms` (SLOs and alarms), `event_post_incident_analysis` (learning loop),
  `event_gameday` (exercises), `event_expiring_materials` and `event_provider_escalation` (provider notices) score
  the practices this meeting reviews.

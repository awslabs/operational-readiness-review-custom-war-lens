# Findings report format (reference mode)

Script mode writes this report with `scripts/orr.py report`. In reference mode, write the same sections in this
order, from the answers table, the risk lines in `lens-<lens>.md` and the plans in `plans-<lens>.md`. Use plain
Markdown. Put text in angle brackets only where it stands for a value you fill in.

```
# ORR findings: <workload>

| Item | Value |
|---|---|
| Workload | <workload> |
| Milestone | <milestone, or "none recorded"> |
| Review | Full, or "Core path (preliminary: a go or no-go needs the full core)" |
| Lenses | <lens name and version from each lens file title> |
| Scoring | By hand from the lens risk rules (reference mode) |
| Report date | <YYYY-MM-DD> |
| Progress | <answered or not applicable> of <questions in scope> questions answered or not applicable |

## Summary

<Take each pillar's question count from the table at the top of lens-<lens>.md; do not count questions yourself.
Unanswered = that count minus the pillar's High, Medium, No risk and Not applicable answers. The All row is the
sum of the rows above it, and its Unanswered must equal the number of questions listed under Unanswered below.>

| Lens | Pillar | High | Medium | No risk | Not applicable | Unanswered |
|---|---|---|---|---|---|---|
| <lens> | <pillar> | <n> | <n> | <n> | <n> | <n> |
| **All** | | **<n>** | **<n>** | **<n>** | **<n>** | **<n>** |

## Readiness decision

`readiness_signoff` scores **<risk>**. The go or no-go decision belongs to the accountable owner; record it, with
its date, in your own records.
<When any question is unanswered, add: "This report cannot support a go or no-go decision yet: <n> questions
are unanswered.">
<In a core-path review, add: "This is a core-path review, so its result is preliminary.">

Warnings: <any that apply, for example rd_scope_complete selected while questions are unanswered, None of these
combined with a statement, an expired acceptance, or notes that look like they hold an account ID>

## High risks (<n>)

### `<question_id>`: <question title>

<lens name>, <pillar>. <"Answered None of these." when it was.>
<"Accepted as <register-id> by role <role>, expiry <expiry>." when the notes carry an EXC: tag; add
"(expired: the risk is open again)" when the expiry date has passed.>

Not in place:

- `<statement_id>`: <statement title>. Improvement plan: <the plan copied word for word from plans-<lens>.md,
  or "not available (plans-<lens>.md was not provided)"; never write a plan of your own>

Notes: <notes>

## Accepted risks

| Question | Register ID | Approver role | Expiry | Status |
|---|---|---|---|---|

## Medium risks (<n>)

<same layout as High risks>

## Not applicable (<n>)

- `<question_id>`: <reason>

## Unanswered (<n>)

- `<question_id>` (<lens>): <question title>

## All answers

| Question | Lens | Risk | Selected |
|---|---|---|---|

## About this report

Scored with the risk rules of the ORR lenses, the same rules the AWS Well-Architected Tool applies to the imported
lens. High means launch-blocking unless remediated or formally accepted in writing by the accountable owner.
Medium means fix on a plan. This report is guidance; it is not an AWS certification, compliance attestation or
audit, and it does not mean AWS reviewed the workload. It holds the review notes, so share it only through
approved channels. Source: https://github.com/awslabs/operational-readiness-review-custom-war-lens
```

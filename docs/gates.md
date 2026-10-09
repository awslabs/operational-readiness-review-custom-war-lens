# Sandbox gate results

Before a release, the maintainers test how the AWS Well-Architected Tool (WA Tool) behaves with the CI-built
candidate lens files. Candidates are named `2.0.0rc0`, `2.0.0rc1` and so on. They are imported only into a
dedicated sandbox AWS account (and an AWS GovCloud (US) sandbox account where the feature exists). They are never
published, shared or imported over a lens that production workloads use.

This page records the result of each gate: the date and AWS Region of the run, the result, and what it means for
the lens. It never records account IDs, workload names or ticket IDs. Gates G2, G5 and G8 are re-run on the last
candidate before release, and the release steps diff each released file against that candidate. The event file
differs only in the version string; the core file differs in the version string plus the three display-text
rewordings listed in the [Final candidate](#final-candidate-re-run) section below, which records that re-run. The
WA Tool also rejects importing a second lens with the same name in the same account and Region (see
[A second lens with the same name is rejected](#a-second-lens-with-the-same-name-is-rejected)).

Status values: `not run` (cannot run in this environment; fallback applied), `pass`, `fail (fallback applied)`, or
`documented` (behavior recorded and the docs updated to match).

**Early pass, 2026-10-06.** All gates were run through the WA Tool API with AWS CLI v2, in a non-production
sandbox account, in us-east-1, against the published v1.3.6 file and an early gate candidate (`2.0.0rc0`: six
fully written 2.0.0 questions in four pillars plus minimal stub questions for the kept IDs `well_architected`,
`architecture_health_checks`, `event_alarms` and `event_gameday`, all with new choice IDs). Console rendering, Jira
and AWS GovCloud (US) were not covered in this pass. Every workload, review template and lens created for the run
was deleted afterwards. The results below therefore describe that early candidate, not the released files; the
[Final candidate](#final-candidate-re-run) re-run of G2, G5 and G8 covers those.

| Gate | What we must learn | Date | Region | Result | Implication |
|---|---|---|---|---|---|
| G1 | Is a choice whose ID ends in `_no` ("None of these") exclusive in the console and in the API? | 2026-10-06 | us-east-1 | fail (fallback applied). API: `UpdateAnswer` accepts `none_no` together with other choices, does not normalize them, and scores as if `none_no` were not selected (None plus all four statements scored No risk). Console (checked later the same day): ticking `none_no` greys out the other choices but keeps any already ticked, and **Save and exit** saves both (High under the guard) | The build sets `none_exclusive_guard: true` in both `lens.yaml` files, which adds `&& !none_no` to the No risk and Medium rules |
| G2 | What carries over on upgrade for kept question IDs whose choice IDs are all new: selections, notes, the "does not apply" flag and its reason? | 2026-10-06 | us-east-1 | documented. Selections are cleared (Unanswered). Notes carry over verbatim. `IsApplicable=false` and its `Reason` carry over, and the question stays Not applicable. The upgrade milestone holds the full v1.3.6 answers. Retired IDs leave the current review | "Does not apply" flags carry over, so `MIGRATION.md` requires re-confirming them, and the two v1 questions whose applicability broadened were given new IDs (`releases_phased_rollout` and `architecture_health_lifecycle`, decision D-2). Notes are kept, so the notes forwarder stays optional |
| G3 | How do choice-level not-applicable statuses score? | 2026-10-06 | us-east-1 | documented. Deterministic, but not described in the lens format specification. A statement marked not applicable is neutral: it satisfies `&&` terms and does not satisfy `\|\|` terms. Marking every statement not applicable, with nothing selected, scores No risk | The docs recommend only scope statements and question-level "does not apply", and tell reviewers to treat statement-level not-applicable marks as answers that need evidence |
| G4 | Are descriptions longer than 1,024 characters, question helpful text longer than 64 characters and additional resources truncated, and how do they render in the console, `GetAnswer`, reports and Jira? | 2026-10-06 | us-east-1 | documented. Import accepts up to 2,048 characters in descriptions and display texts and rejects 2,049; titles reject 129. `GetAnswer` returned every long text in full. The PDF lens review report shows full improvement-plan and additional-resource text, but no question descriptions or helpful text. Restricted character set found (see details). Console and Jira checks not run (API only) | The lens keeps the 1,024 / 64 / 1,024 character limits until the console check is done. CI adds a character-set check for names, titles and descriptions |
| G5 | Do the published v1.3.6 file and the candidate import, and how does import completion show? | 2026-10-06 | us-east-1 | pass (early candidate). v1.3.6 imports as-is, and `CreateLensVersion` 1.3.6 succeeds. `ImportLens` returned only `LensArn` with no `Status` field; the draft was listed under `ListLenses` with `LensStatus=DRAFT` at once. The candidate imported once semicolons were removed from restricted fields | No v1.3.7 default-rule fix is needed: an empty selection on `releases_manual_changes` shows as Unanswered. Automation polls `ListLenses` instead of reading `Status` |
| G6 | Do review templates behave as documented across a lens major version, and do template answers on kept question IDs survive the upgrade? | 2026-10-06 | us-east-1 | documented. After the major version, the template showed the lens as not current. `UpgradeReviewTemplateLensReview` succeeded and added the new pillar. On kept IDs, pre-filled selections were cleared, while notes and "does not apply" with its reason were kept. Pre-filled answers on retired IDs were dropped | `MIGRATION.md` tells template owners to upgrade each template, re-pre-fill selections, and review the carried notes and "does not apply" flags before creating workloads from it |
| G7 | How are Jira items named, and what happens to the items of retired questions after an upgrade? | 2026-10-06 | n/a | not run. No test Jira site was available | Fallback: the docs recommend a manual sync around upgrades. Not covered by this run |
| G8 | Does a major version that renames the lens and adds a pillar behave as documented, keeping answers and notes on kept question IDs? | 2026-10-06 | us-east-1 | fail (fallback applied) for the rename; pass (early candidate) for the new pillar. `ImportLens` over the published lens with a new name was rejected ("Lens name must match published name"). With the published name kept, the major version added pillar `04 - Readiness Decision`, and kept IDs behaved as in G2. Console rename not checked | 2.0.0 keeps the current core lens name. `readiness_signoff` stays in its own pillar `readiness_decision`. A rename is possible only by creating a new lens, which is the least preferred option |
| G9 | Do questions marked "does not apply" leave the risk counts in workload reports and consolidated reports? | 2026-10-06 | us-east-1 | pass. Questions marked "does not apply" move from High or Medium to Not applicable in lens, pillar and workload risk counts, in consolidated report workload totals, and drop out of `ListLensReviewImprovements` | Excluded as expected. Note: the JSON consolidated report breaks counts down only by AWS lens, so per-lens ORR counts come from `GetLensReview` or `ListLensReviewImprovements` |

## Final candidate re-run

The early pass used a 10-question candidate. The released files are larger (36 core questions in four pillars, 8
event questions in three pillars) and use parenthesized rules and the restricted character set found in G4, so
G2, G5 and G8 were re-run on the last candidates built from the released sources, `2.0.0rc2` and `1.0.0rc2`. The
event release file `orr-event-1.0.0.json` differs from `1.0.0rc2` only in the version string in the lens
description. The core release file `orr-core-2.0.0.json` differs from the `2.0.0rc2` these gates ran against in the
version string and in three pieces of display text, reworded after the run for accuracy: one partition note and two
Post-Event Summary lessons. No question ID, choice ID, title, description or risk rule changed. The release files
themselves were also imported as new lenses and published (see
[Release file import](#release-file-import)).

The re-run used the WA Tool API with AWS CLI v2, in the same non-production sandbox account, in us-east-1. Console
rendering, Jira and AWS GovCloud (US) were not covered. Every workload and lens created for the re-run was deleted
afterwards, and the account was confirmed empty (no workloads, custom lenses, review templates, profiles or share
invitations).

| Gate | Candidate | Date | Region | Result |
|---|---|---|---|---|
| G2 | `2.0.0rc2` over a lens created from v1.3.6 | 2026-10-06 | us-east-1 | documented, same as the early pass. On kept IDs, selections are cleared and notes, "does not apply" and its `Reason` carry over. The upgrade milestone holds the full v1.3.6 answers. Retired IDs leave the current review. `architecture_health_checks` is gone and `architecture_health_lifecycle` is Unanswered |
| G5 | `2.0.0rc2` and `1.0.0rc2` | 2026-10-06 | us-east-1 | pass. v1.3.6 imports as-is and `CreateLensVersion` 1.3.6 succeeds. The core candidate imports over the v1.3.6 lens and as a new lens, the event candidate imports as a new lens, and `CreateLensVersion` succeeds each time. `ImportLens` returned only `LensArn`; every import appeared under `ListLenses` with `LensStatus=DRAFT` on the first call |
| G8 | `2.0.0rc2` published as a major version | 2026-10-06 | us-east-1 | pass. `ImportLens` over the v1.3.6 lens and `CreateLensVersion` `2.0.0rc2` with `IsMajorVersion` succeeded. After `UpgradeLensReview`, the review lists four pillars, including the new `04 - Readiness Decision` (`readiness_signoff`, Unanswered), and the lens name is unchanged (`AWS Operational Readiness Review`) |

### G2 and G8 on the final candidate

Method, as in the early pass: v1.3.6 imported unchanged and published as `1.3.6`; a workload on that lens; answers
on eight v1.3.6 questions; a milestone; `ImportLens` with `LensAlias` set to the existing lens and the
`2.0.0rc2` file; `CreateLensVersion` `2.0.0rc2` with `IsMajorVersion`; `UpgradeLensReview` with a
`MilestoneName`; then `GetAnswer` on the current review and on the upgrade milestone for every question touched,
plus three new IDs. The v1.3.6 answers:

| Question ID | Kept or retired | v1.3.6 answer |
|---|---|---|
| `well_architected` | kept | Two selections, `IsApplicable=false`, Reason `OUT_OF_SCOPE` |
| `event_gameday` | kept | One selection, `IsApplicable=false`, Reason `BUSINESS_PRIORITIES` |
| `event_alarms` | kept | Two selections and notes |
| `architecture_rpo_rto` | kept | Two selections and notes |
| `releases_deployment_rollback`, `architecture_defensive_throttling` | kept | Selections only |
| `architecture_health_checks` | retired | One selection and notes |
| `releases_onebox_deployments` | retired | One selection |

Results after the upgrade:

| Field on a kept question ID | Current review | Upgrade milestone |
|---|---|---|
| `SelectedChoices` | Cleared (all choice IDs are new) | The v1.3.6 selections |
| `Notes` | Carried over verbatim (`event_alarms`, `architecture_rpo_rto`) | The v1.3.6 notes |
| `IsApplicable` and `Reason` | `false` with `OUT_OF_SCOPE` and `BUSINESS_PRIORITIES` carried over | Same |
| `Risk` | Not applicable for the two questions marked "does not apply"; Unanswered for the others | The v1.3.6 risks |

Other observations:

- Before the upgrade, the workload's lens review showed `LensStatus` `NOT_CURRENT` on version 1.3.6; after it,
  `CURRENT` on `2.0.0rc2`. The lens name stayed `AWS Operational Readiness Review`.
- The current review has 36 questions in four pillars: 34 Unanswered and 2 Not applicable. The pillars are
  `01 - Architecture` (14 questions), `02 - Release Quality` (5), `03 - Event Management` (16) and
  `04 - Readiness Decision` (1). `ListLensReviewImprovements` returned no items, because no question had a
  selection.
- `architecture_health_checks` and `releases_onebox_deployments` are absent from `ListAnswers`, and `GetAnswer`
  returns a validation error ("No question with ID ... was found"). Their selections and notes remain in the
  upgrade milestone.
- `architecture_health_lifecycle`, `releases_phased_rollout` and `readiness_signoff` are present and Unanswered,
  with no notes and no "does not apply" flag carried from the retired questions. They are not in the upgrade
  milestone.
- The event candidate `1.0.0rc2` was then added to the same workload: its review listed 8 Unanswered questions in
  three pillars (`01 - Prepare`, `02 - Operate`, `03 - After the event`).

### A second lens with the same name is rejected

While the upgraded lens existed, importing `2.0.0rc2` again as a new lens in the same account and Region was
rejected: "A lens with normalized name awsoperationalreadinessreview already exists." So 2.0.0 cannot be added as
a second lens next to an existing lens that has the published name; the supported path is to import 2.0.0 into
the existing lens, as `MIGRATION.md` describes. For the fresh-import tests, the earlier lens was deleted first.

### Release file import

After the gate lenses were deleted, `orr-core-2.0.0.json` and `orr-event-1.0.0.json`, byte for byte the release
files, were each imported as a new lens. Each appeared under `ListLenses` with `LensStatus=DRAFT` on the first call,
and `CreateLensVersion` `2.0.0` and `1.0.0` succeeded. A workload with both lenses listed 36 Unanswered questions in
four pillars (core) and 8 Unanswered questions in three pillars (event), and selecting "None of these" on
`well_architected` scored High. The workload and both lenses were then deleted.

The three display-text rewordings described above were made after that run, so the files were imported once more,
byte for byte the released `orr-core-2.0.0.json` and `orr-event-1.0.0.json`: each appeared under `ListLenses` with
`LensStatus=DRAFT` on the first call, `CreateLensVersion` `2.0.0` and `1.0.0` succeeded, `GetLens` returned the
expected lens names, and both lenses were deleted. The sandbox account held no workloads, custom lenses, review
templates, profiles or share invitations before or after that run.

After that second import, the same partition note (statement `dem_capacity_ready`) was reworded once more, to
record that the AWS Auto Scaling scaling plans API is offered in AWS GovCloud (US) while predictive scaling in
scaling plans and the `AWS::AutoScalingPlans::ScalingPlan` CloudFormation resource are not. It is still
one of the three rewordings above, and it changes only a choice helpful-resource display text, a field that G4
showed accepts every character tested, within the 1,024-character limit the lens keeps.

## Patch release check, 2026-10-09 (core 2.0.1, event 1.0.1, genai 1.0.1)

The patch releases change only display text (see `CHANGELOG.md`), so the gate checked the upgrade path that a patch
uses: a minor version published over an existing lens. The check ran through the WA Tool API with AWS CLI v2 in the
same non-production sandbox account, in us-east-1.

1. The released `orr-core-2.0.0`, `orr-event-1.0.0` and `orr-genai-1.0.0` files were imported as new lenses and
   published (`CreateLensVersion` 2.0.0, 1.0.0 and 1.0.0).
2. A workload with all three lenses and the AWS Well-Architected Framework lens was defined, and four questions
   were answered: one selected choice with notes on `architecture_edge_protection`, `evt_ddos_response` and
   `gai_capacity_quotas`, and `readiness_signoff` marked "does not apply" with reason `OTHER` and notes.
3. The 2.0.1 and 1.0.1 files were imported over each lens (`ImportLens` with `LensAlias`), each appeared as a
   newer `DRAFT` under `ListLenses`, and `CreateLensVersion` succeeded with `IsMajorVersion=false`.

| Check | Result |
|---|---|
| Lens version on the workload (`GetLensReview`) | Moved to 2.0.1, 1.0.1 and 1.0.1 without an upgrade step |
| Notifications for the workload (`ListNotifications`) | None. The console showed no **Lens version not current** banner and no **Question upgraded** labels |
| Selected choices, notes, risk, "does not apply" flag and reason (`GetAnswer`) | Unchanged on all four questions |
| Lens risk counts (`GetLensReview`) | Unchanged on all three lenses |
| Question description | Shows `Category: Defense against overload` |
| `ExportLens` of each new version | Equal to the built file, apart from the `number` fields the WA Tool adds to questions and choices |
| Positive control: the same genai file published once more as a major version | `ListNotifications` returned `LENS_VERSION_UPGRADED` (version in use 1.0.1), and the workload stayed on 1.0.1 until upgraded |

The released files were then imported as new lenses (first install): each appeared as `DRAFT`, `CreateLensVersion`
2.0.1, 1.0.1 and 1.0.1 succeeded, `GetLens` returned the published names, and a new workload listed 36, 8 and 9
Unanswered questions in four, three and three pillars.

The two question screenshots under `_img/` that show changed text (`WAT-Question.png` and
`WAT-GenAIQuestion.png`) were retaken from the 2.0.1 and 1.0.1 lenses in a freshly defined workload. Version
names accept only letters, digits, `_` and `.` (`CreateLensVersion` rejected a hyphen). Everything
created for the run was deleted afterwards; the account held no workloads, custom lenses, review templates,
profiles or share invitations.

## Details of the 2026-10-06 run

### G1: "None of these" exclusivity

Question `architecture_defensive_throttling` in the gate candidate (No risk needs all four statements, Medium
needs the first two, otherwise High):

| `SelectedChoices` sent | Stored as sent? | Risk |
|---|---|---|
| `none_no` | yes | High |
| `none_no` plus one statement | yes | High |
| `none_no` plus the two Medium statements | yes | Medium |
| `none_no` plus all four statements (either order) | yes | No risk |
| All four statements through `ChoiceUpdates`, plus `none_no` | yes | No risk |

The API neither rejects nor normalizes the combination, and the rules ignore `none_no`.

Console, checked later on 2026-10-06 in us-east-1 with the 2.0.0 core lens: on the same question, ticking
one statement and then **None of these** greys out (disables) the other statement checkboxes, but the statement
already ticked stays ticked. **Save and exit** stores both choices, and the question scores High.
The console therefore blocks new selections once **None of these** is ticked but does not clear earlier ones.

### G2 and G8: upgrade from v1.3.6 to the candidate

Method: a workload on v1.3.6; answers on several questions; `IsApplicable=false` with Reason `OUT_OF_SCOPE` on
`architecture_health_checks` and `event_gameday`; notes on `well_architected` and `event_alarms`; a milestone;
`ImportLens` with `LensAlias` set to the existing lens; `CreateLensVersion` `2.0.0rc0` with `IsMajorVersion`;
`UpgradeLensReview` with a `MilestoneName`; then `GetAnswer` on the current review and on the upgrade milestone.

| Field on a kept question ID | After the upgrade |
|---|---|
| `SelectedChoices` | Cleared (all choice IDs are new). Answered questions show as Unanswered |
| `Notes` | Carried over verbatim |
| `IsApplicable` | `false` carried over |
| `Reason` | Carried over (`OUT_OF_SCOPE`) |
| `Risk` | Unanswered for answered questions; Not applicable for questions marked "does not apply" |

Other observations:

- Before the upgrade, the workload's lens review showed `LensStatus` `NOT_CURRENT`; after it, `CURRENT`.
- The milestone created by `UpgradeLensReview` holds the v1.3.6 answers, including selections, notes, "does not
  apply" flags and risks. New question IDs are not in that milestone.
- Retired question IDs are gone from the current review: `GetAnswer` returns a validation error ("No question with
  ID ... was found"), and they are absent from `ListAnswers`. Their answers and notes remain in the milestone.
- New question IDs, including the new pillar's question, are present and Unanswered.
- Lens rename: rejected (see G8 in the table). The lens kept its published name after the upgrade.
- Separately (G9 workload): setting `IsApplicable` back to `true` restores the earlier risk at once, because
  selections are kept while a question is marked "does not apply", and the stored `Reason` is not cleared.

### G3: choice-level not-applicable status

Method: `UpdateAnswer` with `ChoiceUpdates`, marking statements `NOT_APPLICABLE` with Reason `OUT_OF_SCOPE`, on
questions with `&&` rules and with `||` rules. Repeated calls gave the same result.

| Case | Risk |
|---|---|
| Three statements selected, the fourth not applicable (No risk needs all four) | No risk |
| First Medium statement selected, second Medium statement not applicable | Medium |
| All four statements not applicable, nothing selected | No risk |
| One statement not applicable, nothing selected | High |
| Scope statement in an `\|\|` alternative not applicable, core statement selected | Medium (the alternative is not satisfied) |
| `\|\|` Medium term not applicable, nothing selected | High |

Also: `Reason` is optional for a not-applicable statement (stored as `NONE`), and `none_no` cannot be marked not
applicable (validation error).

### G4: long text, limits and rendering

| Field | Accepted at import | Rejected at import | `GetAnswer` read-back |
|---|---|---|---|
| Question description | 1,030 and 2,048 | 2,049 | Full text, not truncated |
| Question helpful display text | 70 and 2,048 | 2,049 | Full text, not truncated |
| Choice helpful and improvement display text | 1,100 and 2,048 | 2,049 | Full text, not truncated |
| Additional resource display text | 1,100 | not tested | Full text, not truncated |
| Question and choice titles | 128 | 129 | not tested |

The API reference documents lower maxima for some `Answer` fields (1,024 for question descriptions, 64 for
question helpful display text), but the service returned longer values. The PDF lens review report shows question
titles, selected and not selected choices, and the full improvement-plan and additional-resource text, but not
question descriptions or question helpful text.

**Character set (found while running G5).** `ImportLens` rejects these fields if they contain any character
other than letters, digits, space, line break, and `- _ . , : / ( ) @ ! & # + ' ?` (the service also allows the
right single quotation mark, which this lens never uses because its text is plain ASCII):

- lens name and lens description;
- pillar names;
- question titles and question descriptions;
- choice titles.

For example, `;`, `%`, `<`, `>`, `=`, `*`, `"`, `[`, `]`, `$`, `|`, `~`, `{` and `}` are all rejected in those
fields. Helpful-resource, improvement-plan and additional-resource display texts accepted every character tested.
The error message lists the allowed characters without `?`, but `?` is accepted. The lens format specification
does not describe this restriction.

### G5: import and completion

- v1.3.6 imported unchanged, even though `releases_manual_changes` has no `default` rule. An empty selection on
  that question shows as Unanswered, and its other choices score as before.
- `ImportLens` returned only `LensArn`; the raw response body had no `Status` field. The draft appeared in
  `ListLenses` with `LensStatus=DRAFT` (and `ALL`) on the first call, and not under `PUBLISHED`.
- `CreateLensVersion` succeeded for `1.3.6` and for `2.0.0rc0` with `IsMajorVersion`.
- The candidate was first rejected for a `;` in the lens description, then for a `;` in a question description.
  After `;` was removed from the restricted fields, it imported over the published lens, keeping that lens's name,
  and also imported as separate new lenses (the G4 variants).

### G6: review templates

A template on v1.3.6 was pre-filled with selections and notes on `well_architected`, a selection on
`event_alarms`, "does not apply" on `architecture_health_checks`, and a selection and notes on a retired question.
After the candidate was published as a major version, the template showed `UpdateStatus` `LENS_NOT_CURRENT`.
After `UpgradeReviewTemplateLensReview`:

- the template's lens became current and listed all four pillars;
- on kept IDs, selections were cleared and notes were kept, as were "does not apply" and its reason (that question
  counts as answered in the template);
- the retired question was gone.

This matches the workload behavior in G2.

### G9: "does not apply" and risk counts

On a v1.3.6 workload with two High and two Medium answers, one High and one Medium question were then marked "does
not apply":

| View | Before | After |
|---|---|---|
| `GetLensReview` (lens and pillar) | High 2, Medium 2, Not applicable 0 | High 1, Medium 1, Not applicable 2 |
| `GetWorkload` risk counts | High 2, Medium 2 | High 1, Medium 1, Not applicable 2 |
| `GetConsolidatedReport` (JSON), workload totals | High 2, Medium 2 | High 1, Medium 1, Not applicable 2 |
| `ListLensReviewImprovements` | not captured before | Only the remaining High and Medium questions |

Workloads created through the API also get the AWS Well-Architected Framework lens, so workload-level counts
combine both lenses. The JSON consolidated report's per-lens breakdown listed only the Framework lens, not the
custom lens. Use `GetLensReview` or `ListLensReviewImprovements` per workload for ORR-only counts.

Related documents: [scoring.md](scoring.md) (how not-applicable answers and "None of these" score),
[decisions.md](decisions.md) (decisions confirmed after G2 and G8) and `MIGRATION.md` (upgrade steps).

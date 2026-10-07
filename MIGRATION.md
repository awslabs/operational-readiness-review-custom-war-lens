# Migrating from v1.3.x to Operational Readiness Review (ORR) core lens 2.0.0

This guide moves an existing ORR custom lens, and the workloads that use it, from v1.3.x (usually v1.3.6) to core
lens 2.0.0. The ORR - Mission-Critical Event Readiness companion is a new lens: install it with the first-install
steps in the [README](README.md#first-install).

What to expect:

- 2.0.0 is published as a **major version of the same lens**. Workloads that use the lens are notified and each
  owner upgrades when ready. Nothing changes in a workload until its owner upgrades it.
- **Every choice ID is new**, so v1.3.6 selections do not carry over. Re-answering is intentional: v1.3.6 could not
  reach High on 22 questions and scored "None of these" as Medium on 23 (see
  [Known scoring limitations of v1.3.x](README.md#known-scoring-limitations-of-v13x)), so its selections are not
  reliable evidence, and new IDs stop stale answers from silently scoring No risk.
- **A workload upgrade cannot be undone.** The WA Tool saves a milestone first, and that milestone keeps every
  v1.3.6 answer and note.
- **The lens keeps its name.** The core lens is still named "AWS Operational Readiness Review": the WA Tool rejects
  an upload whose name differs from the published lens name, so do not rename it when you upload 2.0.0. If your
  published lens has a different name (for example because it was imported from the v1.3.3 or v1.3.4 file, whose
  name carries the version), edit the `name` field of the 2.0.0 file to match it first; see
  [Before upgrading](#before-upgrading), step 1.

| v1.3.6 content | After the workload upgrade to 2.0.0 |
|---|---|
| 20 kept question IDs | Present, but unanswered, because all choice IDs are new. AWS documents that answers to existing questions are retained ([Lens upgrades](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lens-upgrades.html)). In our sandbox test (2026-10-06, [`docs/gates.md`](docs/gates.md)), notes carried over word for word, and a question-level "does not apply" flag carried over with its reason, so the question stayed out of the risk counts. Re-confirm each one (see [After upgrading](#after-upgrading)) |
| 32 merged, split or renamed question IDs | Gone from the current review. Their answers and notes survive only in the milestone the upgrade saved |
| 16 new core question IDs | Unanswered |

Two v1.3.6 question IDs were replaced because their meaning broadened, so that a "does not apply" flag set in
v1.3.6 cannot silently exclude a High question from the risk counts: `releases_onebox_deployments`
("One Box EC2 Deployments") became `releases_phased_rollout` (from EC2 to every platform), and
`architecture_health_checks` ("Health Checks") became `architecture_health_lifecycle` (from load balancer and DNS
checks to health checks and the capacity lifecycle on all compute). Both old IDs are retired. The four misspelled
question IDs
(`architecture_plane_redundency`, `architecture_gradeful_recovery`, `architecture_mulitaccount_stragy`,
`architecture_mutliaccount_credentials`) are retired and never reused.

Contents:
- [Before upgrading](#before-upgrading)
- [Upgrade the lens](#upgrade-the-lens)
- [Upgrade each workload](#upgrade-each-workload)
- [After upgrading](#after-upgrading)
- [Question mapping from v1.3.6](#question-mapping-from-v136)
- [FAQ](#faq)

---

## Before upgrading

1. **Find the lens, and note its name.** Note its ARN, current version and `LensName`. If the lens was shared with
   you, its owner upgrades the lens; you upgrade your workloads after the owner publishes 2.0.0.

   If the name is not exactly `AWS Operational Readiness Review`, edit the `name` field of
   `orr-core-2.0.0.json` to match your published name exactly before you upload it: a lens first imported from the
   v1.3.3 or v1.3.4 file is named `AWS Operational Readiness Review v1.3.3` or `AWS Operational Readiness Review
   v1.3.4`, and the WA Tool rejects an upload whose name differs from the published name (sandbox gate G8). Verify
   the checksum against `SHA256SUMS` before you edit the file; the edited file no longer matches it. Do not use
   **Create custom lens** to work around a name mismatch.

   ```bash
   aws wellarchitected list-lenses --lens-type CUSTOM_SELF \
     --query "LensSummaries[].[LensName,LensVersion,LensStatus,LensArn]" --output table
   LENS_ARN=arn:aws:wellarchitected:<region>:<account-id>:lens/<lens-id>
   ```

   The commands below also use `$WORKLOAD_ID` and `$TEMPLATE_ARN`. List the workloads and review templates in the
   account and Region and set them per workload or template as you work through the steps:

   ```bash
   aws wellarchitected list-workloads --query "WorkloadSummaries[].[WorkloadName,WorkloadId]" --output table
   WORKLOAD_ID=<id>
   aws wellarchitected list-review-templates \
     --query "ReviewTemplates[].[TemplateName,TemplateArn]" --output table
   TEMPLATE_ARN=<arn>
   ```

   In the console, the **Notifications** page lists both the workloads and the review templates whose lens is not
   current.

2. **If you modified this lens** (for example in an ORR workshop), export it and diff it against the published
   v1.3.6 file before you do anything else. Uploading 2.0.0 into the same lens replaces its content, so your own
   questions would be lost. Move them into a separate add-on lens attached to the same workloads
   ([`docs/customizing.md`](docs/customizing.md)).

   ```bash
   aws wellarchitected export-lens --lens-alias "$LENS_ARN" --query LensJSON --output text > orr-current.json
   python3 -m json.tool --sort-keys orr-current.json > a.json
   python3 -m json.tool --sort-keys wafr-operational-readiness-lens/orr-v1.3.6-PUBLISHED.json > b.json
   diff a.json b.json
   ```

3. **Save the current state of each workload.** Generate the lens report for the record (console: the workload's
   lens review, **Generate report**; API: `GetLensReviewReport`) and confirm that a recent milestone exists. The
   workload upgrade saves one more milestone automatically.

   ```bash
   aws wellarchitected get-lens-review-report --workload-id "$WORKLOAD_ID" --lens-alias "$LENS_ARN" \
     --query LensReviewReport.Base64String --output text | base64 --decode > orr-v1.3.6-report.pdf
   aws wellarchitected list-milestones --workload-id "$WORKLOAD_ID"
   ```

4. **List review templates** that include the lens. You upgrade them after the lens (see
   [After upgrading](#after-upgrading)). In the console, the **Notifications** page lists the review templates
   whose lens is not current.

   ```bash
   aws wellarchitected list-review-templates \
     --query "ReviewTemplates[].[TemplateName,TemplateArn]" --output table
   ```

5. **Download 2.0.0** from [GitHub Releases](https://github.com/awslabs/operational-readiness-review-custom-war-lens/releases)
   and verify it against `SHA256SUMS`. If you cannot use the release page, the same files are in
   [`wafr-operational-readiness-lens/`](wafr-operational-readiness-lens/README.md) with their checksums in
   [`dist/SHA256SUMS`](dist/SHA256SUMS).

---

## Upgrade the lens

### Console

1. Sign in to the AWS Management Console, open the AWS Well-Architected Tool console, and choose **Custom lenses**.
2. Select your existing ORR lens and choose **Edit**.
3. Choose **Choose file**, select `orr-core-2.0.0.json` (or `orr-core.json`), and choose **Submit** (or
   **Submit & Preview**). The lens shows in **DRAFT** status.
4. Select the lens again and choose **Publish lens**.
5. On the publish page, check the lens name, the pillar names and the **Updated questions**, **Removed questions**
   and **New questions** lists per changed pillar.
6. Under **Versioning**, for **Version change** choose **Major version** ("Will notify workloads using the lens"),
   enter `2.0.0` in **Version name**, and choose **Publish custom lens**.

Never use **Create custom lens** to upgrade. It creates a second lens with a new ARN, uses one of the 15 custom-lens
slots per account per Region, and existing workloads get no upgrade notice; their answers and notes stay with the
old lens. The service also rejects a second custom lens with the same name in the same account and Region (sandbox
gate run, 2026-10-06), so **Create custom lens** cannot be used to upgrade anyway. Reference:
[Publishing an update to a custom lens](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-publish-update.html).

### API (AWS CLI v2)

1. Import the new content into the existing lens. The API reference lists a `Status` field in the response, but
   in our sandbox test (2026-10-06) `ImportLens` returned only `LensArn`, so do not depend on `Status`. If the call
   fails with a validation error, read the message: it names the field and the characters or length it rejects.

   ```bash
   aws wellarchitected import-lens --lens-alias "$LENS_ARN" --json-string file://orr-core-2.0.0.json
   ```

2. Poll `ListLenses` until the lens ARN appears as a draft with a newer `UpdatedAt`. (`GetLens` has no import
   status field.)

   ```bash
   aws wellarchitected list-lenses --lens-type CUSTOM_SELF --lens-status DRAFT \
     --query "LensSummaries[?LensArn=='$LENS_ARN'].[LensArn,UpdatedAt]"
   ```

3. Publish the draft as a major version.

   ```bash
   aws wellarchitected create-lens-version --lens-alias "$LENS_ARN" --lens-version 2.0.0 --is-major-version
   ```

API references: [ImportLens](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_ImportLens.html),
[ListLenses](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_ListLenses.html),
[CreateLensVersion](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_CreateLensVersion.html).

Repeat these steps in every account and Region where you imported the lens. If you share the lens, check its
shares after the upgrade (step 5 of [After upgrading](#after-upgrading)).

---

## Upgrade each workload

### Console

1. On the **Notifications** page, select the workload and choose **Upgrade lens version** (or choose **View
   available upgrades** on the workload's **Overview** tab).
2. Enter a milestone name, for example `ORR-2026-10-pre-v2-upgrade`. The WA Tool saves this milestone before it
   upgrades.
3. Select **I understand and accept these changes** and choose **Save**.

### API (AWS CLI v2)

```bash
aws wellarchitected upgrade-lens-review --workload-id "$WORKLOAD_ID" --lens-alias "$LENS_ARN" \
  --milestone-name ORR-2026-10-pre-v2-upgrade
```

`UpgradeLensReview` requires a milestone name, saves that milestone first, and cannot be undone. Reference:
[Upgrading a lens](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-upgrading.html) and
[UpgradeLensReview](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_UpgradeLensReview.html).

---

## After upgrading

1. **Re-answer every question**, using the [mapping](#question-mapping-from-v136) to find where each v1.3.6 topic
   now lives. Answer `readiness_signoff` last. A launch go or no-go needs the full core, with every question
   answered or marked not applicable with a reason; the 15-question core path is for triage and recurring
   check-ins.

2. **Re-confirm every question that carried over a "does not apply" flag or notes.** These can only appear on the
   20 kept question IDs. For each one:
   - decide again whether the question applies, using its 2.0.0 description and its "Out of scope if" line, and
     either clear the flag or keep it with a current reason;
   - mark each carried note as history by starting it with `v1.3.6 note (not v2 evidence):`, or delete it. Carried
     notes arrive word for word, with no prefix, and describe answers to v1.3.6 choices, not evidence for 2.0.0
     statements;
   - if you set "does not apply" back to applicable, also replace the carried reason: in our sandbox test, setting
     `IsApplicable` back to `true` did not clear the stored `Reason`.

   Give priority to these kept questions, whose scope or maximum risk grew in 2.0.0, so a v1.3.6 "does not apply"
   flag is most likely to be wrong: `event_expiring_materials` (now every expiring material, and High-capped),
   `event_gameday` and `event_transaction_tracing` (Medium-capped in v1.3.6, High-capped in 2.0.0). The health
   check question is not in this list because it has a new ID, `architecture_health_lifecycle`, so no v1.3.6 flag
   carries into it.

   ```bash
   aws wellarchitected get-answer --workload-id "$WORKLOAD_ID" --lens-alias "$LENS_ARN" \
     --question-id event_expiring_materials --query "Answer.[IsApplicable,Reason,Notes]"
   ```

3. **Compare with the old milestone.** Find the milestone number, then read any v1.3.6 question as it was, including
   questions that no longer exist in the current review:

   ```bash
   aws wellarchitected list-milestones --workload-id "$WORKLOAD_ID" \
     --query "MilestoneSummaries[].[MilestoneNumber,MilestoneName]" --output table
   aws wellarchitected get-answer --workload-id "$WORKLOAD_ID" --lens-alias "$LENS_ARN" \
     --question-id architecture_certificates --milestone-number <n> \
     --query "Answer.[QuestionTitle,SelectedChoices,Notes,Risk]"
   ```

   In the console, open the workload's **Milestones** tab. A question ID that is no longer in the lens returns a
   validation error ("No question with ID ... was found") on the current review; read it from the milestone.

4. **Carry accepted risks forward with the `EXC:` convention.** For each High you accept in 2.0.0, record only
   `EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>` in the question notes, for example
   `EXC:RR-0142 exp:2027-03-31 role:business-owner`. Keep the approver's name, the reason and the compensating
   controls in your risk register or plan of action and milestones (POA&M). An acceptance recorded against a
   v1.3.6 question does not transfer automatically: re-assess it against the 2.0.0 question that absorbed the
   topic.

5. **Upgrade each review template that includes the lens, then check its shares.** Upgrade the template before you
   create any workload from it: on the **Notifications** page select the template and choose **Upgrade lens
   version**, select the confirmation box next to **I understand and accept these changes**, then choose **Upgrade
   and edit template answers** or **Upgrade**; or call
   `UpgradeReviewTemplateLensReview`. Pre-filled selections are cleared, because the choice IDs are new, so set
   them again; pre-fill only platform-provided controls that come with evidence. In our sandbox test, template
   notes and "does not apply" flags with their reasons on kept question IDs were kept (and such a question counts
   as answered), while pre-filled answers on retired question IDs were dropped. Review the carried notes and flags
   before you create workloads from the template.

   ```bash
   aws wellarchitected upgrade-review-template-lens-review --template-arn "$TEMPLATE_ARN" --lens-alias "$LENS_ARN"
   ```

   Then confirm that the lens and template shares still reach the intended OUs and accounts, and re-send any
   account or user invitation that expired: invitations that are not accepted within seven days expire
   ([Sharing a custom lens](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-sharing.html)).

6. **Save a milestone** when the 2.0.0 review is complete, for example `ORR-2026-10-launch` or
   `ORR-2026-10-recurring`.

---

## Question mapping from v1.3.6

Each v1.3.6 question appears exactly once below. Dispositions: **Keep** (the ID stays and its content is
rewritten), **Merge** (its content moves into one 2.0.0 question), **Split** (its content is divided across
several 2.0.0 questions). No v1.3.6 topic is dropped. This block is generated from the ID registry; do not edit it
by hand.

<!-- BEGIN GENERATED MAPPING -->
| v1.3.6 question | v1.3.6 title | Disposition | v2 question(s) |
|---|---|---|---|
| `well_architected` | AWS Well-Architected Framework Review (H) | keep | `well_architected` Current Well-Architected review with high risks dispositioned |
| `architecture_architecture_diagram` | Architecture Diagram (H) | merge | `architecture_failure_models` System model: diagrams, critical journeys and failure modes |
| `architecture_services_used` | AWS Services Used (H) | merge | `underlying_dependencies` Dependency inventory, classification and partition availability |
| `architecture_api_matrix` | Impacted API Matrix (H) | merge | `architecture_failure_models` System model: diagrams, critical journeys and failure modes |
| `architecture_failure_models` | Failure Models (H) | keep | `architecture_failure_models` System model: diagrams, critical journeys and failure modes |
| `architecture_plane_redundency` | Control & Data Plane Redundency (H) | split | `architecture_recovery_dependencies` Regional isolation and data-plane-only recovery; `architecture_rpo_rto` Recovery objectives and proven recovery; `event_resilience_recoveries` Survive the loss of one Availability Zone without scaling |
| `architecture_retry_timeouts` | Retries & Socket Timeouts (H) | keep | `architecture_retry_timeouts` Timeouts, bounded retries and idempotency |
| `architecture_health_checks` | Health Checks (H) | merge | `architecture_health_lifecycle` Health checks and safe capacity lifecycle |
| `architecture_failure_testing` | Failure Testing (H) | split | `architecture_dependency_failure_handling` Core journeys keep working when dependencies fail; `architecture_rpo_rto` Recovery objectives and proven recovery; `event_resilience_recoveries` Survive the loss of one Availability Zone without scaling; `event_gameday` Incident exercises: game days, tabletops and recovery drills |
| `architecture_demand_estimates` | Demand Estimations (H) | keep | `architecture_demand_estimates` Peak demand, quotas and capacity headroom |
| `architecture_load_testing` | Load & Penetration Testing (H) | keep (part moved) | `architecture_load_testing` Load testing to peak margin and breaking point; `releases_security_readiness` Security launch gate: testing, detection and incident readiness |
| `architecture_defensive_throttling` | Defensive Throttling (H) | keep (part moved) | `architecture_defensive_throttling` Overload protection and tenant fairness; `architecture_edge_protection` Edge and DDoS baseline for internet-facing endpoints |
| `architecture_data_corruption` | Data Corruption Recovery (H) | keep | `architecture_data_corruption` Recovery from corruption, deletion and ransomware |
| `architecture_rpo_rto` | Recovery Objectives (M) | keep | `architecture_rpo_rto` Recovery objectives and proven recovery |
| `architecture_gradeful_recovery` | Graceful Recovery (H) | merge | `architecture_dependency_failure_handling` Core journeys keep working when dependencies fail |
| `architecture_dependency_retry` | Dependency Retry/Backoff (M) | merge | `architecture_retry_timeouts` Timeouts, bounded retries and idempotency |
| `architecture_mulitaccount_stragy` | Multi-account Strategy (M) | merge | `architecture_recovery_dependencies` Regional isolation and data-plane-only recovery |
| `architecture_mutliaccount_credentials` | Multi-account Credentials (M) | merge | `event_mutating_access` Production access: read-only by default, time-bound elevation |
| `architecture_shared_resources_redundancy` | Resources shared across regions (M) | merge | `architecture_recovery_dependencies` Regional isolation and data-plane-only recovery |
| `architecture_certificates` | Software Certificates (H) | merge | `event_expiring_materials` Certificates, credentials and other expiring materials |
| `releases_manual_changes` | Manual Changes (H) | keep | `releases_manual_changes` Changes only through reviewed pipelines and IaC, including emergencies |
| `releases_deployment` | Deployment Mechanisms (H) | split | `architecture_health_lifecycle` Health checks and safe capacity lifecycle; `releases_phased_rollout` Phased production rollout with automated stage gates |
| `releases_change_management` | Change Management (H) | merge | `releases_manual_changes` Changes only through reviewed pipelines and IaC, including emergencies |
| `releases_canaries` | Deployment Canaries (H) | split | `releases_deployment_rollback` Automatic rollback and rollback safety; `event_canary_alarms` Independent outside-in monitoring of critical journeys |
| `releases_staged_deployments` | Staged Deployments (M) | keep | `releases_staged_deployments` Pre-production parity and automated test gates |
| `releases_onebox_deployments` | One Box EC2 Deployments (M) | merge | `releases_phased_rollout` Phased production rollout with automated stage gates |
| `releases_deployment_rollback` | Automated Deployment Rollback (H) | keep | `releases_deployment_rollback` Automatic rollback and rollback safety |
| `releases_deployment_gating` | EC2 Deployment Gating (M) | merge | `releases_phased_rollout` Phased production rollout with automated stage gates |
| `releases_performance_impact` | Performance Impact (M) | split | `releases_staged_deployments` Pre-production parity and automated test gates; `releases_deployment_rollback` Automatic rollback and rollback safety; `event_transaction_tracing` Request correlation, tracing and automated diagnostics |
| `releases_validation` | EC2 Deployment Validation (M) | merge | `architecture_health_lifecycle` Health checks and safe capacity lifecycle |
| `releases_canary_errors` | Independent Canary Errors (M) | merge | `event_canary_alarms` Independent outside-in monitoring of critical journeys |
| `releases_traffic_draining` | Traffic Draining (M) | merge | `architecture_health_lifecycle` Health checks and safe capacity lifecycle |
| `releases_custom_amis` | Custom AMIs (M) | split | `architecture_cold_start` Restart and scale out while dependencies are impaired; `releases_staged_deployments` Pre-production parity and automated test gates |
| `automation_of_test_coverage` | Test Coverage (H) | merge | `releases_staged_deployments` Pre-production parity and automated test gates |
| `underlying_dependencies` | Underlying Dependencies (H) | keep | `underlying_dependencies` Dependency inventory, classification and partition availability |
| `event_kpis` | Operational KPIs (H) | merge | `event_alarms` Customer-experience SLOs and alarms that fire before breach |
| `event_oncall_rotation` | On-call Rotation (H) | keep | `event_oncall_rotation` On-call paging, runbooks and escalation |
| `event_alarms` | Alarms & Runbooks (H) | keep (part moved) | `event_alarms` Customer-experience SLOs and alarms that fire before breach; `event_oncall_rotation` On-call paging, runbooks and escalation |
| `event_canary_alarms` | Independent Canary Alarms (H) | keep | `event_canary_alarms` Independent outside-in monitoring of critical journeys |
| `event_automated_data_gathering` | Automated Data Gathering (M) | merge | `event_transaction_tracing` Request correlation, tracing and automated diagnostics |
| `event_host_fs_alarms` | On-host Filesystem Alarms (H) | merge | `event_saturation_alarms` Saturation, dependency health, backlog and usage alarms |
| `event_database_alarms` | Database Alarms (H) | merge | `event_saturation_alarms` Saturation, dependency health, backlog and usage alarms |
| `event_jvm_metrics` | JVM Metrics & Alarms (M) | merge | `event_saturation_alarms` Saturation, dependency health, backlog and usage alarms |
| `event_frontend_alarms` | Frontend Alarms (M) | split | `event_alarms` Customer-experience SLOs and alarms that fire before breach; `event_canary_alarms` Independent outside-in monitoring of critical journeys |
| `event_delayed_consistency` | Delayed Consistency Alarms (M) | merge | `event_saturation_alarms` Saturation, dependency health, backlog and usage alarms |
| `event_transaction_tracing` | Transaction Tracing (M) | keep | `event_transaction_tracing` Request correlation, tracing and automated diagnostics |
| `event_mutating_access` | Mutating Access (H) | keep | `event_mutating_access` Production access: read-only by default, time-bound elevation |
| `event_queue_backlog` | Queue Backlog (M) | split | `architecture_defensive_throttling` Overload protection and tenant fairness; `event_saturation_alarms` Saturation, dependency health, backlog and usage alarms |
| `event_expiring_materials` | Expiring Materials (M) | keep | `event_expiring_materials` Certificates, credentials and other expiring materials |
| `event_gameday` | Event preparedness through game days (M) | keep | `event_gameday` Incident exercises: game days, tabletops and recovery drills |
| `event_resilience_recoveries` | Withstand failures & enable fast recoveries (H) | keep (part moved) | `event_resilience_recoveries` Survive the loss of one Availability Zone without scaling; `event_az_evacuation` Detect and shift away from an impaired Availability Zone |
| `event_budget_alerts` | Alarms for cost management (M) | merge | `event_saturation_alarms` Saturation, dependency health, backlog and usage alarms |

52 v1.3.6 questions: keep 20, merge 24, split 8. Dispositions are computed from the `lineage` of each v2 question: keep means the question id is unchanged (its choice ids are all new); merge means the content moved into one v2 question; split means it moved into several.
<!-- END GENERATED MAPPING -->

---

## FAQ

**Why were my selections reset?**
Every 2.0.0 choice ID is new. The v1.3.6 scoring could not reach High on 22 questions and scored "None of these" as
Medium on 23, and many 2.0.0 statements ask for different, more specific evidence. Carrying selections forward would
have mixed old answers into new scoring, so 2.0.0 asks for fresh answers.

**Where are my old answers?**
In the milestone the workload upgrade saved, and in any earlier milestones. Open the workload's **Milestones** tab,
or call `GetAnswer` or `ListAnswers` with `MilestoneNumber`. The milestone keeps the v1.3.6 answers, notes and risk
for every question, including the 32 question IDs that are no longer in the lens.

**How do I compare risk counts before and after?**
Not by totals. 2.0.0 has 36 questions instead of 52, a fourth pillar, and rebuilt scoring in which High is
reachable on every High-capped question, so expect more High results on the same workload. Compare per topic: use
the mapping to pair each 2.0.0 question with the v1.3.6 questions it absorbed, and read the old answers from the
milestone. Track the trend from the first 2.0.0 milestone onward.

**Do I have to upgrade now?**
No. A major version is not applied automatically; each workload stays on its current version until its owner
upgrades it. New workloads that add the lens after you publish 2.0.0 use 2.0.0.

**Can I keep v1.3.6 and 2.0.0 side by side?**
Yes, within the same lens: each workload stays on v1.3.6 until its owner upgrades it, and workloads that add the
lens after you publish 2.0.0 use 2.0.0. Do not import 2.0.0 as a second lens with **Create custom lens**: that
uses a second custom-lens slot, existing workloads get no upgrade notice, and their history stays split across two
lenses.

**What happened to my questions about one-box deployments, health checks, certificates, or the misspelled IDs?**
Their content moved: one-box deployments into `releases_phased_rollout`, health checks into
`architecture_health_lifecycle`, certificates into `event_expiring_materials`, and the four misspelled IDs into the
questions listed in the mapping. The old IDs are retired and never reused.

**I customized v1.3.6 in a workshop. What now?**
Export the lens before you upgrade (see [Before upgrading](#before-upgrading)), then rebuild your questions as a
separate add-on lens from [`templates/org-addon-lens.json`](templates/org-addon-lens.json) so future ORR upgrades
never touch them.

**Is any of this different in AWS GovCloud (US)?**
The lens and workload upgrade steps are the same. The Jira connector is not available there, so track improvement
items with AWS Systems Manager OpsCenter or an export. See [AWS GovCloud (US)](README.md#aws-govcloud-us).

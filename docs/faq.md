# Frequently asked questions

## About the lens

### What is this lens?

A custom lens for the AWS Well-Architected Tool that structures an Operational Readiness Review (ORR): a
repeatable review of launch-blocking operational risk, run before launch and on a recurring schedule. It is
informed by the AWS
[Operational Readiness Reviews whitepaper](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/wa-operational-readiness-reviews.html)
and Well-Architected best practice
[OPS07-BP02](https://docs.aws.amazon.com/wellarchitected/latest/framework/ops_ready_to_support_const_orr.html).
The family has a 36-question core lens and two companions: the 8-question ORR - Mission-Critical Event Readiness
lens and the 9-question ORR - Generative AI and Agents lens.

### Is this an AWS certification or an AWS review of my workload?

No. The lens is guidance. It is not an AWS certification, compliance attestation, audit or SLA. Completing it does
not mean AWS has reviewed your workload, and it does not change the AWS shared responsibility model. Numeric
targets in the lens are this lens's suggestions. The ORR is customer-run; AWS account teams or partners may
facilitate one, but the lens never assumes they will.

### How is it different from a Well-Architected Framework review?

The Framework review covers breadth across six pillars. The ORR covers launch-blocking operational risk in depth,
and you run it separately. The ORR question `well_architected` checks that a current Framework review exists and
that its high-risk issues are dispositioned, so the two are not double counted.

### How does it relate to the sample ORR lens that OPS07-BP02 links?

OPS07-BP02 links a sample ORR lens in
[aws-samples/custom-lens-wa-hub](https://github.com/aws-samples/custom-lens-wa-hub/tree/main/ORR-Lens). That
sample introduces ORRs from the whitepaper's example questions. This lens is the maintained, scored version, with
improvement plans, links, partition notes, a readiness decision and generated risk rules.

### Does the AWS Well-Architected Agent evaluate this lens?

No. As of 2026-10-06 the agent's architecture reviews support only the Well-Architected Framework lens
([Conducting architecture reviews](https://docs.aws.amazon.com/wellarchitected/latest/userguide/agent-architecture-reviews.html)).
Automated Framework checks complement an ORR; they do not replace the human evidence and judgment it needs.

### Is there a module for generative AI workloads?

Yes. ORR - Generative AI and Agents 1.0.0 (`orr-genai.json`) is for workloads that call foundation models or run
AI agents. Attach it alongside the core lens as part of the pre-launch ORR. It has 9 questions on model lifecycle
and inference routing, token quotas and capacity, incomplete output and fallback models, pinned versions for model,
prompt and guardrail changes, quality gates, telemetry coverage, safeguard enforcement, runaway token spend and
agent action bounds. See [running-an-orr.md](running-an-orr.md#generative-ai-and-agent-workloads).

### Does it replace the AWS Generative AI, Agentic AI or Responsible AI lenses?

No. It complements them, so apply them as well: the AWS Generative AI lens from the
[Lens Catalog](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lens-catalog.html), and the Agentic AI
and Responsible AI lenses from
[aws-samples/sample-well-architected-custom-lens](https://github.com/aws-samples/sample-well-architected-custom-lens).
Those lenses cover how to design, secure, evaluate and govern the workload. The ORR companion scores only
launch-readiness and operational failure modes they do not score, and it does not score again what the core ORR
lens already owns, such as timeouts and retries, phased rollout, alarms and on-call.

## Running a review

### How long does a review take?

The maintainers' planning estimates: the 15-question core path takes about 90-120 minutes; the full core takes
about 3 hours, in two 90-minute sessions, plus 2-4 hours of evidence gathering by the team beforehand. A recurring
review takes about 2 hours, the event lens about 60 minutes on top of a current core review, and the generative AI
lens about 45 minutes on top of the core review. Field use measures these. See [running-an-orr.md](running-an-orr.md).

### Can I run only the core path?

For triage and recurring check-ins, yes. A launch go or no-go requires the full core: `readiness_signoff` includes
`rd_scope_complete`, so a review that skips questions cannot score better than High on the decision question.

### Who should answer the questions?

The people who operate each practice. That can be the in-house team, or an operations partner (for example a
systems integrator or managed service provider) that runs part of the workload under contract, answering for its
part with evidence you can inspect. An independent facilitator challenges the answers; see
[facilitator-guide.md](facilitator-guide.md).

### Why does the lens show so many High risks?

Because each High-capped question now defaults to High until its core practices are in place, and "None of these"
scores the worst risk. In v1.3.6, High could not be reached on 22 questions, and selecting only "None of these"
scored Medium on 23. A first self-assessment at design-complete usually shows many High risks; that is the point of
running it early. [scoring.md](scoring.md) lists every place where the lens rates a practice higher than the
Well-Architected Framework does, with the reason.

### What do High, Medium and No risk mean?

- **High:** launch-blocking unless remediated, or formally accepted in writing by the accountable owner with an
  expiry date.
- **Medium:** the core practice is in place but hardening is outstanding. Fix it on a plan; it does not block
  launch.
- **No risk:** every listed practice is in place and the evidence lines are satisfied.

### Why does selecting "None of these" score High?

"None of these" means none of the practices is in place, so the question scores its maximum risk. An unanswered
question shows as Unanswered, not as High, which is why the readiness decision requires every question to be
answered or marked not applicable.

### A question does not fit my workload. What should I do?

Use a scope-exit statement if the question has one (for example "The workload has no internet-facing endpoints"),
with the evidence its helpful text lists. Otherwise mark the whole question "does not apply" with a reason. See
[scoring.md](scoring.md#not-applicable).

### How do I accept a High risk?

The accountable owner (the business owner or, in government, the authorizing official) records the acceptance in
your risk register or POA&M, with an expiry date. The question notes carry only a tag:
`EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>`. The approver's name, the reason and the compensating
controls stay in the register. An accepted High still shows as High in the WA Tool.

### What can I put in notes?

Short pointers to evidence. Notes appear in reports and sync to Jira when it is enabled. Never paste secrets,
credentials, personal data or sensitive incident details. In AWS GovCloud (US), also keep export-controlled
information out of the workload name, milestone names and review owner; see [govcloud.md](govcloud.md#data-handling).

### Where should improvement items go?

The WA Tool Connector for Jira (commercial Regions), AWS Systems Manager OpsCenter, or your own tracker fed from
`ListLensReviewImprovements`. For ORR-only risk counts use `GetLensReview`, because the consolidated report's
per-lens breakdown covers only the Framework lens. See [running-an-orr.md](running-an-orr.md#track-improvement-items).

### Some statements name services I cannot use. Do I fail them?

No. Statements describe capabilities and name AWS services only as examples ("for example AWS AppConfig"); any
tool that meets the practice counts. Where a service is not available in a partition, the helpful text offers a
method-based alternative. The lens never recommends services that are closed to new customers or near end of
support.

## Upgrading from v1.3.x

### How do I upgrade?

Edit your existing ORR lens; never create a new one. In the console: Custom lenses, select your existing ORR lens,
Edit, Choose file (the new JSON), Submit; then Publish lens, choose Major version, and enter the version name
(for example `2.0.0`)
([Publishing an update](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-publish-update.html)).
Then upgrade each workload's lens review, which saves a milestone first. `MIGRATION.md` has the full steps,
including the API path.

### Why not create a new custom lens for 2.0.0?

Create custom lens makes a second lens with a new ARN. It uses one of the 15 custom-lens slots per account per
Region, existing workloads get no upgrade notice, and their answers and notes stay with the old lens.

### I modified the v1 lens. What happens to my questions?

Uploading a new version replaces the lens content. Before upgrading, export your lens with `ExportLens`, diff it
against v1.3.6, and move your own questions into a separate add-on lens. See [customizing.md](customizing.md).

### Why do my answers reset after the upgrade?

Every choice ID in 2.0.0 is new, so earlier selections do not carry over, and kept questions show as Unanswered.
This is intentional: v1.3.6 selections are not reliable evidence under the v2 bars, and new IDs prevent stale
answers from silently scoring No risk. The 20 kept question IDs keep their place; 32 v1 questions were merged,
split or replaced, and 16 core questions are new. `MIGRATION.md` maps every v1.3.6 question to its v2
question.

### Where are my old answers?

In the milestone that the upgrade saves before it changes the review. Compare with it in the console, or call
`GetAnswer` with that `MilestoneNumber`
([Lens upgrades](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lens-upgrades.html)).

### What about notes and "does not apply" flags on kept questions?

AWS documents that answers to existing questions are retained on a lens upgrade. In sandbox gate G2
(2026-10-06, [gates.md](gates.md)), notes carried over word for word and a question-level "does not apply" flag
carried over with its reason on kept question IDs. Re-confirm each carried flag and note against the v2
question, because they describe v1.3.6 answers, not v2 evidence. The one-box question
(`releases_onebox_deployments`) became `releases_phased_rollout` with a new ID, because its meaning broadened from
EC2 to every platform, so a v1 "does not apply" flag cannot silently exclude it.

### Do review templates upgrade automatically?

No. Upgrade each review template that includes the lens before creating workloads from it
([Upgrading a lens](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-upgrading.html)), then
re-share it. A review template cannot use a lens that was shared with you, so a team that wants templates imports
its own copy of the lens.

### How will later releases reach my workloads?

A PATCH release (text and links only, for example 2.0.1) is published as a WA minor version and applies silently.
A release that changes statements, rules or severity is published as a WA major version, so owners are notified
and upgrade each workload with a milestone. See [scoring.md](scoring.md#how-bars-change).

## Partitions and data

### Does the lens work in AWS GovCloud (US)?

Yes. The WA Tool supports custom lenses, review templates and lens upgrades there (checked 2026-10-06). The Jira
connector, AWS Shield Advanced, Amazon CloudFront in the partition, AWS CodeArtifact and some other features are
not available; [govcloud.md](govcloud.md) lists them with dates and method-based alternatives.

### Does the lens collect any data?

No. The lens files contain no customer data, and the repository runs no hosted service and collects no telemetry
or answers. Answers and notes stay in your account and Region; in AWS GovCloud (US), see the exceptions in
[govcloud.md](govcloud.md#data-handling).

## Contributing

### How do I suggest a change or report a broken link?

Open an issue on [this repository](https://github.com/awslabs/operational-readiness-review-custom-war-lens). A
question proposal needs a public source and the public incident or guidance that motivates it. Never include
customer names, account IDs, workload names or incident details. Bar changes follow the rules in
[scoring.md](scoring.md#how-bars-change).

### Can I add my own questions to the lens?

Put them in a separate add-on lens; see [customizing.md](customizing.md). The ORR lens stays unmodified, so you can
keep upgrading it.

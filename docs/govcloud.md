# Using the ORR lenses in AWS GovCloud (US)

The ORR lenses work in the AWS GovCloud (US) Regions: the AWS Well-Architected Tool supports custom lenses,
review templates and lens upgrades there (checked 2026-10-06). Some services and features that the lenses name as
examples are not available in AWS GovCloud (US), and some WA Tool features differ. This page lists them, gives a
method-based alternative where a statement depends on one, and explains which review data may leave the GovCloud
(US) Regions.

**How to read this page.** Every row has the date it was last checked against public AWS sources: the
[AWS GovCloud (US) User Guide](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-wellarchitected.html)
and [AWS Capabilities by Region](https://builder.aws.com/build/capabilities). This page records only "available"
or "not available" on that date. Availability changes, so check AWS Capabilities by Region for the Region you use
before you rely on a row. Partition notes in each lens statement say "verify per Region" for the same reason.

## Availability

### Not available in AWS GovCloud (US)

| Item | Checked | Notes |
|---|---|---|
| WA Tool Connector for Jira | 2026-10-06 | Track improvement items another way; see [Tracking without Jira](#tracking-without-jira) |
| WA Tool Profiles | 2026-10-06 | Profiles apply to the Framework lens; the ORR lenses do not use them |
| CloudFormation resource `AWS::WellArchitected::Lens` | 2026-10-06 | Distribute lens files through GitHub Releases and import them with the console or `ImportLens` |
| AWS Shield Advanced | 2026-10-06 | No Shield Response Team engagement or cost protection. The AWS DDoS Simulation Testing Policy expects a Shield Advanced protected target unless AWS approves an exception requested at least 14 days ahead ([DDoS simulation testing](https://aws.amazon.com/security/ddos-simulation-testing/)), so GovCloud-only workloads rehearse DDoS response as a tabletop |
| Amazon CloudFront in the GovCloud (US) Regions | 2026-10-06 | The GovCloud User Guide describes using CloudFront from a standard AWS account with GovCloud (US) resources ([Setting up CloudFront](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/setting-up-cloudfront.html)); decide whether that meets your data and compliance requirements |
| AWS CodeArtifact | 2026-10-06 | See the alternative for `cs_artifacts_controlled` below |
| AWS Security Incident Response | 2026-10-06 | Use your own security incident playbooks and AWS Support (`sec_ir_exercised`) |
| AWS Backup logically air-gapped vaults | 2026-10-06 | See the alternative for `dc_immutable_isolated` below |
| AWS Backup restore testing | 2026-10-06 | Run and record restore tests yourself (`rec_restore_tested`, `dc_point_restore_rehearsed`) |
| Amazon Application Recovery Controller (ARC) readiness checks and routing control | 2026-10-06 | Readiness checks are also closed to new customers in every partition. Zonal shift, zonal autoshift and Region switch are available (below) |
| Next-generation AWS Resilience Hub | 2026-10-05 | The classic AWS Resilience Hub is available (below) |
| AWS Well-Architected Agent (preview) | 2026-10-05 | It onboards workloads from AWS commercial Regions only. Its architecture reviews support only the Well-Architected Framework lens, so it does not evaluate the ORR lenses in any partition (checked 2026-10-06) |
| Amazon CloudWatch Transaction Search | 2026-10-06 | The GovCloud CloudWatch page lists Transaction Search as not available ([CloudWatch in GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-cw.html)). Send OpenTelemetry traces to AWS X-Ray and correlate them with logs instead (`tr_open_tracing`) |
| AWS Budgets, AWS Cost Explorer and AWS Cost Anomaly Detection | 2026-10-06 | Billing for a GovCloud (US) account is managed through the associated standard AWS account, and billing information for GovCloud accounts is available only in the commercial partition ([GovCloud (US) Billing and Payment](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/usage-and-payment.html)). Run budgets, cost analysis and cost anomaly detection from that standard account, or copy Cost and Usage Reports into a GovCloud (US) Amazon S3 bucket and analyze them there (`sat_usage_cost`, `cq_scale_down_plan`, `px_cost_review`) |

### Available in AWS GovCloud (US)

| Item | Checked | Notes |
|---|---|---|
| WA Tool custom lenses, lens upgrades and review templates | 2026-10-06 | `ImportLens`, `UpgradeLensReview` and `CreateReviewTemplate` are available |
| AWS WAF | 2026-10-06 | Only the AWS managed rule groups provided with AWS WAF are available; AWS Marketplace seller rule groups are not ([AWS WAF in GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-waf.html)) |
| AWS Shield (Standard protections) | 2026-10-06 | Shield Advanced is not available (above) |
| AWS Fault Injection Service (FIS) | 2026-10-06 | Experiment scheduling and experiment report configuration are not available ([FIS in GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-fis.html)) |
| ARC zonal shift, zonal autoshift and practice runs | 2026-10-06 | Used by `ev_shift_mechanism` and `ev_shift_practiced` |
| ARC Region switch | 2026-10-06 | For multi-Region recovery within the partition |
| Amazon CloudWatch Synthetics | 2026-10-06 | Used by `event_canary_alarms` |
| Amazon CloudWatch Application Signals | 2026-10-06 | One way to define SLOs for `event_alarms` |
| AWS Resilience Hub (classic) | 2026-10-06 | The assessment summary generated with Amazon Bedrock is not available, and Resilience Hub cannot import resources across partitions ([Resilience Hub in GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-arh.html)) |
| AWS Backup Vault Lock and copy jobs | 2026-10-06 | Used by the alternative for `dc_immutable_isolated` below |
| AWS IAM Identity Center multi-Region replication between the AWS GovCloud (US) Regions | 2026-10-06 | Available since 2026-10-01 ([What's New](https://aws.amazon.com/about-aws/whats-new/2026/10/aws-iam-identity-center-extends-multi-region-support-to-more-aws-regions/)). Reduces dependence on one Region for sign-in; still test break-glass access (`ea_tested_independent`) |
| AWS Systems Manager OpsCenter | 2026-10-06 | One way to track ORR improvement items |
| AWS Security Hub and AWS Security Hub CSPM | 2026-10-06 | Used by `sec_detection_routed` |
| AWS Health organizational view | 2026-10-06 | The organization-level Health API is available; see the event-delivery note below |

### Verify before relying on it

Public documentation did not confirm these as of 2026-10-06. Check them in your own GovCloud (US) account before a
statement's evidence depends on them:

| Item | How to check | If it is not available |
|---|---|---|
| The AWS WAF Anti-DDoS managed rule group (`AWSManagedRulesAntiDDoSRuleSet`) | On 2026-10-06, AWS Capabilities by Region listed AWS WAF DDoS Protection (the rule group) as available in both GovCloud (US) Regions, so the lens data records it as available, with lower confidence because no GovCloud page names it. The separate application-layer automatic mitigation entry that is not listed in GovCloud belongs to Shield Advanced. Call `ListAvailableManagedRuleGroups` for a regional web ACL in your GovCloud (US) Region and look for the rule group. Add AWS WAF rate-based rules either way | Use AWS WAF rate-based rules and the other AWS managed rule groups, and page on rate-based rule metrics (`ep_l7_detection_pages`, `dd_l7_enforcing`) |
| AWS FIS scenarios AZ Availability: Power Interruption and the gray-failure scenarios | The GovCloud (US) FIS page lists no scenario-library difference (checked 2026-10-06); it names only experiment scheduling and experiment report configuration ([FIS in GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-fis.html)). Open the FIS scenario library in your GovCloud (US) Region and confirm each action the scenario uses | Build the experiment from the individual FIS actions that are available, or test the same failure another way, and record what you ran (`az_tested_at_load`, `ev_per_az_detection`, `df_faults_injected`) |
| AWS CodePipeline `InspectorScan` action | The GovCloud (US) CodePipeline page does not list it among the actions that differ (checked 2026-10-06). Check the action list in the CodePipeline console in your GovCloud (US) Region | Run a vulnerability scanner in a build or test stage instead; Amazon Inspector is available in AWS GovCloud (US) (checked 2026-10-06) |
| Delivery of organization-level AWS Health events to Amazon EventBridge | When AWS announced organization-level delivery to EventBridge on 2023-10-05, GovCloud (US) was excluded. Check the current [AWS Health documentation](https://docs.aws.amazon.com/health/latest/ug/aggregating-health-events.html) | Create EventBridge rules for AWS Health in each production account, or poll the organization-level Health API on a schedule, and route the events to an owned on-call queue (`pe_events_routed`) |

### AWS Health differences that affect `pe_events_routed`

From [AWS Health in AWS GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-health.html),
checked 2026-10-06:

- The AWS Health API has a single regional endpoint in `us-gov-west-1`.
- Global events, such as IAM events, require an EventBridge rule in AWS GovCloud (US-West).
- Each GovCloud (US) Region is the backup Region for the other, and Health events are delivered to both. Create a
  rule in the backup Region too.
- The EventBridge channel does not send public events from the Service Health view; use the AWS Health API or the
  Service Health RSS feed for those.

## Generative AI and agents

Notes for ORR - Generative AI and Agents 1.0.0, checked 2026-10-07 against the AWS GovCloud (US) User Guide pages
for [Amazon Bedrock](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-bedrock.html),
[Amazon Bedrock AgentCore](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-bedrock-agentcore.html)
and [Amazon SageMaker AI](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-sagemaker.html), and
the Amazon Bedrock User Guide. The lens statements carry the same facts as dated partition notes.

| Item | Checked | Notes |
|---|---|---|
| Amazon Bedrock Regions and models | 2026-10-07 | Amazon Bedrock runs in AWS GovCloud (US-West) and AWS GovCloud (US-East). Model availability differs by Region ([Regional availability by models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html)), and model lifecycle dates can differ by Region, so read each model's row for `us-gov-west-1` and `us-gov-east-1` (`gai_inventory_routing`) |
| Model access | 2026-10-07 | Third-party models need model access enabled in the linked standard AWS account and in the GovCloud (US) account; models provided by Amazon Bedrock need it only in the GovCloud (US) account ([Request access to models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)). Confirm access for every fallback model in every Region it serves (`gai_dependency_fallback`) |
| Cross-Region inference | 2026-10-07 | Global cross-Region inference routes requests to supported commercial Regions, so it does not keep processing inside the partition ([Global cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/global-cross-region-inference.html)). For some models, the US-GOV geographic profile routes between `us-gov-east-1` and `us-gov-west-1`: each model card lists its source and destination Regions ([Supported Regions and models for inference profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html)), and GetInferenceProfile called from each GovCloud source Region confirms the destinations. Test each routing option you use with production service control policies attached (`gai_inventory_routing`) |
| Bedrock Provisioned Throughput | 2026-10-07 | Supported in AWS GovCloud (US-West) only for custom models with a no-commitment purchase ([Supported Region and models for Provisioned Throughput](https://docs.aws.amazon.com/bedrock/latest/userguide/prov-thru-supported.html)). Size on-demand quotas from the token arithmetic in `gai_capacity_quotas`, use the Reserved tier where the model card lists it (for example Claude Sonnet 4.5 in AWS GovCloud (US-West) through the US-GOV profile, [What's New, 2026-01-21](https://aws.amazon.com/about-aws/whats-new/2026/01/amazon-bedrock-reserved-tier-for-claude-sonnet-in-govcloud/)), or use self-hosted capacity |
| Amazon Bedrock AgentCore | 2026-10-07 | Runs in AWS GovCloud (US-West) only. The GovCloud page lists these differences: the Bedrock Guardrails policy and the Temporal policy are not offered, and the CloudFormation resources for `Policy`, `PolicyEngine`, `Evaluator`, `OnlineEvaluationConfig`, `OAuth2CredentialProvider` and `ApiKeyCredentialProvider` are missing. Create those resources with the API or AWS CLI and keep their configuration in version control (`gai_change_safety`, `gai_agent_bounds`) |
| AgentCore traffic that can leave the partition | 2026-10-07 | Gateway targets that call external services, external identity providers, the Browser tool and Code Interpreter sessions with internet access can send data to endpoints outside the GovCloud (US) Regions. Count each one as an inference or tool destination that the data owner approves (`gai_inventory_routing`) |
| SageMaker AI Deep Learning Container images | 2026-10-07 | The GovCloud (US) Regions publish mostly mutable image tags (immutable tags only for a few exceptions), so pin images by digest (`gai_change_safety`). SageMaker JumpStart in GovCloud (US) offers open-weight models only, through the SageMaker AI Python SDK |
| Organization-level guardrail enforcement | 2026-10-07 | Organization-level guardrail enforcement is not available in AWS GovCloud (US). It uses Amazon Bedrock policies in AWS Organizations, and a GovCloud (US) organization can use only service control policies, resource control policies, tag policies and declarative policies for EC2 and S3 ([AWS Organizations in AWS GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-organizations.html)). Turn on account-level guardrail enforcement in each account, which AWS Capabilities by Region lists in both GovCloud (US) Regions, or use an IAM deny on calls without the required guardrail (`gai_safeguards`) |
| Amazon CloudWatch generative AI observability | 2026-10-07 | Amazon CloudWatch generative AI observability is not available in AWS GovCloud (US) ([AWS Capabilities by Region](https://builder.aws.com/build/capabilities) lists it in neither GovCloud (US) Region). Use Bedrock invocation logs, CloudWatch metrics and OpenTelemetry traces sent to AWS X-Ray (`gai_observability`) |
| Export-controlled metadata | 2026-10-07 | Bedrock model evaluation job metadata, AgentCore resource metadata and SageMaker AI resource metadata must not contain export-controlled data. Keep it out of names, descriptions, tags and evaluation configuration (`gai_quality_evaluation`) |
| Token spend data | 2026-10-07 | Billing data for a GovCloud (US) account is in the associated standard account (see the AWS Budgets row above). Drive the spend stop and spike attribution from near-real-time token metrics in the GovCloud (US) account, not from billing data (`gai_runaway_cost`) |

### Generative AI items to check in your own account

Public documentation did not settle these as of 2026-10-07. The lens does not make a bar depend on any of them;
check them in your GovCloud (US) account before your evidence relies on them:

| Item | How to check | If it is missing |
|---|---|---|
| Amazon Bedrock runtime metrics that the lens names as examples, such as `LegacyModelInvocations` and `EstimatedTPMQuotaUsage` | Look for them in the `AWS/Bedrock` namespace in your GovCloud (US) account after a test call | Poll the model lifecycle state from the API on a schedule, and compute quota use from invocation logs (`gai_inventory_routing`, `gai_capacity_quotas`) |
| AgentCore spans in CloudWatch | AgentCore spans rely on CloudWatch Transaction Search. The GovCloud CloudWatch page lists Transaction Search as not available (see the Amazon CloudWatch Transaction Search row at the top of this page), while AWS Capabilities by Region lists it in AWS GovCloud (US-West), so test it in your account | Send OpenTelemetry traces to AWS X-Ray and correlate them with logs (`gai_observability`) |

## Method-based alternatives

Where a statement names a service that is not available in AWS GovCloud (US), the statement's helpful text offers
a method that meets the same practice. The main ones:

| Statement | Not available | Method that meets the practice |
|---|---|---|
| `cs_artifacts_controlled` | AWS CodeArtifact | Mirror the packages you need into a repository you operate inside the partition, and use Amazon ECR for container images. ECR-to-ECR pull through cache rules work only within the same partition, and ECR public registries are not available ([Amazon ECR in GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-ecr.html)) |
| `dc_immutable_isolated` | AWS Backup logically air-gapped vaults | Copy backups to a vault in a separate account with AWS Backup Vault Lock in compliance mode, and keep production credentials out of that account |
| `ep_waf_rate_rules`, `ep_ddos_runbook`, `dd_ddos_tier`, `dd_rehearsed` | AWS Shield Advanced; CloudFront in the partition | AWS WAF regional web ACLs with managed and rate-based rules on the load balancer or API, AWS Shield Standard protections, a DDoS runbook that engages AWS Support, and a tabletop rehearsal. For `dd_ddos_tier`, record the decision and the reason |
| `sec_ir_exercised` | AWS Security Incident Response | Your own playbooks for credential compromise, ransomware and data exposure, exercised as tabletops, with the AWS Support escalation path |
| `rec_restore_tested`, `dc_point_restore_rehearsed` | AWS Backup restore testing | Scheduled restore jobs that you run, validate and record, with the achieved RTO and RPO |

## Tracking without Jira

The WA Tool Connector for Jira is not available in AWS GovCloud (US) (checked 2026-10-06). Use one of these:

- **AWS Systems Manager OpsCenter:** create an OpsItem for each High risk
  ([OpsCenter](https://docs.aws.amazon.com/systems-manager/latest/userguide/OpsCenter.html)).
- **Your own tracker:** export improvement items on a schedule with
  [ListLensReviewImprovements](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_ListLensReviewImprovements.html)
  for each workload to CSV, and import it into your ITSM tool. For ORR-only risk counts use `GetLensReview`; the
  JSON consolidated report breaks counts down only for the AWS Well-Architected Framework lens.

WA Tool events in Amazon EventBridge are delivered on a best-effort basis
([EventBridge events](https://docs.aws.amazon.com/wellarchitected/latest/userguide/eventbridge.html)), so do not
use them as the feed.

## Support plans

The [AWS Support plans](https://docs.aws.amazon.com/awssupport/latest/user/aws-support-plans.html) page (checked
2026-10-06) gives 2027-01-01 as the end-of-support date for Developer Support, Business Support and Enterprise
On-Ramp, and states that these three plans remain available in the AWS GovCloud (US) Region. The lens does not
depend on plan names: `pe_support_fit` asks whether your support arrangement's target initial-response time fits
the workload's RTO.

## Data handling

For the AWS Well-Architected Tool in AWS GovCloud (US), AWS lists the data that may leave the GovCloud (US)
Regions in the normal course of operation
([AWS Well-Architected Tool in AWS GovCloud (US)](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-wellarchitected.html),
checked 2026-10-06):

- the AWS account IDs associated with a workload;
- the workload name;
- milestone names;
- the review owner.

So:

- Keep export-controlled, sensitive and personal information out of the workload name, milestone names and the
  review owner field, as well as out of notes.
- Name milestones `ORR-<yyyy-mm>-<purpose>`, for example `ORR-2026-12-launch`. Do not put system names, program
  names or incident details in them.
- Use a role or team alias as the review owner where your policy allows it.
- Notes appear in reports. Link to evidence held in your own systems instead of pasting it. Never paste secrets,
  credentials, personal data or sensitive incident details.
- Accepted risks carry only `EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>` in notes. The reason, the
  compensating controls and the approver's name stay in your risk register or POA&M.

The lens files themselves contain no customer data, and answers and notes stay in your account and Region except
as listed above.

## Running the sandbox gates in GovCloud (US)

For 2.0.0 the sandbox gates ran in a commercial-Region sandbox account only; [gates.md](gates.md) records the
Region of each run. The AWS GovCloud (US) rows on this page come from public AWS documentation and AWS
Capabilities by Region on the dates shown. If you see different behavior in a GovCloud (US) Region, open an issue
without account IDs, workload names or notes.

# Adding your organization's own questions

Most organizations have readiness requirements of their own: approvals their policy requires, shared services
every workload must register with, or lessons from their own incidents. This page explains how to add them without
losing the ability to upgrade the ORR lenses.

## The default: a separate add-on lens

**Keep the ORR lenses unmodified, and put your own questions in a small custom lens of your own, attached to the
same workload.**

Why:

- Uploading a new ORR release into an existing lens replaces that lens's content
  ([Publishing an update to a custom lens](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-publish-update.html)).
  Questions you added to the ORR lens itself would be lost on the next upgrade.
- An add-on lens has its own versions, so you can change your questions on your schedule and upgrade the ORR lens
  on ours.
- The WA Tool shows each lens review, its risks and its improvement plan separately, so your organization's
  findings stay distinct from the ORR findings.

Costs to plan for:

- Each add-on lens uses one of the 15 custom-lens slots per account per Region, and that quota cannot be raised.
- A workload can have up to 20 lenses attached. The ORR core, the event lens and one add-on fit comfortably
  ([AWS Well-Architected Tool endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/wellarchitected.html)).

Prefer one add-on lens per organization over one per team, so slots stay free for the lenses in the
[Lens Catalog](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lens-catalog.html) and the other
companion lenses you need.

## Start from the template

The repository ships a starter add-on lens:

| File | What it is |
|---|---|
| `lens-src/templates/org-addon.yaml` | The source: one pillar and two example questions in the same YAML format as the ORR lenses ([lens-src/SCHEMA.md](../lens-src/SCHEMA.md)), with the `schema` key set once at the top |
| `templates/org-addon-lens.json` | The generated WA Tool custom-lens JSON, with `none_no` and generated risk rules. Do not edit it by hand |

The two example questions show both patterns:

| Example question | Maximum risk | Pattern |
|---|---|---|
| `x_example_launch_approvals` | High | A scope exit, one core statement with a `severity_basis`, and one secondary statement |
| `x_example_service_inventory` | Medium | Secondary statements only |

### Steps

1. Clone this repository (or a copy you keep for your organization) and edit
   `lens-src/templates/org-addon.yaml` there. Keep your edited copy in your own version control.
2. Rename every ID from `x_example_` to `x_<org>_`, for example `x_acme_`. This applies to the pillar ID, the
   question IDs, each question's `choice_prefix`, the statement IDs and the `concept` values. The `x_` prefix is
   reserved for organizations: ORR lens IDs never start with it, so your IDs never collide with ours.
3. Set `name` and `description`. Keep the name distinct from the ORR lenses, for example
   `ORR add-on - <Organization> requirements`.
4. Replace the example questions with your own, following the [rules for good questions](#rules-for-good-questions).
5. From the repository root, run `python3 -m tools.orrlens build` and then `python3 -m tools.orrlens check
   --offline` (Python standard library plus PyYAML). Build first: `check` compares `templates/org-addon-lens.json`
   with a fresh build, so it fails until `build` has run. The toolchain emits the risk rules, runs the same checks
   as for the ORR lenses, and writes `templates/org-addon-lens.json`.
6. In the WA Tool console, choose **Custom lenses**, then **Create custom lens**, upload the JSON, choose
   **Submit**, then **Publish lens**
   ([Creating a custom lens](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-create.html)).
7. Share it the same way you share the ORR lenses
   ([Sharing a custom lens](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-sharing.html)),
   and attach it to each workload alongside the ORR core.
8. When you change your questions, publish a new version of the same add-on lens (Edit, Choose file, Submit, then
   Publish lens). Never use Create custom lens to update it: that creates a second lens with a new ARN, uses
   another slot, and existing workloads get no upgrade notice.

### Rules for good questions

The same rules the ORR lenses follow keep an add-on lens useful:

- **One observable practice per statement**, never a fact about the workload. "We use a third-party payment
  provider" is a fact; "The payment provider's outage runbook was exercised in the last 12 months" is a practice.
- **No catch-all statements** such as "Relevant risk has been mitigated".
- **At most 4 statements per question**, titles of at most 128 characters, descriptions and helpful texts of at
  most 1,024 characters, and question-level helpful text of at most 64 characters.
- **Tiers, not hand-written rules.** Tag each statement `scope`, `core`, `alt:A` or `sec`. Every High-capped
  question needs at least one `core` or `alt:` statement, and each of those needs a `severity_basis`. For an
  organization's own policy, a `deviation:` with a written rationale is the usual basis.
- **Alternatives become alt groups**, never statements joined with AND.
- **Evidence for scope exits.** A scope exit scores No risk outright, so its helpful text lists the evidence to
  collect.
- **Do not duplicate the ORR lenses.** If an ORR question already scores a practice, do not score it again; one
  owning statement per practice keeps risk counts honest. If you think an ORR bar is wrong, open an issue on this
  repository instead.
- **Keep sensitive content out.** Questions, helpful text and notes appear in reports and sync to Jira when it is
  enabled. Do not put private hostnames, credentials or incident details in the lens; link to your own documents
  from your own systems instead.

### Turning your incidents into questions

The ORR whitepaper describes how to turn an incident into ORR guidance
([Appendix A: Creating ORR guidance from an incident](https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/appendix-a-creating-orr-guidance-from-an-incident.html)).
The core lens asks for this in `event_post_incident_analysis` (statement `pia_orr_feedback`): each post-incident
analysis asks whether an ORR question would have prevented the impact. Questions you derive from your own
incidents go into your add-on lens, not into the ORR lens.

## Review templates and shared lenses

A review template cannot use a lens that was shared with you
([Creating a review template](https://docs.aws.amazon.com/wellarchitected/latest/userguide/creating-a-review-template.html)). If a
platform team wants a template that pre-fills answers, it imports its own copy of the ORR lens and the add-on lens.
Pre-fill only platform-provided controls that come with evidence, such as a shared pipeline with alarm-based
rollback. Never pre-fill statements each workload must prove itself, such as load tests, Availability Zone loss
tests or the readiness sign-off. After a lens major version, upgrade each template before creating workloads from
it ([Upgrading a lens](https://docs.aws.amazon.com/wellarchitected/latest/userguide/lenses-upgrading.html)).

## If you already modified the ORR lens

If you added questions to an earlier ORR lens directly (for example in a workshop), do this before upgrading:

1. Export your current lens with
   [ExportLens](https://docs.aws.amazon.com/wellarchitected/latest/APIReference/API_ExportLens.html) and diff it
   against the published v1.3.6 file in `wafr-operational-readiness-lens/`.
2. Move every question you added into an add-on lens built from the template.
3. Then upgrade the ORR lens as `MIGRATION.md` describes.

## The advanced path: a fork with overlays

If you must change the ORR lens itself, fork this repository and add questions under the reserved `x_<org>_` ID
prefix in `lens-src/`. The generator and the checks work unchanged on overlay questions. Costs:

- You rebase your fork on every release and resolve conflicts yourself.
- Uploading your fork's build into the ORR lens replaces the published content, so every workload sees your
  version, not ours.
- Overlay content is never merged upstream. If an overlay question would help everyone, propose it as a new
  question through an issue, with its public source.

Most organizations do not need this. Start with an add-on lens.

## Summary

<!-- What does this change do, and why? Link the issue it resolves (for example "Resolves #123"). -->

## Type of change

- [ ] Text, link or typo only; no ID or rule change (PATCH; published as a WA minor version)
- [ ] New or changed statement, tier, rule or severity, or a new question (MINOR; published as a WA major version)
- [ ] Removes a statement or question, which retires its ID (MAJOR; needs a `MIGRATION.md` section)
- [ ] Tooling, CI or documentation only

## Checklist

- [ ] `python3 -m tools.orrlens check` passes locally.
- [ ] Lens content is edited only in `lens-src/`; I did not edit `dist/`, `wafr-operational-readiness-lens/` or generated docs by hand, and I did not write `riskRules` by hand.
- [ ] Every new or changed bar cites a public source, and every `core` or `alt:` statement has a `severity_basis`.
- [ ] Each statement describes one observable practice; there are at most four statements per question.
- [ ] No customer names, internal material, account IDs or sensitive information.
- [ ] Third-party standards are linked, not copied.
- [ ] No recommended service is closed to new customers, in maintenance, discontinued, or near end of support.
- [ ] Availability statements are dated, and links are `https` on the allowed hosts.
- [ ] Plain ASCII, no em or en dashes.
- [ ] IDs are new and never reused (no change to the meaning of an existing ID).
- [ ] For bar changes: the truth-table difference is in the description and a `CHANGELOG.md` entry gives the rationale.

By submitting this pull request, I confirm that you can use, modify, copy, and redistribute this contribution, under the terms of your choice.

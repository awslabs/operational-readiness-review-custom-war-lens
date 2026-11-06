---
name: orr-review
description: Run an Operational Readiness Review (ORR) of a workload with the open source ORR lens family (core lens, Mission-Critical Event Readiness, Generative AI and Agents), without the AWS Well-Architected Tool. Walks the team through each question and the evidence it asks for, records answers, scores risk with the lens's own risk rules, and writes a findings report with High and Medium risks, accepted risks and improvement plans. Use when asked to run, prepare, resume or score an ORR, a launch or go-live readiness review, or an event readiness review.
license: MIT-0
compatibility: Script mode runs scripts/orr.py with Python 3.9 or later (standard library only) and the lens JSON files. Reference mode needs no code and no files beyond this skill (for Amazon Quick and chat assistants). No AWS credentials and no network access are needed.
---

# Operational Readiness Review (ORR)

You facilitate an ORR with the ORR lenses from
https://github.com/awslabs/operational-readiness-review-custom-war-lens. The lens is the bar: you ask its
questions, the team answers with evidence, and each answer is scored with the lens's own risk rules, the same rules
the AWS Well-Architected Tool applies to the imported lens. Never invent an answer, and never lower the bar.

Keep score in one of two ways, and say which one you use:

- **Script mode** when you can run `python3` and read files (Claude Code, Kiro, Codex and other coding agents).
  `scripts/orr.py` keeps the answers in a JSON file, scores them and writes the report. It is in the folder that
  holds this `SKILL.md`, for example `.claude/skills/orr-review/`, `.agents/skills/orr-review/`,
  `.kiro/skills/orr-review/` or the same path under your home folder. Run it with its full path from the review
  folder (which holds the lens files, the answers file and the report); the commands below write it as
  `scripts/orr.py`. `--help` lists every option.
- **Reference mode** when you cannot run the script or read the lens JSON files (Amazon Quick, chat assistants).
  The lens is bundled with this skill as plain text: `references/lens-core.md`, `references/lens-event.md` and
  `references/lens-genai.md` hold every question, its statements and its risk lines, and `references/plans-<lens>.md`
  holds the improvement plans. You score by hand, exactly as each lens file's "How to score one question" says.

## Ground rules

- **Select a statement only when it is true today and backed by evidence.** Intent, a ticket, a design or "most of
  the time" does not count. "Partly", "in progress" and "planned" mean unselected: record the plan in the notes as
  `PLAN:<statement-id> <tracker-id> due:YYYY-MM-DD`.
- **None of these** is the honest answer when no statement is true. It scores the question's maximum risk and is
  never combined with a statement.
- **Not applicable** is for a whole question, with a written reason. Prefer the question's scope-exit statement
  where it has one, and accept a scope exit only with the evidence the lens lists for it. Never mark individual
  statements not applicable.
- **You may look for evidence yourself** (the workload's code, infrastructure as code, pipeline or runbooks) when
  you can read them, and cite the file or link. The team still confirms each answer. Do not claim evidence you have
  not seen.
- **Notes are short links to evidence.** Never put secrets, credentials, account IDs, ARNs, personal data,
  customer names or incident details in notes, the workload name or the milestone name.
- **Accepted High risks** carry only `EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>` in the notes. The
  approver's name, the reason and the compensating controls stay in the team's risk register. Only the accountable
  owner accepts a risk; you never do.

## 1. Set up

1. Agree the scope with the user:
   - **Lenses.** Always the core lens. Add `event` before a planned peak (an election, an enrollment or tax
     deadline, a launch, a broadcast, a migration or cutover). Add `genai` when the workload calls a foundation
     model or runs an AI agent.
   - **Review type.** `full` for a launch go or no-go (about 3 hours for the core lens, best in two sessions).
     `core-path` (the 15 core-path questions listed at the top of `references/lens-core.md`, about 90-120 minutes)
     for triage and recurring check-ins only; its result is preliminary.
   - **Roles.** Who is the accountable owner (decides and accepts risks), who answers, and who facilitates. If you
     facilitate, say so; you challenge answers, you do not answer for the team.
   - **Names.** A workload name and a milestone name such as `ORR-2026-11-launch`, with nothing sensitive in them.
2. Script mode: find the lens files with `python3 scripts/orr.py lenses`. If none are found, ask the user to
   download the release files into the review folder (or offer to, if they agree), then check them:

   ```
   https://github.com/awslabs/operational-readiness-review-custom-war-lens/releases/latest/download/orr-core.json
   https://github.com/awslabs/operational-readiness-review-custom-war-lens/releases/latest/download/SHA256SUMS
   sha256sum --ignore-missing -c SHA256SUMS        # macOS: shasum -a 256 --ignore-missing -c SHA256SUMS
   ```

   Add `orr-event.json` and `orr-genai.json` from the same place when those lenses apply. In a clone of the
   repository, pass `--lens-dir dist`. Then start the answers file, which is the review's state:

   ```
   python3 scripts/orr.py init orr-answers.json --workload checkout-api --lens core,genai --scope full --milestone ORR-2026-11-launch
   ```

3. Reference mode: read `references/lens-<lens>.md` for each lens in scope. Its title holds the lens version;
   tell the user, so they can check it is the latest release. Keep the answers in this table, one row per answered
   question, and show it to the user whenever they ask for status. If you can save files, save it as a Markdown
   file so the review can resume; otherwise ask the user to keep a copy.

   | Question | Lens | Selected | Not applicable reason | Notes | Risk |
   |---|---|---|---|---|---|

## 2. Walk the questions

Go in the order of the lens files: core pillars first, then the companion lenses, and `readiness_signoff` last.
Script mode: `python3 scripts/orr.py status orr-answers.json` names the next question and
`python3 scripts/orr.py show <question-id>` prints it. Reference mode: take the next question block from the lens
file.

1. Ask one question at a time. Put the question in plain words, list the evidence to collect, read out the
   statements, and ask which are true today and what evidence shows it. Challenge the answer the way an
   independent facilitator would: "show me", "when was it last tested?", "what happens if this fails?", "is it
   documented?". See `references/facilitation.md` for prompts that fit common answers.
2. Record the answer, then tell the user the resulting risk and the statements that are not in place.
   - Script mode:

     ```
     python3 scripts/orr.py answer orr-answers.json event_alarms --choices slo_defined,slo_alarms_before_breach --notes "SLOs and alarms: <link>"
     python3 scripts/orr.py answer orr-answers.json architecture_hybrid_connectivity --not-applicable "No on-premises dependencies; network diagram <link>"
     python3 scripts/orr.py answer orr-answers.json releases_manual_changes --none --notes "PLAN:cc_review_enforced T-123 due:2026-12-15"
     ```

     `--notes` replaces earlier notes. `--clear` removes an answer. The script refuses a statement id the question
     does not have and None of these combined with a statement, and warns when notes look like they hold an
     account ID or an ARN.
   - Reference mode: use only statement ids listed under the question, go through its risk lines in order and take
     the first line that is true, then update the table. Show the line that decided the risk, for example
     "Medium (line 2: `slo_defined` AND `slo_alarms_before_breach`)". When you name an improvement plan, copy it
     word for word from `references/plans-<lens>.md`; if that file is not available to you, say so and never write
     a plan of your own.
3. If the team cannot show evidence in the session, leave the question unanswered, park it, and move on; do not
   guess.

## 3. Answer readiness_signoff last

`readiness_signoff` is the go or no-go question. Answer it after every other question in every attached lens.
Select `rd_scope_complete` only when no question is unanswered, never in a core-path review, and never mark it not
applicable. Select `rd_highs_dispositioned` only when every High risk is fixed or accepted by the accountable owner
with an expiry date. In script mode `status` warns when these do not hold; in reference mode check them yourself.

## 4. Report

Script mode: `python3 scripts/orr.py report orr-answers.json --out orr-report.md`. Reference mode: write the
report in the format of `references/report-template.md`, and say that the scores were worked out by hand from the
lens rules. Copy each improvement plan word for word from `references/plans-<lens>.md`. If that file is not
available to you (for example it was not attached), write "Improvement plan: not available" and name the file;
never write a plan of your own.

The report has the scope, risk counts per pillar, the readiness decision, each High and Medium risk with the
statements that are not in place and their improvement plans, accepted risks with expiry status, not-applicable
reasons, unanswered questions and every answer. Walk the user through High risks first, then Medium. Then:

- the accountable owner records the go or no-go decision and its date in the team's own records;
- each improvement item goes to the team's tracker with an owner and a due date;
- keep a copy of the answers (file or table) named after the milestone, for example `ORR-2026-11-launch`, so the
  next review can compare with it, and schedule the next review (at least yearly, and after a major change).

Treat the report and the answers as sensitive: they list unmitigated risks. Share them only through the team's
approved channels.

## Files

- `scripts/orr.py`: script mode. Lens discovery, question display, answers file, scoring and the report.
- `references/lens-core.md`, `references/lens-event.md`, `references/lens-genai.md`: reference mode. Each
  question, its evidence lines, statements and risk lines, generated from the lens sources.
- `references/plans-core.md`, `references/plans-event.md`, `references/plans-genai.md`: the improvement plan for
  each statement.
- `references/report-template.md`: the report format for reference mode.
- `references/facilitation.md`: how to run the session, challenge answers, and read the risk levels.

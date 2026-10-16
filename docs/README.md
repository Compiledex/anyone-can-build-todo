# Documentation

This folder holds the documents a software team writes around an app, from the first idea to
the review after release. Every document type has **one example**, written for this to-do app.

- **Real** documents are built from what really happened in this project: the plans, the pull
  requests (PRs), the code and the bugs. Each fact names its source.
- **Simulated** documents (or simulated parts) are practice. The app has no real users besides
  its owner, so interviews, test sessions, bug bash results and experiment numbers are invented.
  They are always marked **SIMULATED** at the top, and use invented first names only.

The folders are sorted by **type** of document, as real teams do. The table below shows them in
the order of the **phases** of the work. Each document's header also says its phase.

## The documents, phase by phase

### 1. Idea: before anything is built

| Document | What it answers | Data |
|---|---|---|
| [Product requirements (PRD)](product/prd.md) | What problem, for whom, what must it do, what not? | Mixed |
| [User research notes](product/user-research-notes.md) | How do people keep and share to-dos today? | Simulated |

### 2. Design: how it should work and look

| Document | What it answers | Data |
|---|---|---|
| [Prototype](design/prototype.md) | What will it look like? (a mockup instead of Figma) | Real |
| [UX test plan and findings](design/ux-test-plan-and-findings.md) | Can people use it? What confused them? | Mixed |
| [Design doc](design/design-doc.md) | How is it built, and why this way? | Real |
| [Architecture decision records (ADRs)](adr/README.md) | One big technical choice each: context, decision, consequences | Real |
| [Data inventory and privacy](design/data-inventory-and-privacy.md) | What personal data is kept, where, for how long, who sees it? | Real |

### 3. Build: making the change

The running example is one real feature, **Undo after deleting a to-do** (PR #51), so you can
follow it from ticket to tested PR.

| Document | What it answers | Data |
|---|---|---|
| [Ticket](process/ticket.md) | What is the job, and when is it done? | Mixed |
| [Task plan](process/task-plan.md) | How will we build it, step by step? (the [feature plans](plans/README.md)) | Real |
| [Pull request description](process/pull-request-description.md) | What changed, why, and how do we know it is safe? | Real |
| [PR review by risk](process/pr-review-by-risk.md) | How hard must a change be reviewed? | Real |
| [Test plan](process/test-plan.md) | Which tests prove it works, at which layer? | Real |

Templates GitHub uses for new PRs and issues:
[`.github/pull_request_template.md`](../.github/pull_request_template.md),
[bug report](../.github/ISSUE_TEMPLATE/bug_report.md),
[feature request](../.github/ISSUE_TEMPLATE/feature_request.md).

### 4. Production: running it, and fixing what breaks

| Document | What it answers | Data |
|---|---|---|
| [QA run and bug bash](process/qa-run-and-bug-bash.md) | Did we check everything before a release? What did a group find? | Mixed |
| [Bug reports and triage](bug-reports/README.md) | How is a bug filed and sorted? Plus three real bug reports | Real (triage cadence simulated) |
| [Deployment runbook](runbooks/deployment.md) | How to install, start, update and roll back | Real |
| [On-call and incident runbook](runbooks/on-call-and-incidents.md) | What to do when something goes wrong | Mixed |
| [Postmortem: merged with red CI](postmortems/2026-10-09-merged-with-red-ci.md) | What went wrong, why, and what changed so it does not happen again | Real |
| [Changelog (release notes)](../CHANGELOG.md) | What is new for the person using the app? | Real |

### 5. Analysis: learning from it

| Document | What it answers | Data |
|---|---|---|
| [Tracking plan](product/tracking-plan.md) | What would we measure, and how, without hurting privacy? (not built) | Mixed |
| [Experiment doc](product/experiment-doc.md) | Does a change really help? (15 or 5 minutes for Undo) | Simulated |
| [Retrospective](retrospectives/2026-10-16-project-retrospective.md) | What went well, what to improve, what we do next | Real |

## Folders

```
docs/
  README.md        this page
  product/         PRD, user research, tracking plan, experiments
  design/          design doc, prototype, UX tests, data inventory
  adr/             architecture decision records, 0001-..., never renumbered
  process/         ticket, task plan, PR description, review by risk, test plan, QA
  bug-reports/     triage process (README) and BUG-001-...
  runbooks/        deployment, on-call and incidents
  postmortems/     YYYY-MM-DD-....md
  retrospectives/  YYYY-MM-DD-....md
  plans/           the feature plans (history), with their own index
```

## Adding a document

- Put it in the folder for its **type**, with a lower-case kebab-case name (`like-this.md`).
  ADRs get the next number (`0009-...`); postmortems and retrospectives start with the date in
  Tokyo (`2026-10-20-...`); bug reports get the next number (`BUG-004-...`).
- Start it with the same header table as the others (Type, Phase, Written by, Status, Date,
  Data), and mark any invented content **SIMULATED**.
- Add a line to the table above.
- These documents describe the app at the time they were written. `AGENTS.md` and the code
  describe it now; when they disagree, the code wins.

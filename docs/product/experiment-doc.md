# Experiment: Undo window of 15 minutes vs 5 minutes

| | |
|---|---|
| Type | Experiment write-up (A/B test) |
| Phase | Analysis |
| Written by | Data scientist with the product manager (in this project: simulated, written by Claude) |
| Status | Done (simulated) |
| Date | 2026-10-16 |
| Data | SIMULATED (see below) |

> **What this document is.** A data scientist writes an experiment doc before an A/B test starts,
> and adds the results when it ends. An **A/B test** shows two versions of a feature to two random
> groups of people and compares what they do. The doc fixes the question, the metric and the
> stopping rule in advance, so nobody can pick the result they like after the fact.

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.
> This experiment was never run. The app has no analytics (see the
> [tracking plan](tracking-plan.md)).

## 1. Background

Real: when a person deletes one to-do, the app shows "Deleted ..." with an **Undo** button. Undo
works for **15 minutes** (`UNDO_SECONDS = 15 * 60` in `todos/undo.py`), only for the person who
deleted it, and only for the last delete (PR #51, `docs/plans/delete-undo.md`). The plan chose 15
minutes as "long enough to notice a mistake, short enough that an old snapshot does not linger",
and listed 5 minutes as another option. No data was used. This experiment is how a team with
users would check that choice.

## 2. Hypothesis

A longer window lets more people recover a to-do they deleted by mistake.

- **H0** (the "null hypothesis", meaning "no effect"): the share of deletes that are undone is the
  same with 5 and 15 minutes.
- **H1:** the share is higher with 15 minutes.

We expect a small effect: most mistakes are noticed in the first minute.

## 3. Variants

| Variant | Undo window | Who |
|---|---|---|
| A (control) | 15 minutes, as today | 50 % of accounts |
| B | 5 minutes | 50 % of accounts |

Accounts are split by user id (even or odd), fixed for the whole test, so one person always sees
the same window. Nothing else changes. The message text stays the same.

## 4. Metrics

**Primary metric** (the one number that decides): **undo rate** = deletes followed by a
successful Undo (`todo_undo_delete` with `result = restored`) divided by all deletes
(`todo_deleted`). Event names are from the [tracking plan](tracking-plan.md).

**Guardrail metrics** (numbers that must not get worse, even if the primary one improves):

| Guardrail | Why | Limit |
|---|---|---|
| "Could not undo." rate (`result = id_taken` or `no_access`) | A longer window gives more time for the list to change | Must not rise above 0.5 % of Undo presses |
| Re-created to-dos: a new to-do within 30 minutes after a delete in the same list, no Undo | A person who missed the window types it again by hand | Must not rise in B by more than 1 point |
| Deletes per active account per week | People should not delete less because they trust Undo less | Within 10 % of control |

## 5. Sample size and why one person cannot run this

The **sample size** is how many deletes we need before a difference is believable, not luck.

Assumptions (simulated): undo rate in A is about 4 %; we want to detect a drop to 2.5 % in B. With
the usual settings (5 % chance of a false alarm, 80 % chance to find a real effect), the standard
formula for two shares gives:

```
n per variant = (1.96 + 0.84)^2 x (0.04 x 0.96 + 0.025 x 0.975) / (0.04 - 0.025)^2
              = 7.84 x 0.0628 / 0.000225
              = about 2,190 deletes in each variant
```

So we need about **4,400 deletes** in total.

**Why the real app cannot run it.** The app has one real user, the owner, on one Mac. At a guess
of 3 deletes a day, 4,400 deletes take about four years. One person also cannot be split into two
random groups: every result would be about that one person's habits. For an app this size, the
honest method is to ask (see the user research notes) or to decide by reasoning, as the plan did.

## 6. Duration (simulated)

- Planned: 4 weeks, or until both variants have 2,190 deletes, whichever is later.
- No early stop for a "good" result. Looking at the result every day and stopping when it looks
  good gives false winners ("peeking").
- Early stop only if a guardrail breaks.

## 7. Results (simulated)

**These numbers are invented.** They show what a results section looks like.

| Variant | Deletes | Undone | Undo rate |
|---|---|---|---|
| A, 15 minutes | 2,195 | 90 | 4.10 % |
| B, 5 minutes | 2,190 | 57 | 2.60 % |
| Difference (A - B) | | | **1.5 points** |

**95 % confidence interval for the difference: 0.4 to 2.6 points.**

In plain words: a **confidence interval** is the range where the true difference probably is. If
we ran this same test many times, about 95 of 100 such ranges would contain the true difference.
Here the whole range is above zero, so the longer window really does help. But it may help only a
little (0.4 points) or a fair bit (2.6 points).

How it was computed: the standard error (the expected size of random wobble) is
`sqrt(0.041 x 0.959 / 2195 + 0.026 x 0.974 / 2190) = 0.0054`. The interval is
`1.5 +/- 1.96 x 0.54 = 1.5 +/- 1.1` points.

When Undo was pressed in A (simulated): 71 % within 1 minute, 18 % from 1 to 5 minutes, 11 % from
5 to 15 minutes. The 11 % is the group that B loses.

Guardrails (simulated): "Could not undo." was 0.2 % in A and 0.1 % in B (both under the limit).
Re-created to-dos were 0.9 points higher in B (inside the limit, but it points the same way as the
primary metric). Deletes per account per week did not change (-2 %).

## 8. Decision (simulated)

**Keep 15 minutes** (variant A). It recovers more deletes, and no guardrail got worse. The cost of
the longer window is small: the snapshot is one small JSON value in the session
(`request.session["undo_delete"]`).

Follow-up questions, not decided here: should "Clear completed" also get Undo (today it asks
first and cannot be undone)? Should the window reset when the person deletes again?

Real note: the code already uses 15 minutes, chosen in the plan without data. This simulated
result agrees with it; a real experiment could have disagreed.

## Related documents

- [Tracking plan](tracking-plan.md): the events this experiment needs (`todo_deleted`, `todo_undo_delete`)
- [Retrospective](../retrospectives/2026-10-16-first-week.md)
- [PRD](./prd.md)
- [User research notes](./user-research-notes.md)
- [UX test plan and findings](../design/ux-test-plan-and-findings.md)
- Plan: [`docs/plans/delete-undo.md`](../plans/delete-undo.md) (Undo after Delete, PR #51)
- Plan: [`docs/plans/clear-completed.md`](../plans/clear-completed.md) (PR #12)

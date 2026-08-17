---
name: operate
description: Run a released pipeline from its artifact reference, judge all five quality checks against the frozen contract, switch the live pointer only after a human approves, and sync the result back to the catalog.
---

# operate — run, gate, switch, roll back (G4)

This is the only phase a routine run enters. A pipeline that was released last
month and runs nightly does not replay G1–G3 — it is a flow of kind
`operation`, judged on G4 alone.

## Procedure

1. **Run from the artifact reference.** Dispatch `operations`. It deploys only
   job definitions the artifact actually contains; anything outside is refused
   and the refusal names which job, so whoever asked knows which artifact has
   to be rebuilt.

2. **New data goes to a new snapshot.** Never overwrite the live copy. The
   previous snapshot stays exactly as it was — that is what makes step 6
   possible at all.

3. **Stop early when there is nothing new.** If the upstream data has not
   changed, finish: no new version, no pointer change, and say "no change".
   Producing an identical snapshot under a fresh version number makes the
   history unreadable, and the history is what an incident is diagnosed from.

4. **Run the quality gate.** All **five** checks must be present — record count,
   anomaly rate, schema match, golden cases, query latency. A run missing one
   does not pass. A gate that quietly stopped checking something still reports
   green, and that is the most expensive failure available here.

   Thresholds come from the **frozen contract in the artifact reference**, never
   from the repository. A threshold anyone could edit is a pass mark the graded
   party sets for itself.

   **A failing check does not move the pointer.** The old version keeps serving.
   Report the failing check with its actual value and its threshold — the reader
   needs both to decide between fixing the pipeline and revisiting the number.

5. **The switch is a separate approval.** A passing gate switches nothing. The
   operations lead approves the pointer move, as its own decision, in their own
   inbox. Until then the pointer does not budge.

   Then END YOUR TURN.

6. **Rolling back** points the live pointer at the previous snapshot. It does
   **not** rebuild data and it does **not** revert code. Both take far longer
   than an incident allows, and neither is what anyone means by rollback.

7. **Sync the catalog.** Version, record counts, quality, lineage, run state —
   all five. This is what an operator reads at 3am, so a dropped field leaves
   them working from a half-truth. A retried sync lands on the same record.

   When the sync fails, say WHICH system was unreachable: the catalog or the
   scheduler. They ship together, which is exactly why conflating them sends the
   next person to the wrong dashboard while the incident continues.

## Alerting

Alert on repeated failure, on structurally destructive change, and on
permission errors. Escalate to the platform administrator **only** for platform
objects or policy changes — escalating routine job failures to them trains
everyone to ignore the channel that matters.

## Boundaries worth restating

- `operations` has no shell and no code-hosting credential. It cannot read or
  change source, and that is guaranteed by having no mechanism, not by a rule.
- Its scheduler credential runs jobs; it does not govern them. A platform
  operation attempted with it is refused, however co-located the scheduler is.
- It writes catalog assets for THIS pipeline only — including not for a
  pipeline whose name merely starts the same way.

---
name: plan-spec
description: Turn a data-pipeline requirement into a unified spec whose nine entry kinds are all filled, get it reviewed against the live catalog, and stop at G1 with the privilege list a human must approve.
---

# plan-spec — requirement to frozen spec (G1)

The spec is what every later phase is graded against, so a gap here does not
stay here: an unstated freshness becomes a quality threshold nobody agreed to,
and the first person to meet it is whoever is paged when the gate fails.

## The nine entry kinds

Every one must be non-empty before the spec can be reviewed:

1. **Sources** — where the data comes from, with the catalog identifier.
2. **Landing tables** — what is produced, with owner and Domain.
3. **Transformation rules** — what happens between the two.
4. **Freshness** — how current the output must be.
5. **Volume** — expected record counts and growth.
6. **Quality thresholds** — the five gate checks and their numbers.
7. **Acceptance cases** — what a correct result looks like, as testable cases.
8. **Lineage** — the upstream/downstream edges to record.
9. **Ownership** — who is accountable after this ships.

## Procedure

1. **Read the sources first.** Dispatch `architect` to read the catalog for the
   structure and ownership of every named source. A spec written before anyone
   looked describes an imagined schema.

2. **Ask about what is missing — do not fill it in.** Freshness and volume are
   the two that requesters most often omit and that you most often could guess.
   Guess neither. Ask, in one round, naming exactly what you need and why it
   matters. A plausible default here is indistinguishable from an agreed number
   three phases later, and nobody will remember which it was.

3. **Get the feasibility review.** Dispatch `governance` to read the live
   catalog and judge the spec implementable or not. When something is not
   possible on this platform, the conclusion says so with the reason and does
   NOT read as implementable. Do not design around a gap silently — the
   requester may drop the requirement once they know its cost.

4. **Revise in place.** When the review sends something back, the SAME spec is
   revised and the change is recorded. Never open a second document: two specs
   that disagree is worse than one that is wrong, because now nobody knows
   which one the build followed.

5. **Stop at G1.** Present the spec plus the list of platform privileges the
   work will need, and wait for the development lead. Do NOT generate the
   change-request package before that confirmation — the package is built from
   the frozen spec, and building it early means building it twice.

   Then END YOUR TURN. You are woken when they decide.

## What G1 does not mean

G1 confirms the spec, not the governance. The privileges listed at G1 are a
preview so the lead knows what they are committing to; nothing has been granted
and nothing has been created. That is phase 2's work, and it is done by a human.

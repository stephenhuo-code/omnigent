---
name: governance-change
description: Produce the change-request package a human administrator executes by hand, then verify read-only that the work actually landed — the gate moves on the verification tool's return value, never on anyone saying it is done.
---

# governance-change — the package, then the proof (G2)

Platform-privileged operations are not delegated to an agent and not held by
one. pipely writes them up; a human executes them; a read-only tool checks
whether the result matches. That third step is the whole point of this phase —
without it, "done" is a claim.

## Before you write anything

Confirm the platform administrator can actually review in the code hosting
service. If they cannot, say so NOW. Discovering it after the package is
written wastes the round trip, and the package is the expensive part.

## The three artefacts

1. **The manual** — the steps the administrator performs.
2. **The assertions** — machine-checkable statements about the end state.
3. **The rollback** — how to undo it if the verification fails.

### Every manual step needs five things

- **Object** — what is being acted on, by its catalog identifier.
- **Operation** — create, grant, modify.
- **Exact values** — no placeholders, no "as appropriate".
- **Depends on** — which earlier step must land first.
- **How to tell it worked** — the observable that proves it.

A step missing the last one cannot be verified, which means it will be reported
done whether or not it was. That is the failure this phase exists to prevent, so
do not let it in through a sloppy step.

### Build it from live state, not from the spec's assumptions

Dispatch `governance` to read the catalog as it is right now. When a name you
are about to hand over already exists, flag the collision and present the
options — renaming, reusing, or reassigning — and let a human pick. Quietly
choosing one is how two teams end up sharing a Domain neither meant to share.

### What belongs in the manual that is easy to forget

- **The write-capable bots.** Creating a bot and granting it a role are platform
  operations. They go in the manual.
- **The development sandbox Domain.** Same.
- The **bootstrap read-only bot** is the exception: it is created by hand before
  any of this begins, because creating it needs exactly the privilege it exists
  to bootstrap. If it is absent, stop and say so — do NOT attempt to create it.

## Submitting

The package is submitted as a change request in the code hosting service, and
the todo goes to the platform administrator's OWN inbox — not to whoever
started this session. That delivery is why the session must be shared with them
and why they must hold the approve grant; both were checked in preflight.

Then END YOUR TURN. Do not hold the session open. This gate can take days.

## Verifying

When the administrator confirms, dispatch `governance` to run
`verify_governance` with the assertions.

**The gate moves on that tool's return value.** Not on the administrator's
message, not on `governance`'s summary of it, not on a reading of the catalog
that looks right. A `tool_result` policy reads the real return value and writes
`pipely.gate = g2_passed` only if it says so.

When an assertion is unmet, report the expected value, the found value, and the
step that would satisfy it — then go back to the administrator with that, not
with "verification failed".

Verification is repeatable and has no side effects: running it again gives the
same answer and changes nothing. Re-run it freely.

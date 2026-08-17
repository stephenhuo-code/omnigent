---
name: build-release
description: Build the pipeline from the frozen spec with a test per acceptance case, open a pull request a human merges, and hand over an immutable artifact reference — never a branch and never a path.
---

# build-release — build, review, hand over (G3)

The output of this phase is not code. It is an **artifact reference**: an
immutable pointer to a verified version, with the thresholds and assertions
frozen alongside it. Everything downstream grades against that reference, so
anything mutable that sneaks into it silently breaks the grading.

## Procedure

1. **Build against the frozen spec.** Dispatch `architect` in its own worktree.
   Every acceptance case in the spec gets an automated test, and they are green
   before anything is handed over. The gate reads results, not intentions.

2. **Job definitions are code.** When scheduling is needed, the job definition
   goes into the SAME pull request as the pipeline and is reviewed with it. A
   job definition that arrives on its own is a job definition nobody reviewed,
   and it is the part that runs unattended at 3am.

3. **Sandbox writes only.** The architect's intermediate and result tables land
   for real, in the sandbox Domain. Writes to governed assets are refused by
   policy — if the work seems to need one, the spec is wrong or the Domain was
   never created, and both are worth stopping for.

4. **Open the pull request.** The architect pushes and opens it. **Nobody
   merges.** The agent's token has no merge permission, so an attempt fails at
   the hosting service rather than depending on anyone's restraint.

5. **Stop at G3.** Tests green and the pull request open is where you stop.
   Present the diff summary and the test results to the development lead and
   wait.

   Then END YOUR TURN.

6. **After the human merges and tags**, produce the artifact reference:
   - the **code tag** — immutable, naming the merged revision;
   - the **artifact digest** — the content hash of what was built;
   - the **frozen thresholds** — what the quality gate will grade against;
   - the **frozen assertions** — what governance verification will re-check.

## What must never cross the handoff

- **A branch name.** It keeps advancing after you wrote it down. The receiver
  fetches something you never verified, and nobody notices until release.
- **A workspace path.** It resolves only on the machine that wrote it.
- **Any writable source location.** If the receiver can change what they were
  given, the review that approved it approved something else.

The handoff check refuses all three at build time rather than catching them
later, and the artifact reference cannot be edited once built — the gate graded
against those values, and an editable reference lets a release be re-pointed
after approval without anyone re-approving it.

## Spec before implementation

If the architecture or scope changes mid-build, the spec changes FIRST. Refuse
to change the implementation while the spec still describes the old design. A
spec that trails the code is worse than no spec, because people trust it.

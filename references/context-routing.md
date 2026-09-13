# Context routing

Read once when starting this workflow. This is the canonical context-diet policy for both backends; it adapts the installed context-diet intent without requiring JM files or changing its toggles.

## Handoff

Send only the facts needed for one bounded outcome:

```text
Task: <id, role, objective>
Ownership: <worktree, base revision, owned paths or questions; read/write boundary>
Constraints: <relevant invariants, authorizations, stop condition; no delegation>
Inputs: <smallest authoritative non-repository facts or upstream artifact pointers>
Acceptance: <observable outcome and required proof>
Return: <status, concise result, changed paths, evidence pointers, unresolved gaps>
```

Use fresh context (`fork_turns: "none"` for native workers; no continuation flags for agy). Workers discover repository details themselves, obey applicable repository instructions, and consult CodeGraph first only where an index exists. Do not copy parent transcripts, source dumps, all sibling reports, or stable orchestration instructions into worker prompts.

Pointers must be accessible to the receiving worker. When correctness depends on an unavailable fact, retrieve or pass that exact fact rather than guessing. Include necessary acceptance criteria and invariants even when they cost context. A local artifact is not a promise of cross-session memory.

## Root state and returns

Keep a compact ledger: task id, role/backend/model, ownership/base, state, result artifact, acceptance gaps, retry count. Preserve decisions and invariants once. Retain full commands, stdout/stderr, diffs, and long research in task artifacts, outside the prompt and version control by default.

Worker returns target a short summary plus changed paths and evidence pointers. Each check identifies the command, target/revision, exit status, result, and coverage gap. A summary cap must not hide unresolved blockers; spill detail into a referenced artifact. Load a log excerpt only when it resolves a decision or a failed check. Do not reread all successful work at every phase.

Provider usage metadata is optional. Missing counters stay unknown; do not estimate exact tokens saved from prompt lengths. To evaluate savings, compare recorded provider usage and accepted outcomes across similar tasks, including repair and review cost.

## Retry and final review

Retry handoff: failed task id, first failure, smallest relevant evidence, owned scope, unchanged invariants, and proof to rerun. Reuse its worker when supported, within the one-retry limit; do not resend the entire original conversation.

Final review handoff: objective, acceptance, base revision, integrated worktree/head, changed paths, and proof pointers. Use a fresh Luna with no implementation transcript or prior verdict. It reads the complete current diff independently, follows references only as needed, and returns findings with file/line evidence plus a verdict and proof gaps. Any repair receives a new fresh review.

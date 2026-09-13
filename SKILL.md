---
name: dynamic-workflows
description: Orchestrate bounded Luna and Antigravity workers with minimal context. Use when the user requests dynamic workflows, subagents, or multi-agent orchestration.
---

# Dynamic Workflows

The model in the current chat stays the orchestrator. Luna is the primary executor; Antigravity (`agy`) handles useful supporting work. This skill is a candidate replacement for JM, not an installer or a global workflow toggle.

## Start

1. Establish the objective, owned scope, invariants, acceptance evidence, and stop conditions. Honor the active repository workflow; when JM remains mandatory, use it and treat this skill as design material until the user explicitly changes that policy. Installing or reading this skill changes no other skill, setting, or sentinel.
2. Read [context-routing.md](references/context-routing.md) once for the minimal handoff and root ledger. This policy is always on within this workflow and has no dependency on JM or its context-diet toggle.
3. Choose the smallest useful graph using the roles below. Read [provider-contract.md](references/provider-contract.md) only for the backends being dispatched. If saving or interpreting a workflow artifact, also read [workflow-language.md](references/workflow-language.md).
4. Publish one plan item per phase, with one in progress. Dispatch bounded tasks, validate their evidence, integrate, then obtain fresh Luna review of the complete integrated change.
5. Accept only after relevant checks and final review succeed, or report the exact remaining blocker. Return the result and evidence gaps; the orchestrator owns the final answer.

## Roles

| Role | Default worker | Boundary |
| --- | --- | --- |
| Orchestration | Current chat model | Scope, decisions, dispatch, integration, conflicts, acceptance |
| Implementation and repair | Luna | One owned implementation unit and its proof |
| Investigation and verification | Antigravity | Bounded reproduction, source research, check execution, or critique when it saves useful work |
| Final review | Fresh Luna | Independently read the complete current diff and verify acceptance evidence |

Role, backend, and model are distinct. Use `codex-native` for Luna and `agy` for the external CLI. Discover actual capabilities before promising delegation. A different chat host remains the orchestrator but must expose a verified Luna adapter; the bundled Python runner cannot supply native Luna. Report a missing adapter rather than silently changing models.

Route substantial supporting tasks to Antigravity by default when available. Skip redundant worker stages for tiny changes. Secondary Antigravity implementation is an explicit task-level routing choice, with its own write scope; Luna remains the default. An Antigravity critique does not replace fresh Luna final review.

## Execution boundaries

- Only the orchestrator dispatches workers. Each worker receives its role and ownership boundary and returns directly; it does not recursively delegate or load the parent orchestration policy.
- Bound parallelism by the host's remaining slots and external process limit, with at most five active workers total by default. Run parallel branches only when their inputs and ownership are independent. Use isolated worktrees for concurrent writers; coordinate shared resources separately.
- Integrate only completed worker changes while preserving existing user work. Resolve conflicts before review. Any subsequent edit invalidates the review and requires another fresh Luna review of the final diff.
- Treat a process completion status separately from task acceptance. Required proof must show the requested outcome on the reviewed revision. A missing or denied check leaves that acceptance item unverified.
- Honor enabled documentation/evidence policies without expanding into unrelated cleanup. No cross-session resume, enforced sandbox, exact token accounting, or savings claim without supporting runtime evidence.

## Failure and cancellation

A failed branch stops only its dependent stages. Keep independent branches running when their contracts remain valid. Return explicit `blocked`, `error`, or `canceled` results instead of losing failure details as `null`.

For a repairable failure, give the same worker one focused retry using the context-routing contract. Inspect partial changes before retrying execution; never automatically replay a task that may have written files. A repeated failure returns to the orchestrator for a decision. Authentication, quota, unsupported capabilities, and missing authorization are blockers, not retry loops. Model or billing fallback is a visible orchestrator decision within the user's authorization.

On cancellation, interrupt every native worker and terminate owned external process trees, preserving available logs and marking unfinished branches canceled. A restart is a fresh dispatch unless the host proves usable session state.

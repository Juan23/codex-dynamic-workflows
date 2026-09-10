---
name: dynamic-workflows
description: Design and execute bounded, phased Codex multi-agent workflows with agent, parallel, pipeline, phase, structured-result, cancellation, and synthesis semantics. Use only when the user explicitly asks for a dynamic workflow, workflow script, swarm, fan-out, parallel agents, subagents, or multi-agent orchestration; do not auto-trigger merely because a task is large or complex.
---

# Dynamic Workflows

Turn a rough request into a small orchestration program, execute it with Codex's native collaboration tools, and synthesize an evidence-backed result.

## Guardrails

- Treat explicit invocation as authorization to delegate only the work already in scope.
- Keep the root agent responsible for scope, acceptance criteria, integration, and the final answer.
- Use collaboration subagents, not user-visible Codex tasks, unless the user explicitly requests separate tasks.
- Keep at most five subagents active concurrently; the root agent occupies the remaining slot.
- Preserve user changes and assign non-overlapping write scopes. Use read-only agents for research and review.
- Never claim that the workflow artifact is executed by Node or securely sandboxed. Codex interprets it and maps it to native tools.
- Never claim cross-session resume or exact token accounting. Report these as unavailable unless the current harness proves otherwise.

## Run a workflow

1. Define a contract with the objective, in-scope inputs, exclusions, deliverables, evidence required, and stop conditions.
2. Choose the smallest useful graph. Prefer two or three workers and one synthesis pass; use five workers only when the tracks are independent.
3. Draft the workflow using the language in [references/workflow-language.md](references/workflow-language.md). Keep it internal unless the user asks to see, save, or reuse it.
4. Publish a plan with one item per phase and exactly one phase in progress.
5. Execute each phase using the mappings below. Send a concise commentary update at phase boundaries.
6. Validate every worker result against its contract. Retry a malformed result once with the missing fields named; otherwise record `null` and continue when safe.
7. Run an independent synthesis or verification task when two or more worker results affect the conclusion.
8. Return the requested deliverable plus a compact status for each requested outcome. Name any unverified gap.

## Map the workflow language to Codex

- `phase(title)`: update the plan so the named phase is in progress.
- `agent(prompt, opts)`: spawn one bounded subagent with a unique task name and the contract in `opts`.
- `parallel(thunks)`: spawn independent thunks without awaiting between them, then wait until every branch completes or needs attention. Preserve input order in the result array.
- `pipeline(items, ...stages)`: process items concurrently, but run stages sequentially for each item. Use a fresh agent per stage unless continuity is part of the contract.
- `log(message)`: send one short progress update; do not narrate unchanged waits.
- `args`: treat the user's supplied JSON-compatible value as immutable workflow input.
- `budget`: enforce explicit limits through worker count, phase count, retry count, and any harness goal budget the user requested.

## Construct every agent task

Include these fields in the subagent message:

```text
Objective: <one bounded outcome>
Scope: <paths, sources, or questions owned by this worker>
Inputs: <only the context required to work independently>
Constraints: <read-only or exact write boundary; safety limits>
Deliverable: <required headings or JSON-compatible shape>
Evidence: <commands, files, lines, URLs, or outputs that must support claims>
Stop when: <completion condition or blocker condition>
```

Ask workers to return results, not instructions for the root agent to rediscover their work. Never delegate the final user-facing answer.

## Handle failures and cancellation

- On an agent failure, capture the location, cause, and available evidence; represent its value as `null`.
- In `parallel`, allow independent branches to finish after one branch fails.
- In `pipeline`, stop only the failed item's remaining stages unless its failure invalidates the whole workflow.
- When the user cancels or replaces the request, interrupt every active subagent and mark unfinished branches skipped.
- After three repeated failures, stop retrying and name the doubtful assumption.

## Finish the run

Report the result first. Then show a compact phase/agent status only when it helps the user verify the work. Distinguish performed actions, verified outcomes, failures, and unverified claims.

Save a reusable workflow only when requested. Write it under `.codex/workflows/<short-name>.workflow.js` and keep it deterministic: no imports, filesystem access, network access, current time, randomness, or hidden side effects.

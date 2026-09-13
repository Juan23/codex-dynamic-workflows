# Workflow language

This JavaScript-shaped notation is an orchestration artifact interpreted by the current chat model. It is not executable JavaScript, a Node runtime, or a sandbox. Only save a requested reusable workflow, under `.codex/workflows/<name>.workflow.js`.

## Semantics

| Form | Meaning |
| --- | --- |
| `phase(title)` | Move the corresponding plan phase to in progress. |
| `agent(prompt, opts)` | Dispatch one bounded worker via its backend and validate its result. |
| `parallel(thunks)` | Dispatch independent tasks within the shared worker limit; preserve result order. |
| `pipeline(items, ...stages)` | Keep stages sequential per item; stop failed items' dependent stages. |
| `log(message)` | Send a meaningful progress update. |
| `args`, `budget` | Immutable task inputs and explicit worker/phase/retry limits. Token limits require actual host support. |

Every agent returns a structured status and evidence or an explicit failure; legacy `null` results are normalized to `error` before dependent dispatch. Fresh tasks are the default. A stage consumes only its required upstream result or artifact pointers.

## Agent options

- Identity: `label`, `role` (`implement`, `investigate`, `verify`, `review`), `backend` (`codex-native`, `agy`), and explicit `model` selected under the provider contract; `effort` only when supported.
- Ownership: `scope`, `worktree`, `base`, `mode` (`read-only`, `workspace-write`), and required isolation. Mode describes a requirement, not enforcement; the adapter must meet it or return `blocked`.
- Context: `input`, `invariants`, `acceptance`, `output` shape, and `stopWhen`. Apply [context routing](context-routing.md), rather than serializing the parent context.
- Bounds: `timeoutSeconds`, `retryLimit` (at most one), and an artifact directory unique to the task. The orchestrator enforces shared concurrency and cancellation.

Example, interpreted rather than run:

```js
export const meta = {
  name: "bounded_fix",
  phases: [{ title: "Implement" }, { title: "Review" }],
};
phase("Implement");
const change = await agent(args.task, {
  label: "implement fix", role: "implement", backend: "codex-native",
  model: "gpt-5.6-luna", mode: "workspace-write",
  worktree: args.worktree, base: args.base, scope: args.scope,
  acceptance: args.acceptance,
});
if (change.status !== "succeeded") return change;
// The orchestrator integrates before providing the final head to review.
phase("Review");
const review = await agent("Review the complete integrated diff independently.", {
  label: "final review", role: "review", backend: "codex-native",
  model: "gpt-5.6-luna", mode: "read-only",
  input: { base: args.base, head: args.integratedHead, proof: change.evidence },
  acceptance: args.acceptance,
});
return { change, review };
```

External workers use `backend: "agy"` and a discovered, pinned model. The orchestrator translates the task into one Python runner invocation from [provider-contract.md](provider-contract.md); the DSL itself never launches subprocesses.

Saved artifacts contain no imports, filesystem/network calls, environment reads, current time, randomness, or hidden side effects. These belong to verified backend execution, with their resulting facts passed through `args` or the minimal task contract.

# Workflow language

Use this JavaScript-shaped DSL as an orchestration artifact. Codex interprets it and calls native collaboration tools; do not execute it with Node.

## Required shape

```js
export const meta = {
  name: "inspect_project",
  description: "Inspect the project and synthesize its architecture",
  phases: [{ title: "Scan" }, { title: "Analyze" }],
};

phase("Scan");
const scans = await parallel([
  () => agent("Map entry points and module boundaries.", {
    label: "module map",
    scope: ["src"],
    mode: "read-only",
    output: { summary: "string", evidence: "array" },
  }),
  () => agent("Map tests, build commands, and quality gates.", {
    label: "test map",
    scope: ["package.json", "tests"],
    mode: "read-only",
    output: { summary: "string", evidence: "array" },
  }),
]);

phase("Analyze");
const result = await agent("Synthesize the supplied scans; flag disagreements.", {
  label: "synthesis",
  input: scans,
  mode: "read-only",
  output: { verdict: "string", findings: "array", gaps: "array" },
});

return { ok: result !== null, result };
```

## Globals

| Global | Semantics |
| --- | --- |
| `agent(prompt, opts)` | Run one isolated, bounded subagent and return its result or `null`. |
| `parallel(thunks)` | Run independent agent thunks concurrently and preserve result order. |
| `pipeline(items, ...stages)` | Fan items out while keeping stages sequential per item. |
| `phase(title)` | Mark a user-visible execution boundary. |
| `log(message)` | Emit a concise progress event. |
| `args` | Immutable JSON-compatible workflow input. |
| `budget` | Logical limits for agents, phases, retries, and requested token budget. |

## Agent options

- `label`: unique two-to-five-word task label.
- `scope`: exact files, directories, sources, or questions owned by the worker.
- `mode`: `read-only` or `workspace-write`; default to `read-only`.
- `input`: JSON-compatible upstream results required by this task.
- `output`: required JSON-compatible result shape or named Markdown headings.
- `model` and `effort`: set only when the user or active harness explicitly permits an override.
- `isolation`: request a worktree only when independent edits require it and the harness supports it.

## Determinism

Keep saved workflows reproducible. Disallow imports, `require`, filesystem or network calls, `Date`, randomness, environment variables, subprocesses, and computed metadata. Put all external information in `args` or agent prompts.

## Pipeline example

```js
phase("Review");
const reviewed = await pipeline(
  args.files,
  (file) => agent(`Inspect ${file}`, { label: `inspect ${file}`, scope: [file] }),
  (finding, file) => finding === null ? null : agent(
    `Verify this finding for ${file}`,
    { label: `verify ${file}`, scope: [file], input: finding },
  ),
);

return reviewed;
```

Treat each stage as a fresh task by default. Pass only the prior result and original item needed by the next stage.

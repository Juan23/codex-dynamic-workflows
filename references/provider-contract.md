# Provider contract

The orchestrator selects a backend per bounded task and records the result in a root ledger.

| Backend | Role | Availability | Model rule |
| --- | --- | --- | --- |
| `codex-native` | Luna implementation or fresh Luna review | Supplied by the Codex host | Request `gpt-5.6-luna` with `fork_turns: none`; a standalone runner returns `blocked` |
| `agy` | Opt-in investigation, check, or critique | `agy` executable plus cached account auth | Omit `--model` to use the subscription account's configured model; set it only when explicitly requested |

Each task starts with a fresh minimal handoff:

```text
Objective: one bounded outcome
Scope: owned paths or authoritative questions
Invariants: facts that must remain true
Proof: commands, files, or outputs required
Stop when: completion or blocker condition
```

The runner emits JSON with `status`, `provider`, `model`, `summary`, `evidence`, `attempts`, and optional `usage` and `log_path`. `blocked` means capability, auth, or permission prevented dispatch; it is never success. `canceled` means timeout or explicit cancellation. Full stdout/stderr and the command are stored at `log_path`.

`agy` headless mode uses `-p` and `--output-format json`; it reads cached credentials and reports authentication errors. Permission enforcement stays enabled. The workflow artifact is interpreted by the orchestrator and is not executed as JavaScript by Node.
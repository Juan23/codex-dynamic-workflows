"""Bounded provider adapters for dynamic-workflows.

The workflow DSL remains declarative: this module runs one already-dispatched
task and returns evidence. It never interprets workflow JavaScript or delegates
to another worker.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TERMINAL = {"succeeded", "blocked", "error", "canceled"}


@dataclass
class Outcome:
    status: str
    provider: str
    model: str | None
    summary: str
    evidence: list[str]
    log_path: str | None = None
    usage: dict[str, Any] | None = None
    attempts: int = 1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _log(artifact_dir: Path, provider: str, payload: dict[str, Any]) -> str:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{provider}-{int(time.time() * 1000)}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return str(path)


def _capabilities(provider: str, model: str | None) -> dict[str, Any]:
    if provider == "codex-native":
        return {
            "provider": provider,
            "available": False,
            "reason": "native collaboration must be supplied by the Codex host",
            "model": model or "gpt-5.6-luna",
            "auth": "host-managed",
        }
    configured = os.environ.get("AGY_BIN", "agy")
    executable = shutil.which(configured) or (configured if Path(configured).is_file() else None)
    return {
        "provider": provider,
        "available": executable is not None,
        "executable": executable,
        "model": model,
        "auth": "cached agy credentials; checked by execution",
    }


def capabilities(provider: str, model: str | None = None) -> dict[str, Any]:
    if provider not in {"codex-native", "agy"}:
        raise ValueError(f"unsupported provider: {provider}")
    return _capabilities(provider, model)


def run_task(
    *,
    provider: str,
    prompt: str,
    model: str | None = None,
    timeout: float = 120,
    retries: int = 0,
    artifact_dir: str | os.PathLike[str] = ".workflow-artifacts",
    cwd: str | os.PathLike[str] | None = None,
    cancel: bool = False,
    dangerously_skip_permissions: bool = False,
) -> Outcome:
    """Run one bounded task; retry only transient process failures."""
    if not prompt.strip():
        raise ValueError("prompt must be non-empty")
    if timeout <= 0 or retries < 0:
        raise ValueError("timeout must be positive and retries cannot be negative")
    if cancel:
        return Outcome("canceled", provider, model, "canceled before dispatch", [], attempts=0)
    if provider == "codex-native":
        return Outcome(
            "blocked", provider, model or "gpt-5.6-luna",
            "native Codex Luna capability is unavailable to this standalone runner",
            ["host must dispatch via native spawn_agent(model=gpt-5.6-luna)"],
            attempts=0,
        )
    if provider != "agy":
        raise ValueError(f"unsupported provider: {provider}")
    if dangerously_skip_permissions:
        return Outcome("blocked", provider, model, "permission bypass is not supported", [], attempts=0)

    configured = os.environ.get("AGY_BIN", "agy")
    executable = shutil.which(configured) or (configured if Path(configured).is_file() else None)
    if executable is None:
        return Outcome("blocked", provider, model, "agy executable is unavailable", [], attempts=0)

    # These are documented headless flags. Model is optional so subscription
    # selection remains the user's agy account configuration, not an API key.
    command = [executable, "-p", prompt, "--output-format", "json"]
    if executable.lower().endswith((".py", ".pyw")):
        command = [sys.executable, executable, "-p", prompt, "--output-format", "json"]
    if model:
        command.extend(["--model", model])
    workdir = str(cwd) if cwd else None
    last: Outcome | None = None
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            process = subprocess.run(command, cwd=workdir, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            log_path = _log(Path(artifact_dir), provider, {"command": command, "stdout": exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout, "stderr": exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr, "status": "canceled", "reason": "timeout"})
            last = Outcome("canceled", provider, model, f"timed out after {timeout:g}s", ["timeout"], log_path, attempts=attempt + 1)
            break
        except OSError as exc:
            last = Outcome("error", provider, model, str(exc), [], attempts=attempt + 1)
            break

        raw = process.stdout.strip()
        stderr = process.stderr.strip()
        log_path = _log(Path(artifact_dir), provider, {"command": command, "stdout": raw, "stderr": stderr, "returncode": process.returncode, "elapsed_seconds": time.monotonic() - started})
        if process.returncode != 0:
            text = (stderr or raw or f"agy exited {process.returncode}").lower()
            status = "blocked" if any(word in text for word in ("authentication", "permission", "denied", "login", "credential")) else "error"
            last = Outcome(status, provider, model, stderr or raw or "agy failed", [f"exit code {process.returncode}"], log_path, attempts=attempt + 1)
            if status == "blocked":
                break
            continue
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            last = Outcome("error", provider, model, "agy returned invalid JSON", ["stdout is not a JSON envelope"], log_path, attempts=attempt + 1)
            continue
        if not isinstance(envelope, dict):
            last = Outcome("error", provider, model, "agy returned a non-object JSON envelope", ["JSON envelope is not an object"], log_path, attempts=attempt + 1)
            break
        denial = (stderr or "").lower()
        if any(word in denial for word in ("permission denied", "approval required", "access denied")):
            return Outcome("blocked", provider, model, stderr, ["permission enforcement denied the task"], log_path, attempts=attempt + 1)
        status = str(envelope.get("status", "")).lower()
        if status != "success":
            last = Outcome("error", provider, model, envelope.get("error", "agy returned a non-success status"), ["JSON envelope status is not SUCCESS"], log_path, envelope.get("usage"), attempt + 1)
            continue
        return Outcome("succeeded", provider, model, envelope.get("response", "").strip(), ["agy JSON envelope status=SUCCESS"], log_path, envelope.get("usage"), attempt + 1)
    assert last is not None
    return last


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one bounded dynamic-workflows provider task")
    parser.add_argument("command", choices=["capabilities", "run"])
    parser.add_argument("--provider", choices=["codex-native", "agy"], required=True)
    parser.add_argument("--model")
    parser.add_argument("--prompt")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--artifact-dir", default=".workflow-artifacts")
    parser.add_argument("--cwd")
    args = parser.parse_args(argv)
    if args.command == "capabilities":
        print(json.dumps(capabilities(args.provider, args.model), indent=2))
        return 0
    if args.prompt is None:
        parser.error("--prompt is required for run")
    result = run_task(provider=args.provider, prompt=args.prompt, model=args.model, timeout=args.timeout, retries=args.retries, artifact_dir=args.artifact_dir, cwd=args.cwd)
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.status in {"succeeded", "blocked", "canceled"} else 1


if __name__ == "__main__":
    sys.exit(main())

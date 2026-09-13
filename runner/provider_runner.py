"""Run one external worker. The orchestrator interprets the workflow DSL."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Outcome:
    status: str
    provider: str
    model: str | None
    summary: str
    evidence: list[str] = field(default_factory=list)
    log_path: str | None = None
    usage: dict[str, Any] | None = None
    attempts: int = 0

    def as_dict(self):
        return asdict(self)


def _executable():
    configured = os.environ.get("AGY_BIN", "agy")
    located = shutil.which(configured)
    if not located and Path(configured).is_file():
        located = str(Path(configured).resolve())
    return located


def _prefix(executable):
    return [sys.executable, executable] if executable.endswith((".py", ".pyw")) else [executable]


def _spawn_options():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def _stop_tree(process):
    """Stop owned descendants as well as their parent; return cleanup evidence."""
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=3)
                return "parent terminated or exited; descendant cleanup unverified"
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
        return "process-tree termination completed"
    except ProcessLookupError:
        return "process already exited; descendant cleanup unverified"
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is None:
            process.kill()
        return "termination attempted; process-tree cleanup unverified"


def capabilities(provider, model=None):
    if provider == "codex-native":
        return {"provider": provider, "available": False,
                "reason": "Luna requires the host native collaboration tool; this runner cannot supply it"}
    if provider != "agy":
        raise ValueError("unsupported provider")
    executable = _executable()
    return {"provider": provider, "available": bool(executable), "executable": executable,
            "model": model, "auth": "unverified until an account-backed run succeeds",
            "read_only_enforced": False, "modes": ["workspace-write"],
            "note": "Executable discovery only. Check installed --help and models before first use."}


def _blocked_diagnostic(text):
    return any(term in text.lower() for term in (
        "authentication", "credential", "sign in", "login", "log in", "quota",
        "rate limit", "rate_limit", "permission", "soft-denied", "soft denied",
        "approval", "access denied", "not allowed", "unknown model", "model not found",
    ))


def _account_blocker():
    # Do not change auth or send requests through a user-configured API-key provider.
    settings = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
    try:
        config = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
        if not isinstance(config, dict):
            return "agy settings are not a JSON object"
        if config.get("modelProvider", "antigravity") not in ("antigravity", None, ""):
            return "agy uses a custom/API model provider; configure subscription account auth explicitly"
        if config.get("useG1Credits") is True:
            return "agy credit overage is enabled; disable it explicitly for subscription-quota-only execution"
    except (OSError, ValueError):
        return "cannot validate agy account settings"
    return None


def run_task(*, provider, prompt, model=None, timeout=120, retries=0,
             artifact_dir=".workflow-artifacts", cwd=None, cancel=False,
             dangerously_skip_permissions=False, mode="read-only"):
    if provider not in ("codex-native", "agy"):
        raise ValueError("unsupported provider")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be non-empty text")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    result = Outcome("blocked", provider, model, "")
    if cancel:
        result.status, result.summary = "canceled", "canceled before dispatch"
        return result
    if provider == "codex-native":
        result.summary = "dispatch Luna with the host native collaboration tool"
        return result
    if retries != 0:
        result.summary = "automatic task replay is disabled; the orchestrator owns focused retries"
        return result
    if dangerously_skip_permissions:
        result.summary = "permission bypass is unsupported"
        return result
    if mode != "workspace-write":
        result.summary = "this adapter cannot enforce read-only execution; a plan prompt is not a sandbox"
        return result
    if not model or not isinstance(model, str):
        result.summary = "pin a model from the installed agy model list"
        return result
    if cwd is None or not Path(cwd).is_dir():
        result.summary = "provide an existing task workspace with --cwd"
        return result
    executable = _executable()
    if not executable:
        result.summary = "agy executable unavailable"
        return result
    account_blocker = _account_blocker()
    if account_blocker:
        result.summary = account_blocker
        return result

    task_dir = Path(artifact_dir).resolve() / ("agy-" + uuid.uuid4().hex)
    task_dir.mkdir(parents=True)
    stdout_path, stderr_path = task_dir / "stdout.txt", task_dir / "stderr.txt"
    meta_path = task_dir / "result.json"
    result.log_path = str(meta_path)
    command = _prefix(executable) + ["-p", prompt, "--output-format", "json", "--model", model]
    process = None
    returncode = None
    try:
        # File-backed output preserves partial logs and avoids inherited pipe deadlocks.
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            process = subprocess.Popen(command, cwd=str(Path(cwd).resolve()), stdout=out,
                                       stderr=err, **_spawn_options())
            result.attempts = 1
            try:
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result.status, result.summary = "canceled", f"timed out after {timeout:g}s"
                result.evidence.append(_stop_tree(process))
            except KeyboardInterrupt:
                result.status, result.summary = "canceled", "interrupted by caller"
                result.evidence.append(_stop_tree(process))
    except OSError as exc:
        result.status, result.summary = "error", str(exc)
    if returncode is not None:
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        result.evidence.append(f"agy exit code {returncode}; workspace {Path(cwd).resolve()}")
        if _blocked_diagnostic(stderr):
            result.status, result.summary = "blocked", stderr.strip()[:2000]
        elif returncode and _blocked_diagnostic(stdout):
            result.status, result.summary = "blocked", stdout.strip()[:2000]
        else:
            try:
                envelope = json.loads(stdout)
                if not isinstance(envelope, dict):
                    raise ValueError("envelope must be an object")
                state = envelope.get("status")
                response = envelope.get("response")
                if state == "SUCCESS" and returncode == 0 and not envelope.get("error"):
                    if not isinstance(response, str) or not response.strip():
                        raise ValueError("successful response must be non-empty text")
                    result.status = "succeeded"
                    result.summary = response[:2000] + (" [full response in artifact]" if len(response) > 2000 else "")
                    result.evidence.append("agent run completed; task acceptance still requires independent proof")
                else:
                    detail = str(envelope.get("error") or state or "missing status")
                    result.status = ("canceled" if state in ("CANCELED", "INTERRUPTED") else
                                     "blocked" if state == "WAITING" or _blocked_diagnostic(detail) else "error")
                    result.summary = detail[:2000]
                if isinstance(envelope.get("usage"), dict):
                    result.usage = envelope["usage"]
            except (ValueError, TypeError) as exc:
                result.status, result.summary = "error", f"invalid agy result: {exc}"
    meta_path.write_text(json.dumps({
        "outcome": result.as_dict(), "command": command, "cwd": str(Path(cwd).resolve()),
        "returncode": returncode, "stdout_path": str(stdout_path), "stderr_path": str(stderr_path),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capabilities", "run"))
    parser.add_argument("--provider", choices=("codex-native", "agy"), required=True)
    parser.add_argument("--model")
    prompts = parser.add_mutually_exclusive_group()
    prompts.add_argument("--prompt")
    prompts.add_argument("--prompt-file", type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--artifact-dir", default=".workflow-artifacts")
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--mode", choices=("read-only", "workspace-write"), default="read-only")
    args = parser.parse_args(argv)
    if args.command == "capabilities":
        print(json.dumps(capabilities(args.provider, args.model)))
        return 0
    prompt = args.prompt_file.read_text(encoding="utf-8-sig") if args.prompt_file else args.prompt
    try:
        outcome = run_task(provider=args.provider, prompt=prompt, model=args.model,
                           timeout=args.timeout, artifact_dir=args.artifact_dir, cwd=args.cwd, mode=args.mode)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(outcome.as_dict(), ensure_ascii=False))
    return {"succeeded": 0, "blocked": 2, "error": 1, "canceled": 130}[outcome.status]


if __name__ == "__main__":
    sys.exit(main())

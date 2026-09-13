"""Exercise real subprocess boundaries with a deterministic fake CLI; no model quota used."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from runner.provider_runner import main, run_task


class ProviderRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fake = self.root / "fake_agy.py"
        self.env = patch.dict(os.environ, {"AGY_BIN": str(self.fake)})
        self.env.start()
        self.addCleanup(self.env.stop)
        account = patch("runner.provider_runner._account_blocker", return_value=None)
        account.start()
        self.addCleanup(account.stop)

    def run_fake(self, source, **overrides):
        self.fake.write_text(source, encoding="utf-8")
        args = dict(provider="agy", prompt="bounded task", model="test-model",
                    cwd=self.root, mode="workspace-write", artifact_dir=self.root / "logs")
        args.update(overrides)
        return run_task(**args)

    def envelope(self, value, **overrides):
        return self.run_fake("import json\nprint(" + repr(json.dumps(value)) + ")\n", **overrides)

    def test_success_preserves_full_output_but_bounds_handoff(self):
        response = "x" * 5000
        result = self.envelope({"status": "SUCCESS", "response": response, "usage": {"tokens": 9}})
        self.assertEqual(result.status, "succeeded")
        self.assertLess(len(result.summary), 2100)
        artifact = json.loads(Path(result.log_path).read_text())
        self.assertEqual(json.loads(Path(artifact["stdout_path"]).read_text())["response"], response)
        self.assertEqual(artifact["command"][-2:], ["--model", "test-model"])
        self.assertNotIn("--dangerously-skip-permissions", artifact["command"])
        self.assertEqual(result.usage, {"tokens": 9})

    def test_soft_denial_overrides_success_exit(self):
        result = self.run_fake("import sys\nprint('Tool command was soft-denied: permission required', file=sys.stderr)\nprint('{\"status\":\"SUCCESS\",\"response\":\"done\"}')")
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.attempts, 1)

    def test_auth_failure_is_blocked(self):
        result = self.run_fake("import sys\nprint('Please sign in to continue', file=sys.stderr)\nsys.exit(1)")
        self.assertEqual(result.status, "blocked")

    def test_malformed_envelopes_are_errors(self):
        for value in (None, [], {"status": "SUCCESS", "response": None},
                      {"status": "SUCCESS", "response": {}}, {"response": "no status"}):
            with self.subTest(value=value):
                self.assertEqual(self.envelope(value).status, "error")

    def test_nonzero_exit_never_accepts_success_envelope(self):
        result = self.run_fake("import sys\nprint('{\"status\":\"SUCCESS\",\"response\":\"done\"}')\nsys.exit(1)")
        self.assertEqual(result.status, "error")

    def test_error_field_prevents_success(self):
        result = self.envelope({"status": "SUCCESS", "response": "done", "error": "failure"})
        self.assertEqual(result.status, "error")

    def test_terminal_statuses(self):
        for state, expected in (("WAITING", "blocked"), ("CANCELED", "canceled"),
                                ("INTERRUPTED", "canceled"), ("RUNNING", "error"), ("INVALID", "error")):
            with self.subTest(state=state):
                self.assertEqual(self.envelope({"status": state}).status, expected)

    def test_missing_capabilities_fail_before_execution(self):
        self.fake.write_text("raise RuntimeError('must not execute')")
        for kwargs in ({"mode": "read-only"}, {"model": None}, {"cwd": None},
                       {"retries": 1}, {"dangerously_skip_permissions": True}):
            with self.subTest(kwargs=kwargs):
                result = self.run_fake("raise RuntimeError('must not execute')", **kwargs)
                self.assertEqual(result.status, "blocked")
                self.assertEqual(result.attempts, 0)
        self.assertEqual(run_task(provider="codex-native", prompt="inspect").status, "blocked")
        self.assertEqual(run_task(provider="agy", prompt="inspect", cancel=True).status, "canceled")

    def test_timeout_preserves_partial_logs(self):
        result = self.run_fake("import time\nprint('partial evidence', flush=True)\ntime.sleep(10)", timeout=0.3)
        self.assertEqual(result.status, "canceled")
        artifact = json.loads(Path(result.log_path).read_text())
        self.assertIn("partial evidence", Path(artifact["stdout_path"]).read_text())

    def test_timeout_stops_descendant_writes(self):
        marker = self.root / "descendant.txt"
        child = "import time; from pathlib import Path; time.sleep(1.2); Path(" + repr(str(marker)) + ").write_text('survived')"
        source = "import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', " + repr(child) + "])\ntime.sleep(10)"
        result = self.run_fake(source, timeout=0.3)
        self.assertEqual(result.status, "canceled")
        time.sleep(1.4)
        self.assertFalse(marker.exists(), "a child process survived cancellation")

    def test_account_provider_and_overage_are_not_changed_or_used(self):
        with patch("runner.provider_runner._account_blocker", return_value="API provider configured"):
            result = self.run_fake("raise RuntimeError('must not execute')")
        self.assertEqual(result.attempts, 0)
        self.assertEqual(result.status, "blocked")

    def test_cli_reports_blocked_with_nonzero_exit(self):
        with patch("builtins.print"):
            self.assertEqual(main(["run", "--provider", "codex-native", "--prompt", "inspect"]), 2)

    def test_invalid_timeout(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run_task(provider="agy", prompt="inspect", timeout=value)


if __name__ == "__main__":
    unittest.main()

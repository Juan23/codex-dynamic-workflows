import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from runner.provider_runner import run_task


class ProviderRunnerTests(unittest.TestCase):
    def test_native_is_explicitly_blocked(self):
        result = run_task(provider="codex-native", prompt="inspect")
        self.assertEqual(result.status, "blocked")
        self.assertIn("native", result.summary)

    def test_cancellation_and_permission_guard(self):
        self.assertEqual(run_task(provider="agy", prompt="x", cancel=True).status, "canceled")
        self.assertEqual(run_task(provider="agy", prompt="x", dangerously_skip_permissions=True).status, "blocked")

    def test_agy_success_contract_and_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "agy.py"
            fake.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'status':'SUCCESS','response':'ok','usage':{'total_tokens':3}}))\n", encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
            old = os.environ.get("AGY_BIN")
            os.environ["AGY_BIN"] = str(fake)
            try:
                result = run_task(provider="agy", prompt="hello", artifact_dir=Path(temp) / "logs")
            finally:
                if old is None:
                    os.environ.pop("AGY_BIN", None)
                else:
                    os.environ["AGY_BIN"] = old
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.summary, "ok")
            self.assertTrue(Path(result.log_path).exists())
            self.assertEqual(json.loads(Path(result.log_path).read_text())["returncode"], 0)

    def test_auth_failure_is_blocked_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "agy.py"
            fake.write_text("#!/usr/bin/env python3\nimport sys\nprint('authentication required', file=sys.stderr)\nsys.exit(2)\n", encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
            old = os.environ.get("AGY_BIN")
            os.environ["AGY_BIN"] = str(fake)
            try:
                result = run_task(provider="agy", prompt="hello", retries=2, artifact_dir=Path(temp) / "logs")
            finally:
                if old is None:
                    os.environ.pop("AGY_BIN", None)
                else:
                    os.environ["AGY_BIN"] = old
            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.attempts, 1)


if __name__ == "__main__":
    unittest.main()

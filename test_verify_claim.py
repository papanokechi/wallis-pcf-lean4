import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import verify_claim


ROOT = Path(__file__).resolve().parent
VERIFY = ROOT / "verify_claim.py"
RESEARCH_TARGET = ROOT / "ramanujan_breakthrough_generator.py"
PYTHON = sys.executable
GIT_COMMIT = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
VERIFY_HASH = hashlib.sha256(VERIFY.read_bytes()).hexdigest().lower()
RESEARCH_HASH = hashlib.sha256(RESEARCH_TARGET.read_bytes()).hexdigest().lower()


class VerifyClaimBehaviorTests(unittest.TestCase):
    def _base_claim(self) -> dict:
        return {
            "inputs": {"function": "demo", "args": {}, "precision": 80, "depth": 1},
            "raw_output": "1.4142135623730951",
            "comparison": {
                "target": "sqrt(2)",
                "target_value": "mp.sqrt(2)",
                "residual": "0",
                "digits": 16.0,
                "threshold": 10,
                "threshold_met": True,
            },
            "reproduce": f'"{PYTHON}" -c "print(1.4142135623730951)"',
            "evidence_class": "independently_verified",
            "environment": {"python": "3.14", "mpmath": "1.3.0", "git_commit": GIT_COMMIT},
            "provenance": {
                "code_path": str(RESEARCH_TARGET),
                "implementation_hash": RESEARCH_HASH,
                "timestamp": "2026-04-14T00:00:00Z",
            },
            "summary": "Independent replay confirms the numerical value.",
        }

    def _run_claim(
        self,
        claim: dict,
        *,
        extra_args: list[str] | None = None,
        health_path: Path | None = None,
        cleanup_health: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(claim, handle, indent=2)
            claim_path = Path(handle.name)
        health_file = health_path or claim_path.with_suffix(".health.json")
        command = [
            PYTHON,
            str(VERIFY),
            str(claim_path),
            "--health-file",
            str(health_file),
            "--agent-id",
            "test-agent",
        ]
        if extra_args:
            command.extend(extra_args)
        try:
            return subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        finally:
            claim_path.unlink(missing_ok=True)
            if cleanup_health:
                health_file.unlink(missing_ok=True)

    def test_verified_claim_returns_verified(self) -> None:
        result = self._run_claim(self._base_claim())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VERIFIED", result.stdout)

    def test_missing_environment_model_still_verifies(self) -> None:
        claim = self._base_claim()
        claim["environment"].pop("model", None)
        result = self._run_claim(claim)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VERIFIED", result.stdout)
        self.assertIn("model=unknown", result.stdout)

    def test_exit_zero_but_wrong_number_returns_mismatch(self) -> None:
        claim = self._base_claim()
        claim["reproduce"] = f'"{PYTHON}" -c "print(1.5)"'
        result = self._run_claim(claim)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("MISMATCH", result.stdout)
        self.assertIn("Reproduced stdout does not match raw_output closely enough", result.stdout)

    def test_near_miss_breakthrough_language_is_rejected(self) -> None:
        claim = self._base_claim()
        claim["evidence_class"] = "near_miss"
        claim["summary"] = "Potential breakthrough observed."
        result = self._run_claim(claim)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("SCHEMA_INVALID", result.stdout)
        self.assertIn("banned phrase", result.stdout)

    def test_stale_provenance_hash_returns_mismatch(self) -> None:
        claim = self._base_claim()
        claim["provenance"]["implementation_hash"] = "deadbeef"
        result = self._run_claim(claim)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("MISMATCH", result.stdout)
        self.assertIn("implementation_hash mismatch", result.stdout)

    def test_self_referential_verifier_provenance_is_rejected(self) -> None:
        claim = self._base_claim()
        claim["provenance"]["code_path"] = str(VERIFY)
        claim["provenance"]["implementation_hash"] = VERIFY_HASH
        result = self._run_claim(claim)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("SCHEMA_INVALID", result.stdout)
        self.assertIn("must point to the research script under audit", result.stdout)

    def test_health_history_updates_for_low_depth_verified_claim(self) -> None:
        claim = self._base_claim()
        claim["raw_output"] = "1.4"
        claim["reproduce"] = f'"{PYTHON}" -c "print(1.4)"'
        claim["comparison"]["digits"] = 1.0
        claim["comparison"]["threshold"] = 50
        claim["comparison"]["threshold_met"] = False
        claim["evidence_class"] = "near_miss"

        health_path = ROOT / "_tmp_agent_health.json"
        result = self._run_claim(claim, health_path=health_path, cleanup_health=False)
        try:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(health_path.exists())
            history = json.loads(health_path.read_text(encoding="utf-8"))
            rolling = history["rolling"]["test-agent"]
            self.assertLess(rolling["axes"]["depth"], 10.0)
            self.assertEqual(rolling["trust_mode"], "human-review-required")
        finally:
            health_path.unlink(missing_ok=True)

    def test_verify_chain_returns_valid_for_fresh_history(self) -> None:
        health_path = ROOT / "_tmp_agent_health_chain.json"
        result = self._run_claim(self._base_claim(), health_path=health_path, cleanup_health=False)
        try:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            history = json.loads(health_path.read_text(encoding="utf-8"))
            status, broken_index = verify_claim.verify_chain(history)
            self.assertEqual(status, "CHAIN_VALID")
            self.assertIsNone(broken_index)
        finally:
            health_path.unlink(missing_ok=True)

    def test_verify_chain_detects_tampered_record_at_index_one(self) -> None:
        health_path = ROOT / "_tmp_agent_health_tamper.json"
        first = self._base_claim()
        second = self._base_claim()
        second["provenance"]["git_commit"] = "session-two"
        second["provenance"]["timestamp"] = "2026-04-14T00:10:00Z"

        result1 = self._run_claim(first, health_path=health_path, cleanup_health=False)
        result2 = self._run_claim(second, health_path=health_path, cleanup_health=False)
        try:
            self.assertEqual(result1.returncode, 0, result1.stdout + result1.stderr)
            self.assertEqual(result2.returncode, 0, result2.stdout + result2.stderr)
            history = json.loads(health_path.read_text(encoding="utf-8"))
            history["sessions"][1]["score"] = 99.0
            status, broken_index = verify_claim.verify_chain(history)
            self.assertEqual(status, "CHAIN_TAMPERED")
            self.assertEqual(broken_index, 1)
        finally:
            health_path.unlink(missing_ok=True)

    def test_precommit_gate_blocks_schema_invalid_session(self) -> None:
        claim = self._base_claim()
        del claim["comparison"]["threshold"]

        health_path = ROOT / "_tmp_agent_health_block.json"
        result = self._run_claim(claim, health_path=health_path, cleanup_health=False)
        try:
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            history = json.loads(health_path.read_text(encoding="utf-8"))
            allowed, message = verify_claim.evaluate_precommit_gate(history, agent_id="test-agent")
            self.assertFalse(allowed)
            self.assertIn("SCHEMA_INVALID", message)
        finally:
            health_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

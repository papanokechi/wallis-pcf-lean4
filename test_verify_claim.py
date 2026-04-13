import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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

    def _run_claim(self, claim: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(claim, handle, indent=2)
            claim_path = Path(handle.name)
        try:
            return subprocess.run(
                [PYTHON, str(VERIFY), str(claim_path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        finally:
            claim_path.unlink(missing_ok=True)

    def test_verified_claim_returns_verified(self) -> None:
        result = self._run_claim(self._base_claim())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VERIFIED", result.stdout)

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


if __name__ == "__main__":
    unittest.main()

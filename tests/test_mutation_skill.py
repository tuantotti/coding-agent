"""Unit tests for the mutation-testing skill helper (run_mutation.py).

All tests mock subprocess and filesystem — no mutmut installation required.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import importlib.util

import pytest

# Load run_mutation.py from the hyphen-named skill directory via importlib
_SKILL_DIR = Path(__file__).resolve().parents[1] / "src" / "skills" / "tester" / "mutation-testing"
_spec = importlib.util.spec_from_file_location("run_mutation", _SKILL_DIR / "run_mutation.py")
rm = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(rm)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    cp: subprocess.CompletedProcess = MagicMock(spec=subprocess.CompletedProcess)
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


# ---------------------------------------------------------------------------
# _check_mutmut
# ---------------------------------------------------------------------------

class TestCheckMutmut:
    def test_returns_true_when_mutmut_present(self):
        with patch.object(rm, "_run", return_value=_make_completed(0, "mutmut 2.4.5")):
            assert rm._check_mutmut() is True

    def test_returns_false_when_mutmut_missing(self):
        with patch.object(rm, "_run", return_value=_make_completed(1)):
            assert rm._check_mutmut() is False


# ---------------------------------------------------------------------------
# _baseline_run
# ---------------------------------------------------------------------------

class TestBaselineRun:
    def test_passes_when_pytest_exits_zero(self):
        with patch.object(rm, "_run", return_value=_make_completed(0, "1 passed")):
            ok, out = rm._baseline_run("tests/", "pytest")
        assert ok is True
        assert "1 passed" in out

    def test_fails_when_pytest_exits_nonzero(self):
        with patch.object(rm, "_run", return_value=_make_completed(1, "", "FAILED test_foo.py")):
            ok, out = rm._baseline_run("tests/", "pytest")
        assert ok is False

    def test_unsupported_runner_returns_false(self):
        ok, out = rm._baseline_run("tests/", "nose2")
        assert ok is False
        assert "Unsupported" in out


# ---------------------------------------------------------------------------
# main() integration paths
# ---------------------------------------------------------------------------

class TestMain:
    def test_error_report_when_mutmut_not_found(self, tmp_path, capsys):
        src = tmp_path / "module.py"
        src.write_text("x = 1\n")
        tests = tmp_path / "tests"
        tests.mkdir()

        with patch.object(rm, "_check_mutmut", return_value=False):
            code = rm.main(["--src", str(src), "--tests", str(tests)])

        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert "mutmut not found" in out["error"]

    def test_error_report_when_baseline_fails(self, tmp_path, capsys):
        src = tmp_path / "module.py"
        src.write_text("x = 1\n")
        tests = tmp_path / "tests"
        tests.mkdir()

        with patch.object(rm, "_check_mutmut", return_value=True), \
             patch.object(rm, "_baseline_run", return_value=(False, "FAILED test_x")):
            code = rm.main(["--src", str(src), "--tests", str(tests)])

        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert "Baseline test run failed" in out["error"]

    def test_success_report_structure(self, tmp_path, capsys):
        src = tmp_path / "module.py"
        src.write_text("def add(a, b): return a + b\n")
        tests = tmp_path / "tests"
        tests.mkdir()

        fake_mutmut_output = "3 to test\nKilled 2\nSurvived 1\n"
        fake_result = _make_completed(0, fake_mutmut_output)

        with patch.object(rm, "_check_mutmut", return_value=True), \
             patch.object(rm, "_baseline_run", return_value=(True, "1 passed")), \
             patch.object(rm, "_run", return_value=fake_result), \
             patch.object(rm, "_parse_mutmut_results", return_value=[]):
            code = rm.main(["--src", str(src), "--tests", str(tests)])

        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert "summary" in out
        assert "killed_ratio" in out
        assert "surviving_mutants" in out

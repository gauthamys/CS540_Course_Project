"""
Code generation evaluation metrics.

Primary metric: pass@1 (fraction of problems where the generated code
passes all EvalPlus unit tests).

Test execution is handled by the test_runner node (multi-agent) or
run_pilot scripts (single-agent), which produce TestRunResult records.
This module aggregates those results.
"""
from src.schemas.codegen_schema import TestRunResult


def compute_codegen_metrics(results: list[TestRunResult | dict]) -> dict:
    """
    Aggregate test run results into evaluation metrics.

    Args:
        results: list of TestRunResult objects or equivalent dicts

    Returns:
        dict with pass_at_1, compile_error_rate, avg_tests_passed, n_samples
    """
    if not results:
        return {
            "pass_at_1": 0.0,
            "compile_error_rate": 0.0,
            "avg_tests_passed": 0.0,
            "n_samples": 0,
        }

    # Normalize to dicts
    dicts = [r if isinstance(r, dict) else r.model_dump() for r in results]

    n = len(dicts)
    n_passed = sum(1 for r in dicts if r.get("passed", False))
    n_errors = sum(1 for r in dicts if r.get("error_output") is not None)

    total_tests_passed = sum(r.get("num_passed", 0) for r in dicts)
    total_tests = sum(r.get("num_total", 1) for r in dicts)
    avg_tests = total_tests_passed / total_tests if total_tests > 0 else 0.0

    return {
        "pass_at_1": n_passed / n,
        "compile_error_rate": n_errors / n,
        "avg_tests_passed": avg_tests,
        "n_samples": n,
    }


def run_single_test(code: str, test_code: str, task_id: str, attempt: int = 1) -> TestRunResult:
    """
    Execute generated code against test_code in a subprocess with a timeout.
    Returns a TestRunResult.
    """
    import subprocess
    import sys
    import tempfile
    import os

    # Write a temp file: solution + test code
    safe_id = task_id.replace("/", "_").replace("\\", "_")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix=f"cs540_{safe_id}_"
    ) as f:
        f.write(code + "\n\n")
        f.write(test_code + "\n")
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        passed = result.returncode == 0
        error_output = None if passed else (result.stderr or result.stdout or "non-zero exit")
        return TestRunResult(
            task_id=task_id,
            passed=passed,
            num_passed=1 if passed else 0,
            num_total=1,
            error_output=error_output,
            attempt_number=attempt,
        )
    except subprocess.TimeoutExpired:
        return TestRunResult(
            task_id=task_id,
            passed=False,
            num_passed=0,
            num_total=1,
            error_output="TimeoutExpired (>10s)",
            attempt_number=attempt,
        )
    finally:
        os.unlink(tmp_path)

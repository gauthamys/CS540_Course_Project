"""
Loader for EvalPlus (HumanEval+ and MBPP+).

Requires: pip install evalplus
EvalPlus caches data locally on first import. Set EVALPLUS_CACHE_DIR to
control where it lands.

Standard record format:
  {id, prompt, entry_point, test_code, canonical_solution, source}
"""
import os


def _set_cache_dir() -> None:
    cache_dir = os.getenv("EVALPLUS_CACHE_DIR", "./data/raw/evalplus")
    os.makedirs(cache_dir, exist_ok=True)
    # EvalPlus respects XDG_CACHE_HOME
    os.environ.setdefault("XDG_CACHE_HOME", os.path.abspath(cache_dir))


def load_humaneval_plus() -> list[dict]:
    """Return all HumanEval+ problems as standard record dicts."""
    _set_cache_dir()
    from evalplus.data import get_human_eval_plus  # type: ignore

    problems = get_human_eval_plus()
    records = []
    for task_id, prob in problems.items():
        records.append(
            {
                "id": task_id,
                "prompt": prob["prompt"],
                "entry_point": prob["entry_point"],
                "canonical_solution": prob.get("canonical_solution", ""),
                "test_code": prob.get("test", ""),
                "source": "humaneval_plus",
                "split": "test",  # EvalPlus has a single evaluation set
            }
        )
    return records


def load_mbpp_plus() -> list[dict]:
    """Return all MBPP+ problems as standard record dicts."""
    _set_cache_dir()
    from evalplus.data import get_mbpp_plus  # type: ignore

    problems = get_mbpp_plus()
    records = []
    for task_id, prob in problems.items():
        records.append(
            {
                "id": task_id,
                "prompt": prob["prompt"],
                "entry_point": prob.get("entry_point", "solution"),
                "canonical_solution": prob.get("canonical_solution", ""),
                "test_code": prob.get("test", ""),
                "source": "mbpp_plus",
                "split": "test",
            }
        )
    return records


def load_evalplus(include_mbpp: bool = True) -> list[dict]:
    """Load both HumanEval+ and (optionally) MBPP+."""
    records = load_humaneval_plus()
    if include_mbpp:
        records += load_mbpp_plus()
    return records

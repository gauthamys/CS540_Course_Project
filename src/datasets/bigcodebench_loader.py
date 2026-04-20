"""
Loader for BigCodeBench-Hard dataset (148 problems).

Fetches from HuggingFace and normalizes to the same record format
used by the rest of this project:
  {id, prompt, test_code, entry_point, libs, source, split}

Usage:
    from src.datasets.bigcodebench_loader import load_bcb_hard, sample_bcb_pilot

    records = load_bcb_hard()           # all 148
    pilot   = sample_bcb_pilot(n=5)     # random 5
"""
import ast
import random


def load_bcb_hard() -> list[dict]:
    """
    Load all BigCodeBench-Hard problems from HuggingFace.
    Returns list of normalized records.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError("Run: pip install datasets")

    ds = load_dataset("bigcode/bigcodebench-hard", split="v0.1.2")

    records = []
    for row in ds:
        records.append({
            "id":          row["task_id"],
            "prompt":      row["instruct_prompt"],
            "test_code":   row["test"],
            "entry_point": row["entry_point"],
            "libs":        ast.literal_eval(row["libs"]) if isinstance(row["libs"], str) else row["libs"],
            "source":      "bigcodebench_hard",
            "split":       "test",
        })

    return records


def sample_bcb_pilot(n: int = 5, seed: int = 42) -> list[dict]:
    """Return n randomly sampled problems (deterministic via seed)."""
    records = load_bcb_hard()
    rng = random.Random(seed)
    return rng.sample(records, min(n, len(records)))


def load_bcb_first_n(n: int = 5) -> list[dict]:
    """Return the first n problems in dataset order (no randomness)."""
    records = load_bcb_hard()
    return records[:n]

"""
Deterministic train/test splitter and pilot sampler.

All randomness flows through RANDOM_SEED so splits are reproducible.
"""
import os
import random
from collections import defaultdict
from typing import Optional


def _get_seed() -> int:
    return int(os.getenv("RANDOM_SEED", "42"))


def split_records(
    records: list[dict],
    test_fraction: float = 0.2,
    stratify_key: Optional[str] = "label",
    seed: Optional[int] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Split records into (train, test) with optional stratification.
    Sets the 'split' field on each record in-place.
    Returns (train_records, test_records).
    """
    if seed is None:
        seed = _get_seed()
    rng = random.Random(seed)

    if stratify_key and records and stratify_key in records[0]:
        # Group by label
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            groups[r[stratify_key]].append(r)

        train, test = [], []
        for label, group in groups.items():
            shuffled = group[:]
            rng.shuffle(shuffled)
            n_test = max(1, round(len(shuffled) * test_fraction))
            test.extend(shuffled[:n_test])
            train.extend(shuffled[n_test:])
    else:
        shuffled = records[:]
        rng.shuffle(shuffled)
        n_test = max(1, round(len(shuffled) * test_fraction))
        test = shuffled[:n_test]
        train = shuffled[n_test:]

    for r in train:
        r["split"] = "train"
    for r in test:
        r["split"] = "test"

    return train, test


def sample_pilot(
    records: list[dict],
    n: int = 10,
    stratify_key: Optional[str] = "label",
    split_filter: Optional[str] = "test",
    seed: Optional[int] = None,
) -> list[dict]:
    """
    Sample n records for a pilot run, optionally stratified.
    Only samples from records where record['split'] == split_filter (if given).
    """
    if seed is None:
        seed = _get_seed()
    rng = random.Random(seed)

    pool = [r for r in records if split_filter is None or r.get("split") == split_filter]

    if stratify_key and pool and stratify_key in pool[0]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in pool:
            groups[r[stratify_key]].append(r)

        labels = sorted(groups.keys())
        per_label = max(1, n // len(labels))
        pilot: list[dict] = []
        for label in labels:
            group = groups[label][:]
            rng.shuffle(group)
            pilot.extend(group[:per_label])
        # If we need more (due to rounding), fill from the full pool
        if len(pilot) < n:
            remaining = [r for r in pool if r not in pilot]
            rng.shuffle(remaining)
            pilot.extend(remaining[: n - len(pilot)])
        return pilot[:n]
    else:
        shuffled = pool[:]
        rng.shuffle(shuffled)
        return shuffled[:n]

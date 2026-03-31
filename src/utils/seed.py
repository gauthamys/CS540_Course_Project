import os
import random


def set_seed(seed: int | None = None) -> int:
    if seed is None:
        seed = int(os.getenv("RANDOM_SEED", "42"))
    random.seed(seed)
    return seed

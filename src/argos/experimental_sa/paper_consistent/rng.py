"""Search randomness belongs to a local PCG64 Generator."""

import copy

import numpy as np


def search_rng(seed):
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("Invalid search seed")
    return np.random.Generator(np.random.PCG64(seed))


def state(rng):
    return copy.deepcopy(rng.bit_generator.state)

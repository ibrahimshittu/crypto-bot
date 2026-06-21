"""Combinatorial Purged Cross-Validation splits (López de Prado)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np


@dataclass(frozen=True)
class CPCVSplit:
    train_idx: np.ndarray
    test_idx: np.ndarray
    test_groups: tuple[int, ...]


def combinatorial_purged_splits(
    n_samples: int,
    *,
    n_groups: int = 6,
    n_test_groups: int = 2,
    embargo_frac: float = 0.01,
    label_horizon: int = 1,
) -> list[CPCVSplit]:
    """Generate CPCV splits over `n_samples` observations.

    n_groups: number of contiguous partitions of the timeline.
    n_test_groups: how many groups form the test set in each combination.
    embargo_frac: fraction of samples to embargo immediately after each test block.
    label_horizon: max bars a label looks forward (for purging the train/test boundary).
    """
    if n_test_groups >= n_groups:
        raise ValueError("n_test_groups must be < n_groups")

    bounds = np.linspace(0, n_samples, n_groups + 1, dtype=int)
    groups = [np.arange(bounds[g], bounds[g + 1]) for g in range(n_groups)]
    embargo = int(n_samples * embargo_frac)

    splits: list[CPCVSplit] = []
    for combo in combinations(range(n_groups), n_test_groups):
        test_idx = np.concatenate([groups[g] for g in combo])
        test_set = set(test_idx.tolist())

        # Build a purge/embargo band around EACH contiguous test group separately, so
        # non-adjacent test blocks don't wipe out all the training data between them.
        # A train sample is purged if it sits within `label_horizon` before a test
        # group's start (its label could peek into the test set) or within `embargo`
        # after the group's end.
        banned: set[int] = set()
        for g in combo:
            g_start, g_end = int(groups[g][0]), int(groups[g][-1])
            banned.update(range(max(0, g_start - label_horizon), g_start))
            banned.update(range(g_end + 1, min(n_samples, g_end + 1 + embargo)))

        train_idx = np.array(
            [i for i in range(n_samples) if i not in test_set and i not in banned],
            dtype=int,
        )
        if train_idx.size == 0 or test_idx.size == 0:
            continue
        splits.append(CPCVSplit(train_idx=train_idx, test_idx=np.sort(test_idx), test_groups=combo))

    return splits

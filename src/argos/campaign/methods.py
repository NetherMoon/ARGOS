"""Comparison strategies reuse core geometry, measured ranking and confirmation."""

from dataclasses import asdict

import numpy as np

from argos.campaign.identity import digest, immutable_json
from argos.controller.argos_controller import Controller
from argos.provenance import read_json
from argos.types import candidate_from_dict


class FixedController(Controller):
    def __init__(self, *args, proposals, **kwargs):
        self.proposals = proposals
        super().__init__(*args, **kwargs)

    def next_batch(self):
        return self.proposals[
            self.state.search_calls : self.state.search_calls + self.config.batch_size
        ]


def fixed_probes(episode, config, domain, regions, predict):
    path = episode / "frozen_probes.json"
    if path.exists():
        record = read_json(path)
        if read_json(episode.parent / "fixed_probes_seal.json")["digest"] != digest(record):
            raise ValueError("Frozen fixed probe set corrupted")
        return [candidate_from_dict(c) for c in record["candidates"]]
    if (episode / "state.json").exists():
        raise ValueError("Cannot construct fixed probes after controller state")
    controller = Controller(episode / "proposal_builder", config, domain, regions, None, predict)
    proposals = controller.next_batch()
    for batch in range(2, config.max_search_batches + 1):
        rng = np.random.default_rng(np.random.SeedSequence([config.candidate_seed, batch]))
        size = min(config.batch_size, config.max_search_calls - len(proposals))
        selected = []
        serial = 0
        guided = max(0, size - config.independent_per_batch)

        def add(candidate, selected=selected):
            domain.validate(candidate)
            if all(
                domain.distance(candidate, c) > config.dedupe_distance for c in proposals + selected
            ):
                selected.append(candidate)

        while len(selected) < guided and regions and serial < 500:
            anchor = regions[serial % len(regions)].representative
            add(
                domain.local(
                    anchor, rng, config.local_radius, f"fixed-b{batch:03d}-local-{serial:04d}"
                )
            )
            serial += 1
        while len(selected) < size and serial < 1500:
            add(domain.independent(rng, f"fixed-b{batch:03d}-independent-{serial:04d}"))
            serial += 1
        proposals.extend(predict(c) for c in selected)
    immutable_json(path, {"policy": "predeclared_v1", "candidates": [asdict(c) for c in proposals]})
    immutable_json(episode.parent / "fixed_probes_seal.json", {"digest": digest(read_json(path))})
    return proposals

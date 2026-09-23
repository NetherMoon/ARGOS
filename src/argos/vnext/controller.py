"""Resumable vNext controller, with frozen predictions before every batch."""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from argos.campaign.identity import digest, immutable_json
from argos.contracts import observation_rank, qualified
from argos.controller.argos_controller import Controller
from argos.provenance import read_json, write_json
from argos.types import Candidate, candidate_from_dict, observation_from_dict
from argos.vnext.correction import Correction, CorrectionSpec
from argos.vnext.costs import objective
from argos.vnext.mechanisms import (
    TrustRegion,
    groups,
    robust_rank,
    scenario_status,
    targeted_probes,
)


class EliteController(Controller):
    """H1 with just protected first-batch endpoints, for the E ablation."""

    def __init__(self, *args, elites, **kwargs):
        self.elites = elites
        super().__init__(*args, **kwargs)

    def next_batch(self):
        if self.state.completed_batches:
            return super().next_batch()
        rng = np.random.default_rng(np.random.SeedSequence([self.config.candidate_seed, 1]))
        chosen = []
        for c in [*self.elites, *[r.representative for r in self.regions]]:
            if all(self.domain.distance(c, p) > self.config.dedupe_distance for p in chosen):
                chosen.append(c)
            if len(chosen) == 6:
                break
        serial = 0
        while len(chosen) < 8:
            c = self.domain.independent(rng, f"b001-independent-{serial:04d}")
            serial += 1
            if all(self.domain.distance(c, p) > self.config.dedupe_distance for p in chosen):
                chosen.append(c)
        return [self.predictor(c) for c in chosen]


class NextController:
    def __init__(
        self,
        episode,
        config,
        domain,
        regions,
        simulator,
        predictor,
        elites,
        repeat_seeds,
        variant="ERT",
        correction=None,
        fixed_table_single_seed=False,
    ):
        correction = correction or CorrectionSpec()
        if variant not in {"ER", "ERT", "ERTC"}:
            raise ValueError("Invalid vNext variant")
        if variant == "ERTC" and correction.model == "C0":
            raise ValueError("A no-correction duplicate is not an ablation")
        if fixed_table_single_seed:
            if (
                repeat_seeds
                or len(config.confirmation_seeds) != 3
                or len({config.search_seed, *config.confirmation_seeds}) != 4
            ):
                raise ValueError("Fixed-table search requires no repeats and three fresh checks")
        elif (
            len(repeat_seeds) != 3
            or len({config.search_seed, *repeat_seeds, *config.confirmation_seeds}) != 7
        ):
            raise ValueError("Search, repeat and three confirmation scenarios must be disjoint")
        config.validate()
        if (
            config.max_search_calls,
            config.max_search_batches,
            config.batch_size,
            config.independent_per_batch,
        ) != (32, 4, 8, 2):
            raise ValueError("vNext requires frozen 32-call/4-batch allocation")
        self.episode = Path(episode)
        self.config = config
        self.domain = domain
        self.regions = regions
        self.simulator = simulator
        self.predictor = predictor
        self.elites = elites
        self.repeat_seeds = repeat_seeds
        self.fixed_table_single_seed = fixed_table_single_seed
        self.variant = variant
        self.correction_spec = correction if variant == "ERTC" else CorrectionSpec()
        self.episode.mkdir(parents=True, exist_ok=True)
        self.path = self.episode / "vnext_state.json"
        self.state = (
            read_json(self.path)
            if self.path.exists()
            else {
                "schema": 1,
                "batch": 0,
                "phase": "SEARCH",
                "observations": [],
                "pending": None,
                "incumbent": None,
                "confirmation_index": 0,
                "search_calls": 0,
                "repeats": 0,
                "timing": {
                    "correction_fit": 0.0,
                    "proposal_scoring": 0.0,
                    "simulator_wall": 0.0,
                    "active_wall": 0.0,
                },
                "regions": [],
            }
        )
        mode = "FIXED_TABLE_SINGLE_SEED" if fixed_table_single_seed else "VNEXT_RACING"
        if self.state.get("mode", mode) != mode:
            raise ValueError("Controller recovery mode changed")
        self.state["mode"] = mode
        self.start = time.perf_counter()
        self.previous = self.state["timing"]["active_wall"]
        self.save()

    def save(self):
        self.state["timing"]["active_wall"] = self.previous + time.perf_counter() - self.start
        write_json(self.path, self.state)

    def observations(self):
        return [observation_from_dict(o) for o in self.state["observations"]]

    def propose(self):
        batch = self.state["batch"] + 1
        config = self.config
        domain = self.domain
        rng = np.random.default_rng(np.random.SeedSequence([config.candidate_seed, batch]))
        obs = [o for o in self.observations() if o.phase == "search"]
        used = [o.candidate for o in obs]
        clustered = sorted(
            groups(obs),
            key=(lambda g: observation_rank(g[0])) if self.fixed_table_single_seed else robust_rank,
        )
        robust = (
            any(qualified(o) for o in obs)
            if self.fixed_table_single_seed
            else any(scenario_status(g) == "SEARCH_ROBUST_FEASIBLE" for g in clustered)
        )
        model = Correction(domain, self.correction_spec)
        fit_start = time.perf_counter()
        model.fit(obs)
        self.state["timing"]["correction_fit"] += time.perf_counter() - fit_start
        start = time.perf_counter()
        chosen = []
        repeat = []
        # Exactly 8 potential racing slots: 2+3+3. Unused repeat slots become
        # exploration when there is no qualified or near-boundary candidate.
        repeat_slots = 0 if self.fixed_table_single_seed else {1: 0, 2: 2, 3: 3, 4: 3}[batch]
        if repeat_slots:
            for g in clustered:
                status = scenario_status(g)
                # Two passes complete the required search screen; failed screens
                # stay fragile. Near-boundary primary failures may get one repeat.
                promising = status == "PROVISIONAL_FEASIBLE" or (
                    len(g) == 1 and g[0].valid and observation_rank(g[0])[1] <= 0.15
                )
                if promising and self.repeat_seeds[batch - 2] not in {o.seed for o in g}:
                    repeat.append(g[0].candidate)
                if len(repeat) == repeat_slots:
                    break
        unique_slots = 8 - len(repeat)

        def add(c):
            domain.validate(c)
            if all(domain.distance(c, p) > config.dedupe_distance for p in used + chosen):
                chosen.append(c)
                return True
            return False

        if batch == 1:
            for c in [*self.elites, *[r.representative for r in self.regions]]:
                if len(chosen) == 6:
                    break
                add(c)
        else:
            unused = [
                r.representative
                for r in self.regions
                if all(domain.distance(r.representative, p) > config.dedupe_distance for p in used)
            ]
            if unused:
                add(unused[0])
            anchors = []
            for group in clustered:
                o = min(group, key=observation_rank)
                if o.valid and all(
                    domain.distance(o.candidate, a.candidate) > 0.06 for a in anchors
                ):
                    anchors.append(o)
                if len(anchors) == 4:
                    break
            pool = []
            trust_records = []
            for ai, anchor in enumerate(anchors):
                nearby = [o for o in obs if domain.distance(o.candidate, anchor.candidate) <= 0.12]
                trust = TrustRegion(anchor.candidate)
                for o in nearby:
                    trust.update(o)
                # Rebuild deterministically from search history on recovery.
                if trust.radius <= 0.0075 and unused:
                    trust.restart(unused[0])
                trust_records.append(asdict(trust))
                if self.variant in {"ERT", "ERTC"}:
                    pool.extend(targeted_probes(anchor, domain, f"b{batch}-target-{ai}"))
                for i in range(32):
                    pool.append(
                        domain.local(
                            trust.center if self.variant != "ER" else anchor.candidate,
                            rng,
                            trust.radius if self.variant != "ER" else 0.12,
                            f"b{batch}-local-{ai}-{i}",
                        )
                    )
            if self.variant in {"ERT", "ERTC"}:
                passing = [g[0].candidate for g in clustered if any(qualified(o) for o in g)]
                failing = [o.candidate for o in obs if o.valid and not qualified(o)]
                for i, p in enumerate(passing[:3]):
                    if failing:
                        f = min(failing, key=lambda q: domain.distance(p, q))
                        mid = Candidate(
                            f"b{batch}-boundary-{i}",
                            (p.Pbar + f.Pbar) / 2,
                            (p.R + f.R) / 2,
                            domain.project((np.array(p.weights) + f.weights) / 2),
                            "boundary_probe",
                            provenance={"pass": p.candidate_id, "fail": f.candidate_id},
                        )
                        domain.validate(mid)
                        pool.append(mid)
            self.state["regions"] = trust_records
            pool = [self.predictor(c) for c in pool]
            if pool:
                y, u = model.predict(pool)

                def key(i):
                    conservative = y[i].copy()
                    if u is not None:
                        conservative[1:] += u[i, 1:]
                    ratios = conservative[1:] / np.array([0.3, 0.1, 0.1, 0.1, 0.1])
                    v = np.maximum(ratios - 1, 0)
                    obj = objective(pool[i], y[i])
                    return (
                        bool(v.max() > 0),
                        float(v.max()),
                        obj if robust else float(ratios.max()),
                        float(v.sum()),
                        obj,
                        pool[i].candidate_id,
                    )

                # Leave two truly independent queries in every batch. Select a
                # targeted slot explicitly so random proposals cannot erase it.
                if self.variant in {"ERT", "ERTC"}:
                    targets = [
                        i
                        for i, c in enumerate(pool)
                        if c.source in {"tracking_direction", "qos_transfer", "boundary_probe"}
                    ]
                    for i in sorted(targets, key=key):
                        if len(chosen) >= unique_slots - 2:
                            break
                        if add(pool[i]):
                            break
                order = (
                    list(range(len(pool)))
                    if self.variant == "ER"
                    else sorted(range(len(pool)), key=key)
                )
                for i in order:
                    if len(chosen) >= unique_slots - 2:
                        break
                    # Prefer distinct scored locations while preserving legal support.
                    if self.variant == "ER" or all(
                        domain.distance(pool[i], c) > 0.01 for c in chosen
                    ):
                        add(pool[i])
        serial = 0
        while len(chosen) < unique_slots and serial < 2000:
            add(domain.independent(rng, f"b{batch}-independent-{serial}"))
            serial += 1
        if len(chosen) != unique_slots:
            raise RuntimeError("Could not fill legal batch")
        chosen = [self.predictor(c) for c in chosen]
        all_candidates = chosen + repeat
        y, u = model.predict(all_candidates)
        entries = [
            {
                "candidate": asdict(c),
                "seed": config.search_seed if i < len(chosen) else self.repeat_seeds[batch - 2],
                "repeat": i >= len(chosen),
                "v3": asdict(c.prediction),
                "corrected_behaviors": y[i].tolist(),
                "corrected_objective": objective(c, y[i]),
                "model_uncertainty": u[i].tolist() if u is not None else None,
            }
            for i, c in enumerate(all_candidates)
        ]
        self.state["timing"]["proposal_scoring"] += time.perf_counter() - start
        return {
            "batch": batch,
            "mode": "IMPROVE" if robust else "DISCOVER",
            "entries": entries,
            "training_ids": model.training_ids,
            "correction_spec": asdict(self.correction_spec),
            "correction_events": model.events,
            "unique_prior_geometries": len(clustered),
            "created_unix": time.time(),
            "regions": self.state["regions"],
        }

    def run(self, pause_path=None):
        while self.state["phase"] not in {"DONE", "NO_BID", "ERROR"}:
            if pause_path and Path(pause_path).exists():
                self.save()
                return self.state
            s = self.state
            if s["phase"] == "SEARCH":
                if s["batch"] == 4:
                    clustered = sorted(
                        groups(self.observations()),
                        key=(lambda g: observation_rank(g[0]))
                        if self.fixed_table_single_seed
                        else robust_rank,
                    )
                    robust = (
                        [g for g in clustered if qualified(g[0])]
                        if self.fixed_table_single_seed
                        else [
                            g for g in clustered if scenario_status(g) == "SEARCH_ROBUST_FEASIBLE"
                        ]
                    )
                    s["search_statuses"] = [
                        {
                            "candidate_id": g[0].candidate.candidate_id,
                            "status": (
                                "SEARCH_OBSERVED_FEASIBLE"
                                if qualified(g[0])
                                else "INFEASIBLE"
                                if g[0].valid
                                else "INVALID_EVIDENCE"
                            )
                            if self.fixed_table_single_seed
                            else scenario_status(g),
                            "scenarios": len({o.seed for o in g}),
                        }
                        for g in clustered
                    ]
                    if robust:
                        s["incumbent"] = asdict(robust[0][0].candidate)
                        s["phase"] = "DONE" if self.fixed_table_single_seed else "CONFIRM"
                        immutable_json(
                            self.episode / "final/selected_candidate.json", s["incumbent"]
                        )
                    else:
                        s["phase"] = "NO_BID"
                        s["stop_reason"] = (
                            "No feasible bid found within 32 fixed-table calls"
                            if self.fixed_table_single_seed
                            else "No search-robust incumbent within 32 calls"
                        )
                    self.save()
                    continue
                if (
                    s["pending"] is None
                    and s["search_calls"] + self.config.batch_size > self.config.max_search_calls
                ):
                    s["phase"] = "ERROR"
                    s["stop_reason"] = (
                        "Abandoned physical attempts leave insufficient budget for the next fixed batch; review preserved evidence"
                    )
                    self.save()
                    continue
                if s["pending"] is None:
                    query_path = self.episode / "prequery" / f"batch_{s['batch'] + 1:03d}.json"
                    if query_path.exists():
                        frozen = read_json(query_path)
                    else:
                        frozen = self.propose()
                        frozen["sha256"] = digest(frozen)
                        immutable_json(query_path, frozen)
                    s["pending"] = frozen
                    s["search_calls"] += len(frozen["entries"])
                    self.save()
                frozen = s["pending"]
                data = {k: v for k, v in frozen.items() if k != "sha256"}
                if digest(data) != frozen["sha256"]:
                    raise ValueError("Pending prediction record changed")
                # Cached completed work resumes through the underlying strict runner.
                start = time.perf_counter()
                results = []
                for seed in dict.fromkeys(e["seed"] for e in frozen["entries"]):
                    entries = [e for e in frozen["entries"] if e["seed"] == seed]
                    candidates = [candidate_from_dict(e["candidate"]) for e in entries]
                    try:
                        actual = self.simulator.evaluate_batch(
                            candidates, seed, "search", frozen["batch"]
                        )
                    except RuntimeError as exc:
                        if "Insufficient remaining budget to retry interrupted batch" not in str(
                            exc
                        ):
                            raise
                        s["phase"] = "ERROR"
                        s["stop_reason"] = (
                            "Hard-crash retries exhausted the physical search budget; review preserved evidence"
                        )
                        if hasattr(self.simulator, "search_attempts"):
                            s["search_calls"] = max(
                                s["search_calls"], self.simulator.search_attempts()
                            )
                        self.save()
                        return s
                    if len(actual) != len(candidates) or any(
                        o.candidate != c or o.seed != seed or o.phase != "search"
                        for o, c in zip(actual, candidates)
                    ):
                        raise ValueError("Simulator query identity mismatch")
                    results.extend(actual)
                s["timing"]["simulator_wall"] += time.perf_counter() - start
                s["observations"].extend(asdict(o) for o in results)
                s["repeats"] += sum(e["repeat"] for e in frozen["entries"])
                s["batch"] += 1
                s["pending"] = None
                if hasattr(self.simulator, "search_attempts"):
                    s["search_calls"] = max(s["search_calls"], self.simulator.search_attempts())
                if any(not o.valid for o in results):
                    s["phase"] = "ERROR"
                    s["stop_reason"] = "Invalid simulator evidence"
                self.save()
                print(
                    f"{self.variant} batch {s['batch']}: {sum(qualified(o) for o in results)} qualified; {s['search_calls']}/32 calls, {s['repeats']} repeats",
                    flush=True,
                )
            else:
                if s["confirmation_index"] == 3:
                    s["phase"] = "DONE"
                    self.save()
                    continue
                c = candidate_from_dict(s["incumbent"])
                idx = s["confirmation_index"]
                start = time.perf_counter()
                o = self.simulator.evaluate_batch(
                    [c], self.config.confirmation_seeds[idx], "confirmation", idx + 1
                )[0]
                if (
                    o.candidate != c
                    or o.seed != self.config.confirmation_seeds[idx]
                    or o.phase != "confirmation"
                ):
                    raise ValueError("Confirmation identity mismatch")
                s["timing"]["simulator_wall"] += time.perf_counter() - start
                s["observations"].append(asdict(o))
                s["confirmation_index"] += 1
                if not o.valid:
                    s["phase"] = "ERROR"
                    s["stop_reason"] = "Invalid confirmation evidence"
                self.save()
        return self.state

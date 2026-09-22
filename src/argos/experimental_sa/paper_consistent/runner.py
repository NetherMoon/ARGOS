"""Explicit, sequential fixed-arrival baseline CLI. Never starts Phase 3."""

import argparse
import configparser
import datetime
import json
from pathlib import Path

from .domain import load_domain
from .evaluator import FixedEvaluator, prepare, worker
from .objective import ObjectiveContract
from .simulated_annealing import optimize


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Experimental paper-consistent fixed-arrival SA; independent search/arrival/runtime seeds. No uncertainty experiment."
    )
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--context-manifest",
        type=Path,
        help="Verified Phase2/2B manifest identifying pinned W2 context",
    )
    parser.add_argument("--case", choices=["c005", "c007"])
    parser.add_argument(
        "--domain",
        choices=["legacy_sa", "argos_v3_physical"],
        help="Required explicit domain; all public candidate values are kW/server",
    )
    for name in ["search-seed", "arrival-seed", "runtime-seed", "iterations"]:
        parser.add_argument("--" + name, type=int)
    parser.add_argument(
        "--output", type=Path, help="New output directory; never overwrite existing work"
    )
    args = parser.parse_args(argv)
    if args.worker:
        worker(args.worker.resolve())
        return
    for name in [
        "context_manifest",
        "case",
        "domain",
        "search_seed",
        "arrival_seed",
        "runtime_seed",
        "iterations",
    ]:
        if getattr(args, name) is None:
            parser.error("--" + name.replace("_", "-") + " is required")
    for name in ["search_seed", "arrival_seed", "runtime_seed"]:
        if not 0 <= getattr(args, name) < 2**32:
            parser.error("Seeds must be integers in [0,2**32)")
    if args.iterations < 0:
        parser.error("Nonnegative iterations required")
    root = Path(__file__).resolve().parents[4]
    source = json.loads(args.context_manifest.read_text())
    spec = source["specification"]
    if source.get("status") != "COMPLETE":
        raise ValueError("Context study is incomplete")
    case = next(c for c in spec["cases"] if c["case"] == args.case)
    contract = ObjectiveContract(root)
    output = (
        args.output
        or root
        / "runs/diagnostics"
        / (
            "phase2c_fixed_arrival_sa_"
            + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        )
    ).resolve()
    context, e, j = prepare(
        root, output, spec, case, args.arrival_seed, source["expected_grid_hash"]
    )
    domain = load_domain(root, args.domain, j, e)
    initial = (case["Pbar"], case["R"], *case["weights"])
    domain.validate(initial)
    c = configparser.ConfigParser()
    c.read(root / "configs/canonical_cost_source.ini")
    sa = c["simulated_annealing"]
    steps = c["step_size"]
    settings = {
        "run_id": output.name,
        "search_seed": args.search_seed,
        "arrival_seed": args.arrival_seed,
        "runtime_seed": args.runtime_seed,
        "iterations": args.iterations,
        "temperature": float(sa["temperature"]),
        "cooling_rate": float(sa["cooling_rate"]),
        "steps": (
            float(steps["p_step"]) * domain.p_ratio_scale,
            float(steps["r_step"]) * domain.r_ratio_scale,
            float(steps["w_step"]),
        ),
        "smart_weight": sa.getboolean("smart_weight"),
    }
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "label": "Experimental paper-consistent SA derived from pinned FlexDC",
                "phase": "2C fixed-arrival baseline",
                "context": context,
                "domain": domain.to_dict(),
                "settings": settings,
                "initial": initial,
            },
            indent=2,
        )
    )
    result = optimize(
        initial,
        domain,
        FixedEvaluator(root, output),
        contract,
        list(j.all_jobs.values()),
        output / "iterations.jsonl",
        **settings,
    )
    (output / "result.json").write_text(json.dumps(result.to_dict(), indent=2, allow_nan=False))
    print(result.status)
    print(output)
    if result.error:
        raise SystemExit(1)

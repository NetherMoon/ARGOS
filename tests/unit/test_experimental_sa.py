"""Phase2C contract tests; no simulator is executed by this unit suite."""

import ast
import contextlib
import io
import json
import random
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from argos.experimental_sa.paper_consistent.domain import Domain, load_domain
from argos.experimental_sa.paper_consistent.feasibility import assess
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract
from argos.experimental_sa.paper_consistent.rng import search_rng, state
from argos.experimental_sa.paper_consistent.simulated_annealing import optimize

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "runs/diagnostics/w2_seed_characterization_10x3_20260919T165931_783442Z"
NAMES = ["Resnet", "GPT2", "Llama", "Bloom"]


def legacy_functions():
    text = (ROOT / "src/argos/experimental_sa/upstream_snapshot/simulated_annealing.py").read_text()
    tree = ast.parse(text)
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    ns = {"np": np, "wandb": SimpleNamespace(log=lambda *a, **k: None)}
    exec(compile(tree, "byte_identical_upstream_snapshot", "exec"), ns)  # noqa: S102 - audited local functions only
    return ns


def legacy_config(iterations=0):
    return SimpleNamespace(
        p_low=0.9,
        p_high=1.2,
        r_low=0.2,
        r_high=0.8,
        w_low=0.1,
        w_high=0.8,
        p_init=1.0,
        r_init=0.6,
        temperature=1.0,
        p_step=0.01,
        r_step=0.01,
        w_step=0.02,
        max_iter=iterations,
        cooling_rate=0.95,
        program_type="RSR",
        smart_weight=False,
    )


def raw(money=50.0, p90=0.2, pj=None, counts=None):
    return {
        "status": "COMPLETE",
        "M_RSR": money,
        "mean_tracking": 0.1,
        "p90": p90,
        "Pj": [0.0, 0.0, 0.0, 0.0] if pj is None else pj,
        "evidence_counts": [100] * 4 if counts is None else counts,
        "initial_job_table_hash": "fixed",
        "grid_signal_hash": "grid",
        "target_trace_hash": "target",
    }


@pytest.mark.parametrize("cell", sorted((PANEL / "cells").iterdir()), ids=lambda p: p.name)
def test_saved_objective_feasibility_parity(cell):
    old = json.loads((cell / "result.json").read_text())
    r = raw(
        old["monetary_power"] + old["monetary_tracking"],
        old["p90"],
        old["Pj"],
        old["evidence_counts"],
    )
    obj = ObjectiveContract(ROOT).evaluate(r["M_RSR"], r["p90"], r["Pj"])
    assert abs(obj.Cfull - old["objective"]) < 1e-12
    a = assess(r, NAMES, obj.Cfull)
    assert a["feasible"] == old["evidence_qualified_pass"]
    assert a["tracking_pass"] == old["assessment"]["tracking_pass"]
    assert a["per_job_pass"] == [x <= 0.1 for x in old["Pj"]]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"Pj": [0] * 3}, "MISSING_JOB_TYPE_EVIDENCE"),
        ({"evidence_counts": [0] * 4}, "MISSING_JOB_TYPE_EVIDENCE"),
        ({"evidence_counts": [True] * 4}, "MISSING_JOB_TYPE_EVIDENCE"),
        ({"p90": float("nan")}, "INVALID_OBSERVATION"),
        ({"status": "ERROR"}, "INVALID_OBSERVATION"),
        ({"Pj": [0, 0, 0, 1.1]}, "INVALID_OBSERVATION"),
    ],
)
def test_invalid(change, reason):
    r = raw()
    r.update(change)
    a = assess(r, NAMES, 90.0)
    assert not a["feasible"]
    assert a["reason"] == reason


def test_inclusive_boundary_and_other_job():
    assert assess(raw(p90=0.3, pj=[0.1] * 4), NAMES, 90.0)["feasible"]
    a = assess(raw(pj=[0, 0.11, 0, 0]), NAMES, 90.0)
    assert a["reason"] == "QOS_FAIL"
    assert a["offending"][0]["index"] == 1


def test_stable_softplus():
    c = ObjectiveContract(ROOT)
    assert np.isfinite(c.evaluate(50, 10000, [1] * 4).Cfull)


def test_upstream_bounds_counterexample():
    ns = legacy_functions()
    c = legacy_config()
    x = ns["enforce_bounds"](
        [1, 0.5, 0.8, 0.1, 0.1, 0.1], [(0.9, 1.2), (0.2, 0.8)] + [(0.1, 0.8)] * 4, c
    )
    assert min(x[2:]) < 0.1


def test_upstream_return_shape():
    ns = legacy_functions()
    ns["sa_evaluate"] = lambda *a, **k: (100.0, 1, 1, 1, 0, 0.2, [1] * 4)
    args = (
        SimpleNamespace(runtime_policy_name="AQA"),
        None,
        None,
        SimpleNamespace(job_type_count=4),
        "unused",
    )
    with contextlib.redirect_stdout(io.StringIO()):
        first = ns["simulated_annealing_optimize"](legacy_config(), *args)
    assert isinstance(first, list) and len(first) == 6
    values = iter([100.0, 90.0])
    ns["sa_evaluate"] = lambda *a, **k: (next(values), 1, 1, 1, 0, 0.2, [1] * 4)
    with contextlib.redirect_stdout(io.StringIO()):
        later = ns["simulated_annealing_optimize"](legacy_config(1), *args)
    assert isinstance(later, tuple) and len(later) == 2


def test_upstream_rejected_qos_feedback():
    ns = legacy_functions()
    seen = []
    values = iter([(0.0, [1] * 4), (1000.0, [2] * 4), (1000.0, [3] * 4)])

    def evaluate(*a, **k):
        cost, q = next(values)
        return cost, 1, 1, 1, 0, 0.2, q

    def perturb(params, *a, **k):
        seen.append(k["qos_cost_each"])
        return params.copy()

    ns.update(sa_evaluate=evaluate, perturb=perturb)
    with contextlib.redirect_stdout(io.StringIO()):
        ns["simulated_annealing_optimize"](
            legacy_config(2),
            SimpleNamespace(runtime_policy_name="AQA"),
            None,
            None,
            SimpleNamespace(job_type_count=4),
            "unused",
        )
    assert seen == [[1] * 4, [2] * 4]  # rejected candidate changes next proposal guidance


@pytest.mark.parametrize("name", ["legacy_sa", "argos_v3_physical"])
def test_domain_properties(name):
    jobs = SimpleNamespace(
        job_type_count=4,
        all_max_job_power={i: v for i, v in enumerate([618, 732, 702, 698])},
        all_min_job_power={i: v for i, v in enumerate([199, 198, 202, 202])},
    )
    d = load_domain(ROOT, name, jobs, SimpleNamespace(utilization=0.6, idle_power=120.0))
    rng = np.random.default_rng(42)
    for _ in range(2000):
        d.validate(d.project(rng.normal(0, 10, 6)))
    for x in [[0] * 6, [100] * 6, [-100] * 6, [d.p_low, d.r_low, 0.8, 0.1, 0.1, 0.1]]:
        d.validate(d.project(x))
    if name == "argos_v3_physical":
        source = (
            ROOT
            / ".deps/CONDOR-FLEXDC/am_flexdc/flexdc_generic_sources/flexdc_generic_sources/flexdc_behavior_inference_utilities.py"
        )
        tree = ast.parse(source.read_text())
        f = next(
            x
            for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "calculate_pr_bounds"
        )
        module = ast.Module(
            body=[
                ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                f,
            ],
            type_ignores=[],
        )
        ns = {"PRBounds": lambda **kwargs: SimpleNamespace(**kwargs)}
        exec(compile(ast.fix_missing_locations(module), str(source), "exec"), ns)  # noqa: S102 - pinned pure function
        actual = ns["calculate_pr_bounds"](
            SimpleNamespace(
                pmin_kw_per_server=np.mean([199, 198, 202, 202]) / 1000,
                pmax_kw_per_server=np.mean([618, 732, 702, 698]) / 1000,
            )
        )
        assert d.p_low == actual.pbar_lower_kw_per_server
        assert d.p_high == actual.pbar_upper_kw_per_server
        assert d.pr_max == actual.pr_upper_kw_per_server


@pytest.mark.parametrize("lo,hi", [(0.3, 0.8), (0.0, 0.2)])
def test_impossible_simplex(lo, hi):
    with pytest.raises(ValueError):
        Domain("bad", 0.2, 0.7, 0.01, 0.1, lo, hi, 4)


def run_sequence(tmp_path, outcomes, seed=9, **overrides):
    d = Domain("test", 0.2, 0.7, 0.01, 0.1, 0.1, 0.8, 4)
    initial = (0.4, 0.05, 0.25, 0.25, 0.25, 0.25)
    c = ObjectiveContract(ROOT)
    iterator = iter(outcomes)

    def evaluator(*args):
        random.seed(123)
        np.random.seed(456)
        np.random.random(100)
        return next(iterator)

    settings = {
        "run_id": "test",
        "search_seed": seed,
        "arrival_seed": 1,
        "runtime_seed": 2,
        "iterations": len(outcomes) - 1,
        "temperature": 1.0,
        "cooling_rate": 0.95,
        "steps": (0.01, 0.01, 0.02),
        "smart_weight": False,
    }
    settings.update(overrides)
    result = optimize(initial, d, evaluator, c, NAMES, tmp_path / "iterations.jsonl", **settings)
    return result, [json.loads(x) for x in (tmp_path / "iterations.jsonl").read_text().splitlines()]


def with_objective(value, feasible=True):
    r = raw(p90=0.2 if feasible else 0.31)
    c = ObjectiveContract(ROOT)
    r["M_RSR"] = value - c.evaluate(0, r["p90"], r["Pj"]).Cfull
    return r


def test_best_feasible_sequence(tmp_path):
    result, rows = run_sequence(
        tmp_path, [with_objective(100), with_objective(80, False), with_objective(95)]
    )
    assert result.scientific_result["candidate_id"] == "test:2"
    assert result.best_scalar["candidate_id"] == "test:1"
    assert result.current["candidate_id"] == "test:1"
    assert not rows[-1]["accepted"]


def test_no_feasible(tmp_path):
    result, _ = run_sequence(tmp_path, [with_objective(80, False)])
    assert result.status == "NO_FEASIBLE_CANDIDATE_FOUND"
    assert result.scientific_result is None
    assert result.best_violation is not None


def test_initial_best_tie(tmp_path):
    result, _ = run_sequence(tmp_path, [with_objective(90), with_objective(90)])
    assert result.scientific_result["candidate_id"] == "test:0"
    assert set(result.to_dict()) == {
        "status",
        "scientific_result",
        "current",
        "best_scalar",
        "best_feasible",
        "best_violation",
        "evaluations",
        "error",
    }


@pytest.mark.parametrize("bad", [{}, raw(counts=[0] * 4), raw() | {"mean_tracking": float("nan")}])
def test_malformed_return(tmp_path, bad):
    result, rows = run_sequence(tmp_path, [bad])
    assert result.status == "EXECUTION_ERROR"
    assert result.scientific_result is None
    assert len(rows) == 1


def test_search_rng_isolation_reproducibility(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    outcomes = [with_objective(90), with_objective(95), with_objective(85)]
    _, x = run_sequence(a, outcomes, arrival_seed=100, runtime_seed=200)
    _, y = run_sequence(b, outcomes, arrival_seed=101, runtime_seed=201)
    for u, v in zip(x, y):
        for key in [
            "Pbar",
            "R",
            "weights",
            "acceptance_draw",
            "search_rng_before",
            "search_rng_after",
        ]:
            assert u[key] == v[key]
    rng = search_rng(9)
    before = state(rng)
    np.random.seed(444)
    random.seed(555)
    assert state(rng) == before


def test_objective_can_rank_feasible_above_infeasible():
    c = ObjectiveContract(ROOT)
    assert c.evaluate(monetary=30, p90=0.4, pj=[0] * 4).Cfull < c.evaluate(60, 0.2, [0] * 4).Cfull


def test_corrected_rejected_feedback_stays_current(tmp_path):
    bad = raw(money=10000, pj=[0, 0, 0, 0.9])
    result, rows = run_sequence(tmp_path, [raw(), bad, bad], smart_weight=True)
    assert not rows[1]["accepted"] and not rows[2]["accepted"]
    assert rows[1]["weights"] == rows[2]["weights"] == [0.25] * 4
    assert result.current["candidate_id"] == "test:0"


def test_real_generator_seed_controls_without_simulation():
    from argos.diagnostics.workload_seed_forensics import generate, load_generator, table_hash

    tables, E, J = load_generator(ROOT)
    m = json.loads((PANEL / "manifest.json").read_text())
    spec = m["specification"]
    c = spec["cases"][0]
    e = E(str(ROOT / spec["experiment_path"]))
    e._utilization = 0.6
    j = J(str(ROOT / c["workload_path"]))
    search = search_rng(77)
    before = state(search)
    _, a, _ = generate(tables, e, j, 1841060571)
    _, b, _ = generate(tables, e, j, 1841060571)
    _, other, _ = generate(tables, e, j, 2381098110)
    assert table_hash(a) == table_hash(b)
    assert table_hash(a) != table_hash(other)
    assert state(search) == before
    assert table_hash(a) == next(
        x["initial_job_table_hash"] for x in c["initial_references"] if x["seed"] == 1841060571
    )


def test_legacy_proxy_is_not_pj(tmp_path):
    import importlib

    import pandas as pd

    from argos.diagnostics.workload_seed_forensics import load_generator

    load_generator(ROOT)
    probability = importlib.import_module("peacsim.calculate_qos_cost").calculate_delay_prob
    summary = importlib.import_module("peacsim.extract_qos_metrics").write_qos_summary_df
    table = pd.DataFrame(
        {
            "job_type_id": [0] * 3,
            "arrival_time": [1, 2, 3],
            "end_time": [-1] * 3,
            "min_execution_time": [10] * 3,
        }
    )
    sim = SimpleNamespace(
        _job_table=table,
        _job_config=SimpleNamespace(all_job_qos_constraints={0: 3}),
        _idle_status=-1,
        _simulation_duration=3600,
        _job_type_count=1,
        qos_violation_percentile_cutoff=0.9,
        _output_dir=str(tmp_path) + "/",
    )
    _, proxy = summary(sim)
    assert proxy == 0
    assert probability(1, 1, table, {0: 3}, {0: 10}) == [1.0]

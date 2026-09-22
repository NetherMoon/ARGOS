"""Use ARGOS assessment; preserve authoritative FlexDC Pj and support."""

import math
from types import SimpleNamespace

from argos.contracts import assessment
from argos.types import Metrics


def assess(raw, job_names, objective):
    empty = {
        "valid": False,
        "feasible": False,
        "reason": "INVALID_OBSERVATION",
        "offending": [],
        "tracking_pass": None,
        "per_job_pass": [],
    }
    if not isinstance(raw, dict) or raw.get("status") != "COMPLETE":
        return empty
    pj, counts = raw.get("Pj"), raw.get("evidence_counts")
    if (
        not isinstance(pj, (list, tuple))
        or not isinstance(counts, (list, tuple))
        or len(pj) != len(job_names)
        or len(counts) != len(job_names)
    ):
        return dict(empty, reason="MISSING_JOB_TYPE_EVIDENCE")
    try:
        if not all(
            math.isfinite(float(x))
            for x in [raw["p90"], raw["mean_tracking"], raw["M_RSR"], objective, *pj]
        ):
            return empty
        if raw["p90"] < 0 or raw["mean_tracking"] < 0 or any(x < 0 or x > 1 for x in pj):
            return empty
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in counts):
            return dict(empty, reason="MISSING_JOB_TYPE_EVIDENCE")
        evidence = [
            SimpleNamespace(
                job=SimpleNamespace(index=i, section=name), pj=pj[i], observation_count=counts[i]
            )
            for i, name in enumerate(job_names)
        ]
        o = SimpleNamespace(
            valid=True,
            metrics=Metrics(raw["mean_tracking"], raw["p90"], tuple(pj), objective),
            qos_evidence=evidence,
            execution_status="PARSED",
        )
        a = assessment(o)
        from argos.contracts import QOS_LIMIT

        offending = [
            {"index": i, "job": name, "Pj": pj[i]}
            for i, name in enumerate(job_names)
            if pj[i] > QOS_LIMIT
        ]
        reason = (
            "TRACKING_AND_QOS_FAIL"
            if offending and not a["tracking_pass"]
            else "QOS_FAIL"
            if offending
            else "TRACKING_FAIL"
            if not a["tracking_pass"]
            else "FEASIBLE"
        )
        return {
            "valid": True,
            "feasible": a["evidence_qualified_feasible"],
            "reason": reason,
            "offending": offending,
            "tracking_pass": a["tracking_pass"],
            "per_job_pass": [v <= QOS_LIMIT for v in pj],
            "authority": a,
        }
    except (TypeError, ValueError, KeyError, OverflowError):
        return empty

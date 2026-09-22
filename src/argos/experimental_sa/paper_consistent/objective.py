"""Component view of the existing ARGOS scientific cost authority."""

from dataclasses import asdict, dataclass

import numpy as np

from argos.simulator.configuration import canonical_costs, read_ini


@dataclass(frozen=True)
class Objective:
    M_RSR: float
    Ctrack: float
    CQoS: float
    Cfull: float
    qos_terms: tuple

    def to_dict(self):
        return asdict(self)


class ObjectiveContract:
    def __init__(self, root):
        self.costs = canonical_costs(root)
        upstream = read_ini(
            root
            / ".deps/FlexDC/configs/optimization/simulated_annealing/SA_train_low_util_RSR_1000server.ini"
        )
        local = read_ini(root / "configs/canonical_cost_source.ini")
        for section in ("cost_function", "dr_program"):
            if dict(upstream[section]) != dict(local[section]):
                raise ValueError("Pinned and canonical cost constants disagree")

    def evaluate(self, monetary, p90, pj):
        c = self.costs
        full = c.objective(float(monetary), float(p90), tuple(pj))
        tracking = float(c.psi1 * np.logaddexp(0, c.psi2 * (p90 - c.tracking_error_constraint)))
        terms = tuple(
            float(x) for x in c.beta * np.logaddexp(0, c.rho * (np.asarray(pj) - c.qos_constraint))
        )
        return Objective(float(monetary), tracking, float(sum(terms)), full, terms)

# Corrected ARGOS v0.3.0 / controlled campaign v2

The user authorized a separately versioned correctness fix after campaign v1 stopped.
The original v0.2.0-pretest tag, pinned dependencies, selected model and v1 results are retained.
See CONTROLLED_CAMPAIGN_V1_STOP.md for the original failure and affected experiments.

## Numerical change

Only the bounded-logistic weight transform changes optimization mathematics. ARGOS now solves
the scalar offset by 80 bracketed bisection steps in float64, then casts to the input dtype.
The bracket is derived from the desired average sigmoid probability and each row's minimum
and maximum logits. Unlike the prior unbracketed Newton updates, the root remains bracketed.
Returned rows must satisfy the existing 1e-6 sum contract; Domain.validate is unchanged.

For d_i=(upper-lower)*sigmoid(z_i+lambda)*(1-sigmoid(z_i+lambda)), the implemented first derivative is

    dw_i/dz_j = d_i * (delta_ij - d_j / sum_k d_k).

This follows by implicit differentiation of sum_i w_i=1. Fully numerically saturated rows
have zero local slope. Second derivatives are intentionally unsupported; the optimizer uses
first derivatives. The affine-softmax branch retains its original formula.

The correction lives in ARGOS's private optimizer function namespace. The pinned source
and optimizer bytecode, trained model, features, objective, safety thresholds, budgets and
initialization settings remain unchanged. Both snapshot capture and non-capture paths use
the corrected transform. Every V3-based method uses the same corrected bank and original
endpoint ranking, so this is a corrected V3 comparison, not a claim about unchanged v0.2.0.

## Regression coverage

Numerical regressions include the actual c001/start454/iteration150 logits, two saturated
counterexamples, J=3/4/5/6/8, float32/float64, random logits across three scales,
finite-difference gradient checks, translation/permutation invariance, zero-sum gradients,
affine and singleton feasible domains, and rejection of invalid inputs.
The real-checkpoint regression uses the original 512 starts and bank seed 300001 through
iteration 200, beyond the original failure. The scenario-invariance and capture parity
regressions remain enabled. A full 1500-iteration validation is recorded separately before
scientific execution.

Candidate-bank raw endpoints, starts, snapshots, trajectory, resolved settings, domain and
optimizer duration are now persisted and hashed before selection/region construction.
A failure-injection regression verifies raw evidence survives a region-construction exception.
Unvalidated raw outputs are never marked as a complete reusable bank.

## New frozen protocol

After tests pass, tag the corrected core v0.3.0-pretest and derive controlled_v2.json with
scripts/freeze_campaign_v2.py. It records the new core and transform identity and preserves
every v1 case, seed, budget and predeclared serious subset. No outcome-driven seed changes.
The existing ledger and provenance files remain byte-identical; reserved benchmark pools
are neither printed nor executed.

V2 writes only to runs/campaigns/controlled_development_v2, recomputes its banks and reruns
engineering smoke. No v1 physical result is imported. Its source and bank identities prevent
old/new optimizer results from being mixed. Use the pinned paper Python and pass the v2
config explicitly to scripts/campaign_gate.py before execution.

## Scope and interpretation

47 contexts / 227 method cases remain declared, including five engineering-only smoke cases.
Historical V4 authority remains the user-approved pinned INIs plus composition/QoS manifest.
The unchanged SA implementation remains protocol-incompatible. No learned components added.

All v1 serious cases were incomplete when the contract failed. The old five-method smoke
is still evidence for v0.2.0 only; it cannot validate v0.3.0. Rerun all v2 comparisons under
the corrected frozen identity. Preserve every NO_BID, invalid execution and confirmation
failure; a new correctness issue again requires a documented campaign stop.

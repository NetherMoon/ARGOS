# ARGOS vNext W2 development report

Final eight-original verification is PENDING USER RUN. No mixed/generalization campaign was reopened.

## Frozen identity

Protocol/code freeze: 4f2fc8e. Branch: argos-vnext-original-workloads. H1 tag: v0.3.0-h1-closed. See VNEXT_OFFLINE_DIAGNOSIS.md for predeclared constants, offline evidence and selection rule.

## W2 development

| Case | Method | Qualified search | Robust search | Confirmation passes | Search calls | Unique points | Repeats | Selected objective | Winner source |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| c005 | E | 1 | 0 | 0/3 | 32 | 32 | 0 | 87.581331 | protected_v3_elite |
| c005 | ER | 1 | 0 | 0/0 | 32 | 29 | 3 | -- | NO_BID |
| c005 | ERT | 1 | 0 | 0/0 | 32 | 26 | 6 | -- | NO_BID |
| c005 | H1 | 0 | 0 | 0/0 | 32 | 32 | 0 | -- | NO_BID |
| c006 | E | 0 | 0 | 0/0 | 32 | 32 | 0 | -- | NO_BID |
| c006 | ER | 0 | 0 | 0/0 | 32 | 31 | 1 | -- | NO_BID |
| c006 | ERT | 1 | 1 | 3/3 | 32 | 29 | 3 | 102.559421 | local |
| c006 | H1 | 0 | 0 | 0/0 | 32 | 32 | 0 | -- | NO_BID |
| c007 | E | 1 | 0 | 1/3 | 32 | 32 | 0 | 91.256468 | V3 snapshot |
| c007 | ER | 1 | 0 | 0/0 | 32 | 30 | 2 | -- | NO_BID |
| c007 | ERT | 1 | 0 | 0/0 | 32 | 29 | 3 | -- | NO_BID |
| c007 | H1 | 1 | 0 | 1/3 | 32 | 32 | 0 | 91.256468 | V3 snapshot |
| c008 | E | 0 | 0 | 0/0 | 32 | 32 | 0 | -- | NO_BID |
| c008 | ER | 0 | 0 | 0/0 | 32 | 32 | 0 | -- | NO_BID |
| c008 | ERT | 1 | 1 | 3/3 | 32 | 31 | 1 | 100.407889 | local |
| c008 | H1 | 0 | 0 | 0/0 | 32 | 32 | 0 | -- | NO_BID |

Zero confirmations means no bid was returned; it is not 0/3 attempted confirmations. H1/E preserve single-scenario selection; ER/ERT require the declared robust search screen. Search robustness is not statistical reliability.

## Mechanism diagnostics

- c005 E: 2 unique protected elites, 2 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c005 ER: 2 unique protected elites, 2 qualified; 2 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c005 ERT: 2 unique protected elites, 2 qualified; 5 provisional points failed a repeated screen; 9 unique targeted/boundary queries, 5 qualified.
- c005 H1: 0 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c006 E: 2 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c006 ER: 2 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c006 ERT: 2 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 10 unique targeted/boundary queries, 3 qualified.
- c006 H1: 0 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c007 E: 2 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c007 ER: 2 unique protected elites, 0 qualified; 1 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c007 ERT: 2 unique protected elites, 0 qualified; 1 provisional points failed a repeated screen; 5 unique targeted/boundary queries, 1 qualified.
- c007 H1: 0 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c008 E: 2 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c008 ER: 2 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.
- c008 ERT: 2 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 8 unique targeted/boundary queries, 1 qualified.
- c008 H1: 0 unique protected elites, 0 qualified; 0 provisional points failed a repeated screen; 0 unique targeted/boundary queries, 0 qualified.

ER records diagnostic region radii but uses its fixed .12 proposal radius; adaptive radii are applied only by ERT. ERT bundles targeted probes, region adaptation and V3 proposal scoring. An ERT-versus-ER difference cannot isolate those components individually. Same-scenario anchor deltas and query provenance support narrower mechanistic observations. No correction was deployed: offline C1/C2/C3 failed the declared improvement criteria.

## Frozen selection

Selected method: **ERT**, using the predeclared lexicographic rule.

```json
[
  {
    "method": "ERT",
    "selection_key": [
      -2,
      -6,
      -2,
      -4,
      58,
      8,
      3
    ]
  },
  {
    "method": "E",
    "selection_key": [
      0,
      -1,
      0,
      -2,
      84,
      8,
      1
    ]
  },
  {
    "method": "H1",
    "selection_key": [
      0,
      -1,
      0,
      -1,
      105,
      12,
      0
    ]
  },
  {
    "method": "ER",
    "selection_key": [
      0,
      0,
      0,
      -2,
      84,
      16,
      2
    ]
  }
]
```

## Original verification and W1

All8 original verification contexts remain pending. The offline W1 control does not replace fresh W1 verification. No claim of preserved W1 scientific performance is made yet. The user will run the frozen choice with a separate search/repeat/confirmation pool.

## GPU and timing

Development uses the unchanged paper CPU environment,4 torch threads and4 FlexDC workers. RX7700S/gfx1102 was enumerated by HIP6.2, but no functioning local PyTorch/HIP environment was established. GPU parity/speed benchmarks were not run. See VNEXT_ROCM.md. Candidate-bank time, active logical time and simulator time are recorded separately; shared-bank time is not multiplied into physical campaign time.

## Remaining failures

- c005 E: DONE; confirmation 0/3. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c005 ER: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c005 ERT: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c005 H1: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c006 E: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c006 ER: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c006 H1: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c007 E: DONE; confirmation 1/3. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c007 ER: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c007 ERT: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c007 H1: DONE; confirmation 1/3. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c008 E: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c008 ER: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.
- c008 H1: NO_BID; confirmation 0/0. Scientific failures retain all actual p90, Pj, evidence counts and objectives in the result JSON/query audit.

### Actual metrics for remaining failures

| Case | Method | Evidence | p90 | Pj in job order | Objective | Per-job observation counts |
|---|---|---|---:|---|---:|---|
| c005 | E | failed confirmation | 0.332000 | 0.000000, 0.036187, 0.000000, 0.001415 | 86.639695 | [21545, 19179, 14705, 12019] |
| c005 | E | failed confirmation | 0.315000 | 0.000000, 0.093193, 0.021338, 0.099550 | 89.875925 | [21203, 19026, 15185, 12216] |
| c005 | E | failed confirmation | 0.327000 | 0.000000, 0.000000, 0.000000, 0.249245 | 90.942818 | [21628, 18978, 14776, 12254] |
| c005 | ER | closest search observation, not a returned bid | 0.285000 | 0.000000, 0.005028, 0.034496, 0.070184 | 87.581331 | [21479, 18895, 15104, 12055] |
| c005 | ERT | closest search observation, not a returned bid | 0.288000 | 0.000000, 0.010109, 0.044561, 0.074913 | 87.490420 | [21479, 18895, 15104, 12055] |
| c005 | H1 | closest search observation, not a returned bid | 0.301000 | 0.000000, 0.020377, 0.071575, 0.071512 | 87.609153 | [21479, 18895, 15104, 12055] |
| c006 | E | closest search observation, not a returned bid | 0.342000 | 0.000378, 0.000000, 0.000000, 0.000000 | 102.476108 | [29074, 25499, 19865, 16412] |
| c006 | ER | closest search observation, not a returned bid | 0.342000 | 0.000378, 0.000000, 0.000000, 0.000000 | 102.476108 | [29074, 25499, 19865, 16412] |
| c006 | H1 | closest search observation, not a returned bid | 0.342000 | 0.000378, 0.000000, 0.000000, 0.000000 | 102.476108 | [29074, 25499, 19865, 16412] |
| c007 | E | failed confirmation | 0.304000 | 0.000000, 0.000000, 0.000000, 0.252333 | 95.268296 | [21268, 18951, 14838, 12112] |
| c007 | E | failed confirmation | 0.263000 | 0.000000, 0.009075, 0.000000, 0.384565 | 98.347729 | [21461, 19175, 14761, 12324] |
| c007 | ER | closest search observation, not a returned bid | 0.296000 | 0.000000, 0.000000, 0.000000, 0.069258 | 91.256468 | [21416, 19135, 14769, 12043] |
| c007 | ERT | closest search observation, not a returned bid | 0.293000 | 0.000000, 0.000000, 0.000000, 0.032387 | 90.029758 | [21416, 19135, 14769, 12043] |
| c007 | H1 | failed confirmation | 0.304000 | 0.000000, 0.000000, 0.000000, 0.252333 | 95.268296 | [21268, 18951, 14838, 12112] |
| c007 | H1 | failed confirmation | 0.263000 | 0.000000, 0.009075, 0.000000, 0.384565 | 98.347729 | [21461, 19175, 14761, 12324] |
| c008 | E | closest search observation, not a returned bid | 0.514000 | 0.000000, 0.000000, 0.000000, 0.000000 | 103.981150 | [28745, 25335, 19887, 16415] |
| c008 | ER | closest search observation, not a returned bid | 0.514000 | 0.000000, 0.000000, 0.000000, 0.000000 | 103.981150 | [28745, 25335, 19887, 16415] |
| c008 | H1 | closest search observation, not a returned bid | 0.514000 | 0.000000, 0.000000, 0.000000, 0.000000 | 103.981150 | [28745, 25335, 19887, 16415] |

The final H1 comparison receipt is archived alongside this report. Final readiness for mixed testing is not established while independent original verification remains pending. No budgets, seed pools, or algorithm constants were changed in response to scientific outcomes.

# Execution plan and design

1. Initialize and pin clean dependencies; inventory immutable artifact.
2. Audit and establish prediction parity using artifact source and saved predictions.
3. Capture per-start trajectories without changing optimizer semantics; prove endpoint parity.
4. Test normalized legal geometry, diverse regions and bounded candidate generation.
5. Validate one exact FlexDC call with episode-local configurations and outputs.
6. Implement and test automatic bounded refinement and fresh frozen-candidate confirmation.
7. Implement recovery and reproducible reporting; execute small and declared full episodes.
8. Finish documentation and commit/push validated milestones.

Stop at a failed scientific gate. Keep source repos, clones and artifact immutable.
No local GP, residual or reliability model belongs in the core.

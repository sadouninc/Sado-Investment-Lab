# Copilot PoC1 implementation lane

担当: 🌙ルナ
種別: Platform Experiment / Safety Contract
Reference: Issue #429 / #431

## Purpose

This PoC tests whether one manually dispatched GitHub Actions run can take a small `READY_FOR_IMPLEMENTATION` Issue toward review-ready output without asking the owner for implementation-time confirmation.

## Fixed boundaries

- Manual `workflow_dispatch` only.
- Issue #79 is fail-closed.
- GitHub token permissions are `contents: read` and `copilot-requests: write` only.
- The agent may edit only the ephemeral Actions worktree and run existing validation commands.
- No commit, push, PR/Issue write, merge, close, dependency change, workflow self-change, secrets/permission/billing change, destructive operation, or Investment Authority decision.
- No transcript artifact by default.
- If the Issue cannot be completed within the boundary, the correct outcome is `BLOCKED`, not scope expansion.

## Pilot eligibility

The target Issue must be open and its body must explicitly contain `READY_FOR_IMPLEMENTATION`. It should be a small, self-contained implementation slice with clear Acceptance Criteria and no dependency/workflow/canonical-investment-state change.

## Result contract

The run summary records:

- outcome (`REVIEW_READY` or `BLOCKED`)
- changed files
- validation commands/results
- blocked reason
- confirmation count (target: 0)
- working-tree diff stat

PoC1 intentionally does not persist the generated patch. This first run validates capability, safety, quality, and cost before Gate B considers a branch/PR-return path.

## Authentication / billing

PoC1 uses the Actions built-in `GITHUB_TOKEN`; it does not introduce a PAT or repository secret. The repository/organization must already permit Copilot CLI requests. Any required policy, billing, secret, or permission change is an Owner gate and must fail closed rather than being inferred or changed by the agent.

# Code-size and quality enforcement

The complete acceptance gate is:

```text
PYTHONPATH=src .venv/bin/python tools/integration_checkpoint.py
```

It runs pinned Pylint structural and production-duplication checks, Pyright
type/private-access checks over production, tests, and maintenance tools, the
aggregate size budget, compilation, the full behavioral suite, and
`git diff --check`. Existing diagnostic sites are grandfathered individually;
new sites and worsened structural measurements fail. New Python files under
`src`, `tests`, or `tools` enter the aggregate budget automatically.

## Bootstrap and hooks

Create the task-local environment and activate the checked-in pre-push hook:

```text
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-quality.txt
.venv/bin/python tools/install_git_hooks.py
.venv/bin/python tools/install_git_hooks.py --check
```

The installer uses worktree-specific Git configuration. It refuses to replace
an existing `core.hooksPath` or bypass an existing default `pre-push` hook. It
does not edit any other checkout. `--audit-worktrees` reports how all retained
worktrees are configured without changing them; each active owner must install
the hook in their own worktree after this change reaches their base.

The hook runs the whole gate before every push. It is intentionally expensive
and can be bypassed with Git's `--no-verify`, so it is deterministic local
enforcement, not a security boundary. The GitHub Actions `quality` job runs the
same gate on pull requests and `main`. After this bootstrap reaches `main`, the
`trusted-policy` workflow also runs the base branch's checker and pinned tools
against proposed files under `pull_request_target`; it does not execute proposed
Python. Repository administrators must make both jobs required branch checks if
merge blocking is desired.

At bootstrap on 2026-09-20, the GitHub API reported that `main` was unprotected
and the repository had no rulesets. CI is therefore present but not yet a
verified merge blocker; no remote security setting was changed by this work.

## Budgets and trusted policy

`.quality/baseline.json` records the measured starting budgets and individual
Pylint/Pyright debt. Code-bearing lines exclude blanks, comments, and standalone
docstrings. Statements are all non-docstring `ast.stmt` nodes. Definitions are
all synchronous/asynchronous functions and methods, including nested/private
ones. Production (`src`), tests (`tests`), maintenance (`tools`), and their
overall total are separate non-growth budgets. Content modules, adapters, and
helpers remain in production; there is no directory that hides first-party
Python from the overall total.

The gate defaults to the approved policy at `PF2E_TRUSTED_BASE` or
`origin/main`, including when the checkpoint is run manually. It extracts and
runs that ref's checker, budget code, configuration, baseline, and exact pinned
tool expectations against the proposed tree. The proposed checker runs too.
Changing proposed measurements, fingerprints, exclusions, test discovery,
integration, hooks, workflows, or dependency pins therefore cannot make the
approved implementation disappear from the normal gate. The one-time bootstrap
is allowed only when the trusted base has no baseline.

Enforcement-code and configuration changes use two reviewable steps. First, a
baseline-only change adds the exact SHA-256 of each intended future Git entry
(canonical mode plus bytes) to
`approved_policy_hashes`; it must pass the old gate and be independently
reviewed. After that authorization is on the trusted base, a second change may
apply exactly those bytes and should remove the spent authorization. Unapproved
changes fail. Baseline budget changes remain visible and the old baseline still
gates the same proposal, so raising a number cannot excuse accompanying growth.
This repository mechanism still needs protected-branch administration: a local
hook is bypassable, and GitHub cannot require either workflow until an
administrator enables the checks.

## Committing consolidation targets

Before a consolidation implementation begins, land a policy-only change that
adds a named entry to `reduction_targets`. Its `paths` must cover the complete
mechanism and any adapters wherever they live, and `maximum` records all three
post-change ceilings. The first experiment should commit at least a 15% lower
code-line ceiling for one substantial duplicated production subsystem, without
raising its statement or definition ceiling. Test-family cleanup should use a
separate target and normally aim for 10% fewer test code lines. The old policy
continues to gate that target-setting change. A newly changed target is staged
during that policy PR and becomes active only after it is present on the trusted
base; the lower target therefore gates every subsequent implementation change.
Do not mix new content budgets with reduction work.

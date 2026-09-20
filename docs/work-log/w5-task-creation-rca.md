# W5 task-creation configuration failure

Root cause confirmed on 2026-09-20 during the user's requested RCA. Project `.codex/config.toml:1` hardcodes `model_catalog_json` to `/Users/andrewlee/.codex/worktrees/8bbe/pf2e-engine-game-2026-07-10/.codex/model-catalogs/luna-v2-20260918.json`. That old worktree no longer exists. Both the saved project and coordinator checkout inherit this path.

The app log records an automatic worktree-cleanup deletion candidate at `2026-09-20T13:26:44.245Z`, while creating the W5 Arms worktree. Its owner is old coordinator `01a0b7a8-3bca-78c0-86bb-67d7b6e1b320`; read-only task metadata maps that owner to worktree `8bbe`. The first configuration error follows at `13:26:44.932Z`. Thus the evidence identifies automatic cleanup of the catalog's containing worktree as the trigger. The underlying configuration defect is a shared project dependency on a disposable worktree's absolute path.

Bundled app code routes worktree creation through a project-specific `config/read` before allocating the new worktree. That call fails with `failed to resolve feature override precedence: No such file or directory (os error 2)`. The wrapper obscures which file is missing. Global config reads and existing tasks can still work.

Controlled reproduction with bundled `codex-cli 0.155.0-alpha.9.2`: a fresh temporary backend, using only initialize and config/read, succeeds for global configuration but reproduces the exact error for the saved PF2e project and coordinator checkout. The app and existing backend both have valid `/` working directories. User TOML parses successfully. A second fresh diagnostic backend with a process-only `model_catalog_json` override pointing to the saved project's surviving catalog succeeds for both project paths. No settings were changed; both diagnostic processes were stopped.

The saved project's and coordinator checkout's surviving catalog copies share SHA-256 `590844c732b8eede171eac4fd02bf648b04c79591524140cbc36cd8c6d3a0bad`. Repair should replace the stale absolute dependency with a verified durable or correctly resolved project-relative catalog path while preserving the exact catalog/models. Verify project config/read and then resume the six pending assignments. Restart alone is not a sufficient repair: a fresh backend reproduces the failure.

Evidence: app log `/Users/andrewlee/Library/Logs/com.openai.codex/2026/09/20/codex-desktop-2a023da3-1b80-44a1-b776-4e9b10d270f2-38462-t0-i1-000009-0.log`, lines 23490 and 23520–23522; tracked `.codex/config.toml:1`; read-only task metadata. Diagnostic script and extracted app snippets are temporary under `/tmp/pf2e-codex-rca`. RCA does not claim task creation has recovered or any W5 independent acceptance.

## Verified recovery

The authorized follow-up repaired the catalog reference to the durable saved-project copy in coordinator commit `3b1ef500ebb4fa08583f71db7feb1aa26d741927`, plus the matching one-line local environment repair in saved project and retained Arms checkout. No main commit/merge occurred; unrelated saved-project files remain untouched. The diagnostic backend passes project config/read without overrides. All six pending W5 tasks were successfully created from the repaired baseline with the requested Luna/Sol models and effort.

Codex's supported user setting `desktop.worktree-auto-cleanup-enabled` was set to false (previously absent/default true) to honor the user's requirement to retain existing checkouts. The installed app reads this setting before cleanup. All fourteen existing PF2e worktrees remained present after dispatch. This also avoids the installed cleanup implementation's forced filesystem removal fallback; merely locking Git worktrees would not reliably protect them. No live app restart was needed.

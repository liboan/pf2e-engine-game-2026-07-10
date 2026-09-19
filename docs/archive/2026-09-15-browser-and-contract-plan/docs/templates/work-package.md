# Work package: `<short result>`

Package states and work-in-progress rules come from [Codex delivery](../design/05-codex-delivery.md). Package, evidence, approval, and support records live in the [canonical registry](../../registry/README.md).

**Package ID:** `<stable-id>`  
**State:** `<state from the authoritative state machine>`  
**Type:** `rules | content | engine | API | client | verification | performance | integration | documentation`  
**Evidence risk tier:** `1 | 2 | 3` for a capability or support claim; otherwise `not a capability claim`  
**Operational risk:** `low | medium | high`, with reason: `<reason>`  
**Support promotion requested:** `yes | no`  
**Owner:** `<one thread/person>`  
**Independent verifier:** `<different thread/person>`  
**Base commit:** `<sha>`  
**Dependencies:** `<merged package IDs>`  
**Return state if blocked:** `<state>`

## Result and scope

**Result:** `<one user-visible, rules-visible, or operational claim>`

**In scope:**

- `<bounded change>`

**Out of scope:**

- `<explicit exclusion>`

**Allowed files or modules:** `<paths/owners>`

## Authority and inputs

- Owning design section: `<link>`
- Rule oracle and exact profile: `<link/ID, required for rules behavior; otherwise omit>`
- Source records and inventory: `<links, required for content/rules; otherwise omit>`
- Related decision packet or registry approval: `<link/ID when required>`
- Exact contracts consumed: `<versions/digests>`

Do not restate linked records. A contract change outside this package stops work.

## Select the gates that apply

Before `ready`, select gates by type, risk, touched contracts, and whether promotion is requested. Delete irrelevant examples rather than marking them not applicable.

- **Every package:** focused checks, current-integration verification, independent review, and bloat limits.
- **Rules/content:** authority, closed inventory, exact and illegal cases, and production compile/load.
- **Tier 2/3 rules:** required transformations, mutations, adopters, holdout, interactions, and review from [verification](../design/03-verification-strategy.md).
- **State/timing/persistence:** atomicity, revision, suspension, save/resume, retry, and randomness.
- **Encounter/API/client:** legal reachability and affected integration-owned continuous scenarios.
- **Performance:** named-hardware budgets and semantic equivalence.
- **Promotion:** every registry dimension, integrated commit, exclusions, and required [approval](../design/06-bloat-and-human-review.md).

| Selected gate | Why it applies | Evidence owner | Result and durable link |
| --- | --- | --- | --- |
| `<gate>` | `<type/risk/contract reason>` | `<owner>` | `<pending/pass/fail + link>` |

## Universal completion checks

- [ ] Diff matches the claim, files, and exclusions.
- [ ] Selected commands were rerun from the integration base and independently verified.
- [ ] Durable files and expiring artifacts follow policy or link an exception.

## Stop conditions

`<ambiguity, failed gate, new shared contract, identity branch, unsupported approximation, overlapping ownership>`

## Handoff

**Head commit:** `<sha>`  
**Files changed:** `<short list>`  
**Commands and results:** `<exact command -> result>`  
**Measurements:** `<summary plus reproduction manifest, if selected>`  
**Known exclusions/failures:** `<short list>`  
**Next action:** `<one action>`

`merged` means integrated only. Set `support-accepted` only after the integrated commit passes every selected promotion gate and the canonical registry contains the exact support and approval entries.

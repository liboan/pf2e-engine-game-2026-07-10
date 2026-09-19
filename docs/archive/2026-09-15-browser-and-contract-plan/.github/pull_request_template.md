<!-- Keep the filled claim, change, evidence, and risk text at or below 500 words. The fixed checklist labels do not count. Link logs; do not paste them. -->

## Claim

- Work package: `<link/ID>`
- Base/head: `<sha> / <sha>`
- Result: `<one sentence>`
- Exclusions: `<short list>`

## Change

`<Smallest behavior change, why it belongs now, and any shared contract changed. Do not retell project history.>`

## Selected evidence

Copy only the gates selected in the work package; do not add `not applicable` rows.

| Gate | Exact command or artifact | Result |
| --- | --- | --- |
| `<selected gate>` | `<command/link>` | `<pass/fail + short fact>` |

## Risk and approval

- Plausible wrong behavior caught: `<example>`
- New unsupported behavior or migration risk: `<short list>`
- Independent verifier: `<name/thread and result>`
- Decision packet: `<link or none>`
- Registry approval/support entry: `<link if this PR performs an authorized promotion; otherwise none>`

## Fixed checklist

- [ ] The work package was `ready`, dependencies were merged, and ownership did not overlap.
- [ ] The diff matches the package claim, allowed files, and exclusions.
- [ ] Selected commands were rerun from the current integration base.
- [ ] The independent verifier reviewed the diff and selected evidence.
- [ ] Raw logs, traces, profiles, repeated reports, and superseded documents are not committed.
- [ ] Comments and durable artifacts follow the bloat policy.

Merging integrates code only. It does not make behavior `support-accepted`; that requires the exact integrated evidence and approval entries in the canonical registry.

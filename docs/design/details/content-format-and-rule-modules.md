# Content format and rule-module detail

**Status:** Proposed architecture detail; all examples are illustrative candidates
**Audience:** Content authors, compiler implementers, and module reviewers
**Owner:** [Rules and content strategy](../01-rules-and-content.md#small-data-format-and-typed-modules)

## Boundary and sources

The format composes engine-owned PF2e operations. It is not a scripting language, and a typed module does not become a private engine. The linked [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256), [Orc Ferocity](https://2e.aonprd.com/Feats.aspx?ID=4514), [Giant Monitor Lizard](https://2e.aonprd.com/Monsters.aspx?ID=3088), and [Shield Block](https://2e.aonprd.com/MonsterAbilities.aspx?ID=75) pages ground the candidate shapes below. No approved source records, behavior inventories, oracles, or capabilities exist for these examples, so they are non-authoritative and support nothing.

## Small fixed YAML

One versioned document shape contains metadata plus exactly one definition. Scalar references resolve inside the package or to compiler-known capabilities. Predicates and operations are tagged unions; arbitrary expressions, loops, callbacks, imports, and string interpolation are invalid.

```yaml
schema: pf2e-definition.v1
id: candidate.monster-core.giant-monitor-lizard.lurching-charge
version: 1
lifecycle: candidate
profile: candidate.remaster-2026-07-10
source_record: candidate.aon.monsters.3088
behavior_inventory: candidate.inventory.monsters.3088.lurching-charge
kind: activity
action_cost: 2
traits: []
requirements: []
plan:
  - op: invoke_core_procedure
    procedure: {key: core.stride, version: 1}
    input: {subject: self}
  - op: invoke_core_procedure
    procedure: {key: core.stride, version: 1}
    input: {subject: self}
  - op: invoke_core_procedure
    procedure: {key: core.strike, version: 1}
    input:
      subject: self
      strike_profile: {component: strikes.jaws}
```

This intentionally partial candidate composes the printed “Stride twice, then jaws Strike” sequence by invoking registered engine-owned procedures. `core.stride@1`, `core.step@1`, and `core.strike@1` are core procedure symbols, never DSL-authored definitions or rule modules. A plan may invoke a symbol but cannot redefine its legality, timing, traits, trigger behavior, movement, check, damage, or commit semantics. The jaws Strike profile is immutable content input to `core.strike@1`, not a replacement procedure. The source also contains a movement-dependent circumstance bonus absent here, so the inventory must remain `unsupported` and the candidate cannot load in production. Repetition is written explicitly rather than adding a loop.

A definition can bind exceptional behavior only to a build-registered module:

```yaml
schema: pf2e-definition.v1
id: candidate.player-core.orc-ferocity
version: 1
lifecycle: candidate
profile: candidate.remaster-2026-07-10
source_record: candidate.aon.feats.4514
behavior_inventory: candidate.inventory.feats.4514.orc-ferocity
kind: triggered_action
action_kind: reaction
resource_claims:
  - {kind: standard_reaction}
  - {kind: frequency_use, period: day, uses: 1}
module:
  key: orc_ferocity
  version: 1
  config: {}
```

The binding supplies versioned data only. `action_kind` causes the trigger window to add the per-creature response claim; the two resource claims separately account for the standard reaction and once-per-day use. The independently reviewed behavior inventory—not the YAML—decides whether every source clause is mapped.

## Compiler contract

The compiler parses one exact schema version, rejects unknown fields, canonicalizes ordering, resolves typed references, and emits an immutable definition plus digest. It verifies:

- profile, source-record, inventory, component, capability, and module references;
- lifecycle and production eligibility without conflating them;
- operation arguments, target types, traits, costs, predicates, duration anchors, and resource kinds;
- module configuration against that module's closed schema;
- that linked module configuration, moments, capabilities, operations, and result variants equal compiler-derived dependencies; and
- that no data path can choose behavior from a creature, encounter, fixture, display name, or raw ID.

The compiler never “best-effort” drops a field or converts unknown prose into behavior. A new operation or predicate is a shared Tier 3 contract change, not a content-local escape hatch.

## Typed first-party modules

Modules are normal first-party code but communicate through phase-specific sealed types. Here `MomentSpec` means the general [engine-owned phase contract](../02-engine-and-interfaces.md#momentspec-contract); reaction trigger discovery is one possible consumer, not its definition. Illustrative Python-like pseudocode:

```python
class RuleModule(Protocol[ConfigT, MomentInputT, MomentResultT]):
    key: ModuleKey
    version: int
    moments: frozenset[MomentSpec]

    def evaluate(
        self, ctx: ReadOnlyRulesView, moment: MomentInputT, config: ConfigT
    ) -> MomentResultT: ...

class ReactiveStrikeV1:
    moments = {ACTION_PROPOSED_V1, MOVEMENT_SQUARE_LEFT_V1,
               TRIGGERED_STRIKE_RESOLVED_V1}
    # Offer carries opaque source/target refs plus typed resource and
    # response-to-trigger claims.
    # Selection invokes the engine Strike procedure; a reviewed critical
    # manipulate result can return only the moment's typed parent directive.

class ShieldBlockV1:
    moments = {PHYSICAL_ATTACK_DAMAGE_PENDING_V1}
    # Returns a typed mitigation/split contribution; the engine owns damage,
    # shield HP, broken state, events, commits, and follow-on trigger windows.
```

The actual signatures use immutable inputs and the named moment's narrower output union. A module cannot mutate state, roll dice, read time/files/network, return a state patch, or invoke an unregistered procedure. It may compare opaque instance references only for typed relationships such as source equals target; it may not inspect raw identities. Reactive Strike and Shield Block are examples of interface pressure, not decisions that either must be implemented as these modules.

## Module authority, descriptor, and evaluation

Rules authority never lives in module code or comments. Citations and normalized facts live in approved source records, expected behavior in an approved oracle, and clause coverage plus mapping to a logical module key/version in independently reviewed behavior inventories. Comments may explain an invariant but cannot approve or replace those external records.

Every code-based module version has one external fixed-registry descriptor. It binds the module key/version and exact code artifact digest to source-record IDs/digests, behavior-inventory IDs/digests, oracle ID/digest, accepted `MomentSpec` key/version pairs, configuration-schema ID/digest, declared build imports and dependencies, engine procedure/capability symbols, and allowed result variants. The descriptor grants no dynamic discovery: the module remains first-party code outside the core engine, imported by an explicit build table, and neither engine nor module may dispatch on content or instance identity.

Build analysis and contract tests reconcile the module's actual import/dependency closure, linked engine symbols, registered moments, and emitted result variants with the descriptor in both directions. For each compiled definition that binds the module, compiler-derived module, moment, operation, capability, configuration, and result dependencies must also reconcile with the descriptor and independent inventory. Missing and extra dependencies both fail. Tests evaluate behavior against the external oracle; evidence and registry promotion remain external and cannot be inferred from a build, descriptor, comment, or passing test.

The digest graph is acyclic. The code artifact digest covers code; the descriptor digest is the package-facing module digest and binds that artifact plus the exact upstream authority records, but excludes evidence and promotion. Inventories and oracles target the logical module key/version, not the later descriptor digest. A package binds the frozen descriptor digest and thus the artifact; evidence manifests cite that package; promotion cites the package and evidence. No upstream record hashes downstream evidence or approval.

## Verification matrix

| Case | Minimum assertions |
| --- | --- |
| Schema and references | Unknown field, operation, version, typed reference, capability, module, or config fails closed. |
| Authority binding | Descriptor binds the exact artifact, source, inventory, oracle, configuration schema, and allowed interface digests. |
| Dependency derivation | Actual imports/dependencies, symbols, moments, and results reconcile with the descriptor; compiled dependencies reconcile with it and the independent inventory. |
| Identity independence | Renaming or reordering package, definition, component, and instance IDs changes only opaque references. |
| Module sealing | State patches, randomness, I/O, clock access, undeclared imports/dependencies, moments/capabilities, and disallowed results fail build or contract tests. |
| Fixed registry | Only build-registered module/version pairs load; filesystem additions and runtime discovery have no effect. |
| Production boundary | Candidate lifecycle, unsupported clauses, digest mismatch, or unapproved versions cannot enter production. |

## Closed operations and versioning

Initial operation families are fixed: invoke the engine-owned check, Strike, Stride/Step, damage/healing, condition/effect, and resource procedures, or a registered module. Each family owns its input version and allowed moments/results. The DSL selects registered symbols; it does not define procedure semantics. Definitions pin schema, profile, capability, compiler, and module versions. Contract changes compile to new versions; unreleased candidates are rebuilt rather than supported by compatibility fallbacks. Saves retain exact compiled-package digests.

## Proposed monorepo placement

The implementation layout remains a human decision in `STATUS.md`. A coherent candidate is:

```text
src/pf2e_engine/                 # moments, closed operations, state procedures
src/pf2e_rules/modules/          # first-party typed module code
src/pf2e_service/                # API, persistence, and composition root
content/packages/<package>/      # reviewed YAML and package metadata
tools/content_compiler/          # strict compiler and validators
src/pf2e_registry/generated/     # build-generated fixed registry
```

The build imports an explicit module table and compiles package references into that registry. Production accepts only the artifact/descriptor pair bound by the package; there is no entry-point discovery, runtime import, uploaded code, filesystem scan, or fallback execution. This keeps first-party printed behavior outside core engine code without creating a plugin system.

Dependency direction is one-way: `pf2e_engine` defines the immutable views and closed result types and does not import `pf2e_rules` or `pf2e_registry`. Rule modules import only those published engine interfaces. A service composition root imports the generated registry and injects registered modules into the engine; content identities therefore cannot leak into core dispatch.

## Promotion boundary

Every example above remains `candidate`. Support still requires an approved profile and source record, closed independent inventory, approved oracle where rules truth is involved, compiler-derived dependency reconciliation, fixed-registry build, and every required evidence dimension. Passing schema validation proves structure only.

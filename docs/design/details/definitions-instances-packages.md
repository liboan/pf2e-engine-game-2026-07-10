# Definitions, instances, and packages

**Status:** Proposed companion design
**Authority:** [Rules and content strategy](../01-rules-and-content.md) owns content lifecycle and loading policy; [Engine and interfaces](../02-engine-and-interfaces.md) owns canonical state and persistence. This document refines their boundary but approves no definition, package, oracle, capability, or profile.

## Source limitation

Archives of Nethys (AoN) is the sole rules source. The examples use live pages read on **2026-07-15**, while the proposed profile cutoff is **2026-07-10** and has no immutable approved profile record. They are illustrative `candidate` records only. They cannot establish what the cutoff contained, close an inventory, or support production play.

## Immutable definitions

A definition is the compiler's immutable, typed meaning for a published or engine-owned thing. Its stable `definition_id` identifies the concept; its `definition_digest` identifies one exact compiled payload. The payload contains rules-profile and source references, typed statistics and traits, declarative constructs, registered-module configuration, and compiler source maps. It contains no current HP, position, spent resources, owner, initiative, active conditions, or encounter identity.

The authoring file is input, not the loadable definition. Compilation resolves all references, type-checks the closed data format, links fixed-registry modules, and derives capability dependencies from constructs and linked symbols. Authors cannot add a trusted `requires` field. Any semantic edit produces a new definition digest; an existing digest is never rebuilt to different bytes.

Lifecycle is registry/package metadata with exactly three values:

- `candidate`: allowed only in verification environments;
- `supported`: eligible for production only after inventory, approval, and every evidence gate closes; or
- `retired`: unavailable for new production play and usable from a save only through an explicit migration.

Changing lifecycle publishes a newly reviewed package manifest, not a mutation to the definition payload. “Compiled successfully” never implies `supported`.

## Mutable instances

An instance is canonical encounter state with a stable `instance_id` and an exact definition reference:

```yaml
instance_id: "actor:vermin-catcher-2"
definition_ref:
  package_id: "example:npc-core-candidates"
  package_digest: "sha256:<exact manifest digest>"
  definition_id: "example:npc-core.vermin-catcher"
  definition_digest: "sha256:<exact compiled digest>"
state:
  hp: 21
  position: {map_id: "map:test", cell: [7, 4]}
  resources: {"example:rat-trap": 3}
  conditions: []
  ownership: "participant:gm"
```

This candidate instance is grounded in the live [Vermin Catcher](https://2e.aonprd.com/NPCs.aspx?ID=3499) entry from *NPC Core*, which currently lists 35 HP, Speed 25 feet, four rat traps, three Strike profiles, Giant Rat Trap, and Sneak Attack. Maximum HP, starting trap count, attacks, and abilities belong to the immutable definition. Damage taken, location, remaining traps, effects, and ownership belong to the instance. A fixture may choose the shown mutable values; it may not omit Giant Rat Trap or change Sneak Attack to make a test pass. If any inventory clause for those abilities is unsupported, the definition stays non-playable.

Items, effects, hazards, and areas follow the same rule: their instances store changing state and opaque relationships, while their exact meaning remains in referenced definitions. Instances may compare opaque references for rules relationships; shared code cannot branch on their names or raw IDs.

## Package manifest and digests

A package is the smallest distributable set of definitions and fixed-registry module references. Its closed manifest has this conceptual shape:

```yaml
schema: pf2e-successor-package-manifest.v1
package_id: <stable ID>
package_version: <monotonic version>
rules_profile: {id: <ID>, digest: "sha256:<digest>"}
compiler: {id: <ID>, version: <version>, digest: "sha256:<digest>"}
dependencies: [{id: <package ID>, digest: "sha256:<manifest digest>"}]
definitions:
  - id: <definition ID>
    digest: "sha256:<compiled digest>"
    lifecycle: "candidate | supported | retired"
    source_records: [{id: <ID>, digest: "sha256:<digest>"}]
    inventory: {id: <ID>, digest: "sha256:<digest>"}
    allowed_use_cases: [<reviewed boundary ID>]
    derived_capabilities: [{id: <ID>, version: <exact version>}]
    derived_modules: [{id: <ID>, version: <version>, digest: "sha256:<digest>"}]
modules: [{id: <ID>, version: <version>, digest: "sha256:<digest>"}]
prerequisite_approval_refs: [{id: <registry approval ID>, digest: "sha256:<digest>"}]
manifest_digest: "sha256:<digest>"
```

Unknown keys and missing keys fail validation. Definition digests hash canonical compiler output. `manifest_digest` hashes the canonical JSON manifest with that field omitted; package bytes are separately content-addressed if an archive exists. Source, inventory, profile, compiler, module, prerequisite-approval, and dependency digests are retained even when their IDs are stable. Derived capabilities and modules come from compiler output; the package-level module list is their exact sorted union, so the package author cannot add, omit, or edit a dependency.

Promotion evidence and the promotion approval are deliberately not embedded in this manifest: both are produced against an integration commit containing the manifest, so embedding them would create a self-invalidating digest cycle. The canonical registry instead joins the exact `manifest_digest` and integration commit to all seven evidence dimensions and the exact promotion-approval ID and digest. Only `generalization` may be `N/A`, with a reason. A candidate package can therefore be structurally valid without that acceptance join and still remain ineligible for production.

Small packages limit the review and migration blast radius. A package may depend on another exact package digest, but a definition reference resolves to one package only. Cycles, floating versions, “latest,” and fallback lookup are forbidden.

## Illustrative candidate definitions

The live [Electric Arc](https://2e.aonprd.com/Spells.aspx?ID=1509) entry from *Player Core* currently supplies activation traits, target/range, basic Reflex defense, electricity damage, and heightening facts. A candidate compiled definition might derive exact versions of `spell-activation`, `trait-semantics`, `spell-targeting`, `basic-save`, `typed-damage`, and `rank-heightening`. These capabilities are derived from compiled fields; the list is not an assertion that any capability exists today.

The live [Reactive Strike](https://2e.aonprd.com/Feats.aspx?ID=5832) entry from *Player Core 2* currently identifies several trigger categories, a melee Strike against the triggering creature, a critical-hit disruption case for a manipulate trigger, and a multiple-attack-penalty exception. A candidate definition could configure one registered typed module. Compilation would derive reaction-window, reach, Strike, degree, disruption, and MAP dependencies from the linked module and configuration. It remains `candidate` until its exact trigger timing, module contract, inventory, oracle, and evidence are independently accepted; this example settles none of those interpretations.

## Atomic loading and precise failure

Verification loading may opt into `candidate` definitions and records that fact. Production loading is atomic and uses no partial package. It:

1. validates manifest schema and recomputes all package and definition digests;
2. requires the exact approved profile, compatible compiler and package-schema versions, source and inventory records, and fixed-registry modules;
3. checks every definition is `supported`, every inventory is closed, and every allowed use case and compiler-derived dependency reconciles;
4. resolves canonical registry entries that bind this exact manifest digest and integration commit to prerequisite and promotion approvals plus every required evidence dimension; and
5. rejects missing, extra, stale, retired, candidate, unsupported, or digest-mismatched material before encounter creation.

The error report names package, definition, clause or dependency, expected value, actual value, and failed gate. It does not substitute another version, omit one definition, or defer mandatory unsupported behavior until a command reaches it.

## Save references and migration

A save stores instance state plus exact rules-profile, complete loaded package graph, definition, compiler, module, and serialization IDs and digests. It does not copy definitions into canonical state. Restore first resolves all exact artifacts and verifies their digests; absence or mismatch fails closed.

Same-identity recovery restores the same artifacts, receipts, random-provider position, and revision. Migrating to a new profile, definition, module, or package is a separately reviewed transformation that names source and destination digests, maps every affected instance/frame/resource, and emits a new snapshot and encounter lineage. It never overwrites the source save. A retired definition therefore requires an approved migration target; without one, the save remains preserved but cannot resume production play.

# Runic Weapon and physical weapon identity

## Status and purpose

Source-checked Astra design with delivered casting, saved decisions and terminal item selection. Independent source/public review found two P1s, both repaired. The final full integration passes after a stale reaction-test assertion was repaired and explicit negative-target checks added. See [current ownership and next action](ACTIVE.md); the sections below retain design and completed checkpoint evidence.

## Printed behavior

Rank-1 Runic Weapon takes two actions, concentrate/manipulate, touch, duration one minute. Target an unattended weapon or a weapon wielded by a willing creature. It grants +1 item attack bonus and two base weapon damage dice. Use the better permanent or temporary value separately for potency and striking; never add the bonuses or weaken permanent runes. [Runic Weapon](https://2e.aonprd.com/Spells.aspx?ID=1658), [Weapon Potency](https://2e.aonprd.com/Equipment.aspx?ID=2830), [Striking](https://2e.aonprd.com/Equipment.aspx?ID=2829).

No Sorcerous Potency on the enchantment or later weapon attacks; no Angelic Blood Magic. The weapon becomes magical for applicable existing trait checks.

## Small physical-item connection

Give the selected mundane longsword and shortsword definitions actual ItemInstances using existing initialization. Preserve runtime IDs across release, ground placement, retrieval and saves; an origin prefix is not current ownership.

One shared resolver maps a held compatible instance to an existing attack profile. An explicit item ID must be held and compatible. With one compatible held instance, infer it; with several, require selection. Retain literal handling for gear outside this conversion. This does not invent proficiency or an attack profile for an unfamiliar weapon.

Add optional item selection to Strike/Vicious Swing and retain it through saved attacks/reactions. The current helpers reconstruct current-actor-prefixed IDs and therefore need this repair for cross-actor transfers.

Initial spell targets are the selected longsword/shortsword families. Armor, shields, handwraps, fists and stowed/worn weapons are invalid. Additional weapon families are not implicitly supported.

## Cast and temporary effect

Use `Cast("runic_weapon", item_id=runtime_item_id, slot_id="angelic_rank1")` with a distinct saved `spell_target_item_id`. Creature and item targets conflict and reject before spending.

Locate the physical item. Ground weapons use their actual position; wielded weapons use the current wielder’s position. Use existing touch and line-of-effect rules, without an extra weapon attack or free-hand requirement. Other wielders make an explicit willingness choice; self-wielded and unattended targets do not need one.

Reuse actual casting commitment and manipulate reactions. A disrupted committed spell retains its costs and creates no effect. Preserve the exact target and wielder across choices and revalidate eligibility after interruption. Never substitute a different weapon or undo already committed reaction outcomes.

Before implementation, the owner should confirm where existing willingness is decided relative to resource commitment. Invalid targets known before commitment reject atomically; a later choice or interruption must follow the established commitment rules, not blindly refund the whole cast. This is a local implementation check, not a new user decision.

Use one concrete item-targeted record: effect ID, caster ID, item ID, source-start expiry and world-time expiry. The existing actor-targeted effect record need not become universal. Rank-1 values are fixed by this record type. At resolution, expire after ten source starts or sixty seconds using the shared clock. Drop/stow/retrieve, caster incapacitation and victory do not themselves cancel a nonsustained effect. Recasting replaces the same rank-1 record with a renewed duration, never stacked bonuses.

Compute effective potency as max(permanent potency, 1) and base weapon dice as max(permanent base dice, 2) while active. Permanent rune IDs and investment flags remain unchanged.

## Damage and maneuver boundaries

Reuse the existing damage composition: Vicious Swing with the enhanced longsword rolls 2d8 weapon plus 1d8 action; eligible shortsword Sneak Attack rolls 2d6 weapon plus separate 1d6 precision. No extra Potency or Blood Magic appears. Only actual weapon/striking dice count for rules based on weapon dice. [Weapon damage dice](https://2e.aonprd.com/Rules.aspx?ID=2194).

Carrying an enchanted sword gives no bonus to free-hand Trip/Grapple or Assurance. If a weapon with Trip/Grapple is later admitted, connect the actual item identity and effective item bonus to that maneuver, retaining Assurance’s modifier exclusion. Current weapon-maneuver helpers do not do this yet, so keep those targets outside the initial finite menu. [Trip trait](https://2e.aonprd.com/Traits.aspx?ID=716).

## Bounded implementation checkpoints

1. **Identity:** selected mundane instances, compatible held-item resolver and saved attack item. Prove drop/retrieve by another compatible actor through public commands.
2. **First enchantment:** actual item target and willingness, temporary record, effective rune profile. Prove one cast and improved Strike.
3. **Saved play and expiry:** interrupted cast/attack snapshots, terminal item selection, strict item/effect references, continuous fight and expiry tests.

Use one shared runtime owner. Split persistence/tests only after the exact contract is stable. Preserve existing numeric rune helpers. No higher spell ranks, broad catalogs or generated inventory.

## Six acceptance families

- Healthy-start fight: cast on willing adjacent Fighter, spend two actions/one slot, actual +1 attack and 2d8, then victory.
- Saved manipulate reaction and willingness; interrupted and direct results match, critical disruption retains cost without effect.
- Enchant/release/save/retrieve by another compatible actor/Strike; original item retains bonus, another mundane copy does not.
- Ordinary versus permanently +1 striking weapons; no stacking, exact expiry restores only the temporary benefit, permanent runes remain unchanged.
- Actual Vicious Swing and Sneak Attack preserve separate added dice; no Sorcerer bonus leakage.
- Invalid touch/stowed/nonweapon/ambiguous targets reject before commitment; malformed missing/duplicated item references or effect deadlines fail load.

This checklist defines the promised checks; the evidence below distinguishes completed paths from remaining coverage checks. No user P0/P1 decision was needed for the design.


## Released physical-item bridge

The public transfer probe now passes through recipient pickup, atomic ambiguous-selection rejection, explicit original-item Strike, an actual Hero choice and save/load retaining both held IDs and the pending selected item. Strike/ViciousSwing append `item_id` after existing optional arguments, preserving older positional calls. Compile passes and 34 focused regressions pass in 0.23 seconds. The delivered code covers model, encounter, persistence and content; the probe was not retained as a test file.

A separate bounded Luna run retained the route in `tests/test_weapon_item_identity.py`: two tests pass. They cover older positional Strike calls; real release, source movement and recipient retrieval; atomic ambiguous/wrong-item rejection; explicit transferred identity through a saved Hero choice and critical Strike; and a saved Reactive Strike retaining the selected source weapon. No core changes were needed for these tests. No new full-suite or Runic Weapon spell acceptance is claimed.

## First actual enchantment

After the first broad casting turn produced no executable checkpoint, the supervisor preserved the edits and narrowed the continuation to one cast and Strike. That public probe passed. `Cast("runic_weapon", item_id="sorcerer_ally:longsword")` consumed two actions and one Angelic rank-1 slot, offered the other wielder an actual willingness choice, and applied the effect on acceptance. The explicit sword Strike used modifier +10 and two d8 rolls (4 and 7), producing 30 critical damage.

The first probe used `ActiveItemSpellEffect`, with the exact physical item ID, potency 1, striking dice 2, magical true, source-start deadline 11 and world deadline 60. At that checkpoint, saved willingness, expiry, permanent-rune interaction, interruptions and malformed-save checks were still outstanding. The foreground probe exited; broader process enumeration was unavailable. Those later checks are recorded below; the first probe alone did not establish spell or Sorcerer acceptance.

## Released saved play, terminal and independent review

Later retained tests now cover saved willingness, the exact physical item, one-time action/slot costs, an active-effect Strike after reload, malformed effects and forged saved casting facts. A saved critical manipulate reaction disrupts the spell while retaining committed costs. Terminal casting selects an actual held or ground item and preserves the engine's willingness decision; it contains no enchantment calculation.

Seven public interaction tests cover the initial cast, release/save/retrieve by another compatible wielder, maximums with permanent runes, expiry, Vicious Swing's separate action die, Sneak Attack's separate precision die, and critical disruption. Test-local setup definitions extend lookup only during their tests; production catalog entries are unchanged. The healthy-start cast/save/enhanced-Strike path reaches victory.

Sol independently checked printed rules and ran actual alternate play. It found and verified repairs for:

- **Refusal after commitment:** a declined target originally bypassed Reactive Strike. The saved continuation now traverses the manipulate reaction window, retaining the exact item and paid costs, then finishes without enchantment. [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256).
- **Public spell information:** Runic Weapon originally still advertised one action, unavailable status and creature targets. Canonical metadata now advertises an available two-action item spell; creature targets are empty, while the terminal lists physical items from inspection. Sorcerer admission still waits for Light and local recovery. [Runic Weapon](https://2e.aonprd.com/Spells.aspx?ID=1658).

The independent duration regression saves at world time 60 before the later-initiative caster's expiry turn: the sword remains enhanced for the earlier actor, then expires at the correct caster start. Public probes also showed a same-rank recast replacing one effect and renewing deadlines from 11/60 to 12/66 without changing permanent item data, and caster unconsciousness leaving the enchantment intact. [Spell durations](https://2e.aonprd.com/Rules.aspx?ID=2221), [duplicate effects](https://2e.aonprd.com/Rules.aspx?ID=2266).

An accidental Runic staging edit moved the canonical dog from (5,2) to (3,2), introducing a valid reaction into the older Halo script. Restoring the accepted position fixed that regression; Runic tests now use public movement where needed. The final source/public review found no outstanding P0/P1. All reported probes/checks were synchronous and exited; host process enumeration was unavailable, so this is not a claim that shared MCP services stopped.

The first full integration also identified an older S2 test using the previous opaque unarmed reaction identifier. The test now selects the physical-item-aware identifier while retaining its fist, bludgeoning and nonlethal behavior checks. A separate negative-target test file rejects out-of-touch, stowed, shield, armor, missing/unknown item and conflicting creature/item requests. Each verifies unchanged inspection and exact saved bytes, including deterministic dice. This focused final group passes 12 tests; these are casting checks, separate from malformed-save checks.

## Final integration evidence

One final serial run passed **590 tests in 2.53 seconds**. The fresh wrapper measured **2.978477 seconds** wall and **64,241,664 bytes / 61.266 MiB** peak child memory on Python 3.11.1, macOS 26.3.1 arm64. Compile and whitespace checks passed. The suite includes the six negative-target cases and terminal save/casting tests; no redundant terminal smoke run was added.

Normal catalog APIs were checked immediately before the final tests-only fixes: 48 accepted setups and 32 creature definitions; staged lookup maps contain five setups and three definitions. This spell delivery does not admit the incomplete Angelic Sorcerer build. Light and local recovery are next. Every integration command exited, with no yielded worker left; shared desktop service shutdown was neither attempted nor claimed.

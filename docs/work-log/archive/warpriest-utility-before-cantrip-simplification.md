# Warpriest utility and alternate preparation

## Decision and status

Close the two advertised Warpriest gaps through two bounded Luna slices after the shared clock works. Astra checked the actual implementation and sources: Read Aura, Identify Magic and Sure Strike have no runtime delivery yet. Reuse the existing item-magic query, resource validation and saved-check procedures. This packet is design evidence, not support or test evidence.

No P0 blocker remains. The explicit local adjudications below use the user's delegated GM judgment. Do not add a general item-identification or spell-preparation framework.

## Read Aura and actual identification

Proposed public interface:

```python
game.read_aura(actor_id, item_id, advised_actor_ids=())
game.identify_magic(actor_id, item_id, skill)
```

Both are outside-combat atomic activities, with no pending decision and the same consciousness/unresolved-health guards as recovery.

**Read Aura:** require real casting access, a real accessible item within 30 feet and line of effect. Advance 60 seconds through shared effect expiry, then inspect the live item's magic. Reuse `_item_is_magical`, which already recognizes attached runes and active Runic Weapon. A subsequent Read Aura cannot demonstrate a positive result from the one-minute Runic Weapon: that enchantment expires by completion. Use permanent runed equipment for the positive case. [Read Aura](https://2e.aonprd.com/Spells.aspx?ID=1646).

Record the magical result and object-specific +2 circumstance identification benefit for the caster and actually advised recipients. The spell specifies neither a duration nor one-check consumption; preserve this knowledge for the unchanged admitted object. The spell's 30-foot limit applies to the object, not later communication. Illusion objects remain excluded. A mundane result does not authorize Identify Magic, and Detect Magic is a separate unimplemented spell rather than a prerequisite.

**Identify Magic:** require that the actor knows this object is magical, can examine it, and is trained in an applicable skill. Fundamental runes have the general magical trait, so trained Arcana, Nature, Occultism or Religion can apply. Advance 600 seconds before resolving the check against current conditions/effects. Apply Read Aura through ordinary typed stacking. [Skills](https://2e.aonprd.com/Skills.aspx?General=true&ID=22), [action and outcomes](https://2e.aonprd.com/Actions.aspx?ID=2365).

Use literal item-bound scene facts: item ID, DC, and nonempty false-identification text chosen before the roll. Do not let the player choose a DC on each attempt. For the admitted common +1 striking longsword, use **DC 19**, the level-4 standard difficulty, as a bounded GM adjudication. Success information comes from actual rune facts. [DCs](https://2e.aonprd.com/Rules.aspx?ID=2627), [striking](https://2e.aonprd.com/Equipment.aspx?ID=2829), [weapon potency](https://2e.aonprd.com/Equipment.aspx?ID=2830).

- Critical success: all attributes and curse status.
- Success: function and activation; no retry simply to seek critical success.
- Failure: actor/item retry deadline at completion plus 86,400 seconds.
- Critical failure: authored misinformation. Its result does not say “as failure,” so do not silently add the failure cooldown.

The check is secret. Since the actor knowingly initiated it, offer a generic saved keep/reroll Hero choice before revealing information. Player-facing events must not disclose the die, DC or degree. Preserve the real result through save/load; no encryption or mystery subsystem is needed. [Secret checks](https://2e.aonprd.com/Rules.aspx?ID=2263).

## Sure Strike and a legal preparation

Add a fixed alternate Warpriest definition/setup: replace `ordinary_heal_2` with rank-1 Sure Strike, keeping one ordinary Heal, four font Heals and the existing five cantrips. Preserve the original build. Later preparation may select these named legal sets; it need not accept arbitrary slot rewriting. Iomedae grants Sure Strike, prepared normally as a divine cleric spell. [Iomedae](https://2e.aonprd.com/Deities.aspx?ID=285), [Cleric](https://2e.aonprd.com/Classes.aspx?ID=33).

Cast costs one action and the ordinary slot. Its concentrate/fortune traits do not create a manipulate reaction. The next actual attack roll before turn-end rolls two d20s and uses the better; preserve both dice, consume once, ignore negative circumstance attack modifiers and that attack's concealed targeting check. MAP, status penalties and the defender's cover/Nimble Dodge AC benefits remain. Grabbed manipulation and targeting for other spells still apply. Hidden creatures remain outside current scene admission. [Sure Strike](https://2e.aonprd.com/Spells.aspx?ID=1709), [errata](https://paizo.com/pathfinder/faq).

**Local unused-expiry ruling:** the ten-minute immunity starts when the attack consumes the spell. An unused spell expires at turn-end without a benefit or cooldown. The printed “then” follows the attack benefit; unused expiry is not separately specified. Keep this interpretation visible and test it.

Classify actual attack rolls, not just the attack trait: Strike, Divine Lance and unarmed-attack Escape qualify; Athletics/Acrobatics Escape, Trip and Grapple do not receive or consume Sure Strike. Assurance(Athletics) remains a fixed skill result, separate from the attack-roll fortune effect. [Attack rolls](https://2e.aonprd.com/Rules.aspx?ID=2288), [Fortune](https://2e.aonprd.com/Traits.aspx?ID=612), [Assurance](https://2e.aonprd.com/Feats.aspx?ID=5121).

## Implementation traps and bounded evidence

`SavedCheckContext.fortune_used` already persists, but the reroll helper currently checks only `reroll_used`; Strike/Divine Lance also have separate Hero paths. Suppress and reject every Sure Strike Hero reroll, including forged saves. Reuse existing casting permission, concrete item-location and clock helpers; one core owner handles encounter/model/persistence/check/spell/skill/content changes. Terminal remains presentation only.

Two proposed public sequences:

1. Finish a real fight; Read Aura a carried permanent +1 striking sword, then Identify with Religion: 10 + 7 + 2 = 19 succeeds. Save after the aura and at the secret Hero choice. Focused cases cover natural-1 misinformation, ordinary failure retry time, mundane objects and advice.
2. Alternate Warpriest in dim light makes one attack, casts Sure Strike, then attacks. With frightened 1 and nonlethal intent, +6 −5 −1 = 0: remove the −2 circumstance penalty, retain MAP/status, and use 3/18 = 18 with no targeting die or Hero reroll. Retain saved pre-roll Guidance/Nimble Dodge and actual defender choices where reachable.

These are proposals. Full implementation and completed play remain required before acceptance.

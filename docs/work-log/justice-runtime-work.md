# Following class: Justice Champion

## Status and purpose

This is a source-checked design packet from the Astra investigation, not implemented or tested Champion behavior. It follows the Angelic Sorcerer's focus and local recovery work. Implement one legal Iomedae/Justice/Lay on Hands build, with Desperate Prayer at level 1. Domains and additional causes are outside this selection.

## Legal starting character

- Human, Skilled Human (Medicine), Natural Skill (Crafting and Society).
- Farmhand: Athletics, Farming Lore and Assurance (Athletics).
- Champion grants Religion and Iomedae's Intimidation; select Diplomacy and Survival as its additional skills.
- Boosts: ancestry Strength/Charisma; background Constitution/Strength; class Strength; final Strength/Dexterity/Constitution/Charisma. Result: Str +4, Dex +1, Con +2, Int +0, Wis +0, Cha +2.
- HP 20, Speed 25 feet, AC 18 (20 with raised shield), Perception +3, Fortitude +7, Reflex +4, Will +5. Class DC 17, divine spell attack +5/DC 15.
- Athletics +7; Intimidation/Diplomacy +5; the other listed trained skills +3. Assurance Athletics 13.
- Longsword +7, 1d8+4 slashing or piercing; fist +7, 1d4+4 bludgeoning, agile/finesse/nonlethal.
- Breastplate 8 gp, longsword 1 gp, steel shield 2 gp; 4 gp remaining and 4 Bulk. Sword/shield start held, armor worn. Strength satisfies the armor requirement.

Sources: [Champion](https://2e.aonprd.com/Classes.aspx?ID=58), [Human](https://2e.aonprd.com/Ancestries.aspx?ID=64), [Skilled Human](https://2e.aonprd.com/Heritages.aspx?ID=261), [Natural Skill](https://2e.aonprd.com/Feats.aspx?ID=4479), [Farmhand](https://2e.aonprd.com/Backgrounds.aspx?ID=422), [breastplate](https://2e.aonprd.com/Armor.aspx?ID=47), [longsword](https://2e.aonprd.com/Weapons.aspx?ID=386), [steel shield](https://2e.aonprd.com/Shields.aspx?ID=19).

## Selected rules

**Class and deity:** grant Shield Block, the 15-foot divine aura, one devotion spell and focus capacity 1. One concentrate action suppresses or resumes the aura; unconsciousness ends it. Deific Weapon does not change this martial longsword. Iomedae requires holy sanctification: every Strike, including fist and retaliation, receives holy; it does not add spirit damage. Keep deity/cause/holy declarations visible and use the existing explicit GM boundary for adjudicating violations. No domains, Cleric spell grants, level-3 blessing or critical specialization. [Champion](https://2e.aonprd.com/Classes.aspx?ID=58), [Iomedae](https://2e.aonprd.com/Deities.aspx?ID=285).

**Retributive Strike:** an enemy damages another ally, with both inside the active aura. A saved accept/decline choice spends one reaction only on acceptance. The ally gains resistance 3 to that damage; then the Champion makes a melee Strike if the enemy is reachable. Protection remains available outside melee reach. Apply the temporary resistance through the current damage calculation and type choice, not as persistent creature resistance. For 6 slashing plus 2 fire, choosing slashing leaves 5 total damage. The ally can then use its own Shield Block. [Justice](https://2e.aonprd.com/Causes.aspx?ID=11), [Spring 2026 errata](https://paizo.com/blog/spring-errata-2026).

The current Reactive Strike helper hardcodes its special exemption from the multiple-attack penalty and attack count. Justice lacks that exemption. Reuse lower-level Strike continuation machinery: outside the Champion's turn the general off-turn rule applies; during its own turn the retaliation uses and advances the current penalty. [Multiple attacks](https://2e.aonprd.com/Rules.aspx?ID=2289).

**Lay on Hands:** one manipulate action, touch, one focus point. A willing living target heals 6; another living target also gains +2 status AC for one round, while self-healing gives no AC bonus. Undead use deals 1d6 vitality with a basic Fortitude save and gives −2 status AC on a failed save. Use source-next-start expiry, ordinary modifier stacking, manipulation interruptions and saved checks. The living route can be an early staged checkpoint; do not advertise the undead route before actual target/health semantics work. [Lay on Hands](https://2e.aonprd.com/Spells.aspx?ID=2047).

**Desperate Prayer:** selected level-1 feat, despite its misleading placement under level 2 in the older research brief. Once per day, when beginning a turn with zero focus, a triggered free action grants one devotion-only point. The unspent point disappears at that turn's end. Declining preserves daily use. This is not an unrestricted mid-turn resource action or a larger focus capacity. [Desperate Prayer](https://2e.aonprd.com/Feats.aspx?ID=5884).

## Small implementation steps

1. After shared focus/recovery works, connect the legal staged sheet and first living Lay on Hands. Test exact focus spending, self/other AC and saves.
2. Add literal aura state, holy Strike tags and saved protection before damage defenses. First execute protection without an in-reach retaliation.
3. Add saved retaliation after the triggering damage, then resume the original action. Preserve attack and damage choices; do not auto-end the action before its pending retaliation.
4. Complete Prayer's start prompt, temporary restricted point and daily reset, plus the selected undead/AC route when its target support is ready.
5. Complete public encounters, terminal continuation and save/load; run one coherent broad/performance review.

Use existing focus resources, damage resolution, Strike continuations, source-turn timing, effects and emanation geometry. Third-party damage prevention followed by retaliation is the substantial new connection. No generic event framework is needed.

## Proposed encounter evidence

These are designs, not counted encounters or completed runs. Start healthy and create damage through ordinary commands.

1. **Reach corridor:** protection at 15 feet without retaliation, then move into reach for retaliation. Targeted branches test 20-foot boundaries and suppressed aura.
2. **Protection and ally shield:** mixed damage, saved resistance assignment, then the ally's Shield Block; save/load cannot apply prevention twice.
3. **Shared reaction:** decline protection then Block a personal hit; alternate route protects first and cannot subsequently Block before refresh.
4. **Living rescue:** healing and status AC change a later attack; self-healing lacks the bonus, shield's circumstance bonus stacks, and the spell expires.
5. **Undead devotion:** actual eligible target, saved save/reroll, vitality damage and AC rider, plus manipulation interruption. Do not count this before the target and all exercised behavior work.
6. **Prayer and recovery:** spend initial focus, save at the next-start offer, cast with the temporary point or let it expire; finish the fight and Refocus. Refocus does not reset Prayer; eligible daily preparation does.

Additional narrow checks cover aura loss on unconsciousness, holy damage interactions and own-turn retaliation. Existing unsupported stable-zero damage remains explicit. Astra identified no new P0 uncertainty in this selected design.

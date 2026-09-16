# Selected Swashbuckler: Braggart and Flying Blade

## Status and scope

Astra checked the selected level-1 build, relevant remaster sources and current interfaces. This is a design packet with proposed encounters, not implemented class coverage. Implement after the preceding selected classes and their shared prerequisites. Keep ownership in [ACTIVE](ACTIVE.md).

Use one Braggart with Flying Blade and a few separately tracked daggers. No other styles or exhaustive feat list. Level 2 follows the level-1 roster acceptance; the suggestions below are not already granted.

## Required behavior

Braggart trains Intimidation and makes Demoralize a bravado action. Every Swashbuckler has bravado Tumble Through. Stylish Combatant grants +1 circumstance to those checks in combat. Panache grants +5-foot status to Speeds. Ordinary Precise Strike adds **2 precision damage without requiring panache**; agile or finesse melee weapons/unarmed attacks qualify. A finisher replaces that damage with 2d6. [Class](https://2e.aonprd.com/Classes.aspx?ID=63), [styles](https://2e.aonprd.com/Styles.aspx).

Bravado success grants panache. Ordinary failure grants it through the end of the actor's next turn; critical failure grants none. Immunity to the action's effect does not prevent gaining panache. Preserve stronger existing panache when a later check fails. Encounter end removes it. [Bravado](https://2e.aonprd.com/Traits.aspx?ID=801).

Confident Finisher costs one action and makes a Strike. Failure deals half the rolled 2d6 precision damage, rounded down, using the weapon's damage type; critical failure deals none. Spend panache and forbid subsequent attack-trait actions that turn. On success, permit choosing the failure effect. [Confident Finisher](https://2e.aonprd.com/Actions.aspx?ID=2818), [Finisher](https://2e.aonprd.com/Traits.aspx?ID=802).

Flying Blade allows qualifying agile/finesse thrown Strikes within their first range increment to use precision damage and finishers. Ordinary throws beyond that remain legal with range penalties, without precision; finishers are illegal there. Thrown damage uses Strength, and the actual weapon leaves the hand. [Flying Blade](https://2e.aonprd.com/Feats.aspx?ID=6130), [Thrown](https://2e.aonprd.com/Traits.aspx?ID=711).

## Shared action connections

Demoralize costs one action against an aware target within 30 feet, Intimidation versus Will DC. Language mismatch gives −4 circumstance. Success/critical success gives frightened 1/2. Every attempt gives source-specific ten-minute immunity. For bravado, permit the check against an immune target while suppressing its fear effect. Frightened affects checks and DCs and decreases at the victim's turn end. Neither Demoralize nor Tumble Through increases MAP. [Demoralize](https://2e.aonprd.com/Actions.aspx?ID=2395), [Frightened](https://2e.aonprd.com/Conditions.aspx?ID=76).

Tumble Through is one Stride-based action. Check Acrobatics against Reflex DC when entering an enemy's space; its squares cost double movement. Insufficient movement gives failure's movement result. Failure stops movement and triggers departure reactions; success also preserves ordinary movement reactions. A ranged throw provokes Reactive Strike; ordinary Demoralize does not. [Tumble Through](https://2e.aonprd.com/Actions.aspx?ID=2370), [Reactive Strike](https://2e.aonprd.com/Feats.aspx?ID=5832).

Current limitations identified by the researcher: Demoralize rejects temporary immunity outright; movement rejects occupied enemy spaces; thrown attacks retain the weapon. These require actual integration, not new content labels.

## Fixed level-1 build

Human, Versatile Human with Assurance (Athletics), Natural Skill granting Nature/Survival; Warrior background grants Warfare Lore/Intimidating Glare. Replace duplicate Intimidation training with Diplomacy. Additional class skill choices: Athletics, Deception, Stealth, Thievery. Expert Perception/Reflex/Will; trained Fortitude, ordinary attacks, light/unarmored defense, class DC, Acrobatics and style skill.

Boosts: ancestry Dexterity/Charisma; background Strength/Dexterity; class Dexterity; four free Strength/Dexterity/Constitution/Charisma. Final modifiers: Strength +2, Dexterity +4, Constitution +1, Intelligence/Wisdom +0, Charisma +2.

| Statistic | Level 1 |
|---|---|
| HP / AC | 19 / 18 |
| Perception; Fortitude / Reflex / Will | +5; +4 / +9 / +5 |
| Class DC | 17 |
| Acrobatics / Intimidation | +7 / +5 before Stylish Combatant |
| Speed | 25 feet, 30 with panache |
| Dagger | +7; 1d4+2; agile MAP −4/−8; thrown increment 10 feet |

Leather armor and three individually tracked daggers cost 2 gp 6 sp, leaving 12 gp 4 sp. [Human](https://2e.aonprd.com/Ancestries.aspx?ID=64), [heritage](https://2e.aonprd.com/Heritages.aspx?ID=262), [Natural Skill](https://2e.aonprd.com/Feats.aspx?ID=4479), [Warrior](https://2e.aonprd.com/Backgrounds.aspx?ID=445), [dagger](https://2e.aonprd.com/Weapons.aspx?ID=358), [armor](https://2e.aonprd.com/Armor.aspx?ID=41).

## Three proposed public encounters

All start at full health and no panache; supplied numbers are die faces. Keep Hero rolls unchanged. These are expected cases, not executed evidence.

1. **Adjacent dog:** HP8, AC15, Will DC14. Ordinary Strike 8+7=15, damage d4=2 plus Strength2 plus precision2 =6. Glare 8+6=14 grants panache/frightened1. Agile second attack finisher 11+3=14 versus reduced AC14; weapon1, precision1+1, Strength2 deal5 and win. Assert ordinary precision works before panache.
2. **Thrown range:** dog at15 feet. Throw 10+7−2=15, damage2+2=4 with no precision. Draw another dagger and Step to10 feet; dog passes. Next turn Glare 8+6=14, thrown finisher 7+7=14 versus AC14, damage1+1+1+2=5 wins. Confirm the first item left the hand and a finisher at15 feet rejects atomically.
3. **Tumble/reaction/failed finisher:** Fighter HP21, AC18, Reflex DC16. Tumble 8+8=16 crosses one occupied square for15 feet. Fighter reaction9+9=18, damage1+4=5 leaves Swashbuckler14. Finisher9+7=16 fails; precision3+4 halved gives3, Fighter18. Next round Tumble7+8=15 fails but grants temporary panache; decline reaction. Finisher11+7=18, damage4+6+6+2=18 ends combat. Save at the first reaction and after failed finisher; assert later attack lockout and encounter-end panache cleanup.

Additional focused cases should cover critical failure, choosing the failure effect on success, immunity/bravado, multiple daggers and saved identity, temporary-panache expiry and rejected actions preserving dice.

## Implementation and adjudication

Reuse saved checks, typed precision damage, item identity, MAP, reactions and literal JSON continuations. Needed state is panache/expiry and turn finisher restriction; needed public behavior is finisher choice, actual Tumble Through, effective Speed and thrown-item transfer. One shared owner coordinates model/encounter/skill actions/persistence/content; terminal work follows the stable command contract.

The source packet identified no P0. For thrown-item recovery, use the user's delegated GM discretion: an ordinary thrown dagger lands in the target's cell at resolution, whether it hits or misses. This is a declared local placement convention, not a printed scatter rule. Recovery uses ordinary item location/reach/hand rules. No random scatter, projectile simulator or returning-weapon behavior is implied. Revisit only if later admitted content requires a different result.

Level-2 proposal: Antagonize and Assurance (Acrobatics), HP30 and proficiency-derived statistics +1. Source-check the selected delta before admission. [Antagonize](https://2e.aonprd.com/Feats.aspx?ID=6136).

Research launched only synchronous read/search commands, all exited; no implementation, tests or engine play occurred.

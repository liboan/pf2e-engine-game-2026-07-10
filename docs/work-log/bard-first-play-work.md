# Maestro Bard: paused design handoff

## State at user stop

Astra completed a read-only draft. No Bard files were edited and no tests or engine probes ran. This is a resume proposal, not accepted Bard coverage. The current accepted engine checkpoint remains799 tests.

## Proposed staged delivery

First outcome: Courageous Anthem→actual improved ally Strike→save/load active composition→expiry at the Bard's next turn. Build only that coherent path before adding Lingering Composition and Counter Performance. Anthem has a60-foot emanation, one-round duration and typed+1 status to attacks, damage and fear saves. Enforce one composition per turn and replacement of the caster's previous composition; define real sound/sight eligibility rather than equating illumination with hearing.

Astra proposes a Human/Farmhand Maestro: Str/Dex/Con/Int/Wis/Cha+1/+2/+2/+0/+0/+4, HP18, Performance/spell attack+7 and DC17; expert Perception/Will, trained Fortitude/Reflex, light armor and martial weapons. Bard supplies Occultism/Performance plus four additional skills. Proposed five ordinary cantrips: Light, Guidance, Void Warp, Message, Forbidding Ward; proposed rank-1 repertoire Fear, Runic Weapon, Soothe with two shared slots. Anthem is separate; Counter Performance and Maestro's Lingering Composition produce focus capacity2. Validate the complete legal sheet when implementing it; no placeholders satisfy printed content counts.

Message and Forbidding Ward still need actual behavior. Message needs local delivery/reply, range/sight/language eligibility. Ward needs two targets, enemy-specific AC/save effects and Sustain up to a minute. The proposed selection remains a draft subject to the user's simplicity/common-content priority.

Lingering follows a passed Anthem probe: free-action spellshape, qualifying immediate composition, adjacency including reactions, Performance versus highest affected level DC (explicit GM override),4/3/1-round results, failure's unspent focus and zero-focus rejection. It is not itself a composition.

**Resolve before Counter Performance implementation:** natural1/20 replacement and Hero Point arbitration. The proposed opposing auditory Fear encounter also needs source confirmation of its actual auditory/visual trigger eligibility; do not infer an effect trait merely from casting speech. No user decision is requested while work is stopped. Preserve check ownership and fortune provenance instead of overwriting a result total.

## Execution pointers

`family_casting.begin_cast`, `_spontaneous_casting_snapshots`, `_focus_casting_snapshots`; Encounter `_apply_angelic_halo`, `_source_turn_start`, `_prepare_skill_check`, `_roll_fear_save`, `_spell_save_modifier_breakdown`, `_damage_modifier`; model `ActiveSpellEffect`, `ActionContinuation`, `PendingChoice`; checks `Modifier`/`combine_modifiers`; areas `emanation_cells`. Follow `sorcerer_content.ANGELIC_SORCERER_STAGED` for a future bard_content fixture and normal persistence/terminal hooks.

Analogues: `tests/test_sorcerer_first_cast.py::_first_cast_game`, `tests/test_soothe_play_review.py::test_injury_soothe_round_trip_then_actual_guided_mental_save_and_victory`, and `tests/test_sorcerer_fear_persistence.py`. Verified environment remains project-root `.venv/bin/python`3.11.1, pytest supplies src, canonical integration `tools/integration_checkpoint.py`.

Sources reported by Astra: [Bard](https://2e.aonprd.com/Classes.aspx?ID=32), [focus](https://2e.aonprd.com/Rules.aspx?ID=2228), [Anthem](https://2e.aonprd.com/Spells.aspx?ID=1763), [Lingering](https://2e.aonprd.com/Spells.aspx?ID=1769), [Counter Performance](https://2e.aonprd.com/Spells.aspx?ID=1762), [Message](https://2e.aonprd.com/Spells.aspx?ID=1598), [Ward](https://2e.aonprd.com/Spells.aspx?ID=1535). Root has not inspected sources or implementation.

Closed design run `bard-first-play-contract-2026-09-16`: Astra/high,12requests,0compactions, **789,532 input (707,840 cached),4,185 output**. Dollar cost unavailable.

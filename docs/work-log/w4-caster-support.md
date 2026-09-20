# W4 caster/support owner handoff

Status: implementation complete pending assembled review.

Roster and contracts:

- `wizard_battle_magic_level_2_energy_ablation`: Energy Ablation is an immediate-successor Spellshape marker. A finite energy choice is persisted, the next matching rank-1 Cast creates a timed typed resistance, and the defense is consumed by normal damage mitigation.
- `warpriest_c_domain_initiate_weapon_surge`: Domain Initiate is fixed to Iomedae's zeal domain and Weapon Surge. The focus spell targets a held weapon, creates a one-use active effect, and the next matching Strike receives a status attack bonus plus a sanctified spirit die.
- `sorcerer_angelic_level_1_widen_spell`: Widen Spell reuses the existing finite Breathe Fire area-spellshape path for a legal level-1 Sorcerer alternate.
- `faiths_flamekeeper_witch_level_1_cackle`: Cackle spends 1 Focus Point, is limited to once per Witch turn, and refreshes the existing Stoke the Heart sustain boundary as a free family action; it does not create a general sustained-effect framework.

Primary files: `src/pf2e/model.py`, `spellshape.py`, `family_casting.py`, `witch.py`, `encounter.py`, `persistence.py`, `terminal.py`, `spells.py`, `w4_caster_content.py`, and `content.py`. Source URLs and scope boundaries are recorded in `w4_caster_content.py`.

Verification complete: module compile, catalog/setup import, direct Energy Ablation cast/resistance and ineligible-cast waste, Weapon Surge cast/effect, Widen Spell Breathe Fire, Cackle focus/once-per-turn behavior, independent reviewer checks, and the assembled suite (1491 passed).

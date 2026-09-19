"""Small, immutable equipment snapshots and numeric item-rule helpers.

This module deliberately does not decide whether an item is held, raised,
within reach, or otherwise legal to activate. Core supplies those facts and
commits the returned snapshot at the appropriate point.

Sources checked 2026-09-15:
- Base shield profiles (Player Core): https://2e.aonprd.com/Shields.aspx
- Shield rules (Player Core): https://2e.aonprd.com/Rules.aspx?ID=2180
- Shield Block (Player Core): https://2e.aonprd.com/Feats.aspx?ID=5212
- Object immunities (Player Core): https://2e.aonprd.com/Rules.aspx?ID=2161
- Weapon potency: https://2e.aonprd.com/Equipment.aspx?ID=2830
- Striking: https://2e.aonprd.com/Equipment.aspx?ID=2829
- Weapon damage dice / counting dice: https://2e.aonprd.com/Rules.aspx?ID=2194
- Armor potency: https://2e.aonprd.com/Equipment.aspx?ID=2785
- Resilient: https://2e.aonprd.com/Equipment.aspx?ID=2786
- Handwraps of Mighty Blows: https://2e.aonprd.com/Equipment.aspx?ID=3086
- Minor Elixir of Life: https://2e.aonprd.com/Equipment.aspx?ID=3308
- Potion/elixir activation: https://2e.aonprd.com/Rules.aspx?ID=3184
"""

from dataclasses import dataclass, replace

from .checks import Modifier


_SHIELDS_SOURCE = "https://2e.aonprd.com/Shields.aspx"
_OBJECT_IMMUNITIES_SOURCE = "https://2e.aonprd.com/Rules.aspx?ID=2161"
_POTENCY_SOURCE = "https://2e.aonprd.com/Equipment.aspx?ID=2830"
_STRIKING_SOURCE = "https://2e.aonprd.com/Equipment.aspx?ID=2829"
_WEAPON_DICE_SOURCE = "https://2e.aonprd.com/Rules.aspx?ID=2194"
_ARMOR_POTENCY_SOURCE = "https://2e.aonprd.com/Equipment.aspx?ID=2785"
_RESILIENT_SOURCE = "https://2e.aonprd.com/Equipment.aspx?ID=2786"
_HANDWRAPS_SOURCE = "https://2e.aonprd.com/Equipment.aspx?ID=3086"
_ELIXIR_SOURCE = "https://2e.aonprd.com/Equipment.aspx?ID=3308"
_ELIXIR_ACTIVATION_SOURCE = "https://2e.aonprd.com/Rules.aspx?ID=3184"

SHIELD_IMMUNE_DAMAGE_TYPES = frozenset(
    {"bleed", "death", "disease", "healing", "mental", "poison", "spirit", "vitality", "void"}
)


def _require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_count(value: int, name: str, *, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}")


@dataclass(frozen=True)
class ItemInstance:
    """An individual item or a stack of identical, untracked consumables."""

    instance_id: str
    definition_id: str
    quantity: int = 1
    charges: int | None = None
    hp: int | None = None
    rune_ids: tuple[str, ...] = ()
    invested: bool = False

    def __post_init__(self) -> None:
        _require_identifier(self.instance_id, "instance_id")
        _require_identifier(self.definition_id, "definition_id")
        _require_count(self.quantity, "quantity")
        if self.charges is not None:
            _require_count(self.charges, "charges")
        if self.hp is not None:
            _require_count(self.hp, "hp")
        if not isinstance(self.rune_ids, tuple):
            raise ValueError("rune_ids must be a tuple")
        for rune_id in self.rune_ids:
            _require_identifier(rune_id, "rune_id")
        if len(set(self.rune_ids)) != len(self.rune_ids):
            raise ValueError("rune_ids must not contain duplicates")
        if type(self.invested) is not bool:
            raise ValueError("invested must be a boolean")
        if self.quantity > 1 and (
            self.charges is not None or self.hp is not None or self.rune_ids or self.invested
        ):
            raise ValueError("items with per-instance charges, HP, runes, or investment must have quantity 1")


def runtime_item_instance_id(actor_id: str, local_instance_id: str) -> str:
    """Namespace a definition-local item identity for one encounter actor."""
    _require_identifier(actor_id, "actor_id")
    _require_identifier(local_instance_id, "local_instance_id")
    return f"{actor_id}:{local_instance_id}"


@dataclass(frozen=True)
class ShieldProfile:
    definition_id: str
    ac_bonus: int
    hardness: int
    max_hp: int
    broken_threshold: int
    source_url: str = _SHIELDS_SOURCE

    def __post_init__(self) -> None:
        _require_identifier(self.definition_id, "definition_id")
        _require_count(self.ac_bonus, "ac_bonus")
        _require_count(self.hardness, "hardness")
        _require_count(self.max_hp, "max_hp", minimum=1)
        _require_count(self.broken_threshold, "broken_threshold", minimum=1)
        _require_identifier(self.source_url, "source_url")
        if self.broken_threshold > self.max_hp:
            raise ValueError("broken_threshold cannot exceed max_hp")


@dataclass(frozen=True)
class ShieldBlockResult:
    prevented: int
    damage_to_actor: int
    damage_to_shield: int
    shield_hp: int


@dataclass(frozen=True)
class ShieldIntegrity:
    broken: bool
    destroyed: bool


def shield_integrity(profile: ShieldProfile, shield_hp: int) -> ShieldIntegrity:
    """Report the shield's broken/destroyed thresholds from its current HP."""
    _require_count(shield_hp, "shield_hp")
    if shield_hp > profile.max_hp:
        raise ValueError("shield_hp cannot exceed the profile's max_hp")
    destroyed = shield_hp == 0
    return ShieldIntegrity(broken=shield_hp <= profile.broken_threshold, destroyed=destroyed)


def shield_ac_modifier(profile: ShieldProfile, *, raised: bool, shield_hp: int) -> Modifier | None:
    """Return the shield's circumstance AC modifier while raised and intact."""
    if type(raised) is not bool:
        raise ValueError("raised must be a boolean")
    integrity = shield_integrity(profile, shield_hp)
    if integrity.broken or integrity.destroyed or not raised:
        return None
    return Modifier(profile.ac_bonus, "circumstance", profile.definition_id)


def shield_block_trigger_eligible(damage_type: str, *, from_attack: bool) -> bool:
    """Check Shield Block's damage gate; core still checks raised/feat state.

    The feat's trigger is physical damage (bludgeoning, piercing, or slashing)
    from an attack. Whether the attack is magical does not change its damage
    type; a magical weapon's physical Strike can qualify, while fire damage
    from an attack cannot.
    """
    if not isinstance(damage_type, str) or not damage_type.strip():
        raise ValueError("damage_type must be a non-empty string")
    if type(from_attack) is not bool:
        raise ValueError("from_attack must be a boolean")
    return from_attack and damage_type.casefold() in {"bludgeoning", "piercing", "slashing"}


def shield_block_result(
    incoming_damage: int,
    profile: ShieldProfile,
    shield_hp: int,
    *,
    shield_vulnerable_damage: int | None = None,
) -> ShieldBlockResult:
    """Apply the shield's Hardness to the actor and object-eligible shield damage.

    Ordinarily both totals are identical. A shield's object immunities can make
    some components unable to damage the shield, even though those components
    still damage its wielder.
    """
    _require_count(incoming_damage, "incoming_damage")
    _require_count(shield_hp, "shield_hp")
    if shield_vulnerable_damage is None:
        shield_vulnerable_damage = incoming_damage
    _require_count(shield_vulnerable_damage, "shield_vulnerable_damage")
    if shield_vulnerable_damage > incoming_damage:
        raise ValueError("shield_vulnerable_damage cannot exceed incoming_damage")
    if shield_hp > profile.max_hp:
        raise ValueError("shield_hp cannot exceed the profile's max_hp")
    integrity = shield_integrity(profile, shield_hp)
    if integrity.broken or integrity.destroyed:
        raise ValueError("a broken shield cannot be used for Shield Block")
    prevented = min(incoming_damage, profile.hardness)
    actor_remainder = incoming_damage - prevented
    shield_remainder = max(0, shield_vulnerable_damage - profile.hardness)
    return ShieldBlockResult(
        prevented=prevented,
        damage_to_actor=actor_remainder,
        damage_to_shield=shield_remainder,
        shield_hp=max(0, shield_hp - shield_remainder),
    )


# Player Core's base shield table: AC bonus, Hardness, HP, BT.
BUCKLER = ShieldProfile("buckler", ac_bonus=1, hardness=3, max_hp=6, broken_threshold=3)
WOODEN_SHIELD = ShieldProfile("wooden_shield", ac_bonus=2, hardness=3, max_hp=12, broken_threshold=6)
STEEL_SHIELD = ShieldProfile("steel_shield", ac_bonus=2, hardness=5, max_hp=20, broken_threshold=10)


@dataclass(frozen=True)
class ArmorRuneProfile:
    """Fundamental armor rune bonuses supported in the selected catalog."""

    potency: int = 0
    resilient_bonus: int = 0
    source_urls: tuple[str, ...] = (_ARMOR_POTENCY_SOURCE, _RESILIENT_SOURCE)

    def __post_init__(self) -> None:
        if type(self.potency) is not int or self.potency not in {0, 1, 2, 3}:
            raise ValueError("armor potency must be 0, 1, 2, or 3")
        if type(self.resilient_bonus) is not int or self.resilient_bonus not in {0, 1, 2, 3}:
            raise ValueError("resilient_bonus must be 0, 1, 2, or 3")
        if not isinstance(self.source_urls, tuple) or not self.source_urls:
            raise ValueError("source_urls must be a non-empty tuple")
        for source_url in self.source_urls:
            _require_identifier(source_url, "source_url")


def armor_item_ac_bonus(base_ac_bonus: int, profile: ArmorRuneProfile) -> int:
    """Return armor's full item bonus to AC, including potency runes."""
    _require_count(base_ac_bonus, "base_ac_bonus")
    return base_ac_bonus + profile.potency


def armor_resilient_modifier(
    profile: ArmorRuneProfile,
    *,
    source: str = "resilient rune",
) -> Modifier | None:
    """Expose resilient as a typed item bonus for saving throws."""
    _require_identifier(source, "source")
    if profile.resilient_bonus == 0:
        return None
    return Modifier(profile.resilient_bonus, "item", source)


@dataclass(frozen=True)
class WeaponRuneProfile:
    """The admitted fundamental rune values attached to a weapon or handwrap."""

    potency: int = 0
    striking_dice: int | None = None
    property_runes: tuple[str, ...] = ()
    handwraps: bool = False
    source_urls: tuple[str, ...] = (
        _POTENCY_SOURCE,
        _STRIKING_SOURCE,
        _WEAPON_DICE_SOURCE,
        _HANDWRAPS_SOURCE,
    )

    def __post_init__(self) -> None:
        if type(self.potency) is not int or self.potency not in {0, 1, 2, 3}:
            raise ValueError("potency must be 0, 1, 2, or 3")
        if self.striking_dice is not None and (
            type(self.striking_dice) is not int or self.striking_dice not in {2, 3, 4}
        ):
            raise ValueError("striking_dice must be None, 2, 3, or 4")
        if not isinstance(self.property_runes, tuple):
            raise ValueError("property_runes must be a tuple")
        for rune_id in self.property_runes:
            _require_identifier(rune_id, "property_rune")
        if len(set(self.property_runes)) != len(self.property_runes):
            raise ValueError("property_runes must not contain duplicates")
        if type(self.handwraps) is not bool:
            raise ValueError("handwraps must be a boolean")
        if not isinstance(self.source_urls, tuple) or not self.source_urls:
            raise ValueError("source_urls must be a non-empty tuple")
        for source_url in self.source_urls:
            _require_identifier(source_url, "source_url")


def weapon_potency_modifier(
    profile: WeaponRuneProfile,
    *,
    unarmed: bool = False,
    source: str = "weapon potency rune",
) -> Modifier | None:
    """Expose only the weapon item's attack bonus for typed stacking.

    The returned value intentionally excludes proficiency, attribute, MAP,
    range, and other check terms. It is also suitable for a later maneuver
    query when a weapon's Trip or Grapple trait makes the weapon's potency
    bonus applicable.
    """
    if type(unarmed) is not bool:
        raise ValueError("unarmed must be a boolean")
    _require_identifier(source, "source")
    if profile.potency == 0 or (unarmed and not profile.handwraps):
        return None
    return Modifier(profile.potency, "item", source)


def weapon_rune_dice(
    base_dice: tuple[int, ...],
    profile: WeaponRuneProfile,
    *,
    striking_applies: bool = True,
    unarmed: bool = False,
) -> tuple[int, ...]:
    """Apply only the striking rune's weapon-die count change.

    Callers pass only the weapon/unarmed attack's own damage dice. Precision,
    deadly, property-rune, bomb, and action-granted dice stay separate. The
    explicit ``striking_applies`` fact handles source-specific exceptions
    such as Bestial Mutagen; ``unarmed=True`` requires handwraps in this helper.
    """
    if not isinstance(base_dice, tuple):
        raise ValueError("base_dice must be a tuple")
    if any(type(sides) is not int or sides not in {4, 6, 8, 10, 12} for sides in base_dice):
        raise ValueError("base_dice must contain standard weapon die sizes")
    if type(striking_applies) is not bool:
        raise ValueError("striking_applies must be a boolean")
    if type(unarmed) is not bool:
        raise ValueError("unarmed must be a boolean")
    if not base_dice or not striking_applies or (unarmed and not profile.handwraps):
        return base_dice
    if len(set(base_dice)) != 1:
        raise ValueError("weapon damage dice supplied to this helper must share one die size")
    if profile.striking_dice is None:
        return base_dice
    return (base_dice[0],) * profile.striking_dice


@dataclass(frozen=True)
class ItemActivationProfile:
    """Source-backed activation facts for one curated item definition."""

    definition_id: str
    action_cost: int
    action: str
    action_traits: frozenset[str]
    hands_required: int
    quantity_cost: int
    charge_cost: int = 0
    source_urls: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.definition_id, "definition_id")
        _require_count(self.action_cost, "action_cost")
        _require_identifier(self.action, "action")
        if not isinstance(self.action_traits, frozenset):
            raise ValueError("action_traits must be a frozenset")
        for trait in self.action_traits:
            _require_identifier(trait, "action_trait")
        _require_count(self.hands_required, "hands_required")
        _require_count(self.quantity_cost, "quantity_cost")
        _require_count(self.charge_cost, "charge_cost")
        if self.quantity_cost == 0 and self.charge_cost == 0:
            raise ValueError("an activation profile must consume quantity or charges")
        if not isinstance(self.source_urls, tuple) or not self.source_urls:
            raise ValueError("source_urls must be a non-empty tuple")
        for source_url in self.source_urls:
            _require_identifier(source_url, "source_url")


MINOR_ELIXIR_OF_LIFE_ACTIVATION = ItemActivationProfile(
    definition_id="elixir_of_life_minor",
    action_cost=1,
    action="Interact",
    action_traits=frozenset({"manipulate"}),
    hands_required=1,
    quantity_cost=1,
    source_urls=(_ELIXIR_SOURCE, _ELIXIR_ACTIVATION_SOURCE),
)


def consume_item(
    instance: ItemInstance,
    *,
    quantity: int = 0,
    charges: int = 0,
) -> ItemInstance:
    """Return the depleted snapshot, rejecting any over-consumption."""
    _require_count(quantity, "quantity")
    _require_count(charges, "charges")
    if quantity == 0 and charges == 0:
        raise ValueError("consumption must spend at least one item or charge")
    if quantity > instance.quantity:
        raise ValueError("insufficient item quantity")
    if charges:
        if instance.charges is None:
            raise ValueError("item does not track charges")
        if charges > instance.charges:
            raise ValueError("insufficient charges")
    return replace(
        instance,
        quantity=instance.quantity - quantity,
        charges=None if instance.charges is None else instance.charges - charges,
    )


def item_after_activation(instance: ItemInstance, profile: ItemActivationProfile) -> ItemInstance:
    """Project one already-authorized activation's consumption result.

    Core decides whether activation is legal and when to commit this returned
    snapshot. A mismatched definition or depleted instance is rejected without
    changing the immutable input.
    """
    if instance.definition_id != profile.definition_id:
        raise ValueError("activation profile does not match item definition")
    return consume_item(instance, quantity=profile.quantity_cost, charges=profile.charge_cost)

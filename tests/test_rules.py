import pytest

from engine.cards import CardDefinition, CardType
from engine.rules import calculate_vault_resources
from engine.state import CardInstance, PlayerState


def make_card(instance_id: int, card_id: str) -> CardInstance:
    """Create a test card owned by player zero."""
    return CardInstance(
        instance_id=instance_id,
        card_id=card_id,
        owner_id=0,
        controller_id=0,
    )


def test_monster_resource_production():
    player = PlayerState(
        player_id=0,
        monster=make_card(1, "test_monster"),
    )

    definitions = {
        "test_monster": CardDefinition(
            card_id="test_monster",
            name="Test Monster",
            card_type=CardType.MONSTER,
            blood_production=5,
            malice_production=1,
            draw_production=2,
        )
    }

    production = calculate_vault_resources(
        player,
        definitions,
    )

    assert production.blood == 5
    assert production.malice == 1
    assert production.cards == 2

    # Calculating production must not modify player resources.
    assert player.blood == 0
    assert player.malice == 0


def test_vault_resource_production():
    player = PlayerState(
        player_id=0,
        monster=make_card(1, "test_monster"),
        vault=[
            make_card(2, "vault_card_a"),
            make_card(3, "vault_card_b"),
        ],
    )

    definitions = {
        "test_monster": CardDefinition(
            card_id="test_monster",
            name="Test Monster",
            card_type=CardType.MONSTER,
            blood_production=5,
            malice_production=1,
            draw_production=2,
        ),
        "vault_card_a": CardDefinition(
            card_id="vault_card_a",
            name="Vault Card A",
            card_type=CardType.MINION,
            blood_production=1,
        ),
        "vault_card_b": CardDefinition(
            card_id="vault_card_b",
            name="Vault Card B",
            card_type=CardType.EVENT,
            blood_production=2,
            malice_production=1,
        ),
    }

    production = calculate_vault_resources(
        player,
        definitions,
    )

    assert production.blood == 8
    assert production.malice == 2
    assert production.cards == 2


def test_missing_card_definition():
    player = PlayerState(
        player_id=0,
        monster=make_card(1, "unknown_monster"),
    )

    with pytest.raises(
        ValueError,
        match="Missing card definition",
    ):
        calculate_vault_resources(player, {})
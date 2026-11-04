import pytest

from engine.state import (
    GameState,
    PlayerState,
    CardInstance,
    LocationState,
    Phase,
)


def test_initial_state():
    player_0 = PlayerState(
        player_id=0,
        monster=CardInstance(
            instance_id=1, 
            card_id="dracula",
            owner_id=0,
            controller_id=0
        ),
    )

    player_1 = PlayerState(
        player_id=1,
        monster=CardInstance(
            instance_id=2, 
            card_id="jaws",
            owner_id=1,
            controller_id=1
        ),
    )

    game = GameState(
        players=[player_0, player_1],
        locations=[
            LocationState("carfax_abbey", 0),
            LocationState("north_beach", 1),
        ],
    )

    assert game.phase == Phase.FEEDING
    assert game.round_number == 1
    assert game.winner is None
    assert len(game.players) == 2
    assert len(game.players[0].health_stack) == 0


def test_clone_is_independent():
    player_0 = PlayerState(
        player_id=0,
        monster=CardInstance(
            instance_id=1,
            card_id="dracula",
            owner_id=0,
            controller_id=0
        )
    )

    player_1 = PlayerState(player_id=1)

    game = GameState(
        players=[player_0, player_1],
        locations=[]
    )

    cloned_game = game.clone()

    # Let's modify the copy.
    cloned_game.players[0].monster.damage = 5

    # The original must remain unchanged.
    assert game.players[0].monster.damage == 0

    # The copy must contain the modification.
    assert cloned_game.players[0].monster.damage == 5


def test_valid_state():
    player_0 = PlayerState(player_id=0)
    player_1 = PlayerState(player_id=1)

    game = GameState(
        players=[player_0, player_1],
        locations=[]
    )

    game.validate()


def test_get_card():
    monster = CardInstance(
        instance_id=1,
        card_id="dracula",
        owner_id=0,
        controller_id=0
    )

    player_0 = PlayerState(
        player_id=0,
        monster=monster
    )

    player_1 = PlayerState(player_id=1)

    game = GameState(
        players=[player_0, player_1],
        locations=[]
    )

    found = game.get_card(1)

    assert found is monster
    assert found.card_id == "dracula"
    assert game.get_card(999) is None


def test_duplicate_card_detection():
    card = CardInstance(
        instance_id=10,
        card_id="test_card",
        owner_id=0,
        controller_id=0
    )

    player_0 = PlayerState(
        player_id=0,
        deck=[card],
        hand=[card]
    )

    player_1 = PlayerState(player_id=1)

    game = GameState(
        players=[player_0, player_1],
        locations=[]
    )

    # The same card instance cannot exist in multiple zones.
    with pytest.raises(ValueError, match="Duplicate card"):
        game.validate()
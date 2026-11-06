
from dataclasses import FrozenInstanceError

import pytest

from engine.game import Game
from engine.state import (
    CardInstance,
    GameState,
    GameStep,
    LocationState,
    Phase,
    PlayerState,
)


def make_observation_field_game() -> Game:
    """Create a game with public and hidden card information."""

    state = GameState(
        players=[
            PlayerState(
                player_id=0,
                hand=[
                    CardInstance(1, "asset_in_hand", 0, 0),
                ],
                minions=[
                    CardInstance(
                        2,
                        "minion_on_field",
                        0,
                        0,
                        exhausted=True,
                        damage=1,
                        location_id=0,
                    ),
                ],
                assets=[
                    CardInstance(
                        3,
                        "asset_on_field",
                        0,
                        0,
                        exhausted=False,
                    ),
                ],
            ),
            PlayerState(
                player_id=1,
                hand=[
                    CardInstance(4, "secret_enemy_card", 1, 1),
                ],
                minions=[
                    CardInstance(
                        5,
                        "enemy_minion",
                        1,
                        1,
                        exhausted=False,
                        location_id=1,
                    ),
                ],
            ),
        ],
        locations=[
            LocationState(
                card_id="location_0",
                controller_id="0",
                malice={0: 2, 1: 1},
            ),
            LocationState(
                card_id="location_1",
                controller_id="1",
                malice={0: 0, 1: 3},
            ),
        ],
        phase=Phase.HORROR,
        step=GameStep.PLAYER_ACTION,
        active_player=0,
    )

    return Game(state)


def test_observation_includes_public_minions():
    game = make_observation_field_game()

    observation = game.observe(0)

    own_minion = observation.players[0].minions[0]
    enemy_minion = observation.players[1].minions[0]

    assert own_minion.instance_id == 2
    assert own_minion.card_id == "minion_on_field"
    assert own_minion.location_id == 0
    assert own_minion.exhausted is True
    assert own_minion.damage == 1

    assert enemy_minion.instance_id == 5
    assert enemy_minion.location_id == 1
    assert enemy_minion.exhausted is False


def test_observation_includes_public_assets():
    game = make_observation_field_game()

    observation = game.observe(1)

    asset = observation.players[0].assets[0]

    assert asset.instance_id == 3
    assert asset.card_id == "asset_on_field"
    assert asset.exhausted is False
    assert asset.location_id is None


def test_observation_includes_locations():
    game = make_observation_field_game()

    observation = game.observe(0)

    assert len(observation.locations) == 2

    location = observation.locations[0]

    assert location.location_id == 0
    assert location.card_id == "location_0"
    assert location.controller_id == "0"
    assert location.malice == ((0, 2), (1, 1))


def test_observation_shows_own_hand_instance_ids():
    game = make_observation_field_game()

    observation = game.observe(0)

    assert len(observation.own_hand_cards) == 1
    assert observation.own_hand_cards[0].instance_id == 1
    assert observation.own_hand_cards[0].card_id == "asset_in_hand"

    # Keep the legacy field for compatibility.
    assert observation.own_hand == ("asset_in_hand",)


def test_observation_hides_opponent_hand():
    game = make_observation_field_game()

    observation = game.observe(0)

    assert observation.players[1].hand_size == 1

    assert all(
        card.card_id != "secret_enemy_card"
        for card in observation.own_hand_cards
    )

    assert all(
        card.card_id != "secret_enemy_card"
        for player in observation.players
        for card in (*player.minions, *player.assets)
    )


def test_observation_is_an_independent_snapshot():
    game = make_observation_field_game()

    observation = game.observe(0)

    with pytest.raises(FrozenInstanceError):
        observation.players[0].minions[0].damage = 5

    with pytest.raises(FrozenInstanceError):
        observation.locations[0].controller_id = "1"

    # Mutating the game must not change an existing observation.
    game.state.players[0].minions[0].damage = 2
    game.state.locations[0].malice[0] = 9

    assert observation.players[0].minions[0].damage == 1
    assert observation.locations[0].malice == (
        (0, 2),
        (1, 1),
    )

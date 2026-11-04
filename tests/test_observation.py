
import pytest

from dataclasses import FrozenInstanceError

from engine.cards import CardDefinition, CardType
from engine.game import Game
from engine.state import (
    CardInstance,
    GameState,
    GameStep,
    Phase,
    PlayerState,
)


def make_observation_game() -> Game:
    """Create a game with hidden information."""

    state = GameState(
        players=[
            PlayerState(
                player_id=0,
                hand=[
                    CardInstance(1, "card_a", 0, 0),
                ],
            ),
            PlayerState(
                player_id=1,
                hand=[
                    CardInstance(2, "secret_card", 1, 1),
                ],
            ),
        ],
        locations=[],
        phase=Phase.FEEDING,
        step=GameStep.INITIATIVE_BID,
    )

    definitions = {
        "card_a": CardDefinition(
            card_id="card_a",
            name="Card A",
            card_type=CardType.MINION,
            cost=3,
        ),
        "secret_card": CardDefinition(
            card_id="secret_card",
            name="Secret Card",
            card_type=CardType.MINION,
            cost=5,
        ),
    }

    return Game(state, definitions)


def test_observation_shows_own_hand():
    game = make_observation_game()

    observation = game.observe(0)

    assert observation.player_id == 0
    assert observation.own_hand == ("card_a",)
    assert observation.players[0].hand_size == 1


def test_observation_hides_opponent_hand():
    game = make_observation_game()

    observation = game.observe(0)

    assert observation.players[1].hand_size == 1

    # The opponent's card identities must remain hidden.
    assert not hasattr(
        observation.players[1],
        "hand",
    )
    assert "secret_card" not in observation.own_hand


def test_observation_hides_opponent_bid():
    game = make_observation_game()

    game.submit_initiative_bid(1, 2)

    observation = game.observe(0)

    assert observation.opponent_bid_submitted is True
    assert observation.own_bid_submitted is False
    assert observation.own_bid_card_id is None


def test_observation_shows_own_bid():
    game = make_observation_game()

    game.submit_initiative_bid(0, 1)

    observation = game.observe(0)

    assert observation.own_bid_submitted is True
    assert observation.own_bid_card_id == 1


def test_observation_is_immutable():
    game = make_observation_game()

    observation = game.observe(0)

    with pytest.raises(FrozenInstanceError):
        observation.round_number = 99

    with pytest.raises(FrozenInstanceError):
        observation.players[0].blood = 999

    assert game.state.round_number == 1


def test_invalid_observation_player():
    game = make_observation_game()

    with pytest.raises(
        ValueError,
        match="Invalid player ID",
    ):
        game.observe(99)

import pytest

from engine.actions import Action, ActionType
from engine.constants import HAND_LIMIT
from engine.game import Game
from engine.state import (
    CardInstance,
    GameState,
    GameStep,
    Phase,
    PlayerState,
)


def make_discard_game(
    hand_0: int = 8,
    hand_1: int = 7,
) -> Game:
    """Create a game during the hand limit step."""

    state = GameState(
        players=[
            PlayerState(
                player_id=0,
                hand=[
                    CardInstance(i, f"card_0_{i}", 0, 0)
                    for i in range(1, hand_0 + 1)
                ],
            ),
            PlayerState(
                player_id=1,
                hand=[
                    CardInstance(i, f"card_1_{i}", 1, 1)
                    for i in range(100, 100 + hand_1)
                ],
            ),
        ],
        locations=[],
        phase=Phase.REFRESH,
        step=GameStep.DISCARD_TO_HAND_LIMIT,
        initiative_player=1,
        active_player=1,
        round_number=3,
    )

    return Game(state)


def discard_first_legal_card(game: Game) -> None:
    """Discard one legal card for the current player."""

    player_id = game.state.active_player
    action = next(
        action
        for action in game.get_legal_actions(player_id)
        if action.action_type == ActionType.DISCARD
    )
    game.step(action)


def test_discard_actions_are_generated():
    game = make_discard_game()

    actions = game.get_legal_actions(1)

    assert len(actions) == 7
    assert all(
        action.action_type == ActionType.DISCARD
        for action in actions
    )

    assert game.get_legal_actions(0) == []


def test_discard_moves_card_to_crypt():
    game = make_discard_game()
    player = game.state.players[1]

    discarded_id = player.hand[0].instance_id
    discard_first_legal_card(game)

    assert len(player.hand) == HAND_LIMIT
    assert len(player.crypt) == 1
    assert player.crypt[0].instance_id == discarded_id

    game.state.validate()


def test_discard_switches_to_next_player():
    game = make_discard_game()

    # Player 1 has initiative and discards first.
    discard_first_legal_card(game)

    assert game.state.active_player == 0
    assert game.state.step == GameStep.DISCARD_TO_HAND_LIMIT


def test_player_can_discard_multiple_cards():
    game = make_discard_game()

    # Player 1 discards one card.
    discard_first_legal_card(game)

    # Player 0 must discard two cards.
    discard_first_legal_card(game)

    assert game.state.active_player == 0
    assert len(game.state.players[0].hand) == 7

    discard_first_legal_card(game)

    assert len(game.state.players[0].hand) == HAND_LIMIT
    assert len(game.state.players[0].crypt) == 2


def test_hand_limit_completion_starts_new_round():
    game = make_discard_game()

    # One discard for player 1 and two for player 0.
    for _ in range(3):
        discard_first_legal_card(game)

    assert game.state.phase == Phase.FEEDING
    assert game.state.step == GameStep.COLLECT_RESOURCES
    assert game.state.round_number == 4
    assert game.state.active_player == 1

    assert all(
        len(player.hand) <= HAND_LIMIT
        for player in game.state.players
    )

    game.state.validate()


def test_inactive_player_cannot_discard():
    game = make_discard_game()

    with pytest.raises(ValueError, match="Illegal action"):
        game.step(
            Action(
                action_type=ActionType.DISCARD,
                player_id=0,
                source_id=1,
            )
        )

    assert len(game.state.players[0].hand) == 8
    assert len(game.state.players[0].crypt) == 0

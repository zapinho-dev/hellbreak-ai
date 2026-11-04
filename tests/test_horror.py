
import pytest

from engine.actions import Action, ActionType
from engine.game import Game
from engine.state import (
    GameState,
    GameStep,
    Phase,
    PlayerState,
)


def make_horror_game() -> Game:
    """Create a game at the start of the Horror Phase."""

    state = GameState(
        players=[
            PlayerState(player_id=0),
            PlayerState(player_id=1),
        ],
        locations=[],
        phase=Phase.HORROR,
        step=GameStep.PLAYER_ACTION,
        initiative_player=0,
        active_player=0,
    )

    return Game(state)


def perform_action(game: Game, action_type: ActionType) -> None:
    """Perform an action with the current active player."""

    action = Action(
        action_type=action_type,
        player_id=game.state.active_player,
    )

    game.step(action)


def test_horror_starts_with_initiative_player():
    game = make_horror_game()

    assert game.state.active_player == 0

    actions = game.get_legal_actions(0)

    assert {a.action_type for a in actions} == {
        ActionType.PASS,
        ActionType.SLUMBER,
    }

    assert game.get_legal_actions(1) == []


def test_pass_switches_active_player():
    game = make_horror_game()

    perform_action(game, ActionType.PASS)

    assert game.state.active_player == 1
    assert game.state.step == GameStep.PLAYER_ACTION
    assert game.state.last_horror_pass_player == 0


def test_two_consecutive_passes_end_horror():
    game = make_horror_game()

    perform_action(game, ActionType.PASS)
    perform_action(game, ActionType.PASS)

    assert game.state.phase == Phase.REFRESH
    assert game.state.step == GameStep.READY_CARDS

    game.state.validate()


def test_slumber_grants_malice():
    game = make_horror_game()

    perform_action(game, ActionType.SLUMBER)

    player_0 = game.state.players[0]

    assert player_0.malice == 1
    assert player_0.has_slumbered is True
    assert game.state.active_player == 1

    # The slumbered player cannot act again.
    assert game.get_legal_actions(0) == []

    # No other player can slumber this round.
    assert {
        a.action_type for a in game.get_legal_actions(1)
    } == {ActionType.PASS}


def test_slumber_then_pass_ends_horror():
    game = make_horror_game()

    perform_action(game, ActionType.SLUMBER)
    perform_action(game, ActionType.PASS)

    assert game.state.phase == Phase.REFRESH
    assert game.state.step == GameStep.READY_CARDS


def test_pass_then_slumber_ends_horror():
    game = make_horror_game()

    perform_action(game, ActionType.PASS)
    perform_action(game, ActionType.SLUMBER)

    assert game.state.phase == Phase.REFRESH
    assert game.state.step == GameStep.READY_CARDS
    assert game.state.players[1].malice == 1


def test_inactive_player_cannot_pass():
    game = make_horror_game()

    with pytest.raises(ValueError, match="Illegal action"):
        game.step(
            Action(
                action_type=ActionType.PASS,
                player_id=1,
            )
        )

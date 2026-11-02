import pytest

from engine.game import Game
from engine.state import GameState, PlayerState


def make_game() -> Game:
    """Create a minimal valid game for testing."""
    state = GameState(
        players=[
            PlayerState(player_id=0),
            PlayerState(player_id=1),
        ],
        locations=[]
    )
    return Game(state)


def test_game_initialization():
    game = make_game()

    assert game.state.round_number == 1
    assert game.state.winner is None
    assert game.is_terminal() is False


def test_game_clone_is_independent():
    game = make_game()
    cloned_game = game.clone()

    cloned_game.state.round_number = 5

    assert game.state.round_number == 1
    assert cloned_game.state.round_number == 5


def test_game_winner():
    game = make_game()

    game.state.winner = 0
    game.state.is_terminal = True

    assert game.is_terminal() is True
    assert game.get_winner() == 0


def test_invalid_game_initialization():
    state = GameState(
        players=[PlayerState(player_id=0)],
        locations=[],
    )

    with pytest.raises(ValueError):
        Game(state)
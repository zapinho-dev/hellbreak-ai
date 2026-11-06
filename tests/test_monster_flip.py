
import pytest

from engine.actions import Action, ActionType
from engine.game import Game
from engine.state import (
    CardInstance,
    GameState,
    GameStep,
    Phase,
    PlayerState,
)


def make_monster_flip_game(
    initiative_player: int = 1,
    from_ready_cards: bool = False,
) -> Game:
    """Create a game ready for Monster Flip decisions."""

    state = GameState(
        players=[
            PlayerState(
                player_id=0,
                monster=CardInstance(1, "monster_0", 0, 0),
            ),
            PlayerState(
                player_id=1,
                monster=CardInstance(2, "monster_1", 1, 1),
            ),
        ],
        locations=[],
        phase=Phase.REFRESH,
        step=(
            GameStep.READY_CARDS
            if from_ready_cards
            else GameStep.MONSTER_FLIP
        ),
        initiative_player=initiative_player,
        active_player=initiative_player,
    )

    return Game(state)


def choose_flip(game: Game, should_flip: bool) -> None:
    """Submit the current player's Monster Flip decision."""

    player_id = game.state.active_player

    action = next(
        action
        for action in game.get_legal_actions(player_id)
        if action.action_type == ActionType.FLIP_MONSTER
        and action.parameters == (should_flip,)
    )

    game.step(action)


def test_ready_cards_initializes_monster_flip():
    game = make_monster_flip_game(
        initiative_player=1,
        from_ready_cards=True,
    )

    # Simulate the last Horror action belonging to player 0.
    game.state.active_player = 0
    game.ready_cards()

    assert game.state.step == GameStep.MONSTER_FLIP
    assert game.state.active_player == 1
    assert game.state.monster_flip_completed == set()


def test_first_player_has_two_flip_decisions():
    game = make_monster_flip_game()

    actions = game.get_legal_actions(1)

    assert {a.parameters for a in actions} == {
        (False,),
        (True,),
    }

    assert all(
        a.action_type == ActionType.FLIP_MONSTER
        for a in actions
    )

    assert game.get_legal_actions(0) == []


def test_flipping_changes_lurking_to_unleashed():
    game = make_monster_flip_game()

    choose_flip(game, True)

    assert game.state.players[1].monster_unleashed is True
    assert game.state.monster_flip_completed == {1}
    assert game.state.active_player == 0
    assert game.state.step == GameStep.MONSTER_FLIP

    game.state.validate()


def test_keeping_current_side_does_not_flip():
    game = make_monster_flip_game()

    choose_flip(game, False)

    assert game.state.players[1].monster_unleashed is False
    assert game.state.active_player == 0


def test_both_decisions_advance_to_discard():
    game = make_monster_flip_game()

    choose_flip(game, True)
    choose_flip(game, False)

    assert game.state.players[1].monster_unleashed is True
    assert game.state.players[0].monster_unleashed is False

    assert game.state.monster_flip_completed == {0, 1}
    assert game.state.phase == Phase.REFRESH
    assert game.state.step == GameStep.DISCARD_TO_HAND_LIMIT

    game.state.validate()


def test_flipping_changes_unleashed_to_lurking():
    game = make_monster_flip_game()

    game.state.players[1].monster_unleashed = True

    choose_flip(game, True)

    assert game.state.players[1].monster_unleashed is False


def test_inactive_player_cannot_flip():
    game = make_monster_flip_game()

    with pytest.raises(ValueError, match="Illegal action"):
        game.step(
            Action(
                action_type=ActionType.FLIP_MONSTER,
                player_id=0,
                parameters=(True,),
            )
        )

    assert game.state.monster_flip_completed == set()


def test_player_cannot_decide_twice():
    game = make_monster_flip_game()

    choose_flip(game, True)

    assert game.get_legal_actions(1) == []

    with pytest.raises(ValueError, match="Illegal action"):
        game.step(
            Action(
                action_type=ActionType.FLIP_MONSTER,
                player_id=1,
                parameters=(True,),
            )
        )
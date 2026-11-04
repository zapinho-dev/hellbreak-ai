import pytest

from engine.game import Game
from engine.state import (
    GameState,
    PlayerState,
    Phase,
    GameStep,
)


def make_phase_game() -> Game:
    """Create a minimal game for testing phase transitions."""

    state = GameState(
        players=[
            PlayerState(player_id=0),
            PlayerState(player_id=1),
        ],
        locations=[],
    )

    return Game(state)


def test_game_starts_in_feeding_phase():
    game = make_phase_game()

    assert game.state.phase == Phase.FEEDING
    assert game.state.step == GameStep.COLLECT_RESOURCES
    assert game.state.round_number == 1


def test_feeding_step_transition():
    game = make_phase_game()

    # Simulate completed resource collection.
    game.state.resources_collected = {0, 1}
    
    game._transition_to(GameStep.INITIATIVE_BID)

    assert game.state.phase == Phase.FEEDING
    assert game.state.step == GameStep.INITIATIVE_BID


def test_invalid_step_transition():
    game = make_phase_game()

    with pytest.raises(
        ValueError,
        match="Invalid step transition",
    ):
        game._transition_to(GameStep.PLAYER_ACTION)


def test_round_increases_after_refresh():
    game = make_phase_game()

    # Simulate completed resource collection.
    game.state.resources_collected = {0, 1}

    # Move through the defined step sequence.
    game._transition_to(GameStep.INITIATIVE_BID)
    game._transition_to(GameStep.INITIATIVE_CHOICE)
    game._transition_to(GameStep.PLAYER_ACTION)

    assert game.state.phase == Phase.HORROR

    game._transition_to(GameStep.READY_CARDS)
    game._transition_to(GameStep.MONSTER_FLIP)
    game._transition_to(GameStep.DISCARD_TO_HAND_LIMIT)

    assert game.state.phase == Phase.REFRESH
    assert game.state.round_number == 1

    # Start the next round.
    game._transition_to(GameStep.COLLECT_RESOURCES)

    assert game.state.phase == Phase.FEEDING
    assert game.state.round_number == 2
    assert game.state.step == GameStep.COLLECT_RESOURCES

    game.state.validate()


def test_invalid_phase_step_combination():
    game = make_phase_game()

    game.state.phase = Phase.HORROR
    game.state.step = GameStep.COLLECT_RESOURCES

    with pytest.raises(
        ValueError,
        match="Invalid phase-step combination",
    ):
        game.state.validate()



def test_cannot_advance_without_resource_collection():
    game = make_phase_game()

    with pytest.raises(
        ValueError,
        match="Resource collection is incomplete",
    ):
        game._transition_to(GameStep.INITIATIVE_BID)

    # Failed transitions must not modify game state.
    assert game.state.step == GameStep.COLLECT_RESOURCES
    assert game.state.phase == Phase.FEEDING
    assert game.state.round_number == 1
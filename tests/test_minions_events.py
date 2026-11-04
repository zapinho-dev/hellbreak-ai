
import pytest

from engine.actions import ActionType
from engine.cards import CardDefinition, CardType, Aspect
from engine.game import Game
from engine.state import (
    CardInstance,
    GameState,
    GameStep,
    LocationState,
    Phase,
    PlayerState,
)


def make_minion_event_game(
    blood: int = 5,
    malice: int = 1,
) -> Game:
    """Create a game with a Minion and an Event in hand."""

    state = GameState(
        players=[
            PlayerState(
                player_id=0,
                blood=blood,
                malice=malice,
                monster=CardInstance(1, "monster", 0, 0),
                hand=[
                    CardInstance(2, "test_minion", 0, 0),
                    CardInstance(3, "test_event", 0, 0),
                ],
            ),
            PlayerState(player_id=1),
        ],
        locations=[
            LocationState("location_0", 0),
            LocationState("location_1", 1),
        ],
        phase=Phase.HORROR,
        step=GameStep.PLAYER_ACTION,
        active_player=0,
    )

    definitions = {
        "monster": CardDefinition(
            card_id="monster",
            name="Test Monster",
            card_type=CardType.MONSTER,
            vault_aspects={Aspect.FERAL: 2},
        ),
        "test_minion": CardDefinition(
            card_id="test_minion",
            name="Test Minion",
            card_type=CardType.MINION,
            cost=3,
            loyalty={Aspect.FERAL: 1},
            combat=2,
            health=3,
        ),
        "test_event": CardDefinition(
            card_id="test_event",
            name="Test Event",
            card_type=CardType.EVENT,
            cost=2,
            loyalty={Aspect.FERAL: 1},
        ),
    }

    return Game(state, definitions)


def test_minion_generates_location_actions():
    game = make_minion_event_game()

    actions = [
        a for a in game.get_legal_actions(0)
        if a.action_type == ActionType.PLAY_CARD
        and a.source_id == 2
    ]

    assert len(actions) == 4
    assert {a.location_id for a in actions} == {0, 1}
    assert {a.parameters for a in actions} == {(), (True,)}


def test_minion_enters_exhausted():
    game = make_minion_event_game()

    action = next(
        a for a in game.get_legal_actions(0)
        if a.action_type == ActionType.PLAY_CARD
        and a.source_id == 2
        and a.location_id == 0
        and a.parameters == ()
    )

    game.step(action)

    player = game.state.players[0]

    assert player.blood == 2
    assert player.malice == 1
    assert len(player.minions) == 1
    assert player.minions[0].location_id == 0
    assert player.minions[0].exhausted is True
    assert game.state.active_player == 1

    game.state.validate()


def test_minion_can_enter_ready():
    game = make_minion_event_game()

    action = next(
        a for a in game.get_legal_actions(0)
        if a.action_type == ActionType.PLAY_CARD
        and a.source_id == 2
        and a.location_id == 1
        and a.parameters == (True,)
    )

    game.step(action)

    player = game.state.players[0]

    assert player.blood == 2
    assert player.malice == 0
    assert player.minions[0].location_id == 1
    assert player.minions[0].exhausted is False

    game.state.validate()


def test_cannot_ready_minion_without_malice():
    game = make_minion_event_game(malice=0)

    actions = [
        a for a in game.get_legal_actions(0)
        if a.action_type == ActionType.PLAY_CARD
        and a.source_id == 2
    ]

    assert len(actions) == 2
    assert all(a.parameters == () for a in actions)


def test_event_moves_to_crypt():
    game = make_minion_event_game()

    action = next(
        a for a in game.get_legal_actions(0)
        if a.action_type == ActionType.PLAY_CARD
        and a.source_id == 3
    )

    game.step(action)

    player = game.state.players[0]

    assert player.blood == 3
    assert len(player.crypt) == 1
    assert player.crypt[0].card_id == "test_event"
    assert len(player.hand) == 1
    assert game.state.active_player == 1

    game.state.validate()


def test_event_with_unimplemented_effect_is_not_playable():
    game = make_minion_event_game()

    # Give the Event an effect the engine cannot resolve yet.
    game.card_definitions["test_event"] = CardDefinition(
        card_id="test_event",
        name="Test Event",
        card_type=CardType.EVENT,
        cost=2,
        loyalty={Aspect.FERAL: 1},
        ability_text="Deal 2 damage to a character.",
    )

    actions = game.get_legal_actions(0)

    assert not any(
        a.action_type == ActionType.PLAY_CARD
        and a.source_id == 3
        for a in actions
    )
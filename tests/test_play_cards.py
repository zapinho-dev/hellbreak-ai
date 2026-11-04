
import pytest

from engine.actions import Action, ActionType
from engine.cards import Aspect, CardDefinition, CardType
from engine.game import Game
from engine.state import (
    CardInstance,
    GameState,
    GameStep,
    Phase,
    PlayerState,
)


def make_asset_game(
    blood: int = 5,
    vault_icons: int = 2,
) -> Game:
    """Create a Horror game with one Asset in hand."""

    state = GameState(
        players=[
            PlayerState(
                player_id=0,
                blood=blood,
                monster=CardInstance(1, "monster", 0, 0),
                vault=[CardInstance(2, "vault_card", 0, 0)],
                hand=[CardInstance(3, "asset", 0, 0)],
            ),
            PlayerState(player_id=1),
        ],
        locations=[],
        phase=Phase.HORROR,
        step=GameStep.PLAYER_ACTION,
        active_player=0,
    )

    definitions = {
        "monster": CardDefinition(
            card_id="monster",
            name="Test Monster",
            card_type=CardType.MONSTER,
        ),
        "vault_card": CardDefinition(
            card_id="vault_card",
            name="Vault Card",
            card_type=CardType.MINION,
            vault_aspects={Aspect.CURSED: vault_icons},
        ),
        "asset": CardDefinition(
            card_id="asset",
            name="Test Asset",
            card_type=CardType.ASSET,
            cost=3,
            loyalty={Aspect.CURSED: 2},
        ),
    }

    return Game(state, definitions)


def test_asset_is_playable():
    game = make_asset_game()

    actions = game.get_legal_actions(0)

    assert any(
        action.action_type == ActionType.PLAY_CARD
        and action.source_id == 3
        for action in actions
    )


def test_asset_requires_enough_blood():
    game = make_asset_game(blood=2)

    actions = game.get_legal_actions(0)

    assert not any(
        action.action_type == ActionType.PLAY_CARD
        for action in actions
    )


def test_asset_requires_loyalty():
    game = make_asset_game(vault_icons=1)

    actions = game.get_legal_actions(0)

    assert not any(
        action.action_type == ActionType.PLAY_CARD
        for action in actions
    )


def test_play_asset_updates_state():
    game = make_asset_game()
    player = game.state.players[0]

    action = next(
        action
        for action in game.get_legal_actions(0)
        if action.action_type == ActionType.PLAY_CARD
    )

    game.step(action)

    assert player.blood == 2
    assert len(player.hand) == 0
    assert len(player.assets) == 1
    assert player.assets[0].instance_id == 3
    assert player.assets[0].exhausted is False

    assert game.state.active_player == 1

    game.state.validate()


def test_play_card_breaks_pass_sequence():
    game = make_asset_game()

    # Simulate an opponent pass before the active player's action.
    game.state.last_horror_pass_player = 1

    action = next(
        action
        for action in game.get_legal_actions(0)
        if action.action_type == ActionType.PLAY_CARD
    )

    game.step(action)

    assert game.state.last_horror_pass_player is None
    assert game.state.active_player == 1


def test_cannot_play_asset_with_insufficient_blood():
    game = make_asset_game(blood=2)

    action = Action(
        action_type=ActionType.PLAY_CARD,
        player_id=0,
        source_id=3,
    )

    with pytest.raises(ValueError, match="Illegal action"):
        game.step(action)

    assert len(game.state.players[0].hand) == 1
    assert len(game.state.players[0].assets) == 0
    assert game.state.players[0].blood == 2

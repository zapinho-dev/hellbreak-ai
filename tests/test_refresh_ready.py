
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


def make_refresh_game() -> Game:
    """Create a game at the beginning of the Refresh Phase."""

    state = GameState(
        players=[
            PlayerState(
                player_id=0,
                monster=CardInstance(
                    1, "monster_0", 0, 0, exhausted=True
                ),
                minions=[
                    CardInstance(
                        2,
                        "minion_0",
                        0,
                        0,
                        exhausted=True,
                        damage=2,
                        location_id=0,
                    ),
                ],
                assets=[
                    CardInstance(
                        3, "asset_0", 0, 0, exhausted=True
                    ),
                ],
                hand=[
                    CardInstance(
                        4, "hand_card", 0, 0, exhausted=True
                    ),
                ],
            ),
            PlayerState(
                player_id=1,
                monster=CardInstance(
                    5, "monster_1", 1, 1, exhausted=True
                ),
                minions=[
                    CardInstance(
                        6,
                        "minion_1",
                        1,
                        1,
                        exhausted=True,
                        location_id=1,
                    ),
                ],
                assets=[
                    CardInstance(
                        7, "asset_1", 1, 1, exhausted=True
                    ),
                ],
            ),
        ],
        locations=[
            LocationState("location_0", "0"),
            LocationState("location_1", "1"),
        ],
        phase=Phase.REFRESH,
        step=GameStep.READY_CARDS,
        initiative_player=0,
        active_player=0,
    )

    return Game(state)


def test_ready_cards_readies_both_players():
    """All cards in play become ready for both players."""

    game = make_refresh_game()

    game.ready_cards()

    for player in game.state.players:
        assert player.monster.exhausted is False

        assert all(
            minion.exhausted is False
            for minion in player.minions
        )

        assert all(
            asset.exhausted is False
            for asset in player.assets
        )

    game.state.validate()


def test_ready_cards_preserves_damage():
    """Refreshing must not remove damage from minions."""

    game = make_refresh_game()

    game.ready_cards()

    minion = game.state.players[0].minions[0]

    assert minion.damage == 2
    assert minion.exhausted is False


def test_ready_cards_does_not_change_hand_cards():
    """Cards outside the battlefield are not refreshed."""

    game = make_refresh_game()

    game.ready_cards()

    hand_card = game.state.players[0].hand[0]

    assert hand_card.exhausted is True


def test_ready_cards_advances_to_monster_flip():
    """Ready Cards automatically advances to Monster Flip."""

    game = make_refresh_game()

    game.ready_cards()

    assert game.state.phase == Phase.REFRESH
    assert game.state.step == GameStep.MONSTER_FLIP
    assert game.state.round_number == 1


def test_ready_cards_cannot_run_twice():
    """Ready Cards cannot be repeated in the same step."""

    game = make_refresh_game()

    game.ready_cards()

    with pytest.raises(
        ValueError,
        match="Not in Ready Cards step",
    ):
        game.ready_cards()


def test_ready_cards_cannot_run_in_horror():
    """Refreshing is forbidden during the Horror Phase."""

    game = make_refresh_game()

    game.state.phase = Phase.HORROR
    game.state.step = GameStep.PLAYER_ACTION

    with pytest.raises(
        ValueError,
        match="Not in Ready Cards step",
    ):
        game.ready_cards()

    assert game.state.players[0].monster.exhausted is True

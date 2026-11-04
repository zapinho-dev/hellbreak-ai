
import pytest

from engine.actions import ActionType
from engine.cards import CardDefinition, CardType
from engine.game import Game
from engine.state import (
    CardInstance,
    GameState,
    GameStep,
    Phase,
    PlayerState,
)


def make_initiative_game() -> Game:
    """Create a game ready for initiative bidding."""

    state = GameState(
        players=[
            PlayerState(
                player_id=0,
                hand=[CardInstance(1, "card_a", 0, 0)],
            ),
            PlayerState(
                player_id=1,
                hand=[CardInstance(2, "card_b", 1, 1)],
            ),
        ],
        locations=[],
        phase=Phase.FEEDING,
        step=GameStep.INITIATIVE_BID,
        initiative_player=0,
    )

    definitions = {
        "card_a": CardDefinition(
            card_id="card_a",
            name="Card A",
            card_type=CardType.MINION,
            cost=3,
        ),
        "card_b": CardDefinition(
            card_id="card_b",
            name="Card B",
            card_type=CardType.MINION,
            cost=5,
        ),
    }

    return Game(state, definitions)


def test_bid_actions_are_generated():
    game = make_initiative_game()

    actions = game.get_legal_actions(0)

    assert len(actions) == 2
    assert all(a.action_type == ActionType.BID for a in actions)
    assert {a.source_id for a in actions} == {None, 1}


def test_bids_remain_hidden_until_both_submit():
    game = make_initiative_game()

    action = next(
        a for a in game.get_legal_actions(0)
        if a.source_id == 1
    )

    game.step(action)

    assert game.state.step == GameStep.INITIATIVE_BID
    assert len(game.state.players[0].hand) == 1
    assert len(game.state.players[0].vault) == 0
    assert game.get_legal_actions(0) == []


def test_higher_bid_wins():
    game = make_initiative_game()

    game.submit_initiative_bid(0, 1)
    game.submit_initiative_bid(1, 2)

    assert game.state.initiative_bid_winner == 1
    assert game.state.step == GameStep.INITIATIVE_CHOICE

    assert len(game.state.players[0].hand) == 0
    assert len(game.state.players[1].hand) == 0
    assert len(game.state.players[0].vault) == 1
    assert len(game.state.players[1].vault) == 1

    game.state.validate()


def test_tied_bid_favors_non_initiative_player():
    game = make_initiative_game()

    # Both players decline to bid, producing a tie at zero.
    game.submit_initiative_bid(0, None)
    game.submit_initiative_bid(1, None)

    assert game.state.initiative_bid_winner == 1
    assert game.state.step == GameStep.INITIATIVE_CHOICE


def test_bid_winner_chooses_initiative():
    game = make_initiative_game()

    game.submit_initiative_bid(0, 1)
    game.submit_initiative_bid(1, 2)

    actions = game.get_legal_actions(1)

    assert len(actions) == 2

    # The winner chooses to give initiative to player 0.
    action = next(a for a in actions if a.target_id == 0)

    game.step(action)

    assert game.state.initiative_player == 0
    assert game.state.active_player == 0
    assert game.state.phase == Phase.HORROR
    assert game.state.step == GameStep.PLAYER_ACTION


def test_cannot_bid_twice():
    game = make_initiative_game()

    game.submit_initiative_bid(0, 1)

    with pytest.raises(
        ValueError,
        match="already submitted",
    ):
        game.submit_initiative_bid(0, None)



def test_invalid_bid_player_id():
    game = make_initiative_game()

    game.state.initiative_bids[99] = None

    with pytest.raises(
        ValueError,
        match="Initiative bids contain invalid player IDs",
    ):
        game.state.validate()


def test_bid_card_must_be_in_hand():
    game = make_initiative_game()

    game.state.initiative_bids[0] = 999

    with pytest.raises(
        ValueError,
        match="Submitted bid card is not in player's hand",
    ):
        game.state.validate()


def test_bid_winner_cannot_exist_before_reveal():
    game = make_initiative_game()

    game.state.initiative_bid_winner = 0

    with pytest.raises(
        ValueError,
        match="Bid winner cannot be assigned during bidding",
    ):
        game.state.validate()


def test_initiative_choice_requires_both_bids():
    game = make_initiative_game()

    game.state.step = GameStep.INITIATIVE_CHOICE

    with pytest.raises(
        ValueError,
        match="Initiative bids are incomplete",
    ):
        game.state.validate()


def test_resolved_bids_are_valid():
    game = make_initiative_game()

    game.submit_initiative_bid(0, 1)
    game.submit_initiative_bid(1, 2)

    assert game.state.step == GameStep.INITIATIVE_CHOICE

    # Bid cards have moved to the vault.
    assert len(game.state.players[0].vault) == 1
    assert len(game.state.players[1].vault) == 1

    # The resolved bidding state must remain valid.
    game.state.validate()
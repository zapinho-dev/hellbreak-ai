
from engine.actions import ActionType
from engine.cards import CardDefinition, CardType
from engine.constants import (
    DECK_SIZE,
    INITIAL_HAND_SIZE,
    INITIAL_HEALTH_STACK_SIZE,
)
from engine.game import Game
from engine.state import GameStep, Phase


def make_feeding_game(seed: int = 42) -> Game:
    """Create a complete game for Feeding Phase integration tests."""

    deck_0 = [
        f"dracula_card_{i}"
        for i in range(DECK_SIZE)
    ]

    deck_1 = [
        f"jaws_card_{i}"
        for i in range(DECK_SIZE)
    ]

    game = Game.new_game(
        deck_0=deck_0,
        deck_1=deck_1,
        monster_0="dracula",
        monster_1="jaws",
        location_0="dracula_location",
        location_1="jaws_location",
        seed=seed,
    )

    # Use fictional values to test the engine mechanics.
    definitions = {
        "dracula": CardDefinition(
            card_id="dracula",
            name="Dracula",
            card_type=CardType.MONSTER,
            blood_production=3,
            malice_production=1,
            draw_production=1,
        ),
        "jaws": CardDefinition(
            card_id="jaws",
            name="Jaws",
            card_type=CardType.MONSTER,
            blood_production=4,
            malice_production=2,
            draw_production=1,
        ),
    }

    # Assign a printed cost to every possible bid card.
    for card_id in deck_0:
        definitions[card_id] = CardDefinition(
            card_id=card_id,
            name=card_id,
            card_type=CardType.MINION,
            cost=2,
        )

    for card_id in deck_1:
        definitions[card_id] = CardDefinition(
            card_id=card_id,
            name=card_id,
            card_type=CardType.MINION,
            cost=5,
        )

    game.card_definitions = definitions

    return game



def test_complete_feeding_phase():
    """Test the complete Feeding Phase from setup to Horror."""

    game = make_feeding_game()
    player_0, player_1 = game.state.players

    # 1. Verify the initial setup.
    assert game.state.phase == Phase.FEEDING
    assert game.state.step == GameStep.COLLECT_RESOURCES
    assert game.state.round_number == 1

    for player in game.state.players:
        assert len(player.deck) == (
            DECK_SIZE
            - INITIAL_HAND_SIZE
            - INITIAL_HEALTH_STACK_SIZE
        )
        assert len(player.hand) == INITIAL_HAND_SIZE
        assert player.health == 16

    game.state.validate()

    # 2. Player 0 collects resources.
    game.collect_resources(0)

    assert player_0.blood == 3
    assert player_0.malice == 1
    assert len(player_0.hand) == INITIAL_HAND_SIZE + 1

    # The game must wait for the other player.
    assert game.state.step == GameStep.COLLECT_RESOURCES

    # 3. Player 1 collects resources.
    game.collect_resources(1)

    assert player_1.blood == 4
    assert player_1.malice == 2
    assert len(player_1.hand) == INITIAL_HAND_SIZE + 1

    # Both players have collected their resources.
    assert game.state.step == GameStep.INITIATIVE_BID

    game.state.validate()

    # 4. Each player submits a hidden bid.
    bid_0 = next(
        action
        for action in game.get_legal_actions(0)
        if action.action_type == ActionType.BID
        and action.source_id is not None
    )

    game.step(bid_0)

    # The opponent must not see the submitted card.
    observation_1 = game.observe(1)

    assert observation_1.opponent_bid_submitted is True
    assert observation_1.own_bid_submitted is False

    # The first bid must remain unresolved.
    assert game.state.step == GameStep.INITIATIVE_BID
    assert len(player_0.vault) == 0

    bid_1 = next(
        action
        for action in game.get_legal_actions(1)
        if action.action_type == ActionType.BID
        and action.source_id is not None
    )

    game.step(bid_1)

    # 5. The higher-cost bid wins.
    assert game.state.initiative_bid_winner == 1
    assert game.state.step == GameStep.INITIATIVE_CHOICE

    assert len(player_0.vault) == 1
    assert len(player_1.vault) == 1

    game.state.validate()

    # 6. The winner assigns initiative to player 0.
    choices = game.get_legal_actions(1)

    choose_player_0 = next(
        action
        for action in choices
        if action.action_type == ActionType.CHOOSE_INITIATIVE
        and action.target_id == 0
    )

    game.step(choose_player_0)

    # 7. The Horror Phase begins.
    assert game.state.phase == Phase.HORROR
    assert game.state.step == GameStep.PLAYER_ACTION
    assert game.state.initiative_player == 0
    assert game.state.active_player == 0

    assert game.state.round_number == 1
    assert game.is_terminal() is False

    # Bidding removed one card from each player's hand.
    assert len(player_0.hand) == INITIAL_HAND_SIZE
    assert len(player_1.hand) == INITIAL_HAND_SIZE

    # All card instances must remain valid.
    game.state.validate()



def test_feeding_phase_with_no_bids():
    """Test Feeding Phase when both players decline to bid."""

    game = make_feeding_game()

    game.collect_resources(0)
    game.collect_resources(1)

    assert game.state.step == GameStep.INITIATIVE_BID

    # Both players submit an empty bid.
    for player_id in (0, 1):
        action = next(
            action
            for action in game.get_legal_actions(player_id)
            if action.action_type == ActionType.BID
            and action.source_id is None
        )

        game.step(action)

    # Player 0 started with initiative.
    # Player 1 wins a tied bid.
    assert game.state.initiative_bid_winner == 1

    # Empty bids do not move any cards to the vault.
    assert len(game.state.players[0].vault) == 0
    assert len(game.state.players[1].vault) == 0

    # The winner chooses to take initiative.
    action = next(
        action
        for action in game.get_legal_actions(1)
        if action.action_type == ActionType.CHOOSE_INITIATIVE
        and action.target_id == 1
    )

    game.step(action)

    assert game.state.phase == Phase.HORROR
    assert game.state.active_player == 1
    assert game.state.initiative_player == 1

    game.state.validate()
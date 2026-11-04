import pytest


from engine.constants import (
    DECK_SIZE,
    INITIAL_HAND_SIZE,
    INITIAL_HEALTH_STACK_SIZE,
)
from engine.game import Game


def make_test_game(seed: int) -> Game:
    """Create a small test game with a fixed random seed."""

    return Game.new_game(
        deck_0=[f"dracula_card_{i}" for i in range(DECK_SIZE)],
        deck_1=[f"jaws_card_{i}" for i in range(DECK_SIZE)],
        monster_0="dracula",
        monster_1="jaws",
        location_0="dracula_location",
        location_1="jaws_location",
        seed=seed,
    )


def test_setup_card_counts():
    game = make_test_game(seed=42)

    assert len(game.state.players) == 2

    for player in game.state.players:
        # Check the number of cards remaining in the deck.
        assert len(player.deck) == (
            DECK_SIZE
            - INITIAL_HAND_SIZE
            - INITIAL_HEALTH_STACK_SIZE
        )

        #Check the initial hand size.
        assert len(player.hand) == INITIAL_HAND_SIZE

        # Check the initial health stack size.
        assert len(player.health_stack) == INITIAL_HEALTH_STACK_SIZE

        # Each health card provides 2 HP.
        assert player.health == INITIAL_HEALTH_STACK_SIZE * 2

        # Verify that all 50 deck cards are accounted for.
        assert (
            len(player.deck)
            + len(player.hand)
            + len(player.health_stack)
        ) == DECK_SIZE

    assert game.state.players[0].monster.card_id == "dracula"
    assert game.state.players[1].monster.card_id == "jaws"


def test_setup_is_reproducible():
    game_a = make_test_game(seed=42)
    game_b = make_test_game(seed=42)

    deck_a = [
        card.card_id
        for card in game_a.state.players[0].deck
    ]

    deck_b = [
        card.card_id
        for card in game_b.state.players[0].deck
    ]

    assert deck_a == deck_b


def test_setup_unique_instance_ids():
    game = make_test_game(seed=42)

    # Validation raises an error if card instance IDs are duplicated.
    game.state.validate()


def test_setup_card_counts():
    game = make_test_game(seed=42)

    assert len(game.state.players) == 2

    for player in game.state.players:
        assert len(player.deck) == 38
        assert len(player.hand) == 4
        assert len(player.health_stack) == 8
        assert player.health == 16

    assert game.state.players[0].monster.card_id == "dracula"
    assert game.state.players[1].monster.card_id == "jaws"


def test_invalid_deck_size():
    with pytest.raises(
        ValueError,
        match="A deck must contain exactly 50 cards",
    ):
        Game.new_game(
            deck_0=["card"] * 49,
            deck_1=["card"] * 50,
            monster_0="dracula",
            monster_1="jaws",
            location_0="dracula_location",
            location_1="jaws_location",
            seed=42,
        )
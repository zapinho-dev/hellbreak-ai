
import pytest

from engine.state import (
    CardInstance,
    GameState,
    HealthCard,
    LocationState,
    PlayerState,
)


def make_valid_state() -> GameState:
    """Create a valid minimal game state."""

    return GameState(
        players=[
            PlayerState(
                player_id=0,
                hand=[
                    CardInstance(1, "hand_card", 0, 0),
                ],
                monster=CardInstance(2, "monster_0", 0, 0),
                health_stack=[
                    HealthCard(
                        CardInstance(3, "health_card", 0, 0)
                    ),
                ],
            ),
            PlayerState(
                player_id=1,
                monster=CardInstance(4, "monster_1", 1, 1),
            ),
        ],
        locations=[
            LocationState("location_0", "0"),
            LocationState("location_1", "1"),
        ],
    )


def test_valid_state_passes_validation():
    state = make_valid_state()

    state.validate()


def test_negative_card_damage_is_invalid():
    state = make_valid_state()

    state.players[0].hand[0].damage = -1

    with pytest.raises(ValueError, match="Negative card damage"):
        state.validate()


def test_negative_health_card_damage_is_invalid():
    state = make_valid_state()

    state.players[0].health_stack[0].card.damage = -1

    with pytest.raises(ValueError, match="Negative card damage"):
        state.validate()


def test_card_in_hand_cannot_have_location():
    state = make_valid_state()

    state.players[0].hand[0].location_id = 0

    with pytest.raises(
        ValueError,
        match="Card outside battlefield has location",
    ):
        state.validate()


def test_health_card_cannot_have_location():
    state = make_valid_state()

    state.players[0].health_stack[0].card.location_id = 0

    with pytest.raises(
        ValueError,
        match="Health card cannot occupy a location",
    ):
        state.validate()


def test_location_malice_cannot_be_negative():
    state = make_valid_state()

    state.locations[0].malice[0] = -1

    with pytest.raises(
        ValueError,
        match="Location Malice cannot be negative",
    ):
        state.validate()


def test_location_malice_requires_valid_player():
    state = make_valid_state()

    state.locations[0].malice[99] = 2

    with pytest.raises(
        ValueError,
        match="Location Malice contains invalid player IDs",
    ):
        state.validate()


def test_location_card_id_cannot_be_empty():
    state = make_valid_state()

    state.locations[0].card_id = ""

    with pytest.raises(
        ValueError,
        match="Location card ID cannot be empty",
    ):
        state.validate()

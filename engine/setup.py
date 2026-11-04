import random

from engine.constants import (
    DECK_SIZE,
    INITIAL_HAND_SIZE,
    INITIAL_HEALTH_STACK_SIZE,
)

from engine.state import (
    CardInstance,
    GameState,
    HealthCard,
    LocationState,
    PlayerState,
)


def create_initial_state(
    deck_0: list[str],
    deck_1: list[str],
    monster_0: str,
    monster_1: str,
    location_0: str,
    location_1: str,
    seed: int | None = None,
) -> GameState:
    """Create a reproducible preliminary game state."""

    rng = random.Random(seed)
    next_instance_id = 1


    def create_card(card_id: str, owner_id: int) -> CardInstance:
        nonlocal next_instance_id

        card = CardInstance(
            instance_id=next_instance_id,
            card_id=card_id,
            owner_id=owner_id,
            controller_id=owner_id,
        )

        next_instance_id += 1
        return card

    players = []

    for player_id, deck_ids, monster_id in [
        (0, deck_0, monster_0),
        (1, deck_1, monster_1),
    ]:
        deck = [
            create_card(card_id, player_id)
            for card_id in deck_ids
        ]

        rng.shuffle(deck)

        if len(deck) != DECK_SIZE:
            raise ValueError(
                f"A deck must contain exactly {DECK_SIZE} cards"
            )

        # Draw the inintial four cards.
        initial_hand = [deck.pop() for _ in range(INITIAL_HAND_SIZE)]

        # Build the initial health stack with eight face-down cards.
        health_stack = [
            HealthCard(card=deck.pop())
            for _ in range(INITIAL_HEALTH_STACK_SIZE)
        ]

        player = PlayerState(
            player_id=player_id,
            deck=deck,
            hand=initial_hand,
            health_stack=health_stack,
            monster=create_card(monster_id, player_id)
        )

        players.append(player)

    locations = [
        LocationState(
            card_id=location_0,
            controller_id=0,
        ),
        LocationState(
            card_id=location_1,
            controller_id=1,
        ),
    ]

    state = GameState(
        players=players,
        locations=locations,
    )

    state.validate()
    return state
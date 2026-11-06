
from engine.actions import ActionType
from engine.cards import CardDefinition, CardType
from engine.constants import DECK_SIZE, HAND_LIMIT
from engine.game import Game
from engine.state import GameStep, Phase


def make_two_round_game(seed: int = 42) -> Game:
    """Create a complete game for a two-round integration test."""

    deck_0 = [f"deck_0_card_{i}" for i in range(DECK_SIZE)]
    deck_1 = [f"deck_1_card_{i}" for i in range(DECK_SIZE)]

    game = Game.new_game(
        deck_0=deck_0,
        deck_1=deck_1,
        monster_0="monster_0",
        monster_1="monster_1",
        location_0="location_0",
        location_1="location_1",
        seed=seed,
    )

    definitions = {
        monster_id: CardDefinition(
            card_id=monster_id,
            name=monster_id,
            card_type=CardType.MONSTER,
            blood_production=2,
            malice_production=1,
            draw_production=3,
        )
        for monster_id in ("monster_0", "monster_1")
    }

    # Events with unsupported effects cannot be played yet.
    # This keeps Horror focused on PASS for this integration test.
    for card_id in deck_0 + deck_1:
        definitions[card_id] = CardDefinition(
            card_id=card_id,
            name=card_id,
            card_type=CardType.EVENT,
            ability_text="Unimplemented test effect.",
        )

    game.card_definitions = definitions
    return game


def perform_action(
    game: Game,
    player_id: int,
    action_type: ActionType,
    *,
    source_id: int | None = None,
    target_id: int | None = None,
    parameters: tuple | None = None,
) -> None:
    """Select and execute a matching legal action."""

    actions = game.get_legal_actions(player_id)

    matching = [
        action
        for action in actions
        if action.action_type == action_type
        and action.source_id == source_id
        and action.target_id == target_id
        and (
            parameters is None
            or action.parameters == parameters
        )
    ]

    assert len(matching) == 1, (
        f"Expected one legal {action_type.name} action "
        f"for player {player_id}, found {len(matching)}"
    )

    game.step(matching[0])
    game.state.validate()


def complete_round(
    game: Game,
    initiative_target: int,
    flip_choices: dict[int, bool],
) -> None:
    """Play one complete Feeding, Horror and Refresh cycle."""

    assert game.state.phase == Phase.FEEDING
    assert game.state.step == GameStep.COLLECT_RESOURCES

    # Feeding: both players collect their resources.
    game.collect_resources(0)
    game.state.validate()

    game.collect_resources(1)
    game.state.validate()

    assert game.state.step == GameStep.INITIATIVE_BID

    # Both players submit an empty bid.
    for player_id in (0, 1):
        perform_action(
            game,
            player_id,
            ActionType.BID,
        )

    assert game.state.step == GameStep.INITIATIVE_CHOICE

    # The bid winner chooses who receives initiative.
    winner = game.state.initiative_bid_winner

    perform_action(
        game,
        winner,
        ActionType.CHOOSE_INITIATIVE,
        target_id=initiative_target,
    )

    assert game.state.phase == Phase.HORROR
    assert game.state.active_player == initiative_target

    # Horror: two consecutive passes end the phase.
    for _ in range(2):
        perform_action(
            game,
            game.state.active_player,
            ActionType.PASS,
        )

    assert game.state.phase == Phase.REFRESH
    assert game.state.step == GameStep.READY_CARDS

    # Refresh: automatic readying.
    game.ready_cards()
    game.state.validate()

    assert game.state.step == GameStep.MONSTER_FLIP
    assert game.state.active_player == initiative_target

    # Each player decides whether to flip their monster.
    for _ in range(2):
        player_id = game.state.active_player

        perform_action(
            game,
            player_id,
            ActionType.FLIP_MONSTER,
            parameters=(flip_choices[player_id],),
        )

    # The engine now enters hand-limit discarding.
    # If no discards are necessary, it may skip this step.
    while game.state.step == GameStep.DISCARD_TO_HAND_LIMIT:
        player_id = game.state.active_player

        discard_actions = [
            action
            for action in game.get_legal_actions(player_id)
            if action.action_type == ActionType.DISCARD
        ]

        assert discard_actions, (
            "Discard step has no legal actions"
        )

        game.step(discard_actions[0])
        game.state.validate()

    # A completed round returns to Feeding.
    assert game.state.phase == Phase.FEEDING
    assert game.state.step == GameStep.COLLECT_RESOURCES
    assert game.state.resources_collected == set()
    assert game.state.initiative_bids == {}
    assert game.state.initiative_bid_winner is None
    assert game.state.monster_flip_completed == set()

    assert all(
        not player.has_slumbered
        for player in game.state.players
    )

    assert all(
        len(player.hand) <= HAND_LIMIT
        for player in game.state.players
    )


def test_two_complete_rounds():
    """Test two full rounds without manually changing game state."""

    game = make_two_round_game()

    assert game.state.round_number == 1
    assert game.state.initiative_player == 0

    # Round 1: player 0 receives initiative and flips.
    complete_round(
        game,
        initiative_target=0,
        flip_choices={0: True, 1: False},
    )

    assert game.state.round_number == 2
    assert game.state.initiative_player == 0
    assert game.state.players[0].monster_unleashed is True
    assert game.state.players[1].monster_unleashed is False

    # Round 2: initiative switches to player 1.
    complete_round(
        game,
        initiative_target=1,
        flip_choices={0: False, 1: True},
    )

    assert game.state.round_number == 3
    assert game.state.initiative_player == 1

    # Both monsters have been flipped once.
    assert game.state.players[0].monster_unleashed is True
    assert game.state.players[1].monster_unleashed is True

    for player in game.state.players:
        # Each round produces 2 Blood and 1 Malice.
        assert player.blood == 4
        assert player.malice == 2

        # Three cards are drawn in each round.
        assert len(player.deck) == 32

        # Discard one in round 1 and three in round 2.
        assert len(player.hand) == HAND_LIMIT
        assert len(player.crypt) == 4

        # Neither monster has taken damage.
        assert player.health == 16

    assert game.is_terminal() is False
    assert game.get_winner() is None

    game.state.validate()

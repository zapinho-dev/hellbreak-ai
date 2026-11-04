import pytest

from engine.actions import Action, ActionType
from engine.cards import CardDefinition, CardType
from engine.game import Game
from engine.state import CardInstance, GameState, GameStep, HealthCard, Phase, PlayerState


def make_game() -> Game:
    """Create a minimal valid game for testing."""
    state = GameState(
        players=[
            PlayerState(player_id=0),
            PlayerState(player_id=1),
        ],
        locations=[]
    )
    return Game(state)


def make_resource_game() -> Game:
    """Create a game with test resource-producing cards."""

    game = make_game()

    player = game.state.players[0]

    player.monster = CardInstance(
        instance_id=1,
        card_id="test_monster",
        owner_id=0,
        controller_id=0,
    )

    player.vault = [
        CardInstance(
            instance_id=2,
            card_id="vault_card",
            owner_id=0,
            controller_id=0
        )
    ]

    game.card_definitions = {
        "test_monster": CardDefinition(
            card_id="test_monster",
            name="Test Monster",
            card_type=CardType.MONSTER,
            blood_production=3,
            malice_production=1,
        ),
        "vault_card": CardDefinition(
            card_id="vault_card",
            name="Vault Card",
            card_type=CardType.MINION,
            blood_production=2,
            malice_production=2,
        ),
    }

    return game


def test_game_initialization():
    game = make_game()

    assert game.state.round_number == 1
    assert game.state.winner is None
    assert game.is_terminal() is False


def test_game_clone_is_independent():
    game = make_game()
    cloned_game = game.clone()

    cloned_game.state.round_number = 5

    assert game.state.round_number == 1
    assert cloned_game.state.round_number == 5


def test_game_winner():
    game = make_game()

    game.state.winner = 0
    game.state.is_terminal = True

    assert game.is_terminal() is True
    assert game.get_winner() == 0


def test_invalid_game_initialization():
    state = GameState(
        players=[PlayerState(player_id=0)],
        locations=[],
    )

    with pytest.raises(ValueError):
        Game(state)


def test_draw_cards():
    game = make_game()

    player = game.state.players[0]

    player.deck = [
        CardInstance(
            instance_id=i,
            card_id=f"card_{i}",
            owner_id=0,
            controller_id=0,
        )
        for i in range(1, 11)
    ]

    drawn = game.draw_cards(player_id=0, count=3)

    assert len(drawn) == 3
    assert len(player.hand) == 3
    assert len(player.deck) == 7

    # Cards are drawn from the end of the deck list.
    assert [card.card_id for card in drawn] == [
        "card_10",
        "card_9",
        "card_8",
    ]

    # Drawing cards does not create or duplicate instances.
    game.state.validate()


def test_draw_from_empty_deck():
    game = make_game()
    player = game.state.players[0]

    # Give the monster 8 health cards (16 HP).    
    player.health_stack = [
        HealthCard(CardInstance(i, f"health_{i}", 0, 0))
        for i in range(1, 9)
    ]

    # The deck is empty.
    assert len(player.deck) == 0

    drawn = game.draw_cards(player_id=0, count=1)

    assert drawn == []
    assert player.health == 14
    assert game.is_terminal() is False

    game.state.validate()


def test_monster_takes_one_damage():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(
            card=CardInstance(
                instance_id=1,
                card_id="health_card",
                owner_id=0,
                controller_id=0,
            )
        )
    ]

    revealed = game.deal_monster_damage(0, 1)

    assert player.health == 1
    assert player.health_stack[-1].vertical is True
    assert revealed == []
    assert game.is_terminal() is False


def test_monster_takes_two_damage():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(
            card=CardInstance(1, "health_card", 0, 0)
        )
    ]

    revealed = game.deal_monster_damage(0, 2)

    assert player.health == 0
    assert len(player.health_stack) == 0
    assert len(player.crypt) == 1
    assert revealed[0].card_id == "health_card"

    assert game.is_terminal() is True
    assert game.get_winner() == 1


def test_monster_takes_three_damage():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(i, f"card_{i}", 0, 0))
        for i in range(1, 9)
    ]

    revealed = game.deal_monster_damage(0, 3)

    assert player.health == 13
    assert len(player.health_stack) == 7
    assert player.health_stack[-1].vertical is True
    assert len(revealed) == 1
    assert len(player.crypt) == 1

    game.state.validate()


def test_monster_damage_cannot_be_negative():
    game = make_game()

    with pytest.raises(
        ValueError,
        match="Damage cannot be negative",
    ):
        game.deal_monster_damage(0, -1)



def test_single_damage_does_not_reveal_card():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(1, "test_card", 0, 0))
    ]

    revealed = game._apply_one_monster_damage(0)

    assert revealed is None
    assert player.health == 1
    assert len(player.health_stack) == 1
    assert len(player.crypt) == 0


def test_second_damage_reveals_card():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(1, "card_1", 0, 0)),
        HealthCard(CardInstance(2, "card_2", 0, 0)),
    ]

    # First damage rotates the top health card.
    first = game._apply_one_monster_damage(0)

    assert first is None
    assert player.health == 3

    # Second damage reveals the same card.
    second = game._apply_one_monster_damage(0)

    assert second is not None
    assert second.card_id == "card_2"
    assert player.health == 2
    assert len(player.crypt) == 1
    assert game.is_terminal() is False

    game.state.validate()



def test_damage_pauses_on_reveal():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(i, f"card_{i}", 0, 0))
        for i in range(1, 9)
    ]

    game.start_damage(player_id=0, amount=5)

    pending = game.state.pending_damage

    assert pending is not None
    assert pending.player_id == 0
    assert pending.remaining == 3
    assert pending.revealed_card_id == 8

    assert player.health == 14
    assert len(player.crypt) == 1

    game.state.validate()



def test_damage_can_resume():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(i, f"card_{i}", 0, 0))
        for i in range(1, 9)
    ]

    game.start_damage(player_id=0, amount=5)

    # Resume after handling the first revealed card.
    game.resume_damage()

    pending = game.state.pending_damage

    assert pending is not None
    assert pending.remaining == 1
    assert pending.revealed_card_id == 7

    # Resume after handling the second revealed card.
    game.resume_damage()

    assert game.state.pending_damage is None
    assert player.health == 11
    assert len(player.crypt) == 2

    game.state.validate()



def test_cannot_start_damage_while_pending():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(i, f"card_{i}", 0, 0))
        for i in range(1, 9)
    ]

    game.start_damage(player_id=0, amount=5)

    with pytest.raises(
        ValueError,
        match="A damage sequence is already pending",
    ):
        game.start_damage(player_id=1, amount=2)



def test_pending_reveal_generates_legal_action():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(i, f"card_{i}", 0, 0))
        for i in range(1, 9)
    ]

    game.start_damage(0, 5)

    actions = game.get_legal_actions(0)

    assert len(actions) == 1
    assert actions[0].action_type == ActionType.RESOLVE_REVEAL
    assert actions[0].source_id == 8

    # The opponent cannot resolve our revealed card.
    assert game.get_legal_actions(1) == []


def test_step_resolves_reveal():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(i, f"card_{i}", 0, 0))
        for i in range(1, 9)
    ]

    game.start_damage(0, 5)

    action = game.get_legal_actions(0)[0]
    game.step(action)

    pending = game.state.pending_damage

    assert pending is not None
    assert pending.remaining == 1
    assert pending.revealed_card_id == 7


def test_step_rejects_illegal_action():
    game = make_game()

    illegal_action = Action(
        action_type=ActionType.ATTACK,
        player_id=0,
        source_id=999,
    )

    with pytest.raises(ValueError, match="Illegal action"):
        game.step(illegal_action)


def test_collect_resources():
    game = make_resource_game()
    player = game.state.players[0]

    game.collect_resources(0)

    assert player.blood == 5
    assert player.malice == 3
    assert 0 in game.state.resources_collected
    assert game.state.step == GameStep.COLLECT_RESOURCES

    game.state.validate()


def test_resources_are_added_to_existing_pool():
    game = make_resource_game()
    player = game.state.players[0]

    player.blood = 4
    player.malice = 2

    game.collect_resources(0)

    assert player.blood == 9
    assert player.malice == 5


def test_cannot_collect_resources_twice():
    game = make_resource_game()

    game.collect_resources(0)

    with pytest.raises(
        ValueError,
        match="has already collected resources",
    ):
        game.collect_resources(0)


def test_cannot_collect_resources_in_wrong_step():
    game = make_resource_game()

    game.state.resources_collected = {0, 1}

    game._transition_to(GameStep.INITIATIVE_BID)

    with pytest.raises(
        ValueError,
        match="Resources can only be collected",
    ):
        game.collect_resources(0)


def test_resource_collection_resets_next_round():
    game = make_resource_game()

    game.collect_resources(0)

    assert game.state.resources_collected == {0}

    # Simulate the second plauer's completed collection.
    game.state.resources_collected.add(1)

    # Advance through the remaining round steps.
    game._transition_to(GameStep.INITIATIVE_BID)
    game._transition_to(GameStep.INITIATIVE_CHOICE)
    game._transition_to(GameStep.PLAYER_ACTION)
    game._transition_to(GameStep.READY_CARDS)
    game._transition_to(GameStep.MONSTER_FLIP)
    game._transition_to(GameStep.DISCARD_TO_HAND_LIMIT)
    game._transition_to(GameStep.COLLECT_RESOURCES)

    assert game.state.round_number == 2
    assert game.state.resources_collected == set()

    # The player can collect resources again.
    game.collect_resources(0)

    assert game.state.resources_collected == {0}
    assert game.state.players[0].blood == 10
    assert game.state.players[0].malice == 6


def test_collect_resources_draws_cards():
    game = make_resource_game()
    player = game.state.players[0]

    # Add ten cards to the player's deck.
    player.deck = [
        CardInstance(
            instance_id=i,
            card_id=f"draw_card_{i}",
            owner_id=0,
            controller_id=0,
        )
        for i in range(10, 20)
    ]

    # The monster generates two card draws.
    game.card_definitions["test_monster"] = CardDefinition(
        card_id="test_monster",
        name="Test Monster",
        card_type=CardType.MONSTER,
        blood_production=3,
        malice_production=1,
        draw_production=2,
    )

    game.collect_resources(0)

    assert player.blood == 5
    assert player.malice == 3

    assert len(player.hand) == 2
    assert len(player.deck) == 8

    # Cards are drawn from the end of the deck.
    assert [card.card_id for card in player.hand] == [
        "draw_card_19",
        "draw_card_18",
    ]

    game.state.validate()



def test_collect_resources_combines_card_draws():
    game = make_resource_game()
    player = game.state.players[0]

    player.deck = [
        CardInstance(i, f"draw_card_{i}", 0, 0)
        for i in range(10, 20)
    ]

    # Monster produces two cards.
    game.card_definitions["test_monster"] = CardDefinition(
        card_id="test_monster",
        name="Test Monster",
        card_type=CardType.MONSTER,
        draw_production=2,
    )

    # Vault card produces one additional card.
    game.card_definitions["vault_card"] = CardDefinition(
        card_id="vault_card",
        name="Vault Card",
        card_type=CardType.MINION,
        draw_production=1,
    )

    game.collect_resources(0)

    assert len(player.hand) == 3
    assert len(player.deck) == 7
    assert 0 in game.state.resources_collected

    game.state.validate()


def test_collect_resources_insufficient_deck():
    game = make_resource_game()
    player = game.state.players[0]

    player.deck = [
        CardInstance(10, "draw_card", 0, 0)
    ]

    player.health_stack = [
        HealthCard(CardInstance(i, f"health_{i}", 0, 0))
        for i in range(20, 28)
    ]

    game.card_definitions["test_monster"] = CardDefinition(
        card_id="test_monster",
        name="Test Monster",
        card_type=CardType.MONSTER,
        blood_production=3,
        malice_production=1,
        draw_production=2,
    )

    game.collect_resources(0)

    # Blood and Malice are collected normally.
    assert player.blood == 5
    assert player.malice == 3

    # Only one card can be drawn.
    assert len(player.hand) == 1
    assert len(player.deck) == 0

    # The failed draw deals 2 damage.
    assert player.health == 14

    # Resource collection is completed.
    assert 0 in game.state.resources_collected

    game.state.validate()


def test_collect_resources_waits_for_both_players():
    game = make_resource_game()

    game.collect_resources(0)

    assert game.state.step == GameStep.COLLECT_RESOURCES
    assert game.state.resources_collected == {0}


def test_collect_resources_advances_to_initiative_bid():
    game = make_resource_game()

    player_1 = game.state.players[1]

    player_1.monster = CardInstance(
        instance_id=3,
        card_id="second_monster",
        owner_id=1,
        controller_id=1,
    )

    game.card_definitions["second_monster"] = CardDefinition(
        card_id="second_monster",
        name="Second Monster",
        card_type=CardType.MONSTER,
        blood_production=4,
        malice_production=2,
    )

    # The first player collects resources.
    game.collect_resources(0)

    assert game.state.step == GameStep.COLLECT_RESOURCES

    # The second player collects resources.
    game.collect_resources(1)

    # Both players have completed the collection step.
    assert game.state.resources_collected == {0, 1}

    # The game automatically advances to the initiative bid.
    assert game.state.step == GameStep.INITIATIVE_BID
    assert game.state.phase == Phase.FEEDING

    assert player_1.blood == 4
    assert player_1.malice == 2

    game.state.validate()


def test_cannot_collect_after_step_advances():
    game = make_resource_game()

    player_1 = game.state.players[1]

    player_1.monster = CardInstance(
        instance_id=3,
        card_id="second_monster",
        owner_id=1,
        controller_id=1,
    )

    game.card_definitions["second_monster"] = CardDefinition(
        card_id="second_monster",
        name="Second Monster",
        card_type=CardType.MONSTER,
    )

    game.collect_resources(0)
    game.collect_resources(1)

    assert game.state.step == GameStep.INITIATIVE_BID

    with pytest.raises(
        ValueError,
        match="Resources can only be collected",
    ):
        game.collect_resources(0)



def test_draw_more_cards_than_available():
    game = make_game()
    player = game.state.players[0]

    player.deck = [
        CardInstance(20, "draw_card_1", 0, 0),
        CardInstance(21, "draw_card_2", 0, 0),
    ]

    player.health_stack = [
        HealthCard(CardInstance(i, f"health_{i}", 0, 0))
        for i in range(1, 9)
    ]

    drawn = game.draw_cards(0, 3)

    # Two cards are drawn successfully.
    assert len(drawn) == 2
    assert len(player.hand) == 2
    assert len(player.deck) == 0

    # The third draw fails and deals 2 damage.
    assert player.health == 14

    game.state.validate()


def test_multiple_failed_draws():
    game = make_game()
    player = game.state.players[0]

    player.health_stack = [
        HealthCard(CardInstance(i, f"health_{i}", 0, 0))
        for i in range(1, 9)
    ]

    drawn = game.draw_cards(0, 3)

    # Three failed draws deal 6 damage.
    assert drawn == []
    assert player.health == 10
    assert len(player.crypt) == 3
    assert game.is_terminal() is False

    game.state.validate()


def test_failed_draw_can_end_game():
    game = make_game()
    player = game.state.players[0]

    # The monster has only 2 HP remaining.
    player.health_stack = [
        HealthCard(
            CardInstance(1, "last_health_card", 0, 0)
        )
    ]

    game.draw_cards(0, 1)

    assert player.health == 0
    assert game.is_terminal() is True
    assert game.get_winner() == 1
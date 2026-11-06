from engine.actions import Action, ActionType
from engine.cards import CardDefinition, CardType
from engine.observation import (
    CardObservation,
    GameObservation,
    HandCardObservation,
    LocationObservation,
    PlayerObservation,
)
from engine.rules import calculate_vault_resources, can_play_card
from engine.setup import create_initial_state
from engine.state import (
    CardInstance,
    GameState,
    GameStep,
    PendingDamage,
    Phase,
    STEP_PHASE_MAP,
)


STEP_TRANSITIONS = {
    GameStep.COLLECT_RESOURCES: GameStep.INITIATIVE_BID,
    GameStep.INITIATIVE_BID: GameStep.INITIATIVE_CHOICE,
    GameStep.INITIATIVE_CHOICE: GameStep.PLAYER_ACTION,

    GameStep.PLAYER_ACTION: GameStep.READY_CARDS,

    GameStep.READY_CARDS: GameStep.MONSTER_FLIP,
    GameStep.MONSTER_FLIP: GameStep.DISCARD_TO_HAND_LIMIT,
    GameStep.DISCARD_TO_HAND_LIMIT: GameStep.COLLECT_RESOURCES,
}


class Game:
    """Manage the lifecycle of a Hellbreak game."""

    def __init__(
        self, 
        state: GameState,
        card_definitions: dict[str, CardDefinition] | None = None
    ):
        """Initialize the game with a state and card definitions."""
        state.validate()

        self.state = state
        self.card_definitions = (
            dict(card_definitions)
            if card_definitions is not None
            else {}
        )


    def get_state(self) -> GameState:
        """Return the current game state."""
        return self.state


    def clone(self) -> "Game":
        """Create an independent copy of the game."""
        return Game(
            self.state.clone(),
            self.card_definitions,
        )


    def is_terminal(self) -> bool:
        """Check whether the game has ended."""
        return self.state.is_terminal


    def get_winner(self) -> int | None:
        """Return the winning player ID, if any."""
        return self.state.winner


    @classmethod
    def new_game(
        cls,
        deck_0: list[str],
        deck_1: list[str],
        monster_0: str,
        monster_1: str,
        location_0: str,
        location_1: str,
        seed: int | None = None,
    ) -> "Game":
        """Create a game from two decks and their starting cards."""

        from engine.setup import create_initial_state

        state = create_initial_state(
            deck_0=deck_0,
            deck_1=deck_1,
            monster_0=monster_0,
            monster_1=monster_1,
            location_0=location_0,
            location_1=location_1,
            seed=seed,
        )

        return cls(state)


    def draw_cards(self, player_id: int, count: int = 1) -> list[CardInstance]:
        """Draw cards and apply damage for failed draws.

        Each draw from an empty deck deals 2 damage to
        the player's monster.

        Jumpscare interruptions are not handled yet.
        """

        if count < 0:
            raise ValueError("Draw count cannot be negative")

        if self.state.is_terminal:
            raise ValueError("Cannot draw in a finished game")

        if self.state.pending_damage is not None:
            raise ValueError("Cannot draw during pending damage")

        player = next(
            (p for p in self.state.players if p.player_id == player_id),
            None,
        )

        if player is None:
            raise ValueError(f"Invalid player ID: {player_id}")

        drawn_cards = []

        for _ in range(count):
            if self.state.is_terminal:
                break

            if player.deck:
                # Draw the top card from the deck.
                card = player.deck.pop()
                player.hand.append(card)
                drawn_cards.append(card)

            else:
                # An empty deck causes 2 monster damage
                # instead of drawing a card.
                self.deal_monster_damage(
                    player_id=player_id,
                    amount=2,
                )

        return drawn_cards


    def _apply_one_monster_damage(
        self,
        player_id: int,
    ) -> CardInstance | None:
        """Apply one damage to a monster.

        Return the revealed card, or None if no card is revealed.
        """

        player = next(
            (p for p in self.state.players if p.player_id == player_id),
            None,
        )

        if player is None:
            raise ValueError(f"Invalid player ID: {player_id}")

        if not player.health_stack:
            raise ValueError("Monster has no health remaining")

        health_card = player.health_stack[-1]

        if not health_card.vertical:
            # First damage: rotate the card vertically.
            health_card.vertical = True
            return None

        # Second damage: reveal and discard the card.
        removed = player.health_stack.pop()
        player.crypt.append(removed.card)

        if not player.health_stack:
            # The monster dies when its health stack is empty.
            self.state.is_terminal = True
            self.state.winner = next(
                p.player_id
                for p in self.state.players
                if p.player_id != player_id
            )

        return removed.card


    def deal_monster_damage(
            self,
            player_id: int,
            amount: int,
        ) -> list:
            """Apply damage and collect revealed health cards.
            
            Jumpscare effects are not resolved yet.
            """
    
            if amount < 0:
                raise ValueError("Damage cannot be negative")
    
            if self.state.is_terminal:
                raise ValueError("Cannot deal damage to a finished game")

            if not any(
                p.player_id == player_id
                for p in self.state.players
            ):
                raise ValueError(f"Invalid player ID: {player_id}")
    
            revealed_cards = []
    
            for _ in range(amount):
                if self.state.is_terminal:
                    break
    
                revealed = self._apply_one_monster_damage(player_id)

                if revealed is not None:
                    revealed_cards.append(revealed)
    
            return revealed_cards


    def _advance_damage(self) -> None:
        """Apply pending damage until a card is revealed or damage ends."""

        pending = self.state.pending_damage

        if pending is None:
            return

        while pending.remaining > 0:
            revealed = self._apply_one_monster_damage(
                pending.player_id
            )

            pending.remaining -= 1

            # Stop if the monster has been defeated.
            if self.state.is_terminal:
                self.state.pending_damage = None
                return

            if revealed is not None:
                # Pause the sequence to handle the revealed card.
                pending.revealed_card_id = revealed.instance_id
                return

        # All pending damage has been resolved.
        self.state.pending_damage = None


    def start_damage(self, player_id: int, amount: int) -> None:
        """Start a damage sequence that can be interrupted."""

        if self.state.is_terminal:
            raise ValueError("Cannot damager a finished game")

        if self.state.pending_damage is not None:
            raise ValueError("A damage sequence is already pending")

        if amount < 0:
            raise ValueError("Damage cannot be negative")

        player = next(
            (p for p in self.state.players if p.player_id == player_id),
            None,
        )

        if player is None:
            raise ValueError(f"Invalid player ID: {player_id}")

        if amount == 0:
            return

        if not player.health_stack:
            raise ValueError("Monster has no health remaining")

        self.state.pending_damage = PendingDamage(
            player_id=player_id,
            remaining=amount,
        )

        self._advance_damage()


    def resume_damage(self) -> None:
        """Resume a damage sequence after handling a revealed card."""

        pending = self.state.pending_damage

        if pending is None:
            raise ValueError("No pending damage to resume")

        if pending.revealed_card_id is None:
            raise ValueError("No revealed card awaiting resolution")

        # The revealed card is considered resolved for now.
        pending.revealed_card_id = None

        self._advance_damage()


    def get_legal_actions(self, player_id: int) -> list[Action]:
        """Return the legal actions available to a player."""

        if self.state.is_terminal:
            return []

        if player_id not in [p.player_id for p in self.state.players]:
            raise ValueError(f"Invalid player ID: {player_id}")

        pending = self.state.pending_damage

        if pending is not None:
            if pending.revealed_card_id is not None:
                if player_id == pending.player_id:
                    return [
                        Action(
                            action_type=ActionType.RESOLVE_REVEAL,
                            player_id=player_id,
                            source_id=pending.revealed_card_id,
                        )
                    ]

            return []

        if self.state.step == GameStep.INITIATIVE_BID:
            # Players who have already bid cannot act again.
            if player_id in self.state.initiative_bids:
                return []

            player = next(
                p for p in self.state.players
                if p.player_id == player_id
            )

            actions = [
                Action(
                    action_type=ActionType.BID,
                    player_id=player_id,
                    source_id=None,
                )
            ]

            # Each card in hand can be submitted as a bid.
            for card in player.hand:
                actions.append(
                    Action(
                        action_type=ActionType.BID,
                        player_id=player_id,
                        source_id=card.instance_id,
                    )
                )

            return actions

        if self.state.step == GameStep.INITIATIVE_CHOICE:
            if player_id != self.state.initiative_bid_winner:
                return []

            return [
                Action(
                    action_type=ActionType.CHOOSE_INITIATIVE,
                    player_id=player_id,
                    target_id=target.player_id
                )
                for target in self.state.players
            ]

        if self.state.step == GameStep.PLAYER_ACTION:

            # Only the active player may perform an action.
            if player_id != self.state.active_player:
                return []

            player = next(
                p for p in self.state.players
                if p.player_id == player_id
            )

            # A slumbered player cannot act again this phase.
            if player.has_slumbered:
                return []

            actions = [
                Action(
                    action_type=ActionType.PASS,
                    player_id=player_id,
                )
            ]

            # Generate actions for playable cards.
            for card in player.hand:
                if not can_play_card(
                    player,
                    card.instance_id,
                    self.card_definitions,
                ):
                    continue

                definition = self.card_definitions[card.card_id]

                if definition.card_type == CardType.MINION:
                    # A minion can enter either location.
                    for location_id in range(len(self.state.locations)):
                        # Play the minion exhausted.
                        actions.append(
                            Action(
                                action_type=ActionType.PLAY_CARD,
                                player_id=player_id,
                                source_id=card.instance_id,
                                location_id=location_id,
                            )
                        )

                        # Optionally pay one Malice to ready it.
                        if player.malice >= 1:
                            actions.append(
                                Action(
                                    action_type=ActionType.PLAY_CARD,
                                    player_id=player_id,
                                    source_id=card.instance_id,
                                    location_id=location_id,
                                    parameters=(True,),
                                )
                            )

                elif definition.card_type in (
                    CardType.ASSET,
                    CardType.EVENT,
                ):
                    actions.append(
                        Action(
                            action_type=ActionType.PLAY_CARD,
                            player_id=player_id,
                            source_id=card.instance_id,
                        )
                    )

            # Only one player may slumber during each round.
            if not any(
                p.has_slumbered for p in self.state.players
            ):
                actions.append(
                    Action(
                        action_type=ActionType.SLUMBER,
                        player_id=player_id,
                    )
                )

            return actions

        if self.state.step == GameStep.MONSTER_FLIP:

            # Players decide in initiative order.
            if player_id != self.state.active_player:
                return []

            if player_id in self.state.monster_flip_completed:
                return []

            player = next(
                p for p in self.state.players
                if p.player_id == player_id
            )

            # Every player can choose to keep the current side.
            actions = [
                Action(
                    action_type=ActionType.FLIP_MONSTER,
                    player_id=player_id,
                    parameters=(False,),
                )
            ]

            # A player with a monster can choose to flip it.
            if player.monster is not None:
                actions.append(
                    Action(
                        action_type=ActionType.FLIP_MONSTER,
                        player_id=player_id,
                        parameters=(True,),
                    )
                )

            return actions
            
        # Normal turn actions are not implemented yet.
        return []


    def step(self, action: Action) -> None:
        """Apply a legal player action to the game state."""

        legal_actions = self.get_legal_actions(action.player_id)

        if action not in legal_actions:
            raise ValueError(f"Illegal action: {action}")

        if action.action_type == ActionType.RESOLVE_REVEAL:
            self.resume_damage()
            return

        if action.action_type == ActionType.BID:
            self.submit_initiative_bid(
                player_id=action.player_id,
                card_instance_id=action.source_id,
            )
            return

        if action.action_type == ActionType.CHOOSE_INITIATIVE:
            self.choose_initiative(
                player_id=action.player_id,
                target_player_id=action.target_id,
            )
            return

        if action.action_type == ActionType.PASS:
            self.pass_action(action.player_id)
            return

        if action.action_type == ActionType.SLUMBER:
            self.slumber_action(action.player_id)
            return

        if action.action_type == ActionType.PLAY_CARD:
            self.play_card(
                player_id=action.player_id,
                card_instance_id=action.source_id,
                location_id=action.location_id,
                ready_minion=(action.parameters == (True,)),
            )
            return

        if action.action_type == ActionType.FLIP_MONSTER:
            self.flip_monster(
                player_id=action.player_id,
                should_flip=action.parameters == (True,),
            )
            return

        raise NotImplementedError(
            f"Action not implemented: {action.action_type}"
        )


    def _transition_to(self, next_step: GameStep) -> None:
        """Apply a permitted internal step transition."""

        if self.state.is_terminal:
            raise ValueError("Cannot advance a finished game")

        if self.state.pending_damage is not None:
            raise ValueError("Cannot advance during pending damage")

        current_step = self.state.step
        expected_next_step = STEP_TRANSITIONS[current_step]

        if next_step != expected_next_step:
            raise ValueError(
                f"Invalid step transition: "
                f"{current_step.name} -> {next_step.name}"
            )

        # Resource collection must be completed before bidding.
        if (
            current_step == GameStep.COLLECT_RESOURCES
            and next_step == GameStep.INITIATIVE_BID
        ):
            all_player_ids = {
                player.player_id
                for player in self.state.players
            }

            if self.state.resources_collected != all_player_ids:
                raise ValueError(
                    "Resource collection is incomplete"
                )

        current_phase = self.state.phase
        next_phase = STEP_PHASE_MAP[next_step]

        # Start a new round and reset collection tracking.
        if (
            current_phase == Phase.REFRESH
            and next_phase == Phase.FEEDING
        ):
            self.state.round_number += 1
            self.state.resources_collected.clear()
            self.state.initiative_bids.clear()
            self.state.initiative_bid_winner = None
            self.state.monster_flip_completed.clear()

            # Reset Horror action tracking for the new round.
            self.state.last_horror_pass_player = None

            for player in self.state.players:
                player.has_slumbered = False

        if (
            current_step == GameStep.INITIATIVE_CHOICE
            and next_step == GameStep.PLAYER_ACTION
        ):
            self.state.last_horror_pass_player = None

        if (
            current_step == GameStep.READY_CARDS
            and next_step == GameStep.MONSTER_FLIP
        ):
            self.state.monster_flip_completed.clear()
            self.state.active_player = self.state.initiative_player

        # Update both the current step and its corresponding phase.
        self.state.step = next_step
        self.state.phase = next_phase


    def collect_resources(self, player_id: int) -> None:
        """Collect Blood, Malice and card draws from the vault."""

        if self.state.is_terminal:
            raise ValueError(
                "Cannot collect resources in a finished game"
            )

        if (
            self.state.phase != Phase.FEEDING
            or self.state.step != GameStep.COLLECT_RESOURCES
        ):
            raise ValueError(
                "Resources can only be collected during COLLECT_RESOURCES"
            )

        if self.state.pending_damage is not None:
            raise ValueError(
                "Cannot collect resources during pending damage"
            )

        player = next(
            (p for p in self.state.players if p.player_id == player_id),
            None,
        )

        if player is None:
            raise ValueError(f"Invalid player ID: {player_id}")

        if player_id in self.state.resources_collected:
            raise ValueError(
                f"Player {player_id} has already collected resources"
            )

        # Calculate resource production without modifying the state.
        production = calculate_vault_resources(
            player,
            self.card_definitions,
        )

        # Add the produced resources to the player's pool.
        player.blood += production.blood
        player.malice += production.malice

        # Draw cards generated by the vault.
        if production.cards > 0:
            self.draw_cards(
                player_id=player_id,
                count=production.cards,
            )

        # Mark this player as having collected resources.
        self.state.resources_collected.add(player_id)

        # Advance once all players have collected their resources.
        all_player_ids = {
            player.player_id
            for player in self.state.players
        }

        if self.state.resources_collected == all_player_ids:
            self._transition_to(GameStep.INITIATIVE_BID)


    def _resolve_initiative_bids(self) -> None:
        """Reveal bids, determine the winner, and update both vaults."""

        if self.state.step != GameStep.INITIATIVE_BID:
            raise ValueError("Not in initiative bidding step")

        player_ids = {p.player_id for p in self.state.players}

        if set(self.state.initiative_bids) != player_ids:
            raise ValueError("Both players must submit a bid")

        bid_costs = {}

        # Validate every bid before modifying game state.
        for player in self.state.players:
            card_id = self.state.initiative_bids[player.player_id]

            if card_id is None:
                bid_costs[player.player_id] = 0
                continue

            card = next(
                (c for c in player.hand if c.instance_id == card_id),
                None,
            )

            if card is None:
                raise ValueError("Bid card is not in player's hand")

            definition = self.card_definitions.get(card.card_id)

            if definition is None:
                raise ValueError(
                    f"Missing card definition: {card.card_id}"
                )

            bid_costs[player.player_id] = definition.cost

        # Compare printed costs.
        player_0, player_1 = self.state.players

        if bid_costs[player_0.player_id] > bid_costs[player_1.player_id]:
            winner = player_0.player_id

        elif bid_costs[player_1.player_id] > bid_costs[player_0.player_id]:
            winner = player_1.player_id

        else:
            #A tied bid is won by the player without initiative.
            winner = next(
                p.player_id
                for p in self.state.players
                if p.player_id != self.state.initiative_player
            )

        # Move every submitted card from hand to its owner's vault.
        for player in self.state.players:
            card_id = self.state.initiative_bids[player.player_id]

            if card_id is None:
                continue

            card = next(
                c for c in player.hand
                if c.instance_id == card_id
            )

            player.hand.remove(card)
            player.vault.append(card)

        self.state.initiative_bid_winner = winner

        # The winner must now choose who receive initiative.
        self._transition_to(GameStep.INITIATIVE_CHOICE)


    def submit_initiative_bid(
        self,
        player_id: int,
        card_instance_id: int | None,
    ) -> None:
        """Submit a hidden initiative bid."""

        if self.state.is_terminal:
            raise ValueError("Cannot bid in a finished game")

        if self.state.step != GameStep.INITIATIVE_BID:
            raise ValueError("Not in initiative bidding step")

        if player_id not in [p.player_id for p in self.state.players]:
            raise ValueError("Invalid player ID")

        if player_id in self.state.initiative_bids:
            raise ValueError("Player has already submitted a bid")

        player = next(
            p for p in self.state.players
            if p.player_id == player_id
        )

        if card_instance_id is not None:
            if not any(
                card.instance_id == card_instance_id
                for card in player.hand
            ):
                raise ValueError("Bid card is not in player's hand")

        # Store the bid without revealing it or moving the card.
        self.state.initiative_bids[player_id] = card_instance_id

        # Reveal only after both players have submitted.
        if len(self.state.initiative_bids) == len(self.state.players):
            self._resolve_initiative_bids()


    def choose_initiative(
        self,
        player_id: int,
        target_player_id: int,
    ) -> None:
        """Assign initiative after winning the bidding process."""

        if self.state.is_terminal:
            raise ValueError("Cannot choose initiative in a finished game")

        if self.state.step != GameStep.INITIATIVE_CHOICE:
            raise ValueError("Not in initiative choice step")

        if player_id != self.state.initiative_bid_winner:
            raise ValueError("Only the bid winner can choose initiative")

        valid_ids = {p.player_id for p in self.state.players}

        if target_player_id not in valid_ids:
            raise ValueError("Invalid initiative target")

        self.state.initiative_player = target_player_id
        self.state.active_player = target_player_id

        self._transition_to(GameStep.PLAYER_ACTION)


    
    def observe(self, player_id: int) -> GameObservation:
        """Return the game information visible to a player."""

        player_ids = {p.player_id for p in self.state.players}

        if player_id not in player_ids:
            raise ValueError(f"Invalid player ID: {player_id}")

        player = next(
            p for p in self.state.players
            if p.player_id == player_id
        )

        opponent = next(
            p for p in self.state.players
            if p.player_id != player_id
        )

        def observe_card(card: CardInstance) -> CardObservation:
            """Create an immutable snapshot of a public card."""
            return CardObservation(
                instance_id=card.instance_id,
                card_id=card.card_id,
                owner_id=card.owner_id,
                controller_id=card.controller_id,
                exhausted=card.exhausted,
                damage=card.damage,
                location_id=card.location_id,
            )

        # Buils observations of both players' public information.
        public_players = tuple(
            PlayerObservation(
                player_id=p.player_id,
                hand_size=len(p.hand),
                deck_size=len(p.deck),
                health=p.health,
                blood=p.blood,
                malice=p.malice,
                vault_cards=tuple(
                    card.card_id for card in p.vault
                ),
                crypt_cards=tuple(
                    card.card_id for card in p.crypt
                ),
                monster_id=(
                    p.monster.card_id
                    if p.monster is not None
                    else None
                ),
                monster_unleashed=p.monster_unleashed,
                minions=tuple(
                    observe_card(card)
                    for card in p.minions
                ),
                assets=tuple(
                    observe_card(card)
                    for card in p.assets
                ),
            )
            for p in self.state.players
        )

        # Create immutable snapshots of the public locations.
        public_locations = tuple(
            LocationObservation(
                location_id=index,
                card_id=location.card_id,
                controller_id=location.controller_id,
                malice=tuple(sorted(location.malice.items())),
            )
            for index, location in enumerate(self.state.locations)
        )

        # Include card instance IDs only for the observing player's hand.
        own_hand_cards = tuple(
            HandCardObservation(
                instance_id=card.instance_id,
                card_id=card.card_id,
            )
            for card in player.hand
        )

        return GameObservation(
            player_id=player_id,
            phase=self.state.phase,
            step=self.state.step,
            round_number=self.state.round_number,
            initiative_player=self.state.initiative_player,
            active_player=self.state.active_player,
            own_hand=tuple(
                card.card_id for card in player.hand
            ),
            own_bid_submitted=(
                player_id in self.state.initiative_bids
            ),
            own_bid_card_id=self.state.initiative_bids.get(
                player_id
            ),
            opponent_bid_submitted=(
                opponent.player_id in self.state.initiative_bids
            ),
            players=public_players,
            is_terminal=self.state.is_terminal,
            winner=self.state.winner,
            own_hand_cards=own_hand_cards,
            locations=public_locations,
        )


    def _advance_horror_turn(self, player_id: int) -> None:
        """Select the next player eligible to act."""

        opponent = next(
            p for p in self.state.players
            if p.player_id != player_id
        )

        # A slumbered opponent cannot take further actions.
        if opponent.has_slumbered:
            self.state.active_player = player_id
        else:
            self.state.active_player = opponent.player_id


    def pass_action(self, player_id: int) -> None:
        """Pass the current Horror action."""

        if self.state.step != GameStep.PLAYER_ACTION:
            raise ValueError("Not in Horror action step")

        if player_id != self.state.active_player:
            raise ValueError("Player is not active")

        opponent = next(
            p for p in self.state.players
            if p.player_id != player_id
        )

        # End Horror after two consecutive passes,
        # or when the opponent has already slumbered.
        if (
            self.state.last_horror_pass_player == opponent.player_id
            or opponent.has_slumbered
        ):
            self.state.last_horror_pass_player = None
            self._transition_to(GameStep.READY_CARDS)
            return

        # Remember this pass and give the opponent a turn.
        self.state.last_horror_pass_player = player_id
        self._advance_horror_turn(player_id)


    def slumber_action(self, player_id: int) -> None:
        """Gain one Malice and slumber for the rest of Horror."""

        if self.state.step != GameStep.PLAYER_ACTION:
            raise ValueError("Not in Horror action step")

        if player_id != self.state.active_player:
            raise ValueError("Player is not active")

        if any(p.has_slumbered for p in self.state.players):
            raise ValueError("A player has already slumbered")

        player = next(
            p for p in self.state.players
            if p.player_id == player_id
        )

        opponent = next(
            p for p in self.state.players
            if p.player_id != player_id
        )

        # Slumber grants one Malice and locks further actions.
        player.malice += 1
        player.has_slumbered = True

        # The phase ends if the opponent's previous action was PASS.
        if self.state.last_horror_pass_player == opponent.player_id:
            self.state.last_horror_pass_player = None
            self._transition_to(GameStep.READY_CARDS)
            return

        self.state.last_horror_pass_player = None
        self._advance_horror_turn(player_id)


    def play_card(
        self,
        player_id: int,
        card_instance_id: int,
        location_id: int | None = None,
        ready_minion: bool = False,
    ) -> None:
        """Play a supported card from the player's hand."""

        if self.state.is_terminal:
            raise ValueError("Cannot play cards in a finished game")

        if self.state.step != GameStep.PLAYER_ACTION:
            raise ValueError("Not in Horror action step")

        if player_id != self.state.active_player:
            raise ValueError("Player is not active")

        player = next(
            (p for p in self.state.players if p.player_id == player_id),
            None,
        )

        if player is None:
            raise ValueError(f"Invalid player ID: {player_id}")

        if not can_play_card(
            player,
            card_instance_id,
            self.card_definitions,
        ):
            raise ValueError("Card cannot be played")

        card = next(
            c for c in player.hand
            if c.instance_id == card_instance_id
        )

        definition = self.card_definitions[card.card_id]

        # Validate all options before modifying the game state.
        if definition.card_type == CardType.MINION:
            if (
                location_id is None
                or not 0 <= location_id < len(self.state.locations)
            ):
                raise ValueError("Invalid minion location")

            if ready_minion and player.malice < 1:
                raise ValueError("Not enough Malice to ready minion")

        elif location_id is not None or ready_minion:
            raise ValueError("Invalid options for this card type")

        # Pay the Blood cost.
        player.blood -= definition.cost

        # Move the Asset from hand to the Asset Row.
        player.hand.remove(card)

        if definition.card_type == CardType.ASSET:
            # Assets enter the Asset Row ready.
            card.exhausted = False
            card.location_id = None
            player.assets.append(card)

        elif definition.card_type == CardType.MINION:
            # Minions enter their chosen location exhausted.
            card.location_id = location_id
            card.exhausted = True

            if ready_minion:
                player.malice -= 1
                card.exhausted = False

            player.minions.append(card)

        elif definition.card_type == CardType.EVENT:
            # Only events without unresolved abilities are supported.
            player.crypt.append(card)

        else:
            raise ValueError("Unsupported card type")

        # Playing a card breaks consecutive passes.
        self.state.last_horror_pass_player = None

        # Give the next action to the opponent.
        self._advance_horror_turn(player_id)


    def ready_cards(self) -> None:
        """Ready all monsters, minions, and assets in play."""

        if self.state.is_terminal:
            raise ValueError("Cannot ready cards in a finished game")

        if self.state.step != GameStep.READY_CARDS:
            raise ValueError("Not in Ready Cards step")

        if self.state.pending_damage is not None:
            raise ValueError("Cannot ready cards during pending damage")

        # Both players ready their cards simultaneously.
        for player in self.state.players:
            if player.monster is not None:
                player.monster.exhausted = False

            for minion in player.minions:
                minion.exhausted = False

            for asset in player.assets:
                asset.exhausted = False

        # Continue to the Monster Flip step.
        self._transition_to(GameStep.MONSTER_FLIP)


    def flip_monster(
        self,
        player_id: int,
        should_flip: bool,
    ) -> None:
        """Resolve a player's Monster Flip decision."""

        if self.state.is_terminal:
            raise ValueError("Cannot flip in a finished game")

        if self.state.pending_damage is not None:
            raise ValueError("Cannot flip during pending damage")

        if self.state.step != GameStep.MONSTER_FLIP:
            raise ValueError("Not in Monster Flip step")

        if player_id != self.state.active_player:
            raise ValueError("Player is not active")

        if player_id in self.state.monster_flip_completed:
            raise ValueError("Player already completed Monster Flip")

        player = next(
            (p for p in self.state.players if p.player_id == player_id),
            None,
        )

        if player is None:
            raise ValueError(f"Invalid player ID: {player_id}")

        if not isinstance(should_flip, bool):
            raise ValueError("Monster Flip decision must be boolean")

        if should_flip:
            if player.monster is None:
                raise ValueError("Player has no monster to flip")

            # Toggle Lurking and Unleashed.
            player.monster_unleashed = not player.monster_unleashed

        # Record the decision, even if the monster was not flipped.
        self.state.monster_flip_completed.add(player_id)

        all_player_ids = {
            p.player_id for p in self.state.players
        }

        # Advance after both players have made their decisions.
        if self.state.monster_flip_completed == all_player_ids:
            self._transition_to(GameStep.DISCARD_TO_HAND_LIMIT)
            return

        # Let the other player decide.
        opponent = next(
            p for p in self.state.players
            if p.player_id != player_id
        )

        self.state.active_player = opponent.player_id
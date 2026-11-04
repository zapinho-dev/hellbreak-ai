from dataclasses import dataclass, field
from copy import deepcopy
from enum import Enum, auto


class Phase(Enum):
    FEEDING = auto()
    HORROR = auto()
    REFRESH = auto()


class GameStep(Enum):
    COLLECT_RESOURCES = auto()
    INITIATIVE_BID = auto()
    INITIATIVE_CHOICE = auto()

    PLAYER_ACTION = auto()

    READY_CARDS = auto()
    MONSTER_FLIP = auto()
    DISCARD_TO_HAND_LIMIT = auto()


STEP_PHASE_MAP = {
    GameStep.COLLECT_RESOURCES: Phase.FEEDING,
    GameStep.INITIATIVE_BID: Phase.FEEDING,
    GameStep.INITIATIVE_CHOICE: Phase.FEEDING,

    GameStep.PLAYER_ACTION: Phase.HORROR,

    GameStep.READY_CARDS: Phase.REFRESH,
    GameStep.MONSTER_FLIP: Phase.REFRESH,
    GameStep.DISCARD_TO_HAND_LIMIT: Phase.REFRESH,
}


@dataclass
class CardInstance:
    """A specific copy of a card in a game."""
    instance_id: int
    card_id: str

    owner_id: int
    controller_id: int

    exhausted: bool = False
    damage: int = 0

    # Location occupied by a minion, if applicable.
    location_id: int | None = None


@dataclass
class HealthCard:
    """Represent a card in a monster's health stack."""

    card: CardInstance
    vertical: bool = False

    @property
    def health(self) -> int:
        """Return the remaining health of this card."""
        return 1 if self.vertical else 2


@dataclass
class PendingDamage:
    """Track an interrupted monster damage sequence."""

    player_id: int
    remaining: int
    revealed_card_id: int | None = None


@dataclass
class PlayerState:
    player_id: int

    deck: list[CardInstance] = field(default_factory=list)
    hand: list[CardInstance] = field(default_factory=list)
    crypt: list[CardInstance] = field(default_factory=list)
    vault: list[CardInstance] = field(default_factory=list)

    monster: CardInstance | None = None
    monster_unleashed: bool = False

    minions: list[CardInstance] = field(default_factory=list)
    assets: list[CardInstance] = field(default_factory=list)

    # Health stack: True = horizontal card (2 HP)
    # False = vertical card (1 HP)
    health_stack: list[HealthCard] = field(default_factory=list)

    blood: int = 0
    malice: int = 0

    has_passed: bool = False
    has_slumbered: bool = False

    @property
    def health(self) -> int:
        """Calculate the monster's remaining health."""
        return sum(card.health for card in self.health_stack)


@dataclass
class LocationState:
    card_id: str
    controller_id: str
    malice: dict[int, int] = field(
        default_factory=lambda: {0: 0, 1: 0}
    )


@dataclass
class GameState:
    players: list[PlayerState]
    locations: list[LocationState]

    phase: Phase = Phase.FEEDING
    round_number: int = 1

    step: GameStep = GameStep.COLLECT_RESOURCES

    initiative_player: int = 0
    active_player: int = 0

    winner: int | None = None
    is_terminal: bool = False

    pending_damage: PendingDamage | None = None

    resources_collected: set[int] = field(default_factory=set)

    # Store submitted bids until both players have chosen.
    # A None value means that the player chose not to bid.
    initiative_bids: dict[int, int | None] = field(default_factory=dict)

    # Store the winner of the bidding process.
    initiative_bid_winner: int | None = None

    last_horror_pass_player: int | None = None

    def clone(self) -> "GameState":
        return deepcopy(self)


    def validate(self) -> None:
        """Validate the structural integrity of the game state."""

        if len(self.players) != 2:
            raise ValueError("The game must have exactly 2 players.")

        player_ids = [player.player_id for player in self.players]

        if len(set(player_ids)) != 2:
            raise ValueError("Player IDs must be unique")

        seen_ids = set()

        for player in self.players:
            zones = [
                player.deck,
                player.hand,
                player.crypt,
                player.vault,
                player.minions,
                player.assets,
            ]

            if player.monster is not None:
                zones.append([player.monster])

            for zone in zones:
                for card in zone:
                    if card.instance_id in seen_ids:
                        raise ValueError(
                            f"Duplicate card: instance_id={card.instance_id}"
                        )

                    seen_ids.add(card.instance_id)

                    if card.owner_id not in player_ids:
                        raise ValueError(
                            f"Invalid card owner: {card.owner_id}"
                        )

                    if card.controller_id not in player_ids:
                        raise ValueError(
                            f"Invalid card controller: {card.controller_id}"
                        )

            vertical_count = 0

            for health_card in player.health_stack:
                card = health_card.card

                if card.instance_id in seen_ids:
                    raise ValueError(
                        f"Duplicate card: instance_id={card.instance_id}"
                    )

                seen_ids.add(card.instance_id)

                if card.owner_id not in player_ids:
                    raise ValueError(
                        f"Invalid card owner: {card.owner_id}"
                    )

                if card.controller_id not in player_ids:
                    raise ValueError(
                        f"Invalid card controller: {card.controller_id}"
                    )

                if health_card.vertical:
                    vertical_count += 1

            if vertical_count > 1:
                raise ValueError(
                    "A health stack cannot contain multiple vertical cards"
                )

        if self.pending_damage is not None:
            pending = self.pending_damage

            if pending.player_id not in player_ids:
                raise ValueError("Invalid pending damage player")

            if pending.remaining < 0:
                raise ValueError("Pending damage cannot be negative")

            if pending.revealed_card_id is not None:
                revealed = self.get_card(pending.revealed_card_id)

                if revealed is None:
                    raise ValueError("Pending revealed card not found")

            if self.is_terminal:
                raise ValueError(
                    "A finished game cannot have pending damage"
                )


        # Verify that the current step belongs to the current phase.
        expected_phase = STEP_PHASE_MAP[self.step]

        if self.phase != expected_phase:
            raise ValueError(
                f"Invalid phase-step combinationo: "
                f"{self.phase.name} / {self.step.name}"
            )


        # Verify that resource collection references valid players.
        if not self.resources_collected.issubset(set(player_ids)):
            raise ValueError(
                "Resource collection contains invalid player IDs"
            )

        # Validate initiative bidding state.
        submitted_ids = set(self.initiative_bids)

        if not submitted_ids.issubset(set(player_ids)):
            raise ValueError("Initiative bids contain invalid player IDs")

        if self.initiative_bid_winner is not None:
            if self.initiative_bid_winner not in player_ids:
                raise ValueError("Invalid initiative bid winner")

        # During bidding, submitted cards must still be in hand.
        if self.step == GameStep.INITIATIVE_BID:
            if self.initiative_bid_winner is not None:
                raise ValueError(
                    "Bid winner cannot be assigned during bidding"
                )

            for player_id, card_instance_id in self.initiative_bids.items():
                if card_instance_id is None:
                    continue

                player = next(
                    p for p in self.players
                    if p.player_id == player_id
                )

                if not any(
                    card.instance_id == card_instance_id
                    for card in player.hand
                ):
                    raise ValueError(
                        "Submitted bid card is not in player's hand"
                    )

        # During initiative choice, bidding must be complete.
        if self.step == GameStep.INITIATIVE_CHOICE:
            if submitted_ids != set(player_ids):
                raise ValueError("Initiative bids are incomplete")

            if self.initiative_bid_winner is None:
                raise ValueError("Initiative bid winner is missing")

        # Validate the player who performed the last Horror pass.
        if (
            self.last_horror_pass_player is not None
            and self.last_horror_pass_player not in player_ids
        ):
            raise ValueError("Invalid last Horror pass player")

        # Only one player may slumber in a round.
        slumbered_players = [
            player for player in self.players
            if player.has_slumbered
        ]

        if len(slumbered_players) > 1:
            raise ValueError(
                "Only one player may slumber per round"
            )

        # Validate minion locations.
        for player in self.players:
            for minion in player.minions:
                if (
                    minion.location_id is None
                    or not 0 <= minion.location_id < len(self.locations)
                ):
                    raise ValueError(
                        f"Invalid minion location: {minion.instance_id}"
                    )

            # Assets must not occupy a location.
            for asset in player.assets:
                if asset.location_id is not None:
                    raise ValueError(
                        f"Asset cannot occupy a location: {asset.instance_id}"
                    )


    def get_card(self, instance_id: str) -> CardInstance | None:
        """Find a card by its instance ID across all player zones."""

        for player in self.players:
            zones = [
                player.deck,
                player.hand,
                player.crypt,
                player.vault,
                player.minions,
                player.assets,
            ]

            if player.monster is not None:
                zones.append([player.monster])

            for zone in zones:
                for card in zone:
                    if card.instance_id == instance_id:
                        return card

            for health_card in player.health_stack:
                if health_card.card.instance_id == instance_id:
                    return health_card.card

        return None
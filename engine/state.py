from dataclasses import dataclass, field
from copy import deepcopy
from enum import Enum, auto


class Phase(Enum):
    FEEDING = auto()
    HORROR = auto()
    REFRESH = auto()


@dataclass
class CardInstance:
    """A specific copy of a card in a game."""
    instance_id: int
    card_id: str

    owner_id: int
    controller_id: int

    exhausted: bool = False
    damage: int = 0


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
    health_stack: list[bool] = field(default_factory=list)

    blood: int = 0
    malice: int = 0

    has_passed: bool = False
    has_slumbered: bool = False


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

    initiative_player: int = 0
    active_player: int = 0

    winner: int | None = None
    is_terminal: bool = False

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

        return None
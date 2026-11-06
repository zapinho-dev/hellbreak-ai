from dataclasses import dataclass

from engine.state import Phase, GameStep

@dataclass(frozen=True)
class CardObservation:
    """Public information about a card in play."""

    instance_id: int
    card_id: int
    owner_id: int
    controller_id: int

    exhausted: bool
    damage: int
    location_id: int | None


@dataclass(frozen=True)
class HandCardObservation:
    """Information about a card in the observing player's hand."""

    instance_id: int
    card_id: str


@dataclass(frozen=True)
class LocationObservation:
    """Public information about a location."""

    location_id: int
    card_id: str
    controller_id: str
    malice: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class PlayerObservation:
    """Public information about a player."""

    player_id: int
    hand_size: int
    deck_size: int
    health: int

    blood: int
    malice: int

    vault_cards: tuple[str, ...]
    crypt_cards: tuple[str, ...]

    monster_id: str | None
    monster_unleashed: bool

    # Public cards currently in play.
    minions: tuple[CardObservation, ...] = ()
    assets: tuple[CardObservation, ...] = ()


@dataclass(frozen=True)
class GameObservation:
    """Information visible to a specific player."""

    player_id: int

    phase: Phase
    step: GameStep
    round_number: int

    initiative_player: int
    active_player: int

    own_hand: tuple[str, ...]

    own_bid_submitted: bool
    own_bid_card_id: int | None

    opponent_bid_submitted: bool

    players: tuple[PlayerObservation, ...]

    is_terminal: bool
    winner: int | None

    # Detailed information about the observing player's hand.
    own_hand_cards: tuple[HandCardObservation, ...] = ()

    # Public location information.
    locations: tuple[LocationObservation, ...] = ()
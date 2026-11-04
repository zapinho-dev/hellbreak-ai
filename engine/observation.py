from dataclasses import dataclass

from engine.state import Phase, GameStep

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
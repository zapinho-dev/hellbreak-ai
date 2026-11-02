from dataclasses import dataclass
from enum import Enum, auto


class ActionType(Enum):
    PLAY_CARD = auto()
    ATTACK = auto()
    DEFEND = auto()
    SCHEME = auto()
    USE_ABILITY = auto()
    SLUMBER = auto()
    PASS = auto()

    BID = auto()
    FLIP_MONSTER = auto()
    DISCARD = auto()


@dataclass(frozen=True)
class Action:
    action_type: ActionType
    player_id: int

    source_id: int | None = None
    target_id: int | None = None
    location_id: int | None = None

    # Additional parameters for special decisions.
    # In the future we can replace them with more specific types.
    parameters: tuple = ()
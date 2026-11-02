from engine.state import GameState, PlayerState


class Game:
    """Manage the lifecycle of a Hellbreak game."""

    def __init__(self, state: GameState):
        """Initialize the game with an existing state."""
        state.validate()
        self.state = state


    def get_state(self) -> GameState:
        """Return the current game state."""
        return self.state


    def clone(self) -> "Game":
        """Create an independent copy of the game."""
        return Game(self.state.clone())


    def is_terminal(self) -> bool:
        """Check whether the game has ended."""
        return self.state.is_terminal


    def get_winner(self) -> int | None:
        """Return the winning player ID, if any."""
        return self.state.winner
"""UserComponent representing student players."""
from __future__ import annotations

from components.game_component import Game


class User:
    def __init__(self, user_id: str = "cadet-1", username: str = "AstroCadet") -> None:
        self.id: str = user_id
        self.username: str = username

    def playGame(self, game: Game) -> None:
        game.play()

    def viewScore(self, game: Game) -> int:
        return game.viewScore()

"""GameComponent domain entity managing gameplay lifecycle and state."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid


class Game:
    def __init__(self, game_id: str | None = None, score: int = 0) -> None:
        self.id: str = game_id or str(uuid.uuid4())[:8]
        self.score: int = score
        self.state: str = "Playing"
        self.current_question_idx: int = 0
        self.streak: int = 0

    def play(self) -> None:
        self.state = "Playing"

    def viewScore(self) -> int:
        return self.score

    def pause(self) -> None:
        if self.state == "Playing":
            self.state = "Paused"

    def resume(self) -> None:
        if self.state == "Paused":
            self.state = "Playing"

    def gameOver(self) -> None:
        self.state = "GameOver"

    def add_score(self, points: int) -> None:
        self.streak += 1
        bonus = self.streak * 10
        self.score += points + bonus

    def reset_streak(self) -> None:
        self.streak = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "score": self.score,
            "state": self.state,
            "streak": self.streak,
            "current_question_idx": self.current_question_idx,
        }

    def save_to_db(self, db_path: Path | str) -> None:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_state JSON NOT NULL
            )
            """
        )
        cursor.execute(
            "INSERT INTO games (game_state) VALUES (?)",
            (json.dumps(self.to_dict()),),
        )
        conn.commit()
        conn.close()

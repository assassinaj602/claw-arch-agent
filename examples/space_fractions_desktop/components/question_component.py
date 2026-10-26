"""QuestionComponent domain entity managing educational fraction questions."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any


class Question:
    def __init__(
        self,
        question_id: str,
        prompt: str,
        options: list[str],
        correct_option: int,
        visual_type: str = "pie",
        fraction_val: tuple[int, int] = (1, 2),
    ) -> None:
        self.id: str = question_id
        self.prompt: str = prompt
        self.options: list[str] = options
        self.correct_option: int = correct_option
        self.visual_type: str = visual_type
        self.fraction_val: tuple[int, int] = fraction_val

    def getPrompt(self) -> str:
        return self.prompt

    def getOptions(self) -> list[str]:
        return list(self.options)

    def check_answer(self, option_index: int) -> bool:
        return option_index == self.correct_option

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "options": self.options,
            "correct_option": self.correct_option,
            "visual_type": self.visual_type,
            "fraction_val": list(self.fraction_val),
        }

    @classmethod
    def load_defaults(cls) -> list[Question]:
        return [
            cls("q1", "What fraction of the spaceship energy core is charged?", ["1/4", "1/2", "3/4", "2/3"], 1, "pie", (1, 2)),
            cls("q2", "Simplify the warp drive fuel ratio: 4/8", ["1/4", "2/3", "1/2", "3/8"], 2, "bar", (4, 8)),
            cls("q3", "Add planetary distance coordinates: 1/5 + 2/5 = ?", ["3/5", "3/10", "2/25", "4/5"], 0, "pie", (3, 5)),
            cls("q4", "Which fraction represents the shaded asteroid shields?", ["2/6", "3/6 (or 1/2)", "4/6", "5/6"], 1, "pie", (3, 6)),
            cls("q5", "Solve satellite signal balance: 5/6 - 2/6 = ?", ["1/6", "3/6 (or 1/2)", "7/6", "2/3"], 1, "bar", (3, 6)),
            cls("q6", "Compare energy levels: Is 2/3 greater than 3/6?", ["Yes (2/3 > 1/2)", "No (2/3 < 1/2)", "They are equal", "Cannot determine"], 0, "bar", (2, 3)),
        ]

    @classmethod
    def init_db(cls, db_path: Path | str) -> None:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                options JSON NOT NULL,
                correct_option INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("SELECT COUNT(*) FROM questions")
        count = cursor.fetchone()[0]
        if count == 0:
            for q in cls.load_defaults():
                cursor.execute(
                    "INSERT INTO questions (prompt, options, correct_option) VALUES (?, ?, ?)",
                    (q.prompt, json.dumps(q.options), q.correct_option),
                )
        conn.commit()
        conn.close()

"""AdminComponent representing instructors and game administrators."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from components.question_component import Question


class Admin:
    def __init__(self, admin_id: str = "admin-1", username: str = "FlightInstructor") -> None:
        self.id: str = admin_id
        self.username: str = username

    def updateQuestions(self, questions: list[Question], db_path: Path | str | None = None) -> bool:
        if not db_path:
            return True
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
        for q in questions:
            cursor.execute(
                "INSERT INTO questions (prompt, options, correct_option) VALUES (?, ?, ?)",
                (q.prompt, json.dumps(q.options), q.correct_option),
            )
        conn.commit()
        conn.close()
        return True
